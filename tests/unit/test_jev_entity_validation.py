"""Typed JEV entity-validation client tests."""

import json

import httpx
import pytest

from cybersecurity_advisor.graph.retrieval import EntityMatch
from cybersecurity_advisor.jev.entity_validation import (
    JevEntityValidator,
    JevResponseError,
    JevUnavailableError,
)


def match() -> EntityMatch:
    return EntityMatch(
        entity_id="control:mfa",
        name="Multi-Factor Authentication",
        entity_type="AuthenticationMethod",
        mention="MFA",
    )


def test_jev_returns_typed_entity_decision() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-key"
        assert payload["model"] == "jev-latest"
        assert payload["state"] == {"query": "MFA protects my account"}
        question = payload["questions"]["entity_0"]
        assert question["type"] == "choice"
        assert set(question["criteria"]) == {"same", "different", "uncertain"}
        assert question["instructions"]["candidate"]["entity_id"] == "control:mfa"
        return httpx.Response(
            200,
            json={
                "model": "jev-2026-09-15",
                "answers": {
                    "entity_0": {
                        "type": "choice",
                        "choice": "same",
                        "confidence": 0.96,
                        "probabilities": {
                            "same": 0.96,
                            "different": 0.02,
                            "uncertain": 0.02,
                        },
                    }
                },
                "usage": {"input_tokens": 80, "output_tokens": 4},
            },
        )

    client = httpx.Client(
        base_url="https://api.typesafe.ai",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(handler),
    )

    decisions = JevEntityValidator(client).validate("MFA protects my account", [match()])

    assert decisions[0].decision == "same"
    assert decisions[0].confidence == 0.96
    assert decisions[0].probabilities["uncertain"] == 0.02
    assert decisions[0].model == "jev-2026-09-15"


def test_jev_rejects_incomplete_typed_response() -> None:
    client = httpx.Client(
        base_url="https://api.typesafe.ai",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"model": "jev-latest", "answers": {"entity_0": {"type": "choice"}}},
            )
        ),
    )

    with pytest.raises(JevResponseError, match="incomplete"):
        JevEntityValidator(client).validate("MFA", [match()])


def test_jev_reports_service_failure_without_leaking_response() -> None:
    client = httpx.Client(
        base_url="https://api.typesafe.ai",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"detail": "secret diagnostic"})
        ),
    )

    with pytest.raises(JevUnavailableError, match="status 401") as raised:
        JevEntityValidator(client).validate("MFA", [match()])

    assert "secret diagnostic" not in str(raised.value)
