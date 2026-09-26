"""Dense indexing and retrieval backed by Qdrant."""

import json
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer


class DenseRetriever:
    """Embed corpus chunks and retrieve their nearest Qdrant points."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "cybersecurity_chunks_gte",
        model_name: str = "Alibaba-NLP/gte-multilingual-base",
        model_revision: str | None = "9bbca17d9273fd0d03d5725c7a4b0f6b45142062",
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
        )
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
