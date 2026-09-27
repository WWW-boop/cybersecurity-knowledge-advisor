"""Small checks for deterministic Ollama benchmark scoring."""

from scripts.benchmark_ollama_models import citation_metrics, select_questions


def test_select_questions_balances_languages_and_scores_citations() -> None:
    rows = [
        {"query_id": "th-1", "language_group": "th"},
        {"query_id": "th-2", "language_group": "th"},
        {"query_id": "en-1", "language_group": "en"},
    ]

    assert [row["query_id"] for row in select_questions(rows, 1)] == ["th-1", "en-1"]
    assert citation_metrics("Supported [S1], invalid [S9].", 2) == (0.5, 1.0)
    assert citation_metrics("No citation", 2) == (0.0, 0.0)
