"""End-to-end grounded answer API."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from pydantic import BaseModel, Field, StringConstraints
from qdrant_client.http.exceptions import ApiException, ResponseHandlingException

from cybersecurity_advisor.api.dependencies import AnswerServiceDependency, SettingsDependency
from cybersecurity_advisor.generation.answering import GenerationError
from cybersecurity_advisor.jev.entity_validation import JevError

router = APIRouter(prefix="/api/v1", tags=["generation"])
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ChatRequest(BaseModel):
    """Question, provider, and reproducible hybrid retrieval controls."""

    query: Query
    provider: Literal["openai", "ollama"]
    top_k: int = Field(default=5, ge=1, le=25)
    dense_k: int = Field(default=10, ge=1, le=50)
    graph_k: int = Field(default=10, ge=1, le=50)
    max_depth: int = Field(default=2, ge=1, le=3)
    language: Literal["th", "en"] | None = None
    topic: str | None = None
    score_threshold: float | None = Field(default=None, ge=-1, le=1)
    fusion_method: Literal["naive", "rrf", "weighted"] | None = None
    dynamic_k: bool = False
    jev_mode: Literal["configured", "none", "pregen", "entity_pregen", "all"] = "configured"


class Source(BaseModel):
    source_id: str
    chunk_id: str
    citation: str
    url: str
    retrievers: list[Literal["dense", "graph"]]
    score: float = Field(ge=0, le=1)
    corpus_source_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    provider: Literal["openai", "ollama"]
    model: str
    sources: list[Source]
    input_tokens: int | None
    output_tokens: int | None
    retrieval_latency_ms: float = Field(ge=0)
    jev_filter_latency_ms: float = Field(default=0, ge=0)
    jev_filter: dict[str, Any] | None = None
    generation_latency_ms: float = Field(ge=0)
    citation_validation_latency_ms: float = Field(default=0, ge=0)
    citation_validation: dict[str, Any] | None = None
    context_tokens: int = Field(default=0, ge=0)
    final_context_k: int = Field(default=0, ge=0)
    process_cpu_seconds: float = Field(default=0, ge=0)
    process_memory_mib: float | None = Field(default=None, ge=0)
    total_latency_ms: float = Field(ge=0)
    retrieval_budget: dict[str, Any] | None = None


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: AnswerServiceDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    """Retrieve trusted evidence and generate one grounded answer."""
    try:
        if request.jev_mode != "configured" and settings.app_env.casefold() == "production":
            raise HTTPException(status_code=403, detail="JEV ablation is disabled in production")
        ablation = {
            "none": (False, False, False),
            "pregen": (False, True, False),
            "entity_pregen": (True, True, False),
            "all": (True, True, True),
        }.get(request.jev_mode)
        options: dict[str, Any] = {}
        if ablation is not None:
            options = {
                "use_entity_validation": ablation[0],
                "use_pregen_filter": ablation[1],
                "use_citation_validation": ablation[2],
            }
        return service.answer(
            request.query,
            request.provider,
            top_k=request.top_k,
            dense_k=request.dense_k,
            graph_k=request.graph_k,
            max_depth=request.max_depth,
            language=request.language,
            topic=request.topic,
            score_threshold=request.score_threshold,
            method=request.fusion_method,
            dynamic_k=request.dynamic_k,
            **options,
        )
    except GenerationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except JevError as error:
        raise HTTPException(status_code=503, detail="JEV validation unavailable") from error
    except (ApiException, ResponseHandlingException) as error:
        raise HTTPException(status_code=503, detail="Vector database unavailable") from error
    except (Neo4jError, ServiceUnavailable) as error:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
