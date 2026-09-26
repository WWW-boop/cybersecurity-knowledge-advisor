"""FastAPI dependencies shared by API routers."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from qdrant_client import QdrantClient

from cybersecurity_advisor.config.settings import Settings, get_settings
from cybersecurity_advisor.retrieval.dense import DenseRetriever

SettingsDependency = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_dense_retriever() -> DenseRetriever:
    """Build the process-wide dense retriever on its first request."""
    settings = get_settings()
    api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    return DenseRetriever(
        client=QdrantClient(url=settings.qdrant_url, api_key=api_key),
        collection_name=settings.qdrant_collection,
        model_name=settings.embedding_model,
        model_revision=settings.embedding_revision,
        trust_remote_code=settings.embedding_trust_remote_code,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_length=settings.embedding_max_length,
    )


DenseRetrieverDependency = Annotated[DenseRetriever, Depends(get_dense_retriever)]
