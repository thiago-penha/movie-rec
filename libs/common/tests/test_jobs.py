from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from sqlalchemy import func, select, update

from common import jobs
from common.db import get_sessionmaker
from common.models import Job


def test_concurrent_claims_never_return_the_same_job(db_session) -> None:
    """Acceptance (Phase 1): SKIP LOCKED gives each job to exactly one worker."""
    job_count, worker_count = 50, 8
    for i in range(job_count):
        jobs.enqueue(db_session, "test", {"n": i})

    # Every worker waits here until all are ready, so they really claim at the same time.
    start = Barrier(worker_count)

    def worker() -> list[int]:
        claimed = []
        with get_sessionmaker()() as session:
            start.wait()
            while (job := jobs.claim_next(session)) is not None:
                claimed.append(job.id)
        return claimed

    with ThreadPoolExecutor(worker_count) as pool:
        results = list(pool.map(lambda _: worker(), range(worker_count)))

    all_claimed = [job_id for claimed in results for job_id in claimed]
    assert len(all_claimed) == len(set(all_claimed)), "a job was claimed twice"
    assert len(all_claimed) == job_count, "a job was never claimed"


def test_claim_takes_oldest_due_job_and_skips_future_ones(db_session) -> None:
    first = jobs.enqueue(db_session, "test", {})
    later = jobs.enqueue(db_session, "test", {})
    db_session.execute(
        update(Job).where(Job.id == first.id).values(run_after=func.now() + timedelta(hours=1))
    )
    db_session.commit()

    claimed = jobs.claim_next(db_session)

    assert claimed is not None
    assert claimed.id == later.id
    assert claimed.status == "running"
    assert claimed.attempts == 1
    assert jobs.claim_next(db_session) is None  # `first` is not due for an hour


def test_failed_job_is_retried_later_then_fails_for_good(db_session) -> None:
    job = jobs.enqueue(db_session, "test", {})

    jobs.claim_next(db_session)
    jobs.mark_failed(db_session, job.id, "boom")
    db_session.refresh(job)
    assert job.status == "queued"
    assert job.last_error == "boom"
    # First retry waits BACKOFF_BASE (30 s), so it is not claimable right away.
    delay = db_session.scalar(select(Job.run_after - func.now()).where(Job.id == job.id))
    assert 25 < delay.total_seconds() <= 30
    assert jobs.claim_next(db_session) is None

    # Use up the remaining attempts (skip the waiting by making the job due now).
    for _ in range(jobs.MAX_ATTEMPTS - 1):
        db_session.execute(update(Job).where(Job.id == job.id).values(run_after=func.now()))
        db_session.commit()
        assert jobs.claim_next(db_session) is not None
        jobs.mark_failed(db_session, job.id, "boom")

    db_session.refresh(job)
    assert job.status == "failed"
    assert job.attempts == jobs.MAX_ATTEMPTS


def test_mark_done(db_session) -> None:
    job = jobs.enqueue(db_session, "test", {})
    jobs.claim_next(db_session)

    jobs.mark_done(db_session, job.id)

    db_session.refresh(job)
    assert job.status == "done"
    assert job.locked_at is None


def test_requeue_stale_requeues_stuck_jobs_and_fails_exhausted_ones(db_session) -> None:
    stuck = jobs.enqueue(db_session, "test", {})
    exhausted = jobs.enqueue(db_session, "test", {})
    recent = jobs.enqueue(db_session, "test", {})
    for _ in range(3):
        jobs.claim_next(db_session)
    long_ago = func.now() - jobs.STALE_AFTER - timedelta(minutes=1)
    db_session.execute(
        update(Job).where(Job.id.in_([stuck.id, exhausted.id])).values(locked_at=long_ago)
    )
    db_session.execute(update(Job).where(Job.id == exhausted.id).values(attempts=jobs.MAX_ATTEMPTS))
    db_session.commit()

    assert jobs.requeue_stale(db_session) == 2

    statuses = dict(db_session.execute(select(Job.id, Job.status)).all())
    assert statuses == {stuck.id: "queued", exhausted.id: "failed", recent.id: "running"}
