"""FastAPI dependencies shared by API routers."""

from functools import lru_cache
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException
from neo4j import GraphDatabase

from cybersecurity_advisor.config.settings import Settings, get_settings
from cybersecurity_advisor.graph.retrieval import (
    GraphRetriever,
    Neo4jGraphRepository,
)
from cybersecurity_advisor.jev.entity_validation import JevEntityValidator
from cybersecurity_advisor.retrieval.hybrid import HybridRetriever

SettingsDependency = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_dense_retriever() -> Any:
    """Build the process-wide dense retriever on its first request."""
    from qdrant_client import QdrantClient

    from cybersecurity_advisor.retrieval.dense import DenseRetriever

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


DenseRetrieverDependency = Annotated[Any, Depends(get_dense_retriever)]


@lru_cache
def get_graph_retriever() -> GraphRetriever:
    """Build the process-wide Neo4j graph retriever on its first request."""
    settings = get_settings()
    password = (
        settings.neo4j_password.get_secret_value() if settings.neo4j_password is not None else None
    )
    if password is None:
        raise HTTPException(status_code=503, detail="Graph database credentials not configured")
    validator = None
    if settings.jev_entity_validation_enabled:
        if settings.jev_api_key is None:
            raise HTTPException(
                status_code=503,
                detail="JEV entity validation credentials not configured",
            )
        api_key = settings.jev_api_key.get_secret_value()
        validator = JevEntityValidator(
            httpx.Client(
                base_url=settings.jev_api_url.rstrip("/"),
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=settings.jev_timeout_seconds,
            ),
            model=settings.jev_model,
        )
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, password) if password is not None else None,
    )
    return GraphRetriever(
        Neo4jGraphRepository(driver, database=settings.neo4j_database),
        max_per_document=settings.graph_max_per_document,
        entity_validator=validator,
        entity_min_confidence=settings.jev_entity_min_confidence,
    )


GraphRetrieverDependency = Annotated[GraphRetriever, Depends(get_graph_retriever)]


@lru_cache
def get_hybrid_retriever() -> HybridRetriever:
    """Compose the cached Dense and Graph retrievers with configured fusion."""
    settings = get_settings()
    return HybridRetriever(
        get_dense_retriever(),
        get_graph_retriever(),
        dense_weight=settings.hybrid_dense_weight,
        graph_weight=settings.hybrid_graph_weight,
        rrf_k=settings.hybrid_rrf_k,
        max_per_document=settings.hybrid_max_per_document,
        default_method=settings.hybrid_fusion_method,
    )


HybridRetrieverDependency = Annotated[HybridRetriever, Depends(get_hybrid_retriever)]


def close_graph_retriever() -> None:
    """Release a cached Neo4j driver without creating one during shutdown."""
    get_hybrid_retriever.cache_clear()
    if get_graph_retriever.cache_info().currsize:
        get_graph_retriever().close()
        get_graph_retriever.cache_clear()
