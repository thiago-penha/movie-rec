from fastapi.testclient import TestClient

from recommender import main
from recommender.main import app

client = TestClient(app)


def test_health_is_ok_when_the_database_answers(migrated_db) -> None:
    response = client.get("/rec/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_is_503_when_the_database_is_down(monkeypatch) -> None:
    monkeypatch.setattr(main, "ping", lambda: False)

    response = client.get("/rec/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error"}
