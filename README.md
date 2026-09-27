# Cybersecurity Knowledge Advisor

Adaptive Hybrid RAG chatbot for answering cybersecurity questions from reviewed,
traceable sources. The implementation currently includes Dense RAG, Graph RAG with JEV entity
validation, and normalized Hybrid Fusion.

Follow [the course MVP scope](docs/mvp.md) for implementation priorities, ingestion
commands, and rubric acceptance evidence. The larger plan is a future backlog.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker Desktop with Docker Compose (for local infrastructure)
- Git

`uv` installs and selects the Python version declared in `.python-version`; a separate
system-wide Python installation is not required.

## First-time setup

```powershell
Copy-Item .env.example .env  # Skip this when a local .env already exists
uv sync --dev
```

Keep all real credentials, including `JEV_API_KEY`, in `.env`. The existing local name
`TYPE_SAFE` is also accepted as an alias, so no secret needs to be copied or renamed. The file
is ignored by Git. Never place a real secret in `.env.example`.

Start the API:

```powershell
uv run uvicorn cybersecurity_advisor.api.main:app --reload
```

Open <http://localhost:8000/docs> or check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Infrastructure

Start the retrieval services when needed:

```powershell
docker compose --profile rag up -d
```

Optional services are grouped into profiles so they do not consume resources by default:

```powershell
docker compose --profile cache up -d redis
docker compose --profile sparse up -d opensearch
```

To build and run the API independently:

```powershell
docker compose --profile app up -d --build
```

## Quality checks

```powershell
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

## Data sources

The source documents have not been selected yet. Do not add arbitrary documents directly
to the repository. Follow [the data source selection guide](docs/data-source-selection.md),
then copy `data/source_manifest.example.json` to a reviewed manifest when the team reaches
agreement.

Downloaded/raw documents and generated artifacts under `data/` are ignored by Git. Commit
only manifests, documentation, small test fixtures with clear permission, and labeled
evaluation data intended for version control.

## Graph retrieval

Generated chunk corpora belong at `data/chunks/chunks.jsonl`; this runtime artifact is ignored by
Git. Build graph records and run an offline smoke query with:

```powershell
uv run python scripts/build_graph.py extract
uv run python scripts/graph_retrieval.py "phishing and MFA" `
  --records data/graph/graph_records.jsonl --max-depth 2 --top-k 5
```

Graph retrieval validates mention-to-entity candidates with JEV before traversal. Configure
`JEV_API_KEY` (or the legacy `TYPE_SAFE`) and `NEO4J_PASSWORD`, start the service, then re-ingest
before querying so Chunk nodes contain evidence text:

```powershell
docker compose --profile rag up -d neo4j
uv run python scripts/build_graph.py ingest
uv run python scripts/graph_retrieval.py "phishing and MFA"
```

Inspect the typed `same` / `different` / `uncertain` decisions independently through:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/graph/entities/validate `
  -ContentType "application/json" `
  -Body '{"query":"บัญชีถูกแฮ็กและต้องเปลี่ยนรหัสผ่าน"}'
```

Use `--skip-jev` only for an explicit no-JEV ablation run. Normal graph retrieval fails closed
with HTTP 503 when JEV is enabled but unavailable, so unvalidated candidates never enter graph
traversal.

## Hybrid retrieval

Hybrid retrieval combines Dense and validated Graph candidates, deduplicates identical evidence,
limits repeated chunks from one document, and returns normalized scores. RRF is the default;
`naive` and `weighted` are available for comparative experiments:

```powershell
uv run python scripts/hybrid_retrieval.py "บัญชีถูกแฮ็ก ต้องเปลี่ยนรหัสผ่านอย่างไร" `
  --language th --fusion-method rrf --top-k 5
```

The API equivalent is `POST /api/v1/hybrid/retrieve`. Configure the default method, weights,
RRF constant, and diversity limit with the `HYBRID_*` values in `.env`. Request-level overrides
make the same query reproducible across fusion experiments.

## Answer generation

Configure either `OLLAMA_MODEL` for a local model or `OPENAI_API_KEY` and `OPENAI_MODEL` for the
OpenAI Responses API. The same hybrid evidence and grounded prompt are used by both providers:

```powershell
$body = @{ query = "phishing and MFA"; provider = "ollama"; fusion_method = "rrf" } |
  ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/chat `
  -ContentType "application/json" -Body $body
```

The response contains the answer, numbered sources, provider-reported token counts, and separate
retrieval/JEV/generation latency. Before generation, JEV checks every fused candidate for relevance,
answer evidence, contradiction, and prompt injection; only `include` candidates reach the prompt.
Use `dynamic_k=true` to apply the final score-gap/token cutoff after this filter. Generated factual
claims then receive deterministic citation checks and batched JEV semantic verdicts in the
`citation_validation` response field. Until JEV credentials are available, disable all three
`JEV_ENTITY_VALIDATION_ENABLED`, `JEV_PREGEN_FILTER_ENABLED`, and
`JEV_CITATION_VALIDATION_ENABLED` flags only for the documented no-JEV baseline.

## Team workflow

Use short-lived feature branches and pull requests; do not push feature work directly to
`main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, review, and completion rules.

The full architecture and research plan is in [plan.md](plan.md).
