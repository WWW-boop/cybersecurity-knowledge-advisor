"""Dense retrieval behavior without downloading a production embedding model."""

import numpy as np
from qdrant_client import QdrantClient

from cybersecurity_advisor.retrieval.dense import DenseRetriever


class FakeModel:
    max_seq_length = 0

    @staticmethod
    def get_embedding_dimension() -> int:
        return 2

    @staticmethod
    def encode(texts, **kwargs):
        def vector(text: str) -> list[float]:
            return [1.0, 0.0] if "phishing" in text.casefold() else [0.0, 1.0]

        if isinstance(texts, str):
            return np.array(vector(texts))
        return np.array([vector(text) for text in texts])


def test_index_then_query_returns_relevant_chunk(tmp_path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(
        """{"chunk_id":"a-0001","title":"Phishing","section":"Signs","content":"phishing signs","language":"en","topic":"phishing","citation":"A","url":"https://example.com/a"}
{"chunk_id":"b-0001","title":"Backups","section":"Copies","content":"offline backup","language":"en","topic":"backup","citation":"B","url":"https://example.com/b"}
""",
        encoding="utf-8",
    )
    retriever = DenseRetriever(QdrantClient(":memory:"), model=FakeModel())

    assert retriever.index(chunks) == 2
    results = retriever.search("How do I spot phishing?", top_k=1)

    assert results[0]["chunk_id"] == "a-0001"
    assert results[0]["score"] == 1.0
