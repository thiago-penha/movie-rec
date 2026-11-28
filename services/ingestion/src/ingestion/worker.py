"""Background worker. In Phase 0 it only logs "idle"; Phase 1+ polls the jobs table.

Run with: python -m ingestion.worker
"""

import logging
import signal
import threading

logger = logging.getLogger("ingestion.worker")

POLL_INTERVAL_SECONDS = 30.0


def run(stop: threading.Event, interval: float = POLL_INTERVAL_SECONDS) -> int:
    """Loop until `stop` is set. Returns how many iterations ran (handy in tests)."""
    iterations = 0
    while not stop.is_set():
        iterations += 1
        logger.info("idle")
        # Event.wait instead of time.sleep: it returns as soon as `stop` is set,
        # so the container shuts down at once instead of finishing a 30 s sleep.
        stop.wait(interval)
    return iterations


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = threading.Event()

    # `docker compose stop` sends SIGTERM. A process running as PID 1 in a container
    # gets no default signal handlers, so without this Docker waits 10 s and kills it.
    # Later this is where an in-flight job gets the chance to finish cleanly.
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
