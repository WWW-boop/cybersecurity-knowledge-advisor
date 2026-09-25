"""Normalize the reviewed corpus into one JSONL document per source."""

import hashlib
import json
import re
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path

import pymupdf

from cybersecurity_advisor.ingestion.schemas import NormalizedDocument

RAW_DIR = Path("data/raw/recommended-corpus-v0.2")
MANIFEST_PATH = RAW_DIR / "download-manifest.json"
OUTPUT_PATH = Path("data/processed/documents.jsonl")
BLOCK_TAGS = {
    "article",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "main",
    "p",
    "section",
    "table",
    "td",
    "th",
    "tr",
}
HIDDEN_TAGS = {"button", "footer", "header", "nav", "noscript", "script", "style", "svg"}


def clean_text(text: str) -> str:
    lines = (re.sub(r"\s+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.main_depth = 0
        self.etda_content_depth = 0
        self.in_title = False
        self.title: list[str] = []
        self.all_text: list[str] = []
        self.main_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        if tag in HIDDEN_TAGS:
            self.hidden_depth += 1
        if tag == "main":
            self.main_depth += 1
        if tag == "div" and self.etda_content_depth:
            self.etda_content_depth += 1
        elif tag == "div" and "content-insite2f" in (dict(attrs).get("class") or "").split():
            self.etda_content_depth = 1
        if tag in BLOCK_TAGS:
            self._append("\n")
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in BLOCK_TAGS:
            self._append("\n")
        if tag == "main" and self.main_depth:
            self.main_depth -= 1
        if tag == "div" and self.etda_content_depth:
            self.etda_content_depth -= 1
        if tag in HIDDEN_TAGS and self.hidden_depth:
            self.hidden_depth -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        elif not self.hidden_depth:
            self._append(data)

    def _append(self, text: str) -> None:
        if self.hidden_depth:
            return
        self.all_text.append(text)
        if self.main_depth or self.etda_content_depth:
            self.main_text.append(text)


def extract_html(path: Path) -> tuple[str, str, dict[str, object]]:
    parser = HTMLTextExtractor()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    main_text = clean_text("".join(parser.main_text))
    content = main_text or clean_text("".join(parser.all_text))
    return clean_text("".join(parser.title)), content, {"extraction_method": "html_parser"}


def extract_json(path: Path) -> tuple[str, str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    faqs = payload.get("Value", [])
    if payload.get("IsSuccess") is not True or not faqs:
        raise ValueError(f"Expected a successful FAQ response in {path}")
    content = "\n\n".join(
        f"คำถาม: {item['FAQ_QUESTION']}\nคำตอบ: {item['FAQ_ANSWER']}" for item in faqs
    )
    return (
        "Thai Police Online FAQ",
        clean_text(content),
        {
            "extraction_method": "json_faq",
            "record_count": len(faqs),
        },
    )


def extract_markdown(path: Path) -> tuple[str, str, dict[str, object]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    title_match = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
    marker = "Markdown Content:"
    content = text.split(marker, maxsplit=1)[-1] if marker in text else text
    return (
        clean_text(title_match.group(1)) if title_match else path.stem,
        clean_text(content),
        {"extraction_method": "markdown"},
    )


def extract_pdf(
    path: Path, page_range: tuple[int, int] | None = None
) -> tuple[str, str, dict[str, object]]:
    with pymupdf.open(path) as document:
        first, last = page_range or (1, document.page_count)
        if not 1 <= first <= last <= document.page_count:
            raise ValueError(f"Invalid PDF page range: {page_range}")
        pages = []
        for number in range(first, last + 1):
            page = document[number - 1]
            text = clean_text(page.get_text("text", sort=True))
            if text:
                pages.append(f"[Page {number}]\n{text}")
        title = clean_text(document.metadata.get("title", "")) or path.stem
        total_pages = document.page_count
    content = "\n\n".join(pages)
    if not content.strip():
        raise ValueError(f"PDF has no usable content after extraction: {path}")
    return (
        title,
        content,
        {
            "extraction_method": "pymupdf_text",
            "page_count": last - first + 1,
            "pdf_total_pages": total_pages,
            "page_range": [first, last],
        },
    )


def build_documents() -> Iterator[dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    extractors = {
        ".html": extract_html,
        ".json": extract_json,
        ".md": extract_markdown,
        ".pdf": extract_pdf,
    }
    for source in manifest["sources"]:
        if source.get("enabled") is not True or source["status"] != "downloaded":
            raise ValueError(f"Source must be enabled and downloaded: {source['source_id']}")
        entries = [source]
        if source.get("companion_filename"):
            entries.append(
                {
                    **source,
                    "document_id": source["source_id"].lower() + "-companion",
                    "filename": source["companion_filename"],
                    "sha256": source["companion_sha256"],
                    "canonical_url": source["companion_url"],
                    "page_range": source["companion_page_range"],
                    "title": source.get("companion_title"),
                }
            )
        for entry in entries:
            path = RAW_DIR / entry["filename"]
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != entry["sha256"]:
                raise ValueError(f"Raw file hash mismatch: {path}")
            if path.suffix.lower() == ".pdf":
                title, content, extra = extract_pdf(path, entry.get("page_range"))
            else:
                title, content, extra = extractors[path.suffix.lower()](path)
            if not content.strip():
                raise ValueError(f"Extracted content is empty: {path}")
            document = NormalizedDocument.model_validate(
                {
                    **{
                        key: entry[key]
                        for key in ("source_id", "organization", "source_type", "language")
                    },
                    "document_id": entry.get("document_id", source["source_id"].lower()),
                    "title": entry.get("title") or title or path.stem,
                    "source_url": entry["canonical_url"],
                    "raw_filename": entry["filename"],
                    "format": path.suffix.removeprefix(".").lower(),
                    "content": content,
                    "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "raw_sha256": entry["sha256"],
                    "retrieved_at": manifest["retrieved_at"],
                    "rights_status": entry.get("rights_status", manifest["rights_status"]),
                    "corpus_version": manifest["corpus_version"],
                    **{
                        key: entry[key]
                        for key in (
                            "audience",
                            "published_at",
                            "updated_at",
                            "authority",
                            "freshness",
                        )
                        if key in entry
                    },
                    **extra,
                }
            )
            yield document.model_dump(mode="json")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    seen = set()
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            for document in build_documents():
                if document["document_id"] in seen:
                    raise ValueError(f"Duplicate document ID: {document['document_id']}")
                seen.add(document["document_id"])
                stream.write(json.dumps(document, ensure_ascii=False) + "\n")
        if not seen:
            raise ValueError("No documents to write")
        temporary.replace(OUTPUT_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"wrote {len(seen)} documents to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
