# Website image.
#
# The pages are built from the live API (content comes from the database), so the build cannot run
# while the image is built: the backend is not running yet. Instead the container builds the site
# when it starts, after the backend is healthy (docker-entrypoint.sh). The result is kept in a
# volume, so a normal restart is fast; it is rebuilt only when this code changes.
FROM node:24-slim

ENV NEXT_TELEMETRY_DISABLED=1
# /app belongs to the unprivileged "node" user, so nothing here runs as root.
RUN mkdir /app && chown node:node /app
USER node
WORKDIR /app

COPY --chown=node:node package.json package-lock.json ./
RUN npm ci

COPY --chown=node:node . .
# Fingerprint of the code. The saved build is reused only while it matches.
RUN find . -path ./node_modules -prune -o -type f ! -name SOURCE_HASH -print0 \
      | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 > SOURCE_HASH \
    && mkdir -p .next && chmod 0555 docker-entrypoint.sh

EXPOSE 3000
# The first start builds the site, which takes a few minutes: no failures are counted until then.
HEALTHCHECK --interval=15s --timeout=4s --start-period=600s --retries=6 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

ENTRYPOINT ["./docker-entrypoint.sh"]
