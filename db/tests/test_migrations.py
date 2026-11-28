"""Acceptance (Phase 1): migrations can be fully undone and redone."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from common.db import get_engine
from common.models import Base

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"


def test_downgrade_base_then_upgrade_head(migrated_db) -> None:
    config = Config(str(ALEMBIC_INI))
    # Pooled connections would keep seeing the old tables' catalog; start clean.
    get_engine().dispose()

    command.downgrade(config, "base")
    assert set(inspect(get_engine()).get_table_names()) <= {"alembic_version"}

    command.upgrade(config, "head")  # leaves the database at head for other tests
    get_engine().dispose()
    assert set(Base.metadata.tables) <= set(inspect(get_engine()).get_table_names())
    with get_engine().connect() as connection:
        extensions = set(connection.scalars(text("SELECT extname FROM pg_extension")))
    assert {"vector", "pg_trgm", "citext"} <= extensions
