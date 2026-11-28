"""Background worker: takes jobs from the Postgres queue (common.jobs) and runs them.

Run with: python -m ingestion.worker
"""

import asyncio
import logging
import signal
import threading
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from common import jobs
from common.db import get_sessionmaker
from ingestion.ingest import ingest_movie

logger = logging.getLogger("ingestion.worker")

# How long to wait before checking again when the queue is empty. Short enough that
# an on-demand job (e.g. a Letterboxd import) starts within seconds.
POLL_INTERVAL_SECONDS = 5.0

Handler = Callable[[Session, dict[str, Any]], None]


def _ingest_movie(session: Session, payload: dict[str, Any]) -> None:
    # The handler is sync like the rest of the worker; asyncio.run gives the async
    # TMDB client an event loop for the duration of this one job.
    asyncio.run(ingest_movie(session, int(payload["tmdb_id"])))


# Job type -> function that runs it. Phase 7 adds match_letterboxd_import.
HANDLERS: dict[str, Handler] = {"ingest_movie": _ingest_movie}


def run_once(session: Session, handlers: dict[str, Handler] = HANDLERS) -> bool:
    """Run one job if one is due. Returns False when the queue had nothing to do."""
    job = jobs.claim_next(session)
    if job is None:
        return False
    # Plain values: rollback() below expires ORM objects, and reading job.id after it
    # would need another query.
    job_id, job_type = job.id, job.type
    handler = handlers.get(job_type)
    try:
        if handler is None:
            raise ValueError(f"no handler for job type {job_type!r}")
        handler(session, job.payload)
    except Exception as error:
        # Log and record the error, then keep the worker alive for the next job.
        session.rollback()  # the handler may have left a failed transaction open
        logger.exception("job %s (%s) failed", job_id, job_type)
        jobs.mark_failed(session, job_id, repr(error))
    else:
        jobs.mark_done(session, job_id)
        logger.info("job %s (%s) done", job_id, job_type)
    return True


def run(stop: threading.Event, interval: float = POLL_INTERVAL_SECONDS) -> None:
    """Loop until `stop` is set: run due jobs back to back, then wait when idle."""
    with get_sessionmaker()() as session:
        while not stop.is_set():
            if run_once(session):
                continue
            # Only when idle: re-queue jobs left `running` by a worker that died.
            if requeued := jobs.requeue_stale(session):
                logger.warning("re-queued %d stale jobs", requeued)
                continue
            # Event.wait instead of time.sleep: it returns as soon as `stop` is set,
            # so the container shuts down at once instead of finishing the wait.
            stop.wait(interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    stop = threading.Event()

    # `docker compose stop` sends SIGTERM. A process running as PID 1 in a container
    # gets no default signal handlers, so without this Docker waits 10 s and kills it.
    # The current job finishes before the loop checks `stop` again.
    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("received signal %s, shutting down", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("worker started")
    run(stop)
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
