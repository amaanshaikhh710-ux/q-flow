"""Tests for application startup, configuration, and root endpoints."""

from app.core.config import settings
from app import __version__


def test_app_configuration():
    """Verify application configuration loads expected defaults and settings."""
    assert settings.APP_NAME == "Q-FLOW"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.ETA_NOTIFICATION_THRESHOLD_MINUTES == 10
    assert "postgresql" in settings.DATABASE_URL or "sqlite" in settings.DATABASE_URL
    assert settings.JWT_SECRET is not None


def test_root_endpoint(test_client):
    """Verify root / endpoint returns metadata."""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "Q-FLOW"
    assert data["version"] == __version__
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"
