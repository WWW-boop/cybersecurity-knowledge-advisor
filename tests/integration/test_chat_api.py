"""End-to-end answer endpoint behavior without external services."""

from typing import Any

from fastapi.testclient import TestClient

from cybersecurity_advisor.api.dependencies import get_answer_service
from cybersecurity_advisor.config.settings import Settings, get_settings


class FakeAnswerService:
    def answer(self, query: str, provider_name: str, **retrieval: Any) -> dict[str, Any]:
        assert query == "phishing and MFA"
        assert provider_name == "openai"
        assert retrieval["method"] == "rrf"
        return {
            "answer": "Use phishing-resistant MFA [S1].",
            "provider": "openai",
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
            "fusion_method": "rrf",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Use phishing-resistant MFA [S1]."
    assert response.json()["sources"][0]["chunk_id"] == "cisa-1"
    assert response.json()["total_latency_ms"] == 24.0
    assert len(response.json()["session_id"]) == 32


def test_chat_reuses_session_history_only_for_matching_id(client: TestClient) -> None:
    histories = []

    class RecordingService(FakeAnswerService):
        def answer(self, query: str, provider_name: str, **retrieval: Any) -> dict[str, Any]:
            histories.append(retrieval["history"])
            return super().answer(query, provider_name, **retrieval)

    client.app.dependency_overrides[get_answer_service] = RecordingService
    first = client.post("/api/v1/chat", json={"query": "phishing and MFA", "fusion_method": "rrf"})
    session_id = first.json()["session_id"]
    second = client.post(
        "/api/v1/chat",
        json={"query": "phishing and MFA", "fusion_method": "rrf", "session_id": session_id},
    )
    client.post("/api/v1/chat", json={"query": "phishing and MFA", "fusion_method": "rrf"})

    assert second.json()["session_id"] == session_id
    assert histories == [(), (("phishing and MFA", "Use phishing-resistant MFA [S1]."),), ()]


def test_chat_refuses_non_cyber_question_without_saving_history(client: TestClient) -> None:
    histories = []

    class PolicyService:
        def answer(self, query: str, provider_name: str, **retrieval: Any) -> dict[str, Any]:
            histories.append(retrieval["history"])
            return {
                "answer": "Sorry, I can only help with cybersecurity questions.",
                "provider": "policy",
                "model": "jev-test",
                "sources": [],
                "input_tokens": None,
                "output_tokens": None,
                "retrieval_latency_ms": 0.0,
                "generation_latency_ms": 0.0,
                "total_latency_ms": 1.0,
            }

    client.app.dependency_overrides[get_answer_service] = PolicyService
    first = client.post("/api/v1/chat", json={"query": "What is the weather?"})
    second = client.post(
        "/api/v1/chat",
        json={"query": "What is the weather?", "session_id": first.json()["session_id"]},
    )

    assert first.status_code == 200
    assert first.json()["provider"] == "policy"
    assert second.status_code == 200
    assert histories == [(), ()]


def test_chat_rejects_jev_ablation_in_production(client: TestClient) -> None:
    client.app.dependency_overrides[get_answer_service] = FakeAnswerService
    client.app.dependency_overrides[get_settings] = lambda: Settings(app_env="production")

    response = client.post(
        "/api/v1/chat",
        json={"query": "phishing and MFA", "jev_mode": "none"},
    )

    assert response.status_code == 403


def test_chat_rejects_ollama_provider(client: TestClient) -> None:
    client.app.dependency_overrides[get_answer_service] = FakeAnswerService

    response = client.post(
        "/api/v1/chat",
        json={"query": "phishing and MFA", "provider": "ollama"},
    )

    assert response.status_code == 422
