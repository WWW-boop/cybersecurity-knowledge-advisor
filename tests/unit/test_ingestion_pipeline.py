"""Regression checks for the small, file-based ingestion pipeline."""

import hashlib
import json

import pymupdf
import pytest

from scripts import build_chunks, build_documents


def test_html_keeps_headings_and_inline_thai(tmp_path):
    path = tmp_path / "sample.html"
    path.write_text(
        "<title>Safety</title><nav>Ignore navigation</nav><main>"
        "<h2>ป้องกันบัญชี</h2><p>รหัส<strong>ผ่าน</strong></p>"
        "<h2>Recover account</h2><p>Reset password.</p></main>",
        encoding="utf-8",
    )
    title, content, _ = build_documents.extract_html(path)
    assert "รหัสผ่าน" in content
    assert "Ignore navigation" not in content
    sections = build_chunks.document_sections({"title": title, "content": content})
    assert [section for _, section, _ in sections] == ["ป้องกันบัญชี", "Recover account"]


def test_text_pdf_preserves_pages_and_accepts_short_content(tmp_path):
    path = tmp_path / "sample.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "Page one advice.")
        pdf.new_page().insert_text((72, 72), "Page two advice.")
        pdf.save(path)
    _, content, metadata = build_documents.extract_pdf(path)
    assert "[Page 1]\nPage one advice." in content
    assert "[Page 2]\nPage two advice." in content
    assert metadata["extraction_method"] == "pymupdf_text"
    _, selected, _ = build_documents.extract_pdf(path, (2, 2))
    assert "[Page 1]" not in selected
    with pytest.raises(ValueError, match="Invalid PDF page range"):
        build_documents.extract_pdf(path, (0, 2))


def test_empty_pdf_is_rejected(tmp_path):
    path = tmp_path / "empty.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(path)
    with pytest.raises(ValueError, match="no usable content"):
        build_documents.extract_pdf(path)


def test_manifest_to_chunks_and_failed_rebuild_preserves_outputs(tmp_path, monkeypatch):
    html = tmp_path / "source.html"
    html.write_text("<title>Main page</title><main><h2>Safety</h2><p>Advice.</p></main>")
    companion = tmp_path / "guide.pdf"
    with pymupdf.open() as pdf:
        pdf.set_metadata({"title": "PDF guide"})
        pdf.new_page().insert_text((72, 72), "Companion advice.")
        pdf.save(companion)
    source = {
        "source_id": "TH-01",
        "enabled": True,
        "status": "downloaded",
        "filename": html.name,
        "sha256": hashlib.sha256(html.read_bytes()).hexdigest(),
        "canonical_url": "https://example.com/article",
        "organization": "ETDA",
        "source_type": "government",
        "language": "th",
        "companion_filename": companion.name,
        "companion_sha256": hashlib.sha256(companion.read_bytes()).hexdigest(),
        "companion_url": "https://example.com/guide.pdf",
        "companion_page_range": [1, 1],
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "sources": [source],
                "retrieved_at": "2026-09-26",
                "rights_status": "review_required",
                "corpus_version": "test",
            }
        )
    )
    documents_path = tmp_path / "documents.jsonl"
    chunks_path = tmp_path / "chunks.jsonl"
    monkeypatch.setattr(build_documents, "RAW_DIR", tmp_path)
    monkeypatch.setattr(build_documents, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(build_documents, "OUTPUT_PATH", documents_path)
    monkeypatch.setattr(build_chunks, "INPUT_PATH", documents_path)
    monkeypatch.setattr(build_chunks, "OUTPUT_PATH", chunks_path)
    build_documents.main()
    build_chunks.main()
    chunks = [json.loads(line) for line in chunks_path.read_text().splitlines()]
    assert len(chunks) == 2
    assert chunks[1]["url"] == source["companion_url"]
    assert chunks[1]["citation"] == "PDF guide, page 1"
    assert chunks[1]["source"] == "ETDA"
    assert chunks[1]["authority"] is None
    previous_documents = documents_path.read_bytes()
    previous_chunks = chunks_path.read_bytes()
    html.write_text("Changed content")
    with pytest.raises(ValueError, match="hash mismatch"):
        build_documents.main()
    assert documents_path.read_bytes() == previous_documents
    documents_path.write_text(previous_documents.decode() + previous_documents.decode())
    with pytest.raises(ValueError, match="Duplicate document ID"):
        build_chunks.main()
    assert chunks_path.read_bytes() == previous_chunks
    assert not chunks_path.with_suffix(".tmp").exists()
