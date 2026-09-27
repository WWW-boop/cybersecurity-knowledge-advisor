"""End-to-end answer endpoint behavior without external services."""

from typing import Any

from fastapi.testclient import TestClient

from cybersecurity_advisor.api.dependencies import get_answer_service
from cybersecurity_advisor.config.settings import Settings, get_settings


class FakeAnswerService:
    def answer(self, query: str, provider_name: str, **retrieval: Any) -> dict[str, Any]:
        assert query == "phishing and MFA"
        assert provider_name == "ollama"
        assert retrieval["method"] == "rrf"
        return {
            "answer": "Use phishing-resistant MFA [S1].",
            "provider": "ollama",
            "model": "qwen-test",
            "sources": [
                {
                    "source_id": "S1",
                    "chunk_id": "cisa-1",
                    "citation": "CISA, Phishing Guidance",
                    "url": "https://example.com/cisa",
                    "retrievers": ["dense", "graph"],
                    "score": 0.9,
                }
            ],
            "input_tokens": 80,
            "output_tokens": 12,
            "retrieval_latency_ms": 4.0,
            "generation_latency_ms": 20.0,
            "total_latency_ms": 24.0,
        }


def test_chat_returns_grounded_answer_and_sources(client: TestClient) -> None:
    client.app.dependency_overrides[get_answer_service] = FakeAnswerService

    response = client.post(
        "/api/v1/chat",
        json={
            "query": "phishing and MFA",
            "provider": "ollama",
            "fusion_method": "rrf",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Use phishing-resistant MFA [S1]."
    assert response.json()["sources"][0]["chunk_id"] == "cisa-1"
    assert response.json()["total_latency_ms"] == 24.0


def test_chat_rejects_jev_ablation_in_production(client: TestClient) -> None:
    client.app.dependency_overrides[get_answer_service] = FakeAnswerService
    client.app.dependency_overrides[get_settings] = lambda: Settings(app_env="production")

    response = client.post(
        "/api/v1/chat",
        json={"query": "phishing and MFA", "provider": "ollama", "jev_mode": "none"},
    )

    assert response.status_code == 403
