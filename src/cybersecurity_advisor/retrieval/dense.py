"""Dense indexing and retrieval backed by Qdrant."""

import json
import uuid
from pathlib import Path
from types import MethodType
from typing import Any

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer


def apply_transformers_v5_compatibility(model: Any) -> None:
    """Apply GTE compatibility fixes removed from the Transformers v5 base model."""
    first_module = getattr(model, "_first_module", None)
    if not callable(first_module):
        return
    auto_model = getattr(first_module(), "auto_model", None)
    embeddings = getattr(auto_model, "embeddings", None)
    position_ids = getattr(embeddings, "position_ids", None)
    if position_ids is None or position_ids.ndim != 1 or auto_model is None:
        return

    import torch

    expected = torch.arange(
        position_ids.numel(), device=position_ids.device, dtype=position_ids.dtype
    )
    if not torch.equal(position_ids, expected):
        embeddings.register_buffer("position_ids", expected, persistent=True)

    if not hasattr(auto_model, "get_extended_attention_mask"):

        def get_extended_attention_mask(
            owner: Any, attention_mask: Any, input_shape: tuple[int, ...]
        ) -> Any:
            if attention_mask.ndim == 3:
                extended = attention_mask[:, None, :, :]
            elif attention_mask.ndim == 2:
                extended = attention_mask[:, None, None, :]
            else:
                raise ValueError(
                    f"Wrong attention_mask shape {tuple(attention_mask.shape)} "
                    f"for input shape {input_shape}"
                )
            dtype = getattr(owner, "dtype", torch.float32)
            extended = extended.to(dtype=dtype)
            return (1.0 - extended) * torch.finfo(dtype).min

        auto_model.get_extended_attention_mask = MethodType(get_extended_attention_mask, auto_model)


class DenseRetriever:
    """Embed corpus chunks and retrieve their nearest Qdrant points."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "cybersecurity_chunks_gte",
        model_name: str = "Alibaba-NLP/gte-multilingual-base",
        model_revision: str | None = "9bbca17d9273fd0d03d5725c7a4b0f6b45142062",
        model_code_revision: str | None = "40ced75c3017eb27626c9d4ea981bde21a2662f4",
        trust_remote_code: bool = True,
        device: str | None = None,
        batch_size: int = 8,
        max_length: int = 1024,
        model: Any | None = None,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.model = model or SentenceTransformer(
            model_name,
            device=device,
            revision=model_revision,
            trust_remote_code=trust_remote_code,
            model_kwargs={"code_revision": model_code_revision},
            config_kwargs={"code_revision": model_code_revision},
        )
        apply_transformers_v5_compatibility(self.model)
        self.model.max_seq_length = min(self.model.max_seq_length, max_length)

    @property
    def vector_size(self) -> int:
        size = self.model.get_embedding_dimension()
        if size is None:
            raise ValueError("Embedding model did not report its vector size")
        return int(size)

    @staticmethod
    def _embedding_text(chunk: dict[str, Any]) -> str:
        return f"{chunk['title']}\n{chunk['section']}\n{chunk['content']}"

    def index(self, chunks_path: Path, recreate: bool = False) -> int:
        chunks = [
            json.loads(line)
            for line in chunks_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if not chunks:
            raise ValueError(f"No chunks found in {chunks_path}")
        if recreate and self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start : start + self.batch_size]
            vectors = self.model.encode(
                [self._embedding_text(chunk) for chunk in batch],
                batch_size=self.batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            points = [
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, str(chunk["chunk_id"]))),
                    vector=vector.tolist(),
                    payload=chunk,
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        language: str | None = None,
        topic: str | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("Query must not be empty")
        conditions = []
        if language:
            conditions.append(
                models.FieldCondition(key="language", match=models.MatchValue(value=language))
            )
        if topic:
            conditions.append(
                models.FieldCondition(key="topic", match=models.MatchValue(value=topic))
            )
        vector = self.model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        points = self.client.query_points(
            collection_name=self.collection_name,
            query=vector.tolist(),
            query_filter=models.Filter(must=conditions) if conditions else None,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        ).points
        return [{"score": point.score, **(point.payload or {})} for point in points]
