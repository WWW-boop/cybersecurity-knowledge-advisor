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
