"""Dense retrieval API."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from qdrant_client.http.exceptions import ApiException, ResponseHandlingException

from cybersecurity_advisor.api.dependencies import DenseRetrieverDependency

router = APIRouter(prefix="/api/v1", tags=["retrieval"])
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RetrievalRequest(BaseModel):
    """Dense retrieval controls exposed to API clients."""

    query: Query
    top_k: int = Field(default=5, ge=1, le=50)
    language: Literal["th", "en"] | None = None
    topic: str | None = None
    score_threshold: float | None = Field(default=None, ge=-1, le=1)


class RetrievalResult(BaseModel):
    """Evidence returned from one matching corpus chunk."""

    chunk_id: str
    content: str
    dense_score: float
    citation: str
    url: str
    metadata: dict[str, Any]


@router.post("/retrieve", response_model=list[RetrievalResult])
def retrieve(
    request: RetrievalRequest,
    retriever: DenseRetrieverDependency,
) -> list[RetrievalResult]:
    """Return the nearest evidence chunks for a query."""
    try:
        rows = retriever.search(
            request.query,
            top_k=request.top_k,
            language=request.language,
            topic=request.topic,
            score_threshold=request.score_threshold,
        )
    except (ApiException, ResponseHandlingException) as error:
        raise HTTPException(status_code=503, detail="Vector database unavailable") from error
    excluded = {"chunk_id", "content", "score", "citation", "url"}
    return [
        RetrievalResult(
            chunk_id=row["chunk_id"],
            content=row["content"],
            dense_score=row["score"],
            citation=row["citation"],
            url=row["url"],
            metadata={key: value for key, value in row.items() if key not in excluded},
        )
        for row in rows
    ]
