# Build context is the repo root (see docker-compose.yml), so libs/common is reachable.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1) Third-party dependencies only. uv needs every workspace member's pyproject.toml
#    to read the lockfile, but not their code. This layer is cached until a
#    pyproject.toml or uv.lock changes, so code edits rebuild in seconds.
COPY pyproject.toml uv.lock ./
COPY libs/common/pyproject.toml libs/common/
COPY db/pyproject.toml db/
COPY services/api/pyproject.toml services/api/
COPY services/ingestion/pyproject.toml services/ingestion/
COPY services/recommender/pyproject.toml services/recommender/
RUN uv sync --frozen --no-dev --package cinematch-api --no-install-workspace

# 2) Our own code: common + this service only.
COPY libs/common libs/common
COPY services/api services/api
RUN uv sync --frozen --no-dev --package cinematch-api

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
