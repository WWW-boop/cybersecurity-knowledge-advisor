"""Deterministic generation-evaluation metrics."""

import httpx
import pytest

from scripts.run_generation_eval import (
    deterministic_citation_metrics,
    error_detail,
    reference_token_f1,
)


def test_generation_metrics_score_reference_overlap_and_citations() -> None:
    assert reference_token_f1("Use MFA now", "Use MFA") == pytest.approx(0.8)
    assert deterministic_citation_metrics("Supported [S1], fabricated [S9].", 2) == (0.5, 1.0)


def test_error_detail_accepts_non_json_response() -> None:
    assert error_detail(httpx.Response(500, text="upstream failed")) == "upstream failed"
