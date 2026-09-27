"""Dense retrieval behavior without downloading a production embedding model."""

import numpy as np
import torch
from qdrant_client import QdrantClient

from cybersecurity_advisor.retrieval.dense import (
    DenseRetriever,
    apply_transformers_v5_compatibility,
)


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


def test_transformers_v5_compatibility_restores_gte_model() -> None:
    embeddings = torch.nn.Module()
    embeddings.register_buffer("position_ids", torch.tensor([0, 99, 0]), persistent=False)
    auto_model = type("AutoModel", (), {"embeddings": embeddings, "dtype": torch.float32})()
    first_module = type("FirstModule", (), {"auto_model": auto_model})()
    model = type("Model", (), {"_first_module": lambda self: first_module})()

    apply_transformers_v5_compatibility(model)

    assert torch.equal(embeddings.position_ids, torch.arange(3))
    mask = auto_model.get_extended_attention_mask(torch.tensor([[1, 0]]), (1, 2))
    assert mask.shape == (1, 1, 1, 2)
    assert mask[0, 0, 0, 0] == 0
    assert mask[0, 0, 0, 1] == torch.finfo(torch.float32).min


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
