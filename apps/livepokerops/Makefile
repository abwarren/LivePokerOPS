.PHONY: help build up down restart logs test lint format shell-backend shell-db migrate makemigrations

help:
	@echo "LivePokerOPS — Makefile"
	@echo ""
	@echo "  make build         — Build all Docker images"
	@echo "  make up            — Start all services (detached)"
	@echo "  make down          — Stop all services"
	@echo "  make restart       — Restart all services"
	@echo "  make logs          — Follow logs"
	@echo "  make test          — Run all tests"
	@echo "  make lint          — Run linting"
	@echo "  make format        — Format code"
	@echo "  make shell-backend — Open a shell in the backend container"
	@echo "  make shell-db     — Open psql in the database"
	@echo "  make migrate       — Run Alembic migrations"
	@echo "  make makemigrations — Create a new Alembic migration (message=...)"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest -v

lint:
	docker compose exec backend ruff check .
	docker compose exec backend ruff format --check .

format:
	docker compose exec backend ruff format .

shell-backend:
	docker compose exec backend /bin/bash

shell-db:
	docker compose exec db psql -U livepokerops -d livepokerops

migrate:
	docker compose exec backend alembic upgrade head

makemigrations:
	@[ -n "$(message)" ] || (echo "Usage: make makemigrations message='description'"; exit 1)
	docker compose exec backend alembic revision --autogenerate -m "$(message)"
