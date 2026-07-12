import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture()
def client():
    """
    Opretter en TestClient og sikrer, at FastAPI-appens lifespan
    bliver startet og afsluttet korrekt for hver test.
    """
    with TestClient(app) as test_client:
        yield test_client


def test_root_returns_service_information(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "sproki-backend",
    }


def test_health_returns_ok(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_version_returns_version_value(client: TestClient):
    response = client.get("/version")

    assert response.status_code == 200
    assert "version" in response.json()


def test_openapi_schema_is_available(client: TestClient):
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert schema["info"]["title"] == "Sproki API"
    assert "/health" in schema["paths"]
