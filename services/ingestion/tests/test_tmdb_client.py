"""TMDB client tests. respx intercepts httpx requests, so nothing reaches the network."""

import httpx
import pytest
import respx
from tenacity import wait_none

from ingestion.tmdb_client import BASE_URL, MAX_ATTEMPTS, TmdbClient

DETAILS_URL = f"{BASE_URL}/movie/157336"

# anyio's pytest plugin (installed with httpx) runs `async def` tests in an event loop.
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def client() -> TmdbClient:
    # wait_none: retry immediately, so the tests do not sleep through the backoff.
    return TmdbClient("test-token", wait=wait_none())


@respx.mock
async def test_sends_the_bearer_token_and_returns_json() -> None:
    route = respx.get(DETAILS_URL).respond(json={"id": 157336})

    async with client() as tmdb:
        assert await tmdb.movie_details(157336) == {"id": 157336}

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.url.params["append_to_response"] == "keywords,credits"


@respx.mock
async def test_retries_rate_limit_and_server_errors_then_succeeds() -> None:
    route = respx.get(DETAILS_URL).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(503),
            httpx.ConnectTimeout("slow"),
            httpx.Response(200, json={"id": 157336}),
        ]
    )

    async with client() as tmdb:
        assert await tmdb.movie_details(157336) == {"id": 157336}

    assert route.call_count == 4


@respx.mock
async def test_gives_up_after_max_attempts_with_the_real_error() -> None:
    route = respx.get(DETAILS_URL).respond(500)

    async with client() as tmdb:
        with pytest.raises(httpx.HTTPStatusError):
            await tmdb.movie_details(157336)

    assert route.call_count == MAX_ATTEMPTS


@respx.mock
async def test_not_found_returns_none_without_retrying() -> None:
    route = respx.get(DETAILS_URL).respond(404)

    async with client() as tmdb:
        assert await tmdb.movie_details(157336) is None

    assert route.call_count == 1


@respx.mock
async def test_bad_token_is_not_retried() -> None:
    route = respx.get(DETAILS_URL).respond(401)

    async with client() as tmdb:
        with pytest.raises(httpx.HTTPStatusError):
            await tmdb.movie_details(157336)

    assert route.call_count == 1
