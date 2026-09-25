"""Normalize the reviewed corpus into one JSONL document per source."""

import concurrent.futures
import hashlib
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pymupdf

RAW_DIR = Path("data/raw/recommended-corpus-v0.2")
MANIFEST_PATH = RAW_DIR / "download-manifest.json"
OUTPUT_PATH = Path("data/processed/documents.jsonl")
LOCAL_TESSERACT = Path(".tools/tesseract/tesseract.exe")
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
        elif tag == "div" and "content-insite2f" in dict(attrs).get("class", "").split():
            self.etda_content_depth = 1
        if tag in BLOCK_TAGS:
            self._append("\n")

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
    main_text = clean_text(" ".join(parser.main_text))
    content = main_text if len(main_text) >= 500 else clean_text(" ".join(parser.all_text))
    return clean_text(" ".join(parser.title)), content, {"extraction_method": "html_parser"}


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


def _ocr_page(path: Path, page_number: int) -> tuple[int, str]:
    executable = LOCAL_TESSERACT if LOCAL_TESSERACT.exists() else shutil.which("tesseract")
    if not executable:
        raise RuntimeError("Tesseract is required for image-only PDFs")
    with pymupdf.open(path) as document:
        image = document[page_number - 1].get_pixmap(dpi=300, alpha=False).tobytes("png")
    result = subprocess.run(
        [str(executable), "stdin", "stdout", "-l", "tha+eng", "--psm", "6", "--dpi", "300"],
        input=image,
        capture_output=True,
        check=True,
    )
    return page_number, clean_text(result.stdout.decode("utf-8", errors="replace"))


def extract_pdf(
    path: Path, page_range: tuple[int, int] | None = None
) -> tuple[str, str, dict[str, object]]:
    with pymupdf.open(path) as document:
        first, last = page_range or (1, document.page_count)
        pages = []
        for number in range(first, last + 1):
            text = clean_text(document[number - 1].get_text("text", sort=True))
            if text:
                pages.append(f"[Page {number}]\n{text}")
        title = clean_text(document.metadata.get("title", "")) or path.stem
        total_pages = document.page_count
    content = "\n\n".join(pages)
    extraction_method = "pymupdf_text"
    if len(content) < 500:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            ocr_pages = executor.map(lambda number: _ocr_page(path, number), range(first, last + 1))
        content = "\n\n".join(f"[Page {number}]\n{text}" for number, text in ocr_pages if text)
        extraction_method = "pymupdf_render+tesseract_ocr"
    if len(content) < 500:
        raise ValueError(f"PDF has no usable content after extraction: {path}")
    return (
        title,
        content,
        {
            "extraction_method": extraction_method,
            "page_count": last - first + 1,
            "pdf_total_pages": total_pages,
            "page_range": [first, last],
        },
    )


def build_documents() -> list[dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = []
    extractors = {
        ".html": extract_html,
        ".json": extract_json,
        ".md": extract_markdown,
        ".pdf": extract_pdf,
    }

    for source in manifest["sources"]:
        if source["status"] != "downloaded":
            raise ValueError(f"Source is not downloaded: {source['source_id']}")
        path = RAW_DIR / source["filename"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Raw file hash mismatch: {path}")
        title, content, extra = extractors[path.suffix.lower()](path)
        if companion_name := source.get("companion_filename"):
            companion_path = RAW_DIR / companion_name
            companion_raw = companion_path.read_bytes()
            if hashlib.sha256(companion_raw).hexdigest() != source["companion_sha256"]:
                raise ValueError(f"Companion file hash mismatch: {companion_path}")
            first, last = source["companion_page_range"]
            _, companion_content, companion_extra = extract_pdf(companion_path, (first, last))
            content += "\n\n[EDC Plus: Digital Security]\n" + companion_content
            extra["companion"] = {
                "raw_filename": companion_name,
                "raw_sha256": source["companion_sha256"],
                **companion_extra,
            }
        if len(content) < 500:
            raise ValueError(f"Extracted content is too short: {path}")
        documents.append(
            {
                "document_id": source["source_id"].lower(),
                "source_id": source["source_id"],
                "title": title or path.stem,
                "language": "th" if source["source_id"].startswith("TH-") else "en",
                "source_url": source["canonical_url"],
                "raw_filename": source["filename"],
                "format": path.suffix.removeprefix(".").lower(),
                "content": content,
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "raw_sha256": source["sha256"],
                "retrieved_at": manifest["retrieved_at"],
                "rights_status": manifest["rights_status"],
                "corpus_version": manifest["corpus_version"],
                **extra,
            }
        )

    if len(documents) != len(manifest["sources"]):
        raise ValueError("Output count does not match the manifest")
    return documents


def main() -> None:
    documents = build_documents()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "".join(json.dumps(document, ensure_ascii=False) + "\n" for document in documents),
        encoding="utf-8",
    )
    print(f"wrote {len(documents)} documents to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
