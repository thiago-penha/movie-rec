"""Command line for one-off ingestion tasks.

docker compose run --rm ingestion python -m ingestion.cli seed --limit 10000
"""

import argparse
import asyncio
import logging
import time

from common.db import get_sessionmaker
from ingestion.ingest import MissingTokenError, seed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ingestion.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    seed_parser = commands.add_parser("seed", help="fetch the most voted TMDB movies")
    seed_parser.add_argument("--limit", type=int, default=10_000, help="how many movies")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx logs every request at INFO; 10k lines would bury the progress messages.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    start = time.monotonic()
    with get_sessionmaker()() as session:
        try:
            report = asyncio.run(seed(session, args.limit))
        except MissingTokenError as error:
            raise SystemExit(str(error)) from None  # one clear line, no traceback
    print(
        f"seed done in {time.monotonic() - start:.0f} s: {report.upserted} upserted, "
        f"{report.not_found} not found, {report.failed} failed"
    )
    if report.failed:
        raise SystemExit(1)  # a failed movie is worth noticing; re-running retries it


if __name__ == "__main__":
    main()
