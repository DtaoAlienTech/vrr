.PHONY: up down logs db db-down backend frontend migrate test lint typecheck check

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

db:
	docker compose up -d db

db-down:
	docker compose stop db

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && .venv/bin/alembic upgrade head

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test

lint:
	cd backend && .venv/bin/ruff check . && cd ../frontend && npm run lint

typecheck:
	cd frontend && npm run typecheck

check: lint typecheck test
