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
    qdrant_collection: str = "cybersecurity_chunks"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr | None = None

    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/cyber_rag"
    redis_url: str = "redis://localhost:6379/0"
    opensearch_url: str = "http://localhost:9200"

    jev_api_url: str = "https://api.typesafe.ai"
    jev_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("JEV_API_KEY", "TYPE_SAFE"),
    )

    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_deployment: str | None = None

    ollama_url: str = "http://localhost:11434"
    ollama_model: str | None = None
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str | None = None
    embedding_batch_size: int = Field(default=8, ge=1)
    embedding_max_length: int = Field(default=1024, ge=128)


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object per process."""
    return Settings()
