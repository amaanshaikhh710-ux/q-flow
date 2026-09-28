"""Tests for health check endpoints."""


def test_root_health_endpoint(test_client):
    """Verify root /health endpoint returns healthy status and DB connected."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Q-FLOW"
    assert data["database_connected"] is True
    assert data["details"]["database_engine"] == "PostgreSQL"


def test_api_v1_health_endpoint(test_client):
    """Verify /api/v1/health endpoint functions correctly."""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True


def test_api_v1_health_db_direct(test_client):
    """Verify direct SQL health check /api/v1/health/db."""
    response = test_client.get("/api/v1/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["connected"] is True
    assert data["query_result"] == 1
