.PHONY: help install lint format typecheck test build check-all compose-up compose-down

help:
	@echo "ChangeScope Engineering Tasks:"
	@echo "  make install       Install backend (uv) and frontend (pnpm) dependencies"
	@echo "  make lint          Execute Ruff lint checks"
	@echo "  make format        Format Python codebase with Ruff"
	@echo "  make typecheck     Execute Mypy static type analysis"
	@echo "  make test          Run full Pytest automated test suite"
	@echo "  make build         Build frontend React application"
	@echo "  make check-all     Execute all quality invariants (lint, typecheck, test, build)"
	@echo "  make compose-up    Start PostgreSQL, Redis, Neo4j in background"
	@echo "  make compose-down  Tear down development services"

install:
	uv pip install -e ".[dev]"
	pnpm install

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy packages/ apps/

test:
	uv run pytest -v tests/

build:
	pnpm --filter @changescope/web build

check-all: lint typecheck test build

compose-up:
	docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis neo4j

compose-down:
	docker compose -f infrastructure/docker/docker-compose.yml down
