"""Alembic entry point: connects to DATABASE_URL and runs migrations.

`alembic revision --autogenerate -m "..."` compares common.models with the live
database and writes the difference as a new file in versions/. Always read and fix
the generated file: autogenerate misses things (extensions, some index options).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from common.config import get_settings
from common.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # NullPool: a migration is a one-off run, no reason to keep connections open.
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# Offline mode (printing SQL instead of running it) is not used in this project.
run_migrations_online()
