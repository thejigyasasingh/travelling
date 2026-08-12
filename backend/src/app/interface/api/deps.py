"""Request-scoped dependency providers.

The bridge between the process-scoped :class:`Container` and a single request.
Two lifetimes, kept strictly apart:

* **Process-scoped** — engines, Redis pools, the token service. Built once at
  boot. Read from ``request.app.state.container``, never from a module global,
  so tests can build an app with a different container and nothing else has to
  change.
* **Request-scoped** — the database session, the Unit of Work, the current
  actor. Created per request and, critically, *torn down* per request by
  FastAPI's generator dependencies. A session that outlives its request is a
  connection leak that shows up as pool exhaustion under load and never in a
  test.

The read/write session split is exposed as two distinct dependencies rather
than one parameterised dependency. Choosing the replica must be a visible
decision at the endpoint, because getting it wrong on a booking read is an
overbooking, and a boolean default is the kind of thing that gets flipped in a
hurried refactor.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthenticatedError, ValidationError
from app.core.logging import user_id_var
from app.core.security.tokens import AccessTokenClaims, TokenService
from app.infrastructure.cache.cache import RedisCache
from app.infrastructure.cache.idempotency import RedisIdempotencyStore
from app.infrastructure.database.unit_of_work import SqlUnitOfWork
from app.shared.application.use_case import Actor

# ``auto_error=False``: we raise our own UnauthenticatedError so that a missing
# token produces the same error envelope as everything else, rather than
# FastAPI's bare ``{"detail": "Not authenticated"}``.
_bearer = HTTPBearer(auto_error=False)


# ══════════════════════════════════════════════════════════════════════════
# Process-scoped
# ══════════════════════════════════════════════════════════════════════════


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


ContainerDep = Annotated[Container, Depends(get_container)]


def get_settings_dep(request: Request) -> Settings:
    """Read from ``app.state``, not from the container.

    Settings exist from the moment ``create_app`` runs; the container does not
    exist until the lifespan has connected to Postgres and Redis. Endpoints
    that only need configuration — ``/version``, ``/metrics`` — must not become
    unavailable because a dependency is still coming up.
    """
    return request.app.state.settings  # type: ignore[no-any-return]


def get_clock(container: ContainerDep) -> Clock:
    return container.clock


def get_cache(container: ContainerDep) -> RedisCache:
    return container.cache


def get_token_service(container: ContainerDep) -> TokenService:
    return container.tokens


def get_idempotency_store(container: ContainerDep) -> RedisIdempotencyStore:
    return container.idempotency


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ClockDep = Annotated[Clock, Depends(get_clock)]
CacheDep = Annotated[RedisCache, Depends(get_cache)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
#: The store was built and wired into the container from Phase 1 and used by
#: nothing until Phase 15 — `POST /bookings` required an `Idempotency-Key`,
#: validated its length, and threw it away, so a retried booking created a
#: second booking and held a second set of rooms.
IdempotencyDep = Annotated[RedisIdempotencyStore, Depends(get_idempotency_store)]


# ══════════════════════════════════════════════════════════════════════════
# Request-scoped persistence
# ══════════════════════════════════════════════════════════════════════════


async def get_write_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    """Primary connection, transaction committed on success.

    The ``async with`` in ``Database.write_session`` owns the commit/rollback,
    so an endpoint that raises after a partial write cannot leave it committed.
    """
    async with container.database.write_session() as session:
        yield session


async def get_read_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    """Replica connection. Read-only, may be up to a few hundred ms stale.

    Never use this to read data that a write in the same request depends on.
    """
    async with container.database.read_session() as session:
        yield session


async def get_uow(container: ContainerDep) -> AsyncIterator[SqlUnitOfWork]:
    """Unit of Work — the dependency a command endpoint should take.

    Prefer this over :func:`get_write_session`: it commits domain events to the
    outbox in the same transaction, which a raw session does not.
    """
    async with container.database.write_session() as session:
        uow = SqlUnitOfWork(session)
        yield uow


WriteSessionDep = Annotated[AsyncSession, Depends(get_write_session)]
ReadSessionDep = Annotated[AsyncSession, Depends(get_read_session)]
UnitOfWorkDep = Annotated[SqlUnitOfWork, Depends(get_uow)]


# ══════════════════════════════════════════════════════════════════════════
# Authentication
# ══════════════════════════════════════════════════════════════════════════


async def get_current_claims(
    request: Request,
    tokens: TokenServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AccessTokenClaims:
    """Verify the bearer token. Signature-only — no database round trip.

    That is the deliberate trade documented in ``core/security/tokens.py``:
    stateless verification keeps Redis and Postgres out of the hot path of
    every authenticated request, at the cost of revocation taking up to one
    access-token TTL to take effect.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthenticatedError

    claims = tokens.verify_access_token(credentials.credentials)

    # Bind for logging and for the rate limiter's user bucket.
    request.state.user_id = str(claims.subject)
    request.state.session_id = str(claims.session_id)
    user_id_var.set(str(claims.subject))
    return claims


