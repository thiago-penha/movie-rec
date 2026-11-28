from sqlalchemy import create_engine

from common import db


def test_ping_is_true_when_the_database_answers(migrated_db) -> None:
    assert db.ping() is True


def test_ping_is_false_instead_of_raising_when_the_database_is_unreachable(monkeypatch) -> None:
    # Port 1: nothing listens there. Same timeout as the real engine, so this test also
    # proves a dead database fails within seconds instead of hanging.
    unreachable = create_engine(
        "postgresql+psycopg://user:pw@127.0.0.1:1/none",
        connect_args={"connect_timeout": db.CONNECT_TIMEOUT_SECONDS},
    )
    monkeypatch.setattr(db, "get_engine", lambda: unreachable)

    assert db.ping() is False
