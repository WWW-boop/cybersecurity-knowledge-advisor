"""Liveness and readiness endpoints."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from cybersecurity_advisor import __version__
from cybersecurity_advisor.api.dependencies import SettingsDependency

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Public application health response."""

    status: Literal["ok", "ready"]
    service: str
    version: str
    environment: str


def _response(status: Literal["ok", "ready"], settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(
        status=status,
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
    )


@router.get("/health", response_model=HealthResponse)
def health(settings: SettingsDependency) -> HealthResponse:
    """Compatibility health endpoint for local tools and Docker."""
    return _response("ok", settings)


@router.get("/health/live", response_model=HealthResponse)
def liveness(settings: SettingsDependency) -> HealthResponse:
    """Confirm that the API process is alive."""
    return _response("ok", settings)


@router.get("/health/ready", response_model=HealthResponse)
def readiness(settings: SettingsDependency) -> HealthResponse:
    """Confirm that Phase 1 application configuration can be loaded.

    Dependency-specific checks will be added together with each integration.
    """
    return _response("ready", settings)
