# CineMatch

Movie recommendations from what you already love. Pick a few films, or upload your Letterboxd export, and CineMatch finds what to watch next using semantic vector search over ~10k movies, with grounded "why this movie" explanations from an LLM.

Built as a portfolio and learning project: a small service-based monorepo with PostgreSQL + pgvector, embeddings, RAG and a LangGraph agent.

> Status: Phase 0 (repository skeleton). Features arrive phase by phase.

## Architecture

```
                    ┌──────────────────────────────────────────────┐
 Browser ──HTTPS──▶ │ Caddy (reverse proxy, automatic TLS)         │
                    │   /            → frontend (static React)     │
                    │   /api/*       → api                         │
                    │   /rec/*       → recommender                 │
                    └───────┬──────────────────────┬───────────────┘
                            │                      │
                 ┌──────────▼─────────┐  ┌─────────▼────────────┐
                 │ services/api       │  │ services/recommender │
                 │ FastAPI            │  │ FastAPI + LangGraph  │
                 │ auth, users,       │  │ vector search, RAG,  │
                 │ Letterboxd upload  │  │ Claude calls         │
                 └──────────┬─────────┘  └─────────┬────────────┘
                            │ enqueue jobs         │ read movies/vectors
                            ▼                      ▼
                 ┌──────────────────────────────────────────────┐
                 │ PostgreSQL 16 + pgvector                     │
                 │ users, movies, embeddings, letterboxd data,  │
                 │ jobs queue, LLM usage                        │
                 └──────────▲───────────────────────────────────┘
                            │ poll jobs, write movies + vectors
                 ┌──────────┴─────────┐        ┌──────────────┐
                 │ services/ingestion │──────▶ │ TMDB API     │
                 │ background worker  │        └──────────────┘
                 │ sentence-transf.   │
                 └────────────────────┘
                 recommender ──────────────────▶ Anthropic API (Claude Haiku)
```

In development there is no Caddy: the Vite dev server proxies `/api` and `/rec` to the services.

## Running locally

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/), [uv](https://docs.astral.sh/uv/), Node.js ≥ 22.22 (24 LTS recommended) and GNU Make.
On Windows: `winget install astral-sh.uv ezwinports.make OpenJS.NodeJS.LTS`.

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
make install                # Python + frontend dependencies
make up                     # db, api (:8000), recommender (:8001), ingestion
make dev-fe                 # frontend on http://localhost:5173
```

Check it works:

```bash
curl localhost:8000/api/health   # {"status":"ok","db":"ok"}
curl localhost:8001/rec/health   # {"status":"ok","db":"ok"}
```

In Windows PowerShell, `curl` is an alias for `Invoke-WebRequest`: type `curl.exe` instead.

Open http://localhost:5173: both services should show **ok**. API docs: http://localhost:8000/api/docs and http://localhost:8001/rec/docs.

Other commands: `make test`, `make lint`, `make fmt`, `make logs`, `make down`. Run `make help` for the full list.

`make test` needs the database running (`make up`): integration tests use a separate `cinematch_test` database on the same Postgres, created automatically, so they never touch your dev data.

### Database migrations

`make up` applies migrations automatically (the one-shot `migrate` service runs `alembic upgrade head` before the other services start). After changing `libs/common/src/common/models.py`:

```bash
make migration id=0002 m="add reviews"   # writes db/migrations/versions/0002_add_reviews.py
make migrate                             # apply it
```

Always read the generated file: autogenerate does not detect everything (extensions, for example). To undo everything and redo it: `docker compose run --rm migrate sh -c "alembic downgrade base && alembic upgrade head"`.

## Repository layout

```
frontend/              React + TypeScript + Vite
services/api/          FastAPI: auth, users, Letterboxd upload, movie search
services/ingestion/    background worker: TMDB data, embeddings, matching
services/recommender/  FastAPI: vector search, RAG, LangGraph agent
libs/common/           shared Python package (config, db, models, job queue, embeddings)
db/                    Alembic migrations, run by the one-shot migrate service
```
