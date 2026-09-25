# Phase 2 Ingestion Handoff

## Current status

- Phase 1 merged into `main`
- Base commit: `779d6b3`
- Working branch: `feat/ingestion-foundation`
- Phase 2 implementation has not started
- Existing tests pass

## Goal

Implement a local document ingestion pipeline:

Manifest
→ Loader
→ Cleaner
→ Metadata validation
→ Section-aware chunking
→ Deduplication
→ JSONL output

## Required work

- Source manifest loader
- RawDocument and Chunk schemas
- TXT/Markdown loader
- HTML loader
- PDF loader
- Unicode and whitespace normalization
- Repeated header/footer removal
- Duplicate paragraph removal
- Stable document and chunk IDs
- SHA-256 hashes
- Section-aware chunking
- JSONL writer
- `scripts/ingest.py`
- Synthetic Thai and English fixtures
- Unit and integration tests

## Constraints

- Process only local files declared in the manifest
- Do not implement a web crawler yet
- Do not connect Qdrant or create embeddings yet
- Do not commit `.env`, raw documents, generated chunks, or API keys
- Use synthetic fixtures until the team approves real sources

## Verification

```powershell
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run pytest