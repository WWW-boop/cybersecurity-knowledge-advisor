"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and local `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "Cybersecurity Knowledge Advisor"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "cybersecurity_chunks_gte"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr | None = None
    neo4j_database: str = "neo4j"
    graph_max_per_document: int = Field(default=2, ge=1, le=10)

    hybrid_fusion_method: Literal["naive", "rrf", "weighted"] = "rrf"
    hybrid_dense_weight: float = Field(default=0.6, ge=0)
    hybrid_graph_weight: float = Field(default=0.4, ge=0)
    hybrid_rrf_k: int = Field(default=60, ge=1)
    hybrid_max_per_document: int = Field(default=2, ge=1, le=10)

    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/cyber_rag"
    redis_url: str = "redis://localhost:6379/0"
    opensearch_url: str = "http://localhost:9200"

    jev_api_url: str = "https://api.typesafe.ai"
    jev_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("JEV_API_KEY", "TYPE_SAFE"),
    )
    jev_model: str = "jev-latest"
    jev_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    jev_entity_validation_enabled: bool = True
    jev_entity_min_confidence: float = Field(default=0.7, ge=0, le=1)
    jev_pregen_filter_enabled: bool = True
    jev_candidate_max: int = Field(default=12, ge=1, le=25)
    jev_relevance_threshold: float = Field(default=0.6, ge=0, le=1)
    jev_evidence_threshold: float = Field(default=0.6, ge=0, le=1)
    jev_contradiction_threshold: float = Field(default=0.5, ge=0, le=1)
    jev_injection_threshold: float = Field(default=0.5, ge=0, le=1)
    jev_citation_validation_enabled: bool = True
    jev_citation_min_confidence: float = Field(default=0.7, ge=0, le=1)

    psu_ai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("PSU_AI_API_KEY", "OPENAI_API_KEY"),
    )
    psu_ai_model: str | None = Field(
        default="qwen/qwen3.6-flash",
        validation_alias=AliasChoices("PSU_AI_MODEL", "OPENAI_MODEL"),
    )
    psu_ai_base_url: str = Field(
        default="https://ai.psu.blue/v1",
        validation_alias=AliasChoices("PSU_AI_BASE_URL", "OPENAI_BASE_URL"),
    )
    psu_ai_max_output_tokens: int = Field(default=3000, ge=1, le=8192)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_deployment: str | None = None

    ollama_url: str = "http://localhost:11434"
    ollama_model: str | None = None
    generation_timeout_seconds: float = Field(default=120, gt=0, le=600)
    generation_max_output_tokens: int = Field(default=500, ge=1, le=8192)
    generation_max_context_chars: int = Field(default=12000, ge=1000, le=100000)
    generation_temperature: float = Field(default=0.1, ge=0, le=2)
    embedding_model: str = "Alibaba-NLP/gte-multilingual-base"
    embedding_revision: str = "9bbca17d9273fd0d03d5725c7a4b0f6b45142062"
    embedding_trust_remote_code: bool = True
    embedding_device: str | None = None
    embedding_batch_size: int = Field(default=8, ge=1)
    embedding_max_length: int = Field(default=1024, ge=128)


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object per process."""
    return Settings()
