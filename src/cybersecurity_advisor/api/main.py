"""FastAPI application factory and application instance."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from cybersecurity_advisor import __version__
from cybersecurity_advisor.api.dependencies import close_graph_retriever
from cybersecurity_advisor.api.routers.graph import router as graph_router
from cybersecurity_advisor.api.routers.health import router as health_router
from cybersecurity_advisor.api.routers.hybrid import router as hybrid_router
from cybersecurity_advisor.api.routers.retrieval import router as retrieval_router
from cybersecurity_advisor.config.logging import configure_logging
from cybersecurity_advisor.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure process-wide services for the application lifecycle."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger(__name__)
    logger.info("application_started", environment=settings.app_env)
    try:
        yield
    finally:
        close_graph_retriever()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    """Build the API application without connecting to external services."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(graph_router)
    application.include_router(health_router)
    application.include_router(hybrid_router)
    application.include_router(retrieval_router)
    return application


app = create_app()
