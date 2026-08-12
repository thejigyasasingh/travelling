"""Health and readiness probes.

Three endpoints, because Kubernetes asks three different questions and
answering them with one handler causes outages:

``/health/live`` — **"is this process wedged?"**
    Checks *nothing external*. Returns 200 if the event loop can run a
    coroutine. This is deliberate: if liveness checked Postgres, a database
    blip would make every pod fail liveness, and Kubernetes would respond by
    restarting the entire fleet — turning a recoverable database incident into
    a full outage with a cold cache. Liveness failure means "restart me"; only
    a wedged process qualifies.

``/health/ready`` — **"should traffic be routed here?"**
    Checks Postgres and Redis. Failing here removes the pod from the load
    balancer but leaves it running, so it rejoins automatically when the
    dependency recovers. This is the probe that may fail during an incident.

``/health/startup`` — **"has boot finished?"**
    Gives a slow first boot (migrations, connection warm-up) time to complete
    without the liveness probe killing it mid-way. Once it passes, Kubernetes
    stops asking.

None of these are rate limited (see the exemption in the rate-limit
middleware) and none require auth. They also return ``Cache-Control:
no-store`` — a cached readiness response would keep a dead pod in rotation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.container import Container
from app.core.logging import get_logger
from app.interface.api.deps import get_container
from app.interface.api.schemas import HealthStatus

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"], include_in_schema=False)

ContainerDep = Annotated[Container, Depends(get_container)]


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness(response: Response) -> dict[str, str]:
    """No dependency checks. See the module docstring."""
    response.headers["Cache-Control"] = "no-store"
    return {"status": "alive"}


@router.get("/ready", response_model=HealthStatus)
async def readiness(response: Response, container: ContainerDep) -> HealthStatus:
    """Checks every hard dependency, each with its own 2-second timeout.

    Returns 503 with a per-dependency breakdown when something is down, so the
    on-call engineer learns *what* is broken from the probe itself instead of
    from a bare "not ready".

    The replica is checked but is **not** disqualifying: reads degrade to the
    primary, which is slower but correct. Losing the primary or Redis is.
    """
    response.headers["Cache-Control"] = "no-store"
    checks = await container.check_dependencies()

    critical_down = [
        name for name in ("postgres", "redis") if checks.get(name, {}).get("status") != "up"
    ]

    if critical_down:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("readiness_failed", down=critical_down)
        overall = "degraded"
    elif checks.get("postgres_replica", {}).get("status") != "up":
        overall = "degraded_replica"  # still serving; reads fall back to primary
    else:
        overall = "ready"

    return HealthStatus(
        status=overall,
        version=container.settings.app_version,
        environment=container.settings.app_env.value,
        checks=checks,
    )


@router.get("/startup")
async def startup(response: Response, container: ContainerDep) -> dict[str, str]:
    """Passes once the primary database is reachable. Deliberately weaker than
    readiness: a pod should be allowed to finish booting even if Redis is still
    coming up, because it will be healthy shortly and a restart loop would not
    help."""
    response.headers["Cache-Control"] = "no-store"
    await container.database.ping()
    return {"status": "started"}
