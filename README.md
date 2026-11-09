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

Open **http://localhost:3000**. The first start takes a few minutes: the images are built, the backend adds the starter content (college details, courses, photos, sample pages) to the empty database, and then the website builds its pages from the live API. Later starts take seconds, because the website build is saved and reused until the code changes.

| Container | What it does |
|---|---|
| `vrr-caddy` | The only door in: `/api/*` goes to the backend, everything else to the website, `/internal/*` is blocked |
| `vrr-frontend` | The Next.js website. Builds its pages from the API when it starts (the build is saved in a volume) |
| `vrr-backend` | The FastAPI API. Applies database migrations and, on an empty database, adds the starter content |
| `vrr-db` | PostgreSQL (data is kept in a Docker volume) |
| `vrr-mailcatcher` | Optional (`--profile mail`): a test mailbox that prints enquiry emails, see "Try the enquiry email" |

Useful commands:

```bash
docker compose ps                     # are all four healthy?
docker compose logs -f backend        # follow one service (backend, frontend, caddy, db)
docker compose up -d --build          # after changing code: rebuilds only what changed
docker compose down                   # stop and remove containers (data is kept)
docker compose down -v                # ... and DELETE the database data too
```

Only Caddy (port 3000) and the database (localhost:5433) are reachable from the host. The backend and the website have no published ports.

Photos and PDFs live in the `uploads` volume: the backend writes them and Caddy serves them at `/uploads/...`. Every uploaded photo is checked (real file type, at most 6000 px and `MAX_UPLOAD_MB`), turned upright, stripped of camera data and GPS location, and saved as WebP copies 400, 800, 1200 and 1600 px wide. The photo exactly as uploaded is kept in the private `originals` volume. A photo that is still used on a page cannot be deleted.

```bash
docker compose exec backend python -m app.cli media-reprocess     # resized copies for photos that lack them (runs at every start)
docker compose exec backend python -m app.cli media-cleanup --dry-run   # list files no library entry refers to (drop --dry-run to delete them)
``` The starter content is added only when the database has no pages (`SEED_ON_START=0` in `.env` turns that off; `docker compose exec backend python -m app.cli seed --if-empty` runs it by hand). The texts marked "Sample" in it are placeholders and must be replaced before launch.

### Test the whole site on your computer

1. `cp .env.example .env`, replace every `CHANGE_ME` (see "Secrets"), then `docker compose up -d --build` and wait until `docker compose ps` shows all four containers healthy.
2. Public site: **http://localhost:3000** (home, courses, faculty, news, gallery, admissions, contact, privacy). Try the phone view too (browser dev tools, narrow window).
3. Sign in at **http://localhost:3000/admin** with the ready-made account (below), or create your own admin.
4. Try these, and check each one on the public site in a second tab:
   - **News and notices:** add a news item, publish it, then change its web address (slug). The old address now sends visitors to the new one.
   - **Draft preview:** open any page or news item, press **Preview**. It opens the saved draft in a new tab with an orange "Draft preview" bar; the link stops working after 30 minutes and is never shown to search engines.
   - **Page content:** change a heading or a photo on any page, hide or move a section, then press **Save**. The public page updates within seconds. **History** on the same screen puts an older version back.
   - **Photos:** upload a photo in the media library (big camera photos are resized automatically).
   - **Enquiry:** fill in the enquiry form on the public site, then look under **Enquiries** in the admin panel. To also see the email, follow "Try the enquiry email".
5. Start again from a clean site whenever you like: `docker compose down -v && docker compose up -d --build` (this deletes the database and uploads).

### Ready-made account for local testing

With `DEV_ADMIN_EMAIL` and `DEV_ADMIN_PASSWORD` in `.env` (the local `.env` has `admin@gmail.com` / `vrr@123`), the backend creates that super admin when it starts, if it does not exist yet. It is never changed afterwards, so a password you change in the admin panel stays. The first sign-in asks you to set up two-factor login (an authenticator app on your phone): super admins cannot skip it, and until it is on, the other menu entries stay locked.

On the setup screen, open the authenticator app on your phone, choose "Add account" → "Scan a QR code" and point the camera at the picture (it is drawn in your browser; the key never goes to another website). If you cannot scan, the same screen shows the key to type in.

No authenticator app at hand? For local testing the code can come from the backend container. Copy the long key from the setup screen, then run (each time you sign in, run it again for a fresh code):

```bash
docker compose exec backend python -c "import pyotp; print(pyotp.TOTP('PASTE_THE_KEY_HERE').now())"
```

Type the 6 digits into the page. Save the recovery codes it shows (they are the way back in if the key is lost).

