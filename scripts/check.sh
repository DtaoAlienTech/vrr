#!/usr/bin/env bash
# Runs every check the CI runs. Use before each commit: ./scripts/check.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== backend: ruff (lint + format)"
(cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .)

echo "== backend: website API types are up to date"
(cd backend && .venv/bin/python -m app.typegen --check)

echo "== backend: tests"
(cd backend && .venv/bin/pytest -q)

echo "== frontend: eslint"
(cd frontend && npm run --silent lint)

echo "== frontend: typecheck"
(cd frontend && npm run --silent typecheck)

echo "== frontend: tests"
(cd frontend && npm test --silent)

echo
echo "All checks passed."
