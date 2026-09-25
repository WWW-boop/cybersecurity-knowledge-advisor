"""Build section-aware JSONL chunks from normalized documents."""

import hashlib
import json
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from cybersecurity_advisor.ingestion.schemas import NormalizedDocument

INPUT_PATH = Path("data/processed/documents.jsonl")
OUTPUT_PATH = Path("data/chunks/chunks.jsonl")
# Character units are explicit until the embedding model's tokenizer is integrated.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
PAGE_RE = re.compile(r"^\[Page (\d+)]$")
TOPICS = (
    ("ransomware", ("ransomware", "เรียกค่าไถ่")),
    ("phishing", ("phishing", "ฟิชชิง", "ลิงก์", "qr code")),
    ("multi_factor_authentication", ("multi-factor", "two-factor", "mfa", "2fa", "ยืนยันตัวตน")),
    ("password_security", ("password", "passphrase", "passkey", "รหัสผ่าน")),
    ("backup", ("backup", "back up", "สำรองข้อมูล", "สํารองข้อมูล")),
    ("malware", ("malware", "มัลแวร์")),
    ("public_wifi", ("wi-fi", "wifi", "ไวไฟ")),
    ("identity_theft", ("identity theft", "สวมรอย", "ข้อมูลส่วนบุคคล")),
    ("account_recovery", ("hacked account", "account recovery", "บัญชีถูก")),
    ("financial_scam", ("financial fraud", "loan", "เงินกู้", "ภัยการเงิน", "กลโกง")),
    ("mobile_security", ("mobile phone", "android", "โทรศัพท์")),
    ("software_updates", ("update software", "software update", "อัปเดต")),
)


def is_heading(line: str) -> bool:
    text = line.strip()
    if not 3 <= len(text) <= 140 or text.startswith(("- ", "* ", "• ")):
        return False
    if text.startswith("#") or re.match(r"^\d+(?:\.\d+){0,4}\s+\S", text):
        return True
    letters = [char for char in text if char.isascii() and char.isalpha()]
    return (
        len(text.split()) >= 2
        and bool(letters)
        and all(char.isupper() for char in letters)
        and len(letters) >= 4
    )


def document_sections(document: dict[str, object]) -> list[tuple[str, str, int | None]]:
    sections = []
    page = None
    section = str(document["title"])
    lines = []
    for raw_line in str(document["content"]).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if match := PAGE_RE.match(line):
            if lines:
                sections.append(("\n".join(lines), section, page))
                lines = []
            page = int(match.group(1))
            continue
        if is_heading(line):
            if lines:
                sections.append(("\n".join(lines), section, page))
                lines = []
            section = line.lstrip("# ").strip()
        lines.append(line)
    if lines:
        sections.append(("\n".join(lines), section, page))
    return sections


def classify_topic(text: str) -> str:
    lowered = text.casefold()
    for topic, keywords in TOPICS:
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "general_cybersecurity"


def build_chunk(
    document: dict[str, object], content: str, section: str, page: int | None, sequence: int
) -> dict[str, object]:
    title = str(document["title"])
    topic = classify_topic(f"{title} {section} {content}")
    citation = title
    if page is not None:
        citation += f", page {page}"
    elif section != title:
        citation += f", {section}"
    return {
        "chunk_id": f"{document['document_id']}-{sequence:04d}",
        "document_id": document["document_id"],
        "source_id": document["source_id"],
        "title": title,
        "section": section,
        "page_start": page,
        "page_end": page,
        "citation": citation,
        "topic": topic,
        "subtopic": None,
        "language": document["language"],
        "audience": document.get("audience", "general"),
        "source": document["organization"],
        "source_type": document["source_type"],
        "authority": document.get("authority"),
        "freshness": document.get("freshness"),
        "published_at": document.get("published_at"),
        "updated_at": document.get("updated_at"),
        "retrieved_at": document["retrieved_at"],
        "url": document["source_url"],
        "rights_status": document["rights_status"],
        "corpus_version": document["corpus_version"],
        "char_count": len(content),
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "content": content,
    }


def chunk_document(document: dict[str, object]) -> list[dict[str, object]]:
    document = NormalizedDocument.model_validate(document).model_dump(mode="json")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = []
    for content, section, page in document_sections(document):
        for piece in splitter.split_text(content):
            chunks.append(build_chunk(document, piece, section, page, len(chunks) + 1))
    return chunks


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    seen = set()
    count = 0
    try:
        with (
            INPUT_PATH.open(encoding="utf-8") as source,
            temporary.open("w", encoding="utf-8") as target,
        ):
            for line in source:
                if not line.strip():
                    continue
                document = json.loads(line)
                if document["document_id"] in seen:
                    raise ValueError(f"Duplicate document ID: {document['document_id']}")
                seen.add(document["document_id"])
                chunks = chunk_document(document)
                if not chunks:
                    raise ValueError(f"No chunks for document: {document['document_id']}")
                for chunk in chunks:
                    target.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    count += 1
        if not count:
            raise ValueError("No chunks to write")
        temporary.replace(OUTPUT_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"wrote {count} chunks from {len(seen)} documents to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