async def get_optional_claims(
    request: Request,
    tokens: TokenServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AccessTokenClaims | None:
    """For endpoints that serve both anonymous and signed-in users — search
    results are personalised when we know who is asking, and still work when we
    do not. A bad token here is ignored rather than rejected, so an expired
    session degrades to anonymous browsing instead of an error wall."""
    if credentials is None:
        return None
    try:
        return await get_current_claims(request, tokens, credentials)
    except UnauthenticatedError:
        return None


def get_actor(claims: Annotated[AccessTokenClaims, Depends(get_current_claims)]) -> Actor:
    """The authenticated caller, in the shape use cases expect."""
    return Actor(
        user_id=claims.subject,
        roles=claims.roles,
        vendor_id=claims.vendor_id,
        session_id=claims.session_id,
        email_verified=claims.email_verified,
    )


def get_optional_actor(
    claims: Annotated[AccessTokenClaims | None, Depends(get_optional_claims)],
) -> Actor:
    if claims is None:
        return Actor(user_id=None)
    return Actor(
        user_id=claims.subject,
        roles=claims.roles,
        vendor_id=claims.vendor_id,
        session_id=claims.session_id,
        email_verified=claims.email_verified,
    )


ClaimsDep = Annotated[AccessTokenClaims, Depends(get_current_claims)]
ActorDep = Annotated[Actor, Depends(get_actor)]
OptionalActorDep = Annotated[Actor, Depends(get_optional_actor)]


# ══════════════════════════════════════════════════════════════════════════
# Authorisation
# ══════════════════════════════════════════════════════════════════════════


class RequireRoles:
    """Coarse, route-level gate: "is this caller an admin at all?".

    Fine-grained ownership ("is this *your* booking?") is not expressible here
    — it needs the resource, which only the use case has loaded. Doing it in a
    dependency would mean fetching the row twice, and would silently drift from
    whatever the use case actually enforces. Keep the two clearly separated:
    this checks capability, the domain checks ownership.
    """

    def __init__(self, *roles: str) -> None:
        self.roles = frozenset(roles)

    def __call__(self, actor: ActorDep) -> Actor:
        if not actor.has_role(*self.roles):
            raise ForbiddenError(
                "This action requires elevated permissions.",
                details={"required_roles": sorted(self.roles)},
            )
        return actor


require_admin = RequireRoles("admin", "superadmin")
require_vendor = RequireRoles("vendor", "admin", "superadmin")
require_support = RequireRoles("support", "admin", "superadmin")


def get_vendor_scope(actor: ActorDep) -> uuid.UUID:
    """The vendor a vendor-user may act for.

    Read from the token, never from a request parameter. A ``vendor_id`` in the
    body or path is caller-controlled, and trusting it is a one-line
    cross-tenant data breach.
    """
    if actor.vendor_id is None:
        raise ForbiddenError("This account is not linked to a vendor.")
    return actor.vendor_id


# ══════════════════════════════════════════════════════════════════════════
# Idempotency
# ══════════════════════════════════════════════════════════════════════════


def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    """Optional here; required by the endpoints that create money or inventory
    (see the booking and payment routers), where a missing key is rejected
    outright rather than defaulted."""
    if idempotency_key is None:
        return None
    key = idempotency_key.strip()
    if not 8 <= len(key) <= 128:
        raise ValidationError("Idempotency-Key must be between 8 and 128 characters")
    return key
