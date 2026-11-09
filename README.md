# VRR Degree College Website

Public website and admin panel for V.R.R. Degree College, Kallur.

- **Backend:** FastAPI + PostgreSQL (`backend/`)
- **Frontend and admin:** Next.js + TypeScript (`frontend/`)
- **Plan:** `../VRR-College-Full-Plan.md` (architecture, database, API, phases, checklists)
- **Design reference:** `../design-preview/` (14 approved pages as static HTML)

Every text, photo, menu and SEO field on the public site is meant to be editable from the admin panel. Pages are built from reusable sections (plan section 4A).

## Run locally

```bash
cp .env.example .env            # then replace every CHANGE_ME (or use the generated .env)
docker compose up -d db         # PostgreSQL in Docker (localhost:5433)

# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload   # http://127.0.0.1:8000/api/v1/health

# frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

## Checks before every commit

```bash
./scripts/check.sh   # ruff, pytest, eslint, TypeScript, frontend tests (same as CI)
```

`make` shortcuts (`make db`, `make backend`, `make check`) also exist if `make` is installed.

## Rules

- No secrets in git. `.env` is ignored.
- Each content field is defined once in the backend schema; the admin form and the TypeScript types are generated from it.
- Only the `RichText` component may render HTML. JSON-LD goes through the `JsonLd` component.
