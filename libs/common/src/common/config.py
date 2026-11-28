"""Settings read from environment variables (see .env.example).

Each phase adds the fields it uses; unknown variables in the environment are ignored.
"""

from functools import cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Env var names are matched case-insensitively: DATABASE_URL -> database_url.
    database_url: str


@cache
def get_settings() -> Settings:
    # Cached so the environment is read once per process, and lazily so importing
    # this module (e.g. in tests) does not fail when a variable is missing.
    return Settings()
