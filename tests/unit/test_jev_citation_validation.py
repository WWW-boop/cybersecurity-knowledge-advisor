"""Claim extraction and typed JEV citation-validation tests."""

import json

import httpx

from cybersecurity_advisor.jev.citation_validation import (
    JevCitationValidator,
    extract_claims,
)


def test_extract_claims_preserves_citations_and_marks_deterministic_failures() -> None:
    claims = extract_claims("MFA protects accounts [S1]. Change passwords [S9]. Report it now.")
    validator = JevCitationValidator(httpx.Client(base_url="https://api.example"))

    result = validator.validate(
        "Change passwords [S9]. Report it now.",
        [
            {
                "source_id": "S1",
                "chunk_id": "chunk-1",
                "url": "https://example.com/1",
                "evidence_text": "MFA protects accounts.",
            }
        ],
    )

    assert claims[0].citation_ids == ["S1"]
    assert [claim.status for claim in result.claims] == ["invalid_citation", "uncited"]


def test_jev_verifies_semantic_claim_support_in_one_batch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert len(payload["questions"]) == 1
        assert payload["questions"]["pair_0"]["instructions"]["source"]["source_id"] == "S1"
        return httpx.Response(
            200,
            json={
                "model": "jev-test",
                "answers": {
                    "pair_0": {
                        "type": "choice",
                        "choice": "supports",
                        "confidence": 0.96,
                        "probabilities": {
                            "supports": 0.96,
                            "contradicts": 0.01,
                            "says_nothing": 0.01,
                            "uncertain": 0.02,
                        },
                    }
                },
            },
        )

    validator = JevCitationValidator(
        httpx.Client(base_url="https://api.example", transport=httpx.MockTransport(handler))
    )
    result = validator.validate(
        "MFA reduces risk from stolen passwords [S1].",
        [
            {
                "source_id": "S1",
                "chunk_id": "chunk-1",
                "url": "https://example.com/1",
                "evidence_text": "MFA helps prevent access when a password is compromised.",
            }
        ],
    )

    assert result.claims[0].status == "verified"
    assert result.summary()["groundedness"] == 1.0
