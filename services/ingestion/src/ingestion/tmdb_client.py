"""Async client for the TMDB API (https://developer.themoviedb.org/reference).

Why async here: seeding fetches ~10k movie details. Each request spends almost all
its time waiting for the network, so one thread can keep many requests in flight
with asyncio. The database code stays synchronous (decision 008).
"""

import asyncio
import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tenacity.wait import wait_base

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
# TMDB allows roughly 40-50 requests/s. 10 requests in flight stays under that at
# normal latency; if TMDB still answers 429 (too many requests), the retry backs off.
MAX_CONCURRENCY = 10
MAX_ATTEMPTS = 5
# Doubling delays with random jitter: ~1 s, 2 s, 4 s, 8 s (capped at 30 s). The jitter
# keeps 10 concurrent requests that failed together from retrying in lockstep.
DEFAULT_WAIT = wait_exponential_jitter(initial=1, max=30)


def _is_retryable(error: BaseException) -> bool:
    """Retry network failures, 429 and 5xx. A 4xx (bad id, bad token) will not fix itself."""
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return isinstance(error, httpx.TransportError)  # timeouts, connection resets, DNS


class TmdbClient:
    """Use as `async with TmdbClient(token) as tmdb: ...` so connections are closed."""

    def __init__(
        self,
        token: str,
        *,
        max_concurrency: int = MAX_CONCURRENCY,
        wait: wait_base = DEFAULT_WAIT,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            # v4 "API Read Access Token", sent as a bearer token on every request.
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=httpx.Timeout(10.0),
        )
        # The semaphore is the concurrency limit: at most N requests in flight,
        # however many tasks are waiting to send one.
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._wait = wait

    async def __aenter__(self) -> "TmdbClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        retrying = AsyncRetrying(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=self._wait,
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,  # after the last attempt, raise the real HTTP error, not RetryError
        )
        async for attempt in retrying:
            with attempt:
                # Hold a semaphore slot only while the request is in flight, not
                # while sleeping before a retry, so a backoff does not block others.
                async with self._semaphore:
                    response = await self._http.get(path, params=params)
                response.raise_for_status()
                return response.json()
        raise AssertionError("unreachable: tenacity either returns or raises")

    async def discover_page(self, page: int) -> dict[str, Any]:
        """One page (20 movies) of the most voted movies with at least 200 votes."""
        return await self._get(
            "/discover/movie",
            params={
                "sort_by": "vote_count.desc",
                "vote_count.gte": 200,
                "include_adult": "false",
                "page": page,
            },
        )

    async def movie_details(self, tmdb_id: int) -> dict[str, Any] | None:
        """Details with keywords and credits in one request. None if TMDB has no such id."""
        try:
            return await self._get(
                f"/movie/{tmdb_id}", params={"append_to_response": "keywords,credits"}
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise
