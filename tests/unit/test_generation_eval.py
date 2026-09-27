"""Deterministic generation-evaluation metrics."""

import pytest

from scripts.run_generation_eval import deterministic_citation_metrics, reference_token_f1


def test_generation_metrics_score_reference_overlap_and_citations() -> None:
    assert reference_token_f1("Use MFA now", "Use MFA") == pytest.approx(0.8)
    assert deterministic_citation_metrics("Supported [S1], fabricated [S9].", 2) == (0.5, 1.0)
