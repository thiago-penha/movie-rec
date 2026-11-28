from fastapi.testclient import TestClient

from recommender.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/rec/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
