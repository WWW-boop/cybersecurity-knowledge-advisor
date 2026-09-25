"""Build section-aware JSONL chunks from normalized documents using only stdlib."""

import hashlib
import json
import math
import re
import statistics
from pathlib import Path

INPUT_PATH = Path("data/processed/documents.jsonl")
OUTPUT_PATH = Path("data/chunks/chunks.jsonl")
TARGET_TOKENS = 300
MAX_TOKENS = 500
MIN_TOKENS = 200
OVERLAP_TOKENS = 75
TITLE_OVERRIDES = {"TH-07": "คู่มือ คนไทยรู้ทันภัยไซเบอร์"}
PAGE_RE = re.compile(r"^\[Page (\d+)]$")
LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-_./'][A-Za-z0-9]+)*")
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


def estimate_tokens(text: str) -> int:
    latin_words = len(LATIN_WORD_RE.findall(text))
    without_latin = LATIN_WORD_RE.sub("", text)
    thai_chars = sum("\u0e00" <= char <= "\u0e7f" for char in without_latin)
    other_chars = sum(
        not char.isspace() and not ("\u0e00" <= char <= "\u0e7f") for char in without_latin
    )
    return latin_words + math.ceil(thai_chars / 2.5) + math.ceil(other_chars / 4)


def split_oversized(text: str) -> list[str]:
    pieces = []
    remaining = text.strip()
    while estimate_tokens(remaining) > MAX_TOKENS:
        cut = max(1, int(len(remaining) * MAX_TOKENS / estimate_tokens(remaining) * 0.9))
        space = remaining.rfind(" ", int(cut * 0.75), cut)
        if space > 0:
            cut = space
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


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


def document_units(document: dict[str, object]) -> list[dict[str, object]]:
    units = []
    page = None
    section = TITLE_OVERRIDES.get(str(document["source_id"]), str(document["title"]))
    boundary = True
    for raw_line in str(document["content"]).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if match := PAGE_RE.match(line):
            page = int(match.group(1))
            boundary = True
            continue
        if is_heading(line):
            section = line.lstrip("# ").strip()
            boundary = True
        for piece in split_oversized(line):
            units.append(
                {
                    "text": piece,
                    "tokens": estimate_tokens(piece),
                    "section": section,
                    "page": page,
                    "boundary": boundary,
                }
            )
            boundary = False
    return units


def overlap_tail(units: list[dict[str, object]]) -> list[dict[str, object]]:
    tail = []
    tokens = 0
    for unit in reversed(units):
        if tokens >= OVERLAP_TOKENS:
            break
        tail.append(unit)
        tokens += int(unit["tokens"])
    return list(reversed(tail))


def source_metadata(source_id: str) -> tuple[str, str]:
    prefix, number_text = source_id.split("-")
    number = int(number_text)
    if prefix == "TH":
        if number in {1, 2, 7, 8}:
            return "ETDA", "government"
        if number in {3, 9, 10, 11}:
            return "Bank of Thailand", "government"
        if number == 4:
            return "Royal Thai Police", "government"
        return "ThaiCERT", "government"
    if number in {1, 2, 3, 4, 12}:
        return "CISA", "government"
    if number in {5, 6, 7, 13, 14, 15, 16, 17, 18, 19, 20}:
        return "FTC", "government"
    if number in {8, 9, 10, 11}:
        return "NIST", "standard" if number == 8 else "government"
    return "Australian Cyber Security Centre", "government"


def classify_topic(text: str) -> str:
    lowered = text.casefold()
    for topic, keywords in TOPICS:
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "general_cybersecurity"


def build_chunk(
    document: dict[str, object], units: list[dict[str, object]], sequence: int
) -> dict[str, object]:
    content = "\n".join(str(unit["text"]) for unit in units)
    title = TITLE_OVERRIDES.get(str(document["source_id"]), str(document["title"]))
    sections = list(dict.fromkeys(str(unit["section"]) for unit in units))
    pages = [int(unit["page"]) for unit in units if unit["page"] is not None]
    page_start = min(pages) if pages else None
    page_end = max(pages) if pages else None
    section = " > ".join(sections[:3])
    source, source_type = source_metadata(str(document["source_id"]))
    topic = classify_topic(f"{title} {section} {content}")
    citation = title
    if page_start is not None:
        citation += (
            f", page {page_start}" if page_start == page_end else f", pages {page_start}-{page_end}"
        )
    elif section != title:
        citation += f", {section}"
    return {
        "chunk_id": f"{document['document_id']}-{sequence:04d}",
        "document_id": document["document_id"],
        "source_id": document["source_id"],
        "title": title,
        "section": section,
        "page_start": page_start,
        "page_end": page_end,
        "citation": citation,
        "topic": topic,
        "subtopic": None,
        "language": document["language"],
        "audience": "general",
        "source": source,
        "source_type": source_type,
        "authority": 1.0,
        "freshness": None,
        "published_at": None,
        "updated_at": None,
        "retrieved_at": document["retrieved_at"],
        "url": document["source_url"],
        "rights_status": document["rights_status"],
        "corpus_version": document["corpus_version"],
        "estimated_tokens": estimate_tokens(content),
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "content": content,
    }


def chunk_document(document: dict[str, object]) -> list[dict[str, object]]:
    chunks = []
    current = []
    current_tokens = 0
    new_content = False
    sequence = 1

    for unit in document_units(document):
        unit_tokens = int(unit["tokens"])
        if current and (bool(unit["boundary"]) and current_tokens >= MIN_TOKENS):
            chunks.append(build_chunk(document, current, sequence))
            sequence += 1
            current = overlap_tail(current)
            current_tokens = sum(int(item["tokens"]) for item in current)
            new_content = False
        if current and current_tokens + unit_tokens > MAX_TOKENS:
            chunks.append(build_chunk(document, current, sequence))
            sequence += 1
            current = overlap_tail(current)
            current_tokens = sum(int(item["tokens"]) for item in current)
            new_content = False
            if current_tokens + unit_tokens > MAX_TOKENS:
                current = []
                current_tokens = 0
        current.append(unit)
        current_tokens += unit_tokens
        new_content = True
        if current_tokens >= TARGET_TOKENS:
            chunks.append(build_chunk(document, current, sequence))
            sequence += 1
            current = overlap_tail(current)
            current_tokens = sum(int(item["tokens"]) for item in current)
            new_content = False

    if current and (new_content or not chunks):
        chunks.append(build_chunk(document, current, sequence))
    return chunks


def main() -> None:
    documents = [
        json.loads(line) for line in INPUT_PATH.read_text(encoding="utf-8").splitlines() if line
    ]
    chunks = [chunk for document in documents for chunk in chunk_document(document)]
    ids = [chunk["chunk_id"] for chunk in chunks]
    represented = {chunk["document_id"] for chunk in chunks}
    assert len(ids) == len(set(ids))
    assert represented == {document["document_id"] for document in documents}
    assert all(chunk["content"] and chunk["url"] for chunk in chunks)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(
        "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        encoding="utf-8",
    )
    temporary.replace(OUTPUT_PATH)
    sizes = [int(chunk["estimated_tokens"]) for chunk in chunks]
    print(
        f"wrote {len(chunks)} chunks from {len(documents)} documents to {OUTPUT_PATH} "
        f"(tokens min/median/max={min(sizes)}/{statistics.median(sizes):g}/{max(sizes)})"
    )


if __name__ == "__main__":
    main()
