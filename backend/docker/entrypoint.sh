#!/usr/bin/env bash
#
# Container entrypoint. One image, several roles, selected by argument:
#
#   api      — gunicorn + uvicorn workers (the HTTP service)
#   worker   — Celery worker; QUEUES selects which queues it serves
#   beat     — Celery Beat scheduler (exactly ONE per environment)
#   migrate  — run migrations and exit (init container / one-shot job)
#   shell    — python REPL with the app importable
#
# Building one image per role would mean five images to scan, sign and keep in
# sync. One image with a role argument is a single artifact whose exact bytes
# ran in staging before they ran in production.

set -euo pipefail

ROLE="${1:-api}"
shift || true

log() { printf '[entrypoint] %s\n' "$*" >&2; }

# ── graceful shutdown ─────────────────────────────────────────────────────
# The orchestrator sends SIGTERM, waits `terminationGracePeriodSeconds`, then
# SIGKILLs. Forwarding the signal to the actual child is what lets in-flight
# requests finish; without it, every rolling deploy drops live connections.
_child_pid=""
_forward() {
    log "received signal, forwarding to ${_child_pid}"
    [[ -n "$_child_pid" ]] && kill -TERM "$_child_pid" 2>/dev/null || true
    wait "$_child_pid" 2>/dev/null || true
}
trap _forward SIGTERM SIGINT

run() {
    "$@" &
    _child_pid=$!
    wait "$_child_pid"
}

case "$ROLE" in

  api)
    # gunicorn supervises; uvicorn workers do the ASGI work. Bare uvicorn has
    # no worker recycling and no clean master-process reload.
    #
    # WEB_CONCURRENCY defaults to (2 x cores) + 1 for a mixed I/O workload.
    # Set it explicitly in Kubernetes: the container sees the *node's* core
    # count, not its CPU limit, so autodetection over-forks badly.
    : "${WEB_CONCURRENCY:=$(( $(nproc) * 2 + 1 ))}"
    log "starting API with ${WEB_CONCURRENCY} workers"
    run gunicorn app.main:app \
        --worker-class uvicorn.workers.UvicornWorker \
        --workers "${WEB_CONCURRENCY}" \
        --bind "0.0.0.0:${HTTP__PORT:-8000}" \
        --timeout 30 \
        --graceful-timeout 30 \
        --keep-alive 65 `# must exceed the ALB idle timeout, or the LB reuses a socket we just closed` \
        --max-requests 2000 \
        --max-requests-jitter 200 `# stagger recycling so workers do not all restart together` \
        --access-logfile - \
        --error-logfile - \
        --logger-class gunicorn.glogging.Logger \
        --config python:app.interface.api.gunicorn_conf \
        "$@"
    ;;

  worker)
    : "${QUEUES:=default}"
    : "${CELERY__WORKER_CONCURRENCY:=4}"
    log "starting Celery worker on queues: ${QUEUES}"
    run celery -A app.infrastructure.queue.celery_app.celery_app worker \
        --queues "${QUEUES}" \
        --concurrency "${CELERY__WORKER_CONCURRENCY}" \
        --prefetch-multiplier 1 \
        --max-tasks-per-child 1000 \
        --loglevel INFO \
        --without-gossip --without-mingle `# both are chatty and useless below ~50 workers` \
        "$@"
    ;;

  beat)
    # EXACTLY ONE of these per environment. Two Beat processes double every
    # scheduled task — including the payout run.
    log "starting Celery Beat"
    run celery -A app.infrastructure.queue.celery_app.celery_app beat \
        --loglevel INFO \
        --schedule /tmp/celerybeat-schedule \
        "$@"
    ;;

  migrate)
    # Runs as a Kubernetes init container or a one-shot Job — never from the
    # API container. Concurrent migrations from N booting pods is how a schema
    # ends up half-applied; Alembic's advisory lock helps, but not racing at
    # all is better.
    log "running migrations"
    alembic upgrade head
    log "migrations complete"
    ;;

  shell)
    exec python
    ;;

  *)
    # Escape hatch: `docker run <image> alembic history`, etc.
    exec "$ROLE" "$@"
    ;;
esac
