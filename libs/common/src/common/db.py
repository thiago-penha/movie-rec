"""Database engine and session factory, shared by all services."""

import logging
from functools import cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from common.config import get_settings

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 3


@cache
def get_engine() -> Engine:
    # One engine per process: it owns the connection pool. pool_pre_ping checks a
    # connection before handing it out, so a restarted Postgres does not cause one
    # failed request per stale pooled connection.
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        # Without a timeout, connecting to an unreachable database can hang for
        # minutes (seen on Windows), so /health and requests would hang instead of failing.
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@cache
def get_sessionmaker() -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit() without a new
    # query. The job queue functions commit and then return the job.
    return sessionmaker(get_engine(), expire_on_commit=False)


def ping() -> bool:
    """True if the database answers `SELECT 1`. Used by the /health endpoints."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("database ping failed")
        return False
    return True
