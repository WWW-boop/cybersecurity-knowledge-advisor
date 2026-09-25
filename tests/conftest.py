"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from cybersecurity_advisor.api.main import create_app
from cybersecurity_advisor.config.settings import get_settings


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
