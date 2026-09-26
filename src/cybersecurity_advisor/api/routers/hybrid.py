"""Hybrid Dense + Graph retrieval API."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from pydantic import BaseModel, Field, StringConstraints
from qdrant_client.http.exceptions import ApiException, ResponseHandlingException

from cybersecurity_advisor.api.dependencies import HybridRetrieverDependency
from cybersecurity_advisor.jev.entity_validation import JevError

router = APIRouter(prefix="/api/v1/hybrid", tags=["retrieval"])
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class HybridRetrievalRequest(BaseModel):
    """Candidate budgets and fusion controls for hybrid retrieval."""

    query: Query
    top_k: int = Field(default=5, ge=1, le=25)
    dense_k: int = Field(default=10, ge=1, le=50)
    graph_k: int = Field(default=10, ge=1, le=50)
    max_depth: int = Field(default=2, ge=1, le=3)
    language: Literal["th", "en"] | None = None
    topic: str | None = None
    score_threshold: float | None = Field(default=None, ge=-1, le=1)
    fusion_method: Literal["naive", "rrf", "weighted"] | None = None
    dense_weight: float | None = Field(default=None, ge=0)
    graph_weight: float | None = Field(default=None, ge=0)
    rrf_k: int | None = Field(default=None, ge=1, le=1000)


class HybridRetrievalResult(BaseModel):
    """One normalized candidate with both retrieval signals and provenance."""

    chunk_id: str
    content: str
    hybrid_score: float = Field(ge=0, le=1)
    dense_score: float | None
    graph_score: float | None
    dense_rank: int | None
    graph_rank: int | None
    retrievers: list[Literal["dense", "graph"]]
    fusion_method: Literal["naive", "rrf", "weighted"]
    citation: str
    url: str
    duplicate_chunk_ids: list[str]
    metadata: dict[str, Any]


@router.post("/retrieve", response_model=list[HybridRetrievalResult])
def retrieve_hybrid(
    request: HybridRetrievalRequest,
    retriever: HybridRetrieverDependency,
) -> list[HybridRetrievalResult]:
    """Return normalized, deduplicated, and diverse Dense + Graph evidence."""
    try:
        rows = retriever.search(
            request.query,
            top_k=request.top_k,
            dense_k=request.dense_k,
            graph_k=request.graph_k,
            max_depth=request.max_depth,
            language=request.language,
            topic=request.topic,
            score_threshold=request.score_threshold,
            method=request.fusion_method,
            dense_weight=request.dense_weight,
            graph_weight=request.graph_weight,
            rrf_k=request.rrf_k,
        )
    except JevError as error:
        raise HTTPException(status_code=503, detail="JEV entity validation unavailable") from error
    except (ApiException, ResponseHandlingException) as error:
        raise HTTPException(status_code=503, detail="Vector database unavailable") from error
    except (Neo4jError, ServiceUnavailable) as error:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    excluded = {
        "chunk_id",
        "content",
        "hybrid_score",
        "dense_score",
        "graph_score",
        "dense_rank",
        "graph_rank",
        "retrievers",
        "fusion_method",
        "citation",
        "url",
        "duplicate_chunk_ids",
    }
    return [
        HybridRetrievalResult(
            chunk_id=row["chunk_id"],
            content=row["content"],
            hybrid_score=row["hybrid_score"],
            dense_score=row["dense_score"],
            graph_score=row["graph_score"],
            dense_rank=row["dense_rank"],
            graph_rank=row["graph_rank"],
            retrievers=row["retrievers"],
            fusion_method=row["fusion_method"],
            citation=row["citation"],
            url=row["url"],
            duplicate_chunk_ids=row["duplicate_chunk_ids"],
            metadata={key: value for key, value in row.items() if key not in excluded},
        )
        for row in rows
    ]
