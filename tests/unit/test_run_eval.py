"""Deterministic retrieval-evaluation metrics."""

import pytest

from scripts.run_eval import deduplicate_source_ids, retrieval_metrics


def test_document_metrics_deduplicate_ranked_chunk_sources() -> None:
    ranked = deduplicate_source_ids(
        [
            {"metadata": {"source_id": "EN-01"}},
            {"metadata": {"source_id": "EN-01"}},
            {"metadata": {"source_id": "EN-02"}},
            {"metadata": {"source_id": "EN-03"}},
        ]
    )

    assert ranked == ["EN-01", "EN-02", "EN-03"]
    assert retrieval_metrics({"EN-01", "EN-03"}, ranked, k=3) == pytest.approx(
        {
            "recall_at_k": 1.0,
            "precision_at_k": 2 / 3,
            "hit_rate_at_k": 1.0,
            "mrr_at_k": 1.0,
            "ndcg_at_k": 0.9197207891,
        }
    )
