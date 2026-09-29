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

Configure `PSU_AI_API_KEY` for the `ai.psu.blue` OpenAI-compatible API. The selected answer
model is `qwen/qwen3.6-flash` with `PSU_AI_MAX_OUTPUT_TOKENS=3000`. Online answers use this API
first; if generation fails or API credentials are absent, the same prompt and retrieved context
go to local Ollama. Install Ollama, pull `qwen3.5:2b` with `ollama pull qwen3.5:2b`, and keep its
service running on `http://localhost:11434`. Override `OLLAMA_BASE_URL` and `OLLAMA_MODEL` if
needed. Responses identify the actual generator in `provider` (`openai` or `ollama`). If both
generators are unavailable, the chat API returns HTTP 503. The API attempt times out after
`PSU_AI_FAILOVER_TIMEOUT_SECONDS` (default 20) before trying Ollama; adjust this if the API
normally takes longer. The fallback applies to answer generation, not retrieval or JEV services.
The API uses an XML-structured prompt to answer directly and use hybrid evidence where relevant:

```powershell
$body = @{ query = "phishing and MFA"; fusion_method = "rrf" } |
  ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/chat `
  -ContentType "application/json" -Body $body
```

The response includes a `session_id`. Send it with the next `POST /api/v1/chat` request to ask
follow-up questions in the same conversation. Omit it to start a new conversation. The server keeps
the last three question-answer pairs per session for 30 minutes in process memory; history disappears
when the API restarts and is not shared across multiple API workers.

The response contains the answer, numbered sources, provider-reported token counts, and separate
retrieval/JEV/generation latency. Before generation, JEV checks every fused candidate for relevance,
answer evidence, contradiction, and prompt injection; only `include` candidates reach the prompt.
Use `dynamic_k=true` to apply the final score-gap/token cutoff after this filter. Generated factual
claims then receive deterministic citation checks and batched JEV semantic verdicts in the
`citation_validation` response field. When no evidence passes, the model can still give cautious
general guidance without citations; uncited advice is reported as ungrounded by this validator.
Until JEV credentials are available, disable all three
`JEV_ENTITY_VALIDATION_ENABLED`, `JEV_PREGEN_FILTER_ENABLED`, and
`JEV_CITATION_VALIDATION_ENABLED` flags only for the documented no-JEV baseline.

## LINE Messaging API

The LINE adapter accepts signed text-message webhooks at `POST /api/v1/line/webhook`, runs the
existing Dynamic Hybrid + configured JEV answer pipeline in a background task, and replies through
the LINE Reply API. Successful answers are rendered as a Flex Message with a bounded answer
preview, up to five source names without links, and quick replies for common questions. Verification
requests with an empty `events` list return HTTP 200 without loading the embedding model or
connecting to the retrieval services.

LINE remembers recent turns separately for each user and chat room. Retrieval carries the previous
question into an explicit follow-up, not every new topic. The `เริ่มแชตใหม่` message clears that
context without calling the answer model. To install the AI-first default Rich Menu (ask AI,
describe an incident, example questions, new chat), run `python -m scripts.setup_line_rich_menu`
with `LINE_CHANNEL_ACCESS_TOKEN` configured. The menu image is `assets/line-rich-menu.png`;
`assets/line-rich-menu.html` is its editable source. Installation replaces the current default
Messaging API rich menu, but does not replace per-user rich menus.

Create a Messaging API channel in LINE Developers Console and put its credentials only in the
ignored local `.env`:

```dotenv
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token
LINE_DYNAMIC_K=true
```

LINE uses the configured `PSU_AI_*` gateway. Start all required RAG services and the API,
then expose this webhook URL through a public HTTPS endpoint with a trusted certificate:

```text
https://your-public-host.example/api/v1/line/webhook
```

Enter the URL under the channel's Messaging API settings, click **Verify**, enable **Use webhook**,
and disable the LINE Official Account's automatic response messages to avoid duplicate answers.
The webhook verifies `X-Line-Signature` against the exact raw request body before parsing JSON.
Image, audio, file, and sticker messages receive a text-only support notice.

The Phase 12 dataset and generated answers still require independent human review. Treat the LINE
channel as a supervised pilot and do not present its cybersecurity answers as production-approved
guidance until that review is complete.

For a temporary Cloudflare Quick Tunnel on Windows, install the project-local verified binary once,
start the API, and then launch the tunnel. The installer stores the executable under the ignored
`.tools/` directory and verifies its SHA-256 against the official GitHub release metadata.

```powershell
.\scripts\install_cloudflared.ps1
.\scripts\start_line_tunnel.ps1 -CheckOnly
.\scripts\start_line_tunnel.ps1
```

The last command prints a random `https://*.trycloudflare.com` URL. Append
`/api/v1/line/webhook`, set that complete URL in LINE Developers Console, click **Verify**, and
enable **Use webhook**. The URL changes whenever the Quick Tunnel is restarted, so use a named
Cloudflare Tunnel and a controlled domain for a stable deployment.

## Evaluation

`scripts/run_eval.py` compares Dense, Graph, fixed Hybrid, and Dynamic Hybrid retrieval and exports
JSON, CSV, Markdown, and a Matplotlib chart. `scripts/run_generation_eval.py` measures answer,
citation, latency, token, CPU/RAM/GPU, estimated API cost, and JEV-ablation metrics. The consolidated
preliminary report is generated by `scripts/build_phase12_report.py`; complete
`data/evaluation/results/dataset-review.csv` and each `manual_review.csv` before making final claims.

For offline local-LLM evaluation, start Ollama with the models you want to compare, then run
`python -m scripts.benchmark_ollama_models --models qwen3.5:4b` while the API is running. This
uses the same retrieved Hybrid RAG context for offline comparisons, and writes results to
`data/evaluation/ollama-benchmark/`.

## Team workflow

Use short-lived feature branches and pull requests; do not push feature work directly to
`main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, review, and completion rules.

The full architecture and research plan is in [plan.md](plan.md).
