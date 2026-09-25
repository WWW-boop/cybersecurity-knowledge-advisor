# Contributing

## Workflow

1. Update local `main` and create a short-lived branch.
2. Use `feat/`, `fix/`, `test/`, `docs/`, or `chore/` as the branch prefix.
3. Keep each pull request focused on one concern.
4. Ask at least one teammate to review before merging.
5. Resolve ownership or contract changes in an ADR under `docs/adr/`.

Suggested ownership for the three work streams:

- Platform: API, configuration, containers, CI, and observability.
- Knowledge: source review, ingestion, chunking, embeddings, and Dense RAG.
- Reasoning/evaluation: Graph RAG, JEV adapters, evaluation, and experiments.

Hybrid retrieval contracts and integration changes require cross-review from another stream.

## Before opening a pull request

```powershell
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run pytest
docker compose config --quiet
```

Confirm that the staged changes contain no secrets, downloaded corpora, generated indexes,
database volumes, model weights, or notebook output.

## Commit messages

Prefer an imperative Conventional Commit style, for example:

```text
feat: add document metadata validation
test: cover dynamic retrieval budgets
docs: record graph schema decision
```
