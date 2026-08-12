"""Operational endpoints: metrics and build info.

``/metrics`` is Prometheus scrape output. It is **not** exposed publicly — the
ingress routes it only from the monitoring namespace. Application metrics leak
real information (request volume, error rates, queue depth) that is useful to
someone probing for a weak moment, and the endpoint is also expensive enough
to be a DoS target at high scrape frequency.

``/version`` exists so that "which build is actually running?" — the first
question in any incident — is answerable without shell access to a pod.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.interface.api.deps import SettingsDep

router = APIRouter(tags=["meta"], include_in_schema=False)


@router.get("/metrics")
async def metrics(settings: SettingsDep) -> Response:
    if not settings.observability.metrics_enabled:
        return Response(status_code=404)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/version")
async def version(settings: SettingsDep) -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env.value,
    }
