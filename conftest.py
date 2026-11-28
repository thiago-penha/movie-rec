"""Shared pytest fixtures for integration tests against a real Postgres + pgvector.

Tests use their own database, `cinematch_test`, on the same Postgres server as the
dev stack (`make up`), or on the Postgres service container in CI. They never use the
dev database, because they delete rows.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError

# 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and the Docker
# port is bound to IPv4 only, which adds a long connection timeout.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://cinematch:change-me@127.0.0.1:5433/cinematch_test"
)
if not make_url(TEST_DATABASE_URL).database.endswith("_test"):
    raise RuntimeError(f"TEST_DATABASE_URL must point to a *_test database: {TEST_DATABASE_URL}")

# Overwrite (not setdefault) before any test imports common.db: even with a
# DATABASE_URL in the shell, the code under test can only reach the test database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

ALEMBIC_INI = Path(__file__).parent / "db" / "alembic.ini"


def _create_database_if_missing() -> None:
    url = make_url(TEST_DATABASE_URL)
    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT, and it must
    # be run from another database, hence the built-in "postgres" one.
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as error:
        pytest.fail(
            f"Postgres is not reachable at {url.render_as_string(hide_password=True)}. "
            f"Start it with `make up`.\n{error}",
            pytrace=False,
        )
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """Test database at the latest migration, set up once per test run."""
    _create_database_if_missing()
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


@pytest.fixture
def db_session(migrated_db):
    """A session on an empty test database. Tables are emptied before each test."""
    from common.db import get_engine, get_sessionmaker
    from common.models import Base

    # TRUNCATE instead of rolling back a transaction: the job queue tests need real
    # commits seen by several connections at once.
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    with get_sessionmaker()() as session:
        yield session
