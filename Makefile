.PHONY: help install up down logs dev backend frontend test test-unit test-int migrate migrate-new lint fmt

help:
	@echo "Targets:"
	@echo "  install        backend (.venv) + frontend (node_modules)"
	@echo "  up / down      docker compose Postgres on :5432"
	@echo "  logs           tail Postgres logs"
	@echo "  dev            backend (:8000) + frontend (:5173) in parallel"
	@echo "  backend        uvicorn reload"
	@echo "  frontend       vite dev"
	@echo "  test           pytest with coverage"
	@echo "  test-unit      pytest tests/unit"
	@echo "  test-int       pytest tests/integration"
	@echo "  migrate        alembic upgrade head"
	@echo "  migrate-new name=X  generate revision"
	@echo "  lint / fmt     ruff"

install:
	cd backend && python3.11 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -e ".[dev]"
	cd frontend && npm install

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f db

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Starting backend (:8000) and frontend (:5173). Ctrl-C stops both."
	@trap 'kill 0' EXIT INT TERM; \
	  ( cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000 ) & \
	  ( cd frontend && npm run dev ) & \
	  wait

test:
	cd backend && . .venv/bin/activate && pytest --cov=app --cov-report=term-missing

test-unit:
	cd backend && . .venv/bin/activate && pytest tests/unit -v

test-int:
	cd backend && . .venv/bin/activate && pytest tests/integration -v

migrate:
	cd backend && . .venv/bin/activate && alembic upgrade head

migrate-new:
	@if [ -z "$(name)" ]; then echo "usage: make migrate-new name=<short-message>"; exit 2; fi
	cd backend && . .venv/bin/activate && alembic revision --autogenerate -m "$(name)"

lint:
	cd backend && . .venv/bin/activate && ruff check .

fmt:
	cd backend && . .venv/bin/activate && ruff format .
