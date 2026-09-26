"""Graph retrieval API behavior without a live Neo4j service."""

from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from cybersecurity_advisor.api.dependencies import get_graph_retriever


class FakeGraphRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        assert query == "phishing และ MFA"
        assert kwargs == {
            "top_k": 3,
            "max_depth": 2,
            "language": "th",
            "topic": "phishing",
        }
        return [
            {
                "chunk_id": "th-01-0001",
                "document_id": "th-01",
                "content": "เปิด MFA และรายงานข้อความฟิชชิง",
                "graph_score": 0.8,
                "citation": "ThaiCERT, การรับมือฟิชชิง",
                "url": "https://example.com/phishing",
                "matched_entity_ids": ["threat:phishing", "control:mfa"],
                "matched_entities": ["Multi-Factor Authentication", "Phishing"],
                "relationships": ["MITIGATED_BY"],
                "entity_path": ["threat:phishing", "control:mfa"],
                "graph_depth": 1,
                "language": "th",
                "topic": "phishing",
            }
        ]


class UnavailableGraphRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        raise ServiceUnavailable("offline")


class EmptyGraphRetriever:
    def search(self, query: str, **kwargs) -> list[dict]:
        return []


def test_graph_retrieve_returns_paths_and_evidence(client: TestClient) -> None:
    client.app.dependency_overrides[get_graph_retriever] = FakeGraphRetriever

    response = client.post(
        "/api/v1/graph/retrieve",
        json={
            "query": "  phishing และ MFA  ",
            "top_k": 3,
            "max_depth": 2,
            "language": "th",
            "topic": "phishing",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["chunk_id"] == "th-01-0001"
    assert body[0]["graph_score"] == 0.8
    assert body[0]["relationships"] == ["MITIGATED_BY"]
    assert body[0]["metadata"]["language"] == "th"
    assert "matched_entity_ids" not in body[0]["metadata"]


def test_graph_retrieve_returns_empty_for_unknown_entity(client: TestClient) -> None:
    client.app.dependency_overrides[get_graph_retriever] = EmptyGraphRetriever
    response = client.post("/api/v1/graph/retrieve", json={"query": "unknown concept"})

    assert response.status_code == 200


def test_graph_retrieve_reports_unavailable_database(client: TestClient) -> None:
    client.app.dependency_overrides[get_graph_retriever] = UnavailableGraphRetriever

    response = client.post("/api/v1/graph/retrieve", json={"query": "phishing"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Graph database unavailable"}
