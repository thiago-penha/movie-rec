import threading

from sqlalchemy import select

from common import jobs
from common.config import Settings
from common.models import Job
from ingestion import ingest
from ingestion.worker import run, run_once


def test_run_once_runs_the_handler_and_marks_the_job_done(db_session) -> None:
    seen = []
    job = jobs.enqueue(db_session, "echo", {"x": 1})

    assert run_once(db_session, {"echo": lambda _session, payload: seen.append(payload)})

    assert seen == [{"x": 1}]
    assert db_session.scalar(select(Job.status).where(Job.id == job.id)) == "done"


def test_a_failing_handler_requeues_the_job_with_the_error(db_session) -> None:
    def boom(_session, _payload) -> None:
        raise RuntimeError("tmdb down")

    job = jobs.enqueue(db_session, "boom", {})

    assert run_once(db_session, {"boom": boom})

    status, error = db_session.execute(
        select(Job.status, Job.last_error).where(Job.id == job.id)
    ).one()
    assert status == "queued"  # retried later (backoff)
    assert "tmdb down" in error


def test_unknown_job_type_is_recorded_as_an_error(db_session) -> None:
    job = jobs.enqueue(db_session, "nope", {})

    assert run_once(db_session, {})

    assert "no handler" in db_session.scalar(select(Job.last_error).where(Job.id == job.id))


def test_missing_tmdb_token_fails_the_job_without_killing_the_worker(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(ingest, "get_settings", lambda: Settings(database_url="x", tmdb_api_key=""))
    job = jobs.enqueue(db_session, "ingest_movie", {"tmdb_id": 157336})

    assert run_once(db_session)  # real handlers; raising SystemExit would end the test run

    assert "TMDB_API_KEY" in db_session.scalar(select(Job.last_error).where(Job.id == job.id))


def test_run_once_returns_false_when_the_queue_is_empty(db_session) -> None:
    assert run_once(db_session, {}) is False


def test_run_stops_when_the_event_is_set(db_session) -> None:
    stop = threading.Event()
    stop.set()

    run(stop)  # returns at once instead of polling forever
