# syntax=docker/dockerfile:1.9
#
# Multi-stage build. Three properties matter:
#
#   1. The runtime image contains no compiler, no build headers and no package
#      index. Every one of those is an attacker's toolkit if they get RCE.
#   2. Dependencies are a separate cached layer from source. Editing a Python
#      file rebuilds in seconds; only a lockfile change re-resolves deps.
#   3. The process runs as a non-root user with a read-only-friendly layout.
#      A container running as root shares the host kernel with everything else
#      on the node.

ARG PYTHON_VERSION=3.13

# ══════════════════════════════════════════════════════════════════════════
# Stage 1 — builder
# ══════════════════════════════════════════════════════════════════════════
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# build-essential and libpq-dev exist ONLY in this stage.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl

# uv resolves and installs an order of magnitude faster than pip, which is the
# difference between a 30-second and a 5-minute CI build.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /build

ENV VIRTUAL_ENV=/opt/venv
RUN uv venv "$VIRTUAL_ENV"

# Dependency layer. A stub package is enough for hatchling to build metadata,
# so this whole layer stays cached until pyproject.toml itself changes — source
# edits never trigger a dependency re-resolve.
COPY pyproject.toml ./
RUN mkdir -p src/app && touch src/app/__init__.py
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install .

# Source layer. --no-deps: everything is already installed above.
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps --force-reinstall .

# ══════════════════════════════════════════════════════════════════════════
# Stage 2 — runtime
# ══════════════════════════════════════════════════════════════════════════
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# libpq5 is the runtime library only — not libpq-dev, which pulls in headers
# and a compiler toolchain.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# A fixed non-root UID, so a volume mounted from the host has predictable
# ownership across every machine.
RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid app --shell /bin/false --create-home app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    # Malloc arena limit: without it, glibc allocates a 64 MB arena per thread
    # and a gunicorn worker's RSS looks like a leak that isn't one.
    MALLOC_ARENA_MAX=2

COPY --from=builder --chown=app:app /opt/venv /opt/venv

WORKDIR /app
COPY --from=builder --chown=app:app /build/src ./src
COPY --from=builder --chown=app:app /build/alembic ./alembic
COPY --from=builder --chown=app:app /build/alembic.ini ./
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app

EXPOSE 8000

# Hits the liveness probe, which checks nothing external — see routes/health.py
# for why a healthcheck that pings Postgres would restart the fleet during a
# database incident.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live || exit 1

# tini as PID 1: reaps zombies and forwards SIGTERM properly, which is what
# makes graceful shutdown work during a rolling deploy.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["api"]
