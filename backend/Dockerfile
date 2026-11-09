# API image: pinned dependencies, no build tools, runs as an unprivileged user.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Dependencies first, so this layer is reused until requirements.txt changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini docker-entrypoint.sh ./
RUN chmod 0555 docker-entrypoint.sh

# Uploaded photos live in volumes. "uploads" is shared with Caddy, which serves it; "originals"
# (the photos exactly as uploaded) is private to this container. Creating the folders here, owned
# by the unprivileged user, lets the new volumes inherit that ownership.
RUN mkdir -p /data/uploads /data/originals && chown 10001:10001 /data/uploads /data/originals

# Never run as root inside the container.
USER 10001:10001

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=4s --start-period=25s --retries=6 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status == 200 else 1)"]

ENTRYPOINT ["./docker-entrypoint.sh"]
