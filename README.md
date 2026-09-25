# Cybersecurity Knowledge Advisor

Adaptive Hybrid RAG chatbot for answering cybersecurity questions from reviewed,
traceable sources. The project is currently in **Phase 1: Foundation**.

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

Start the Phase 1 core services:

```powershell
docker compose up -d qdrant neo4j postgres
```

Optional services are grouped into profiles so they do not consume resources by default:

```powershell
docker compose --profile cache up -d redis
docker compose --profile sparse up -d opensearch
```

To build and run the API in Docker with the core services:

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

## Team workflow

Use short-lived feature branches and pull requests; do not push feature work directly to
`main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, review, and completion rules.

The full architecture and research plan is in [plan.md](plan.md).