This is for your own computer only: the password is short and public. The backend **refuses to start** when `ENV=prod` and these two lines are still set, so remove them (and create your real account below) before going live.

### First admin account

Create the first super admin once (it asks for the password on the keyboard; it is never stored in clear text):

```bash
docker compose exec backend python -m app.cli create-admin --email you@college.example --name "Your Name"
docker compose exec backend python -m app.cli reset-password --email you@college.example   # if it is ever lost
```

Passwords need at least 12 characters. Super admins must turn on two-factor login (an authenticator app) the first time they sign in; five wrong passwords lock an account for 15 minutes.

### The admin panel

Open **http://localhost:3000/admin** and sign in with the account you created above. Super admins are asked to set up two-factor login (an authenticator app) the first time. From there staff can publish news and notices, add activities with many photos at once, manage the gallery, courses, faculty and enquiries, and change the text and photos of every page of the website (Page content). Super admins also manage site settings (menu, footer, contact details, search-engine defaults), users and the activity log. Every change shows on the website within seconds, is kept in the history and can be undone.

The admin screens are built from the backend's own definitions of every form, so a new field added in the backend appears in the admin by itself. Browser tests for the main flows are in `frontend/e2e/` (see its README).

### Old addresses, draft preview and email

- **Old addresses keep working.** When an editor changes the address (slug) of a page, course or news item, the old address is saved as a redirect and the website answers it with a real `301` to the new one (Google follows it and old links do not break). Redirects can also be added by hand under **History > Redirects**. The website checks the list on every visit to a public address, keeps it for at most 30 seconds, and ignores any rule that would leave the site.
- **Draft preview.** **Preview** (on page and news screens) asks the backend for a signed link, `/preview/<token>`. The token is valid for 30 minutes, opens exactly one page or news item for reading, and shows the saved version (not unsaved edits) in the real website layout. The answer is never cached and carries `noindex`.
- **The website's API types are generated** from the backend's own schema, so the two cannot drift apart. After changing a public response model (`backend/app/schemas/public.py`) run `./scripts/generate-types.sh`; `./scripts/check.sh` fails if you forgot.

### Try the enquiry email

Enquiries are always saved in the database; the email to the college office is an extra. Two ways to try it:

**A. Without any account (local test mailbox).** Put this in `.env`, then start the mailbox and restart the backend:

```bash
SMTP_HOST=mailcatcher
SMTP_PORT=1025
SMTP_SECURITY=none
ENQUIRY_TO_EMAIL=office@example.org
MAIL_FROM=website@example.org

docker compose --profile mail up -d mailcatcher
docker compose up -d backend
docker compose exec backend python -m app.cli send-test-email   # prints "Sent."
docker compose logs -f mailcatcher                              # every email appears here
```

Now submit the enquiry form on the website: the email shows in the `mailcatcher` log. (The mailbox has no encryption and no login: it is only for this test, and it has no published port.)

**B. With the real mail account.** Fill `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` and `ENQUIRY_TO_EMAIL` in `.env`. Port 587 uses `SMTP_SECURITY=starttls`, port 465 uses `ssl`. Gmail and Microsoft need an *app password*, not the normal one. Then `docker compose up -d backend` and run `send-test-email` as above: it says exactly what went wrong (wrong password, wrong port, server not reachable) in plain words. A password is never sent without encryption.

### Staff API (what the admin panel uses)

All under `/api/v1/admin`, for signed-in staff (with the CSRF token on every change): `media`, `news`, `activities`, `gallery`, `courses`, `departments`, `faculty`, `pages` (and their `sections`), `redirects`, `revisions` (history and undo), `enquiries` (and `enquiries/export.csv`). Super admins only: `settings`, `users`, `audit-log`, and creating or deleting courses and departments. In development the interactive list is at http://localhost:3000/api/docs.

```bash
docker compose exec backend python -m app.cli reset-two-factor --email you@college.example   # lost phone
docker compose exec backend python -m app.cli purge-enquiries --days 365 --dry-run           # privacy: old enquiries
```

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

# photos: the starter content saved its photos in the Docker volume; copy them for local use
mkdir -p ../uploads && docker cp vrr-backend:/data/uploads/. ../uploads/

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
- Each content field is defined once in the backend schema; the admin forms and the website's API types (`frontend/src/lib/content/api.generated.ts`) are generated from it.
- Only the `JsonLd` component may write raw HTML. Rich text is data, drawn by React.
- Behind a proxy the backend trusts only the address the proxy adds (`TRUSTED_PROXY_HOPS`), never the one the visitor sends.
