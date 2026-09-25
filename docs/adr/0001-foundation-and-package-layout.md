# ADR 0001: Foundation and package layout

- Status: Accepted
- Date: 2026-09-25

## Context

The system will grow across ingestion, retrieval, graph, validation, generation, and evaluation
work streams. Three contributors need stable import paths and low-conflict ownership boundaries.

## Decision

- Use `uv` for Python selection, dependency locking, virtual environments, and command execution.
- Target Python 3.12 and keep the environment in the repository-local `.venv` directory.
- Use a `src/cybersecurity_advisor` package rather than placing modules directly under `src`.
- Load secrets only through environment variables or the Git-ignored `.env` file.
- Keep optional Redis and OpenSearch services behind Docker Compose profiles.
- Add integrations phase by phase; do not create empty implementations for the full final tree.
- Establish source metadata contracts now, while deferring selection and ingestion of documents.

## Consequences

Imports and packaging are deterministic, and each phase can add one cohesive package. Local
setup requires `uv`, while Docker remains available for shared infrastructure and the API.
