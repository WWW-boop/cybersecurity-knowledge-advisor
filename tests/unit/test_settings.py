"""Settings behavior tests."""

from pydantic import SecretStr

from cybersecurity_advisor.config.settings import Settings


def test_settings_accept_jev_credentials_without_exposing_value(monkeypatch) -> None:
    monkeypatch.setenv("JEV_API_KEY", "test-secret")

    settings = Settings(_env_file=None)

    assert isinstance(settings.jev_api_key, SecretStr)
    assert str(settings.jev_api_key) == "**********"
    assert settings.jev_api_key.get_secret_value() == "test-secret"


def test_settings_accept_type_safe_as_jev_api_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.setenv("TYPE_SAFE", "legacy-test-secret")

    settings = Settings(_env_file=None)

    assert settings.jev_api_url == "https://api.typesafe.ai"
    assert settings.jev_api_key is not None
    assert settings.jev_api_key.get_secret_value() == "legacy-test-secret"


def test_gte_is_the_default_embedding_model() -> None:
    settings = Settings(_env_file=None)

    assert settings.embedding_model == "Alibaba-NLP/gte-multilingual-base"
    assert settings.embedding_trust_remote_code is True
    assert settings.qdrant_collection == "cybersecurity_chunks_gte"


def test_rrf_is_the_default_hybrid_fusion_policy() -> None:
    settings = Settings(_env_file=None)

    assert settings.hybrid_fusion_method == "rrf"
    assert settings.hybrid_dense_weight == 0.6
    assert settings.hybrid_graph_weight == 0.4
    assert settings.hybrid_rrf_k == 60
    assert settings.hybrid_max_per_document == 2
