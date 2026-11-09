#!/bin/sh
# Bring the database schema up to date, then start the API.
# "exec" makes uvicorn the main process, so it receives stop signals from Docker.
set -eu

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
