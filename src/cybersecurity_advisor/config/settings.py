"""Environment-backed application settings."""

from functools import lru_cache

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

    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_deployment: str | None = None

    ollama_url: str = "http://localhost:11434"
    ollama_model: str | None = None
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
