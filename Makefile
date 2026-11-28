# Shortcuts for common commands. Recipes stick to commands that work the same in
# cmd, PowerShell and bash (docker, uv, npm), so this runs on Windows and in CI.
# Usage: make <target>   (e.g. make up, make test)

.PHONY: help install up down logs ps dev-fe test test-py test-fe lint fmt migrate migration seed

help:
	@echo "install  install Python (uv) and frontend (npm) dependencies"
	@echo "up       build and start db + services in the background"
	@echo "down     stop the stack (data in the db volume is kept)"
	@echo "logs     follow logs of all services"
	@echo "ps       show container status"
	@echo "dev-fe   start the frontend dev server on http://localhost:5173"
	@echo "test     run all tests (Python + frontend)"
	@echo "lint     run all linters"
	@echo "fmt      auto-format Python code"
	@echo "migrate  apply database migrations (also runs on every make up)"
	@echo "migration id=0002 m=\"add reviews\"  generate a migration from model changes"

install:
	uv sync --all-packages
	cd frontend && npm ci

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

dev-fe:
	cd frontend && npm run dev

test: test-py test-fe

test-py:
	uv run pytest

test-fe:
	cd frontend && npm test

lint:
	uv run ruff check .
	uv run ruff format --check .
	cd frontend && npm run lint

fmt:
	uv run ruff check --fix .
	uv run ruff format .

migrate:
	docker compose run --rm migrate

# Autogenerate runs in the migrate container (it has the right DATABASE_URL) and
# writes into db/migrations/versions/ through the bind mount. Read the file after:
# autogenerate misses things such as extensions.
migration:
	docker compose run --rm migrate alembic revision --autogenerate --rev-id $(id) -m "$(m)"
	uv run ruff format db
	uv run ruff check --fix db

seed:
	@echo "Not implemented yet (Phase 2)."
