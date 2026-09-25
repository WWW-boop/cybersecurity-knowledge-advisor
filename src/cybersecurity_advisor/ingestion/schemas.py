"""Stable data contracts for future document ingestion implementations."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SourceDefinition(BaseModel):
    """A reviewed source that may later supply one or more documents."""

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
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
    topic: str
    subtopic: str | None = None
    audience: str = "general"
    published_at: date | None = None
    updated_at: date | None = None
    authority: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
