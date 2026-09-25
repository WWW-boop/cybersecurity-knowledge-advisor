from scripts.build_chunks import CHUNK_SIZE, chunk_document


def test_chunks_keep_section_and_page_metadata() -> None:
    document = {
        "organization": "ETDA",
        "source_type": "government",
        "content_sha256": "0" * 64,
        "document_id": "example",
        "source_id": "TH-01",
        "title": "Cyber safety",
        "content": (
            "[Page 1]\n# Phishing\n"
            + "ป้องกันการหลอกลวงออนไลน์" * 100
            + "\n[Page 2]\n# Recovery\nกู้คืนบัญชี"
        ),
        "language": "th",
        "retrieved_at": "2026-01-01",
        "source_url": "https://example.com",
        "rights_status": "public",
        "corpus_version": "test",
    }

    chunks = chunk_document(document)

    assert len(chunks) > 2
    assert all(chunk["char_count"] <= CHUNK_SIZE for chunk in chunks)
    assert all(chunk["page_start"] == chunk["page_end"] for chunk in chunks)
    assert all(chunk["section"] == "Phishing" for chunk in chunks[:-1])
    assert chunks[-1]["section"] == "Recovery"
    assert chunks[-1]["citation"] == "Cyber safety, page 2"


def test_recursive_splitter_uses_character_units_and_overlap():
    from scripts.build_chunks import CHUNK_OVERLAP

    text = "".join(chr(0x0E01 + i % 40) for i in range(2200))
    document = {
        "document_id": "thai",
        "source_id": "TH-01",
        "title": "Safety",
        "organization": "ETDA",
        "source_type": "government",
        "language": "th",
        "content": text,
        "content_sha256": "0" * 64,
        "retrieved_at": "2026-09-26",
        "source_url": "https://example.com/thai",
        "rights_status": "review_required",
        "corpus_version": "test",
    }
    chunks = chunk_document(document)
    assert len(chunks[0]["content"]) == CHUNK_SIZE
    assert chunks[0]["content"][-CHUNK_OVERLAP:] == chunks[1]["content"][:CHUNK_OVERLAP]
    reconstructed = chunks[0]["content"] + "".join(
        chunk["content"][CHUNK_OVERLAP:] for chunk in chunks[1:]
    )
    assert reconstructed == text
