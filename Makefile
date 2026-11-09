.PHONY: db db-down backend frontend migrate test lint typecheck check

db:
	docker compose up -d db

db-down:
	docker compose down

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
