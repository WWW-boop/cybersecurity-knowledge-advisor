"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from cybersecurity_advisor.api.dependencies import get_dense_retriever, get_graph_retriever
from cybersecurity_advisor.api.main import create_app
from cybersecurity_advisor.config.settings import get_settings


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    get_dense_retriever.cache_clear()
    get_graph_retriever.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
    get_dense_retriever.cache_clear()
    get_graph_retriever.cache_clear()
