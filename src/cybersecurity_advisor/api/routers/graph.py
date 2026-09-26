"""Knowledge-graph retrieval API."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from pydantic import BaseModel, Field, StringConstraints

from cybersecurity_advisor.api.dependencies import GraphRetrieverDependency

router = APIRouter(prefix="/api/v1/graph", tags=["retrieval"])
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GraphRetrievalRequest(BaseModel):
    """Controls for bounded graph evidence retrieval."""

    query: Query
    top_k: int = Field(default=5, ge=1, le=25)
    max_depth: int = Field(default=2, ge=1, le=3)
    language: Literal["th", "en"] | None = None
    topic: str | None = None


class GraphRetrievalResult(BaseModel):
    """One provenance-preserving chunk recovered through the graph."""

    chunk_id: str
    content: str
    graph_score: float
    citation: str
    url: str
    matched_entities: list[str]
    relationships: list[str]
    entity_path: list[str]
    graph_depth: int
    metadata: dict[str, Any]


@router.post("/retrieve", response_model=list[GraphRetrievalResult])
def retrieve_graph(
    request: GraphRetrievalRequest,
    retriever: GraphRetrieverDependency,
) -> list[GraphRetrievalResult]:
    """Return graph-linked evidence chunks for explicit query entities."""
    try:
        rows = retriever.search(
            request.query,
            top_k=request.top_k,
            max_depth=request.max_depth,
            language=request.language,
            topic=request.topic,
        )
    except (Neo4jError, ServiceUnavailable) as error:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from error
    excluded = {
        "chunk_id",
        "content",
        "graph_score",
        "citation",
        "url",
        "matched_entity_ids",
        "matched_entities",
        "relationships",
        "entity_path",
        "graph_depth",
    }
    return [
        GraphRetrievalResult(
            chunk_id=row["chunk_id"],
            content=row["content"],
            graph_score=row["graph_score"],
            citation=row["citation"],
            url=row["url"],
            matched_entities=row["matched_entities"],
            relationships=row["relationships"],
            entity_path=row["entity_path"],
            graph_depth=row["graph_depth"],
            metadata={key: value for key, value in row.items() if key not in excluded},
        )
        for row in rows
    ]
