"""ASGI entry point.

``uvicorn app.main:app`` locally; gunicorn with uvicorn workers in production
(see ``docker/entrypoint.sh``) — gunicorn supplies the process supervision,
graceful reload and worker recycling that bare uvicorn does not.

The app is created at import because an ASGI server needs a module-level
callable. Nothing expensive happens here: the container is built inside the
lifespan, so importing this module opens no connections.
"""

from __future__ import annotations

from app.interface.api.app import create_app

app = create_app()


if __name__ == "__main__":  # pragma: no cover
    # Local convenience only — `python -m app.main`. Production never takes
    # this path; it goes through gunicorn.
    import uvicorn

    from app.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.http.host,
        port=settings.http.port,
        reload=settings.app_env.value == "local",
        log_config=None,  # our structlog pipeline owns logging
        access_log=False,  # AccessLogMiddleware does this properly
        proxy_headers=True,
        forwarded_allow_ips="*",  # safe: only reachable behind our own proxy
    )
