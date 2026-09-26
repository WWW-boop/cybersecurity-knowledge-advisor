# Final project MVP

This is the implementation scope for the course rubric. The larger `plan.md` is a
backlog, not a requirement to build every proposed service. Aim first for all Level 3
workflows to function, then improve fusion and evaluation toward Level 4. Scores depend
on demonstrated results, not the number of technologies installed.

## Current state

Implemented: API health endpoints, text extraction, validated document metadata,
section/page-aware chunking, GTE/Qdrant dense retrieval, `POST /api/v1/retrieve`, deterministic
graph construction with chunk-level provenance, bounded entity-aware graph retrieval through
`POST /api/v1/graph/retrieve`, JEV entity validation before traversal with typed decisions through
`POST /api/v1/graph/entities/validate`, and synthetic pipeline tests. The recorded Neo4j ingestion
contains 999 chunks and 162 semantic facts and must be re-ingested after graph schema changes.
Fusion, answer generation, and final experiment results are still to be completed.

## Smallest complete workflow

1. Use a reviewed Thai/English corpus with source URLs and page/section citations.
2. Embed chunks into Qdrant. Start with fixed Top-K; record retrieved chunk IDs.
3. Store meaningful entities and relations in Neo4j, each linked to supporting chunk IDs.
   Start with a small manually checked graph and bounded one-hop queries.
4. Support `dense`, `graph`, and `hybrid` modes. For hybrid, combine ranked chunk lists
   with reciprocal rank fusion, deduplicate by chunk ID, and cap the final context.
5. Pass the same context/prompt format to either an Ollama model or one API LLM.
   Show source citations; return an explicit failure when a provider is unavailable.
6. Provide one query endpoint and a small demo interface. Record mode, model, sources,
   latency, and provider-reported token usage when available. Never fabricate usage.
7. Evaluate all three retrieval modes with both LLMs on the same 20–30 reviewed
   questions. Record retrieval Recall@K, answer correctness, citation correctness,
   latency, and API usage/cost where known. Keep model names and configuration with results.

Hybrid integration and this six-configuration comparison are the priority. Add a
second Top-K or fusion setting only after the baseline works. Defer adaptive routing,
rerankers, caching, OpenSearch, Postgres, and multi-provider abstractions until an
experiment demonstrates a need.

## Ingestion baseline

```sh
uv sync --group ingestion
uv run --group ingestion python scripts/build_documents.py
uv run --group ingestion python scripts/build_chunks.py
```

Place raw files and `download-manifest.json` under
`data/raw/recommended-corpus-v0.2/`. Start from
`data/download_manifest.example.json`; replace the example hash and metadata.
Set `enabled` to true for sources selected for the project.

The download manifest is the file-level input; `source_manifest.example.json` is a
publisher selection template. They serve different purposes.

- PDF input must contain selectable text. Extraction uses PyMuPDF directly, preserves
  page numbers, and rejects documents without usable text. No OCR tools are required.
- HTML headings become Markdown headings; inline Thai text is kept intact.
- `RecursiveCharacterTextSplitter` splits within each page/section using **1,000
  characters**, with a target overlap of **200 characters**. These are character units,
  not tokens. Short sections remain short; overlap does not cross section/page boundaries.
- When embedding is connected, validate chunks against that model's actual token limit.
  Character sizing alone does not guarantee any model's token budget.
- Publisher, source type, language, and optional dates/scores come from the manifest.
  Unknown authority/freshness remains null. Regenerate old JSONL artifacts after updating
  the manifest; generated chunks now contain `char_count` instead of `estimated_tokens`.
- Optional companions require `companion_filename`, `companion_sha256`, `companion_url`,
  and `companion_page_range`. They produce a separate document with its own title and URL.
- Output is written incrementally through a temporary file and replaced only on success.

## Services

```sh
docker compose --profile app up -d --build
docker compose --profile rag up -d
```

The API can start independently. The `rag` profile starts Qdrant and Neo4j when needed.
Postgres (`storage`), Redis (`cache`), and OpenSearch (`sparse`) remain optional.

## Acceptance evidence

Keep a reproducible command, dataset version, model settings, and results table for each
experiment. Demonstrate a question where a graph relationship contributes evidence to
the final hybrid answer. Document failures and hardware limits as well as successful
answers. A passing unit test suite alone does not establish RAG answer quality.
