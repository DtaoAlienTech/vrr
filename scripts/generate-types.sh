#!/usr/bin/env bash
# Rewrites the website's API types from the backend's schema. Run it after changing a public
# response model (backend/app/schemas/public.py): ./scripts/generate-types.sh
set -euo pipefail
cd "$(dirname "$0")/../backend"
.venv/bin/python -m app.typegen "$@"
