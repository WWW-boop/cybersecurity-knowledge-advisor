"""Hybrid retrieval API behavior without external retrieval services."""

from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import ResponseHandlingException

from cybersecurity_advisor.api.dependencies import get_hybrid_retriever


class FakeHybridRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        assert query == "รับมือ phishing"
        assert kwargs == {
            "top_k": 3,
            "dense_k": 8,
            "graph_k": 6,
            "max_depth": 2,
            "language": "th",
            "topic": "phishing",
            "score_threshold": 0.4,
            "method": "weighted",
            "dense_weight": 0.7,
            "graph_weight": 0.3,
            "rrf_k": 40,
        }
        return [
            {
                "chunk_id": "th-01-0001",
                "document_id": "th-01",
                "content": "อย่าคลิกลิงก์ที่น่าสงสัย",
                "hybrid_score": 0.88,
                "dense_score": 0.92,
                "graph_score": 0.8,
                "dense_rank": 1,
                "graph_rank": 2,
                "retrievers": ["dense", "graph"],
                "fusion_method": "weighted",
                "citation": "คำแนะนำ, การรับมือฟิชชิง",
                "url": "https://example.com/phishing",
                "duplicate_chunk_ids": [],
                "language": "th",
                "relationships": ["MITIGATED_BY"],
            }
        ]


class UnavailableHybridRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        raise ResponseHandlingException("offline")


class InvalidWeightsHybridRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        raise ValueError("at least one fusion weight must be positive")


def test_hybrid_retrieve_returns_normalized_candidate(client: TestClient) -> None:
    client.app.dependency_overrides[get_hybrid_retriever] = FakeHybridRetriever

    response = client.post(
        "/api/v1/hybrid/retrieve",
        json={
            "query": "  รับมือ phishing  ",
            "top_k": 3,
            "dense_k": 8,
            "graph_k": 6,
            "max_depth": 2,
            "language": "th",
            "topic": "phishing",
            "score_threshold": 0.4,
            "fusion_method": "weighted",
            "dense_weight": 0.7,
            "graph_weight": 0.3,
            "rrf_k": 40,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "chunk_id": "th-01-0001",
            "content": "อย่าคลิกลิงก์ที่น่าสงสัย",
            "hybrid_score": 0.88,
            "dense_score": 0.92,
            "graph_score": 0.8,
            "dense_rank": 1,
            "graph_rank": 2,
            "retrievers": ["dense", "graph"],
            "fusion_method": "weighted",
            "citation": "คำแนะนำ, การรับมือฟิชชิง",
            "url": "https://example.com/phishing",
            "duplicate_chunk_ids": [],
            "metadata": {
                "document_id": "th-01",
                "language": "th",
                "relationships": ["MITIGATED_BY"],
            },
        }
    ]


def test_hybrid_retrieve_reports_vector_database_failure(client: TestClient) -> None:
    client.app.dependency_overrides[get_hybrid_retriever] = UnavailableHybridRetriever

    response = client.post("/api/v1/hybrid/retrieve", json={"query": "phishing"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Vector database unavailable"}


def test_hybrid_retrieve_rejects_zero_effective_weights(client: TestClient) -> None:
    client.app.dependency_overrides[get_hybrid_retriever] = InvalidWeightsHybridRetriever

    response = client.post(
        "/api/v1/hybrid/retrieve",
        json={"query": "phishing", "dense_weight": 0, "graph_weight": 0},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "at least one fusion weight must be positive"}
