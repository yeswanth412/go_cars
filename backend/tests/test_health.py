"""Tests for the service health check endpoint."""

from fastapi import status


def test_health_check_endpoint(client):
    """Test that the /api/v1/health endpoint responds with HTTP 200 and expected schema."""
    response = client.get("/api/v1/health")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]
    assert data["app_name"] == "GoCars API"
    assert data["version"] == "1.0.0"
    assert data["environment"] == "development"
    assert data["database"] in ["connected", "disconnected"]
    assert "timestamp" in data


def test_root_redirect(client):
    """Test that the root endpoint redirects to Swagger docs."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code in [status.HTTP_307_TEMPORARY_REDIRECT, status.HTTP_302_FOUND]
    assert response.headers["location"] == "/docs"
