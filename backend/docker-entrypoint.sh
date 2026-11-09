#!/bin/sh
# Bring the database schema up to date, add the starter content to an empty database, then start
# the API. "exec" makes uvicorn the main process, so it receives stop signals from Docker.
set -eu

alembic upgrade head
if [ "${SEED_ON_START:-0}" = "1" ]; then
    python -m app.cli seed --if-empty
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
