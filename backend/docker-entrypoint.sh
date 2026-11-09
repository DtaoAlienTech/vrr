#!/bin/sh
# Bring the database schema up to date, add the starter content to an empty database, then start
# the API. "exec" makes uvicorn the main process, so it receives stop signals from Docker.
set -eu

alembic upgrade head
if [ "${SEED_ON_START:-0}" = "1" ]; then
    python -m app.cli seed --if-empty
fi
# Development only: create the ready-made account from DEV_ADMIN_EMAIL / DEV_ADMIN_PASSWORD (if set).
python -m app.cli ensure-dev-admin || echo "The development account could not be created; see above."
# Make resized copies for any photo that lacks them (photos from older versions). A photo that
# cannot be processed must never stop the website from starting.
python -m app.cli media-reprocess || echo "Some photos could not be resized; see the lines above."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
