"""Integration tests for FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from cataphract.main import app


@pytest.fixture
def client():
    """Create test client for API testing."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test /health endpoint returns healthy status."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "database" in data
    assert "version" in data

    # Database should be connected in tests
    assert data["database"] == "connected"
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


def test_root_endpoint(client):
    """Test root endpoint returns API information."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Cataphract Game System"
    assert data["version"] == "1.0.0"
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


def test_health_endpoint_structure(client):
    """Test health endpoint returns all expected fields."""
    response = client.get("/health")
    data = response.json()

    required_fields = ["status", "database", "version", "environment"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


def test_api_docs_available(client):
    """Test that OpenAPI documentation is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Cataphract Game System"
