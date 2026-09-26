"""Hybrid fusion, normalization, deduplication, and diversity tests."""

import pytest

from cybersecurity_advisor.retrieval.hybrid import HybridRetriever


def dense_row(
    chunk_id: str,
    document_id: str,
    score: float,
    *,
    content: str | None = None,
    url: str | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "content": content or f"Evidence {chunk_id}",
        "score": score,
        "citation": f"Citation {chunk_id}",
        "url": url or f"https://example.com/{document_id}",
        "language": "en",
    }


def graph_row(
    chunk_id: str,
    document_id: str,
    score: float,
    *,
    content: str | None = None,
    url: str | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "content": content or f"Evidence {chunk_id}",
        "graph_score": score,
        "citation": f"Citation {chunk_id}",
        "url": url or f"https://example.com/{document_id}",
        "matched_entities": ["Phishing"],
        "relationships": ["MITIGATED_BY"],
    }


class FakeDenseRetriever:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.call = None

    def search(self, query: str, **kwargs) -> list[dict]:
        self.call = (query, kwargs)
        return self.rows


class FakeGraphRetriever:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.call = None

    def search(self, query: str, **kwargs) -> list[dict]:
        self.call = (query, kwargs)
        return self.rows


def test_search_runs_both_retrievers_and_rrf_rewards_overlap() -> None:
    dense = FakeDenseRetriever(
        [dense_row("shared", "doc-shared", 0.9), dense_row("dense-only", "doc-d", 0.8)]
    )
    graph = FakeGraphRetriever(
        [graph_row("graph-only", "doc-g", 0.9), graph_row("shared", "doc-shared", 0.8)]
    )
    retriever = HybridRetriever(dense, graph)

    rows = retriever.search(
        "phishing",
        top_k=3,
        dense_k=7,
        graph_k=6,
        max_depth=3,
        language="en",
        topic="phishing",
        score_threshold=0.4,
    )

    assert rows[0]["chunk_id"] == "shared"
    assert rows[0]["retrievers"] == ["dense", "graph"]
    assert rows[0]["dense_rank"] == 1
    assert rows[0]["graph_rank"] == 2
    assert 0 <= rows[0]["hybrid_score"] <= 1
    assert dense.call == (
        "phishing",
        {
            "top_k": 7,
            "language": "en",
            "topic": "phishing",
            "score_threshold": 0.4,
        },
    )
    assert graph.call == (
        "phishing",
        {
            "top_k": 6,
            "max_depth": 3,
            "language": "en",
            "topic": "phishing",
        },
    )


def test_weighted_fusion_normalizes_dense_and_graph_scores() -> None:
    retriever = HybridRetriever(FakeDenseRetriever([]), FakeGraphRetriever([]))

    rows = retriever.fuse(
        [dense_row("shared", "doc-a", 0.8)],
        [graph_row("shared", "doc-a", 0.5)],
        method="weighted",
        dense_weight=0.6,
        graph_weight=0.4,
    )

    assert rows[0]["hybrid_score"] == pytest.approx(0.74)
    assert rows[0]["dense_score"] == 0.8
    assert rows[0]["graph_score"] == 0.5
    assert "score" not in rows[0]


def test_deduplicates_identical_source_content_and_merges_provenance() -> None:
    retriever = HybridRetriever(FakeDenseRetriever([]), FakeGraphRetriever([]))
    url = "https://example.com/advice"

    rows = retriever.fuse(
        [dense_row("dense-id", "doc-a", 0.9, content="Use MFA now", url=url)],
        [graph_row("graph-id", "doc-a", 0.8, content="  Use  MFA now ", url=url)],
    )

    assert len(rows) == 1
    assert rows[0]["chunk_id"] == "dense-id"
    assert rows[0]["duplicate_chunk_ids"] == ["graph-id"]
    assert rows[0]["retrievers"] == ["dense", "graph"]
    assert rows[0]["relationships"] == ["MITIGATED_BY"]


def test_limits_results_per_document_after_ranking() -> None:
    retriever = HybridRetriever(
        FakeDenseRetriever([]),
        FakeGraphRetriever([]),
        max_per_document=2,
    )
    rows = retriever.fuse(
        [
            dense_row("a-1", "doc-a", 0.99),
            dense_row("a-2", "doc-a", 0.98),
            dense_row("a-3", "doc-a", 0.97),
            dense_row("b-1", "doc-b", 0.80),
        ],
        [],
        top_k=4,
        method="weighted",
    )

    assert [row["chunk_id"] for row in rows] == ["a-1", "a-2", "b-1"]


def test_naive_baseline_is_normalized_and_deterministic() -> None:
    retriever = HybridRetriever(FakeDenseRetriever([]), FakeGraphRetriever([]))

    rows = retriever.fuse(
        [dense_row("dense", "doc-a", 0.5)],
        [graph_row("graph", "doc-b", 0.9)],
        method="naive",
    )

    assert [row["chunk_id"] for row in rows] == ["dense", "graph"]
    assert [row["hybrid_score"] for row in rows] == [1.0, 0.5]


def test_rejects_invalid_fusion_weights() -> None:
    with pytest.raises(ValueError, match="at least one"):
        HybridRetriever(
            FakeDenseRetriever([]),
            FakeGraphRetriever([]),
            dense_weight=0,
            graph_weight=0,
        )
