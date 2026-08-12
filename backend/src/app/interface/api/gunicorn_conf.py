"""Gunicorn configuration.

Referenced by ``docker/entrypoint.sh``. Everything here exists to make the
master/worker model behave correctly under a rolling deploy and to route
gunicorn's own output through our structlog pipeline instead of producing a
second, unstructured log stream.
"""

from __future__ import annotations

import os
from typing import Any

# ── worker model ──────────────────────────────────────────────────────────
worker_class = "uvicorn.workers.UvicornWorker"
worker_tmp_dir = "/dev/shm"  # noqa: S108 — gunicorn's heartbeat file; a disk-backed
# /tmp on a network filesystem makes workers appear hung and get killed.

# ── connection handling ───────────────────────────────────────────────────
# Must exceed the load balancer's idle timeout (60s on an AWS ALB). If the
# server closes a keep-alive socket the LB still considers open, the LB reuses
# it and the client sees a 502.
keepalive = 65
timeout = 30
graceful_timeout = 30

# ── worker recycling ──────────────────────────────────────────────────────
# Bounds the impact of any slow leak in a C extension. Jitter prevents every
# worker from recycling in the same second and dropping throughput to zero.
max_requests = 2000
max_requests_jitter = 200

# ── logging ───────────────────────────────────────────────────────────────
# logconfig=None: our own configure_logging() owns the root logger. Letting
# gunicorn configure logging would clobber the structlog handlers and produce
# unstructured, unscrubbed lines alongside the JSON ones.
logconfig = None
accesslog = None  # AccessLogMiddleware does this with correlation IDs
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# ── proxy ─────────────────────────────────────────────────────────────────
forwarded_allow_ips = "*"  # only reachable through our own ingress
proxy_protocol = False

preload_app = False
"""Deliberately off.

Preloading forks workers from one parent, so every worker inherits the
parent's already-created asyncio event loop objects and connection pools —
which are not fork-safe. The memory saved is not worth the class of bug it
introduces.
"""


def on_starting(server: Any) -> None:  # pragma: no cover
    server.log.info("gunicorn master starting")


def worker_int(worker: Any) -> None:  # pragma: no cover
    worker.log.info("worker received SIGINT/SIGQUIT, draining")


def child_exit(server: Any, worker: Any) -> None:  # pragma: no cover
    """Clean up this worker's Prometheus metric files.

    In multiprocess mode each worker writes its own metric file; without this
    hook, a recycled worker's file lingers forever and ``/metrics`` slowly
    accumulates series from processes that no longer exist.
    """
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
