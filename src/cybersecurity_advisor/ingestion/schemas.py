"""Stable data contracts for future document ingestion implementations."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceDefinition(BaseModel):
    """A reviewed source that may later supply one or more documents."""

    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str
    organization: str
    base_url: HttpUrl
    languages: list[Literal["th", "en"]]
    source_type: Literal["government", "standard", "academic", "other"]
    enabled: bool = False
    license_notes: str | None = None
    review_notes: str | None = None


class SourceManifest(BaseModel):
    """Versioned team decision about which sources may enter ingestion."""

    manifest_version: str
    reviewed_at: date | None = None
    reviewed_by: list[str] = Field(default_factory=list)
    sources: list[SourceDefinition] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """Metadata required before a normalized document enters retrieval pipelines."""

    document_id: str
    title: str
    source_id: str
    source_url: HttpUrl
    language: Literal["th", "en"]
    organization: str = Field(min_length=1)
    source_type: Literal["government", "standard", "academic", "other"]
    topic: str = "general_cybersecurity"
    subtopic: str | None = None
    audience: str = "general"
    published_at: date | None = None
    updated_at: date | None = None
    authority: float | None = Field(default=None, ge=0, le=1)
    freshness: float | None = Field(default=None, ge=0, le=1)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class NormalizedDocument(DocumentMetadata):
    """Validated input shared by normalization and chunking."""

    model_config = ConfigDict(extra="allow")

    content: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    rights_status: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
