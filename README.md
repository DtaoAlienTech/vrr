# VRR Degree College Website

Public website and admin panel for V.R.R. Degree College, Kallur.

- **Backend:** FastAPI + PostgreSQL (`backend/`)
- **Frontend and admin:** Next.js + TypeScript (`frontend/`)
- **Entry point:** Caddy (one address for the website and the API)
- **Plan:** `../VRR-College-Full-Plan.md` (architecture, database, API, phases, checklists)
- **Design reference:** `../design-preview/` (14 approved pages as static HTML)

Every text, photo, menu and SEO field on the public site is meant to be editable from the admin panel. Pages are built from reusable sections (plan section 4A).

## Run everything with Docker

```bash
cp .env.example .env            # then replace every CHANGE_ME (see "Secrets" below)
docker compose up -d --build    # builds both apps, starts everything
```

Open **http://localhost:3000**. The first build takes a few minutes; after that it takes seconds.

| Container | What it does |
|---|---|
| `vrr-caddy` | The only door in: `/api/*` goes to the backend, everything else to the website, `/internal/*` is blocked |
| `vrr-frontend` | The Next.js website |
| `vrr-backend` | The FastAPI API. Applies database migrations by itself on every start |
| `vrr-db` | PostgreSQL (data is kept in a Docker volume) |

Useful commands:

```bash
docker compose ps                     # are all four healthy?
docker compose logs -f backend        # follow one service (backend, frontend, caddy, db)
docker compose up -d --build          # after changing code: rebuilds only what changed
docker compose down                   # stop and remove containers (data is kept)
docker compose down -v                # ... and DELETE the database data too
```

Only Caddy (port 3000) and the database (localhost:5433) are reachable from the host. The backend and the website have no published ports.

### Secrets

`.env` holds the secrets and is never committed. Make a strong value for each `CHANGE_ME`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

`POSTGRES_PASSWORD` appears twice in `.env` (once inside `DATABASE_URL`); use the same value in both.

## Develop with hot reload (apps outside Docker)

Stop the app containers first because they use port 3000, then keep only the database:

```bash
docker compose stop caddy frontend backend
docker compose up -d db

# backend (terminal 1)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload   # http://127.0.0.1:8000/api/v1/health

# frontend (terminal 2)
cd frontend
npm install
npm run dev                     # http://localhost:3000 (/api is proxied to port 8000)
```

## Checks before every commit

```bash
./scripts/check.sh   # ruff, pytest, eslint, TypeScript, frontend tests (same as CI)
```

`make` shortcuts (`make up`, `make down`, `make logs`, `make check`) also exist if `make` is installed.

## Rules

- No secrets in git. `.env` is ignored.
- Each content field is defined once in the backend schema; the admin form and the TypeScript types are generated from it.
- Only the `JsonLd` component may write raw HTML. Rich text is data, drawn by React.
- Behind a proxy the backend trusts only the address the proxy adds (`TRUSTED_PROXY_HOPS`), never the one the visitor sends.
