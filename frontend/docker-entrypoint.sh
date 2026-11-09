#!/bin/sh
# Build the site from the live API when the code is new, then serve it.
# "exec" makes the server the main process, so it receives stop signals from Docker.
set -eu

want="$(cat SOURCE_HASH)"
have="$(cat .next/SOURCE_HASH 2>/dev/null || true)"

if [ "$want" != "$have" ]; then
    echo "Building the website from the live API (the first start takes a few minutes)..."
    find .next -mindepth 1 -delete
    node_modules/.bin/next build
    printf '%s' "$want" > .next/SOURCE_HASH
else
    echo "Using the saved website build."
fi

exec node_modules/.bin/next start --hostname 0.0.0.0 --port 3000
