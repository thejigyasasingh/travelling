"""Operational CLI.

Everything here is a task an engineer would otherwise do by pasting SQL into a
production console at 2am. Making them commands means they are code-reviewed,
logged, and run the same way every time.

The CLI is a *second interface over the same use cases* — it never reaches
around the application layer into the database. That is the whole payoff of
clean architecture: ``create-admin`` runs the same validation, hashing and
audit-event recording that the HTTP endpoint would.

Uses argparse rather than typer/click: three commands do not justify a
dependency, and this file has no reason to grow much beyond them.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable

from app.container import Container, get_container
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.interface.cli.seed import cmd_seed

logger = get_logger("cli")


async def cmd_healthcheck(_: argparse.Namespace, container: Container) -> int:
    """Also used as the Docker HEALTHCHECK for worker containers, which have no
    HTTP port to probe."""
    checks = await container.check_dependencies()
    for name, result in checks.items():
        status = result.get("status")
        marker = "ok " if status == "up" else "FAIL"
        sys.stdout.write(f"{marker} {name:20s} {result.get('latency_ms', '-')}ms\n")
    down = [n for n, r in checks.items() if r.get("status") != "up" and n != "postgres_replica"]
    return 1 if down else 0


async def cmd_show_config(_: argparse.Namespace, container: Container) -> int:
    """Print the effective configuration with secrets masked.

    "Which config is this pod actually running?" is a question that otherwise
    gets answered by guessing at the deployment manifest. Pydantic's
    ``SecretStr`` masks itself on repr, so this is safe to run and paste.
    """
    settings = container.settings
    sys.stdout.write(settings.model_dump_json(indent=2) + "\n")
    return 0


async def cmd_relay_outbox(args: argparse.Namespace, container: Container) -> int:
    """Drain the outbox manually.

    For the case where Celery Beat was down and a backlog accumulated — the
    events are safe in Postgres, they just need pushing.
    """
    from app.infrastructure.queue.outbox_relay import relay_batch

    total = 0
    while True:
        async with container.database.write_session() as session:
            sent = await relay_batch(session, batch_size=args.batch_size)
        total += sent
        if sent == 0 or (args.limit and total >= args.limit):
            break
    sys.stdout.write(f"relayed {total} events\n")
    return 0


COMMANDS: dict[str, Callable[[argparse.Namespace, Container], Awaitable[int]]] = {
    "healthcheck": cmd_healthcheck,
    "show-config": cmd_show_config,
    "relay-outbox": cmd_relay_outbox,
    "seed": cmd_seed,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rw", description="Roaming & Wandering operations CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("healthcheck", help="Verify every dependency; exit non-zero if any is down")
    sub.add_parser("show-config", help="Print effective configuration (secrets masked)")

    sub.add_parser("seed", help="Create development accounts and a demo listing (local/test only)")

    relay = sub.add_parser("relay-outbox", help="Drain pending outbox events")
    relay.add_argument("--batch-size", type=int, default=100)
    relay.add_argument("--limit", type=int, default=0, help="0 = drain everything")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(get_settings())

    async def _run() -> int:
        container = await get_container()
        try:
            return await COMMANDS[args.command](args, container)
        finally:
            await container.shutdown()

    return asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
