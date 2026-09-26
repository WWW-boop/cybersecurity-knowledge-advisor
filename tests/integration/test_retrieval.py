"""Dense retrieval API behavior without external services."""

from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import ResponseHandlingException

from cybersecurity_advisor.api.dependencies import get_dense_retriever


class FakeRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        assert query == "รับมือ phishing"
        assert kwargs == {
            "top_k": 3,
            "language": "th",
            "topic": "phishing",
            "score_threshold": 0.5,
        }
        return [
            {
                "chunk_id": "th-01-0001",
                "content": "อย่าคลิกลิงก์ที่น่าสงสัย",
                "score": 0.91,
                "citation": "คำแนะนำ, การรับมือฟิชชิง",
                "url": "https://example.com/phishing",
                "source_id": "TH-01",
                "language": "th",
                "topic": "phishing",
            }
        ]


class UnavailableRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        raise ResponseHandlingException("offline")


def test_retrieve_returns_ranked_evidence(client: TestClient) -> None:
    client.app.dependency_overrides[get_dense_retriever] = FakeRetriever

    response = client.post(
        "/api/v1/retrieve",
        json={
            "query": "  รับมือ phishing  ",
            "top_k": 3,
            "language": "th",
            "topic": "phishing",
            "score_threshold": 0.5,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "chunk_id": "th-01-0001",
            "content": "อย่าคลิกลิงก์ที่น่าสงสัย",
            "dense_score": 0.91,
            "citation": "คำแนะนำ, การรับมือฟิชชิง",
            "url": "https://example.com/phishing",
            "metadata": {
                "source_id": "TH-01",
                "language": "th",
                "topic": "phishing",
            },
        }
    ]


def test_retrieve_rejects_blank_query(client: TestClient) -> None:
    client.app.dependency_overrides[get_dense_retriever] = FakeRetriever
    response = client.post("/api/v1/retrieve", json={"query": "   "})

    assert response.status_code == 422


def test_retrieve_reports_unavailable_vector_database(client: TestClient) -> None:
    client.app.dependency_overrides[get_dense_retriever] = UnavailableRetriever

    response = client.post("/api/v1/retrieve", json={"query": "phishing"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Vector database unavailable"}
