"""Job queue on a Postgres table (PROJECT_SPEC §5.4). No Redis or RabbitMQ to run.

Life of a job: queued -> running -> done, or back to queued with a delay after a
failure, and failed for good after MAX_ATTEMPTS.

Delivery is "at least once": if a worker dies or takes longer than STALE_AFTER, the
job runs again on another worker. Job handlers must be safe to run twice.

Every function here commits its own transaction, so a claimed job is visible as
`running` to everyone right away and its row lock is released.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import case, func, select, text, update
from sqlalchemy.orm import Session

from common.models import Job

MAX_ATTEMPTS = 5
# Retry delays double: 30 s, 1 min, 2 min, 4 min.
BACKOFF_BASE = timedelta(seconds=30)
# A job `running` for longer than this is assumed to belong to a dead worker.
STALE_AFTER = timedelta(minutes=15)

# Written as raw SQL to match the spec. The inner SELECT picks the oldest due job and
# locks its row. FOR UPDATE SKIP LOCKED is what makes concurrent workers safe: a row
# another transaction has locked is skipped instead of waited on, so two workers
# polling at the same moment get different jobs (or none), never the same one.
_CLAIM_SQL = text("""
    UPDATE jobs SET status = 'running', locked_at = now(), attempts = attempts + 1
    WHERE id = (
        SELECT id FROM jobs
        WHERE status = 'queued' AND run_after <= now()
        ORDER BY id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING *
""")


def enqueue(session: Session, type: str, payload: dict[str, Any]) -> Job:
    job = Job(type=type, payload=payload)
    session.add(job)
    session.commit()
    return job


def claim_next(session: Session) -> Job | None:
    """Take the oldest due job and mark it running. None if there is nothing to do."""
    # populate_existing: if this session already holds the job (it enqueued it, or
    # claimed it before a retry), overwrite the stale in-memory copy with the values
    # RETURNING sent back. Without it the caller would see the old status and attempts.
    statement = select(Job).from_statement(_CLAIM_SQL).execution_options(populate_existing=True)
    job = session.scalars(statement).one_or_none()
    session.commit()
    return job


def mark_done(session: Session, job_id: int) -> None:
    session.execute(update(Job).where(Job.id == job_id).values(status="done", locked_at=None))
    session.commit()


def mark_failed(session: Session, job_id: int, error: str) -> None:
    """Retry later with exponential backoff, or fail for good after MAX_ATTEMPTS.

    `attempts` was already incremented by claim_next, so it counts this run.
    """
    give_up = Job.attempts >= MAX_ATTEMPTS
    # BACKOFF_BASE * 2^(attempts-1), computed in SQL with the database clock, the same
    # clock claim_next compares run_after against.
    seconds = BACKOFF_BASE.total_seconds() * func.power(2, Job.attempts - 1)
    delay = func.make_interval(0, 0, 0, 0, 0, 0, seconds)  # (years, ..., mins, secs)
    session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status=case((give_up, "failed"), else_="queued"),
            run_after=case((give_up, Job.run_after), else_=func.now() + delay),
            last_error=error,
            locked_at=None,
        )
    )
    session.commit()


def requeue_stale(session: Session) -> int:
    """The "reaper": put jobs stuck in `running` back in the queue. Returns how many.

    A job that crashes the worker every time would otherwise loop forever, so it is
    failed once it has used up its attempts.
    """
    give_up = Job.attempts >= MAX_ATTEMPTS
    result = session.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_at < func.now() - STALE_AFTER)
        .values(
            status=case((give_up, "failed"), else_="queued"),
            last_error=case(
                (give_up, "worker stopped responding; no attempts left"), else_=Job.last_error
            ),
            locked_at=None,
        )
    )
    session.commit()
    return result.rowcount
