$ErrorActionPreference = "Stop"

uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run pytest
docker compose config --quiet
