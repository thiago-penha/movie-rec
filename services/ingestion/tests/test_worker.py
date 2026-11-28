import logging
import threading

from ingestion.worker import run


def test_run_logs_idle_and_stops_when_event_is_set(caplog) -> None:
    stop = threading.Event()
    # Stop the loop after the first iteration by setting the event from a timer.
    threading.Timer(0.05, stop.set).start()

    with caplog.at_level(logging.INFO, logger="ingestion.worker"):
        iterations = run(stop, interval=1.0)

    assert iterations == 1
    assert "idle" in caplog.messages


def test_run_does_nothing_if_already_stopped() -> None:
    stop = threading.Event()
    stop.set()

    assert run(stop) == 0
