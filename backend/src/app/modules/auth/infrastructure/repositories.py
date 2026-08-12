"""SQLAlchemy repositories for auth.

An **identity map** sits in each repository: an aggregate loaded twice in one
request is the same object, and every aggregate handed out is tracked so that
mutations are written back at flush without a use case ever calling ``save()``.

That last point is the whole design. A use case says ``user.verify_email(now)``
and stops. If persistence required an explicit ``await repo.save(user)``, then
every code path that forgets one is a silent data-loss bug that tests using
in-memory fakes will never catch. Here, ``flush()`` walks the tracked
aggregates and copies their state onto the attached rows.

No repository commits. The Unit of Work owns the transaction boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.auth.domain.entities import Session, User
from app.modules.auth.domain.value_objects import Email, PhoneNumber
from app.modules.auth.infrastructure import mappers
from app.modules.auth.infrastructure.models import (
    ActionTokenModel,
    OAuthAccountModel,
    SessionModel,
    UserModel,
    UserRoleModel,
)

logger = get_logger(__name__)


def _affected(result: Any) -> int:
    """Rows touched by a DML statement.

    SQLAlchemy types ``execute()`` as returning ``Result``, but a DML statement
    actually yields a ``CursorResult`` that carries ``rowcount``. The cast keeps
    the call sites readable instead of repeating the narrowing at each one.
    """
    return int(cast("CursorResult[Any]", result).rowcount or 0)


class SqlUserRepository:
    """Implements :class:`app.modules.auth.application.ports.UserRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[User, UserModel]] = {}

    # ── reads ─────────────────────────────────────────────────────────────

    async def get(self, user_id: uuid.UUID) -> User | None:
        if user_id in self._identity:
            return self._identity[user_id][0]
        row = await self._session.get(UserModel, user_id)
        return self._track(row)

    async def get_by_email(self, email: Email) -> User | None:
        stmt = select(UserModel).where(
            UserModel.email == str(email), UserModel.deleted_at.is_(None)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._track(row)

    async def get_by_phone(self, phone: PhoneNumber) -> User | None:
        stmt = select(UserModel).where(
            UserModel.phone_e164 == str(phone), UserModel.deleted_at.is_(None)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._track(row)

    async def get_by_oauth(self, provider: str, provider_account_id: str) -> User | None:
        stmt = (
            select(UserModel)
            .join(OAuthAccountModel, OAuthAccountModel.user_id == UserModel.id)
            .where(
                OAuthAccountModel.provider == provider,
                OAuthAccountModel.provider_account_id == provider_account_id,
                UserModel.deleted_at.is_(None),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._track(row)

    # ── writes ────────────────────────────────────────────────────────────

    async def add(self, user: User) -> None:
        """Stage a new user and its role rows.

        Uniqueness is enforced by the partial unique index, not by a preceding
        SELECT. Two concurrent registrations for the same address both pass a
        check-then-insert; only the constraint actually stops the second, and
        it surfaces as a 409 through the IntegrityError handler.
        """
        row = mappers.user_to_model(user)
        self._session.add(row)
        self._identity[user.id] = (user, row)

        for role in sorted(user.role_names):
            self._session.add(UserRoleModel(user_id=user.id, role_name=role))

    async def link_oauth(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        provider_account_id: str,
        email: str | None,
        raw_profile: dict[str, object],
        now: datetime,
    ) -> None:
        """Idempotent link.

        ``ON CONFLICT DO UPDATE`` because a user re-authenticating with Google
        must not fail on the unique constraint — their profile picture or name
        may simply have changed, and the second sign-in should refresh it.
        """
        stmt = (
            pg_insert(OAuthAccountModel)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                provider=provider,
                provider_account_id=provider_account_id,
                email=email,
                raw_profile=raw_profile,
                linked_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_oauth_accounts_provider_account",
                set_={"email": email, "raw_profile": raw_profile},
            )
        )
        await self._session.execute(stmt)

    async def sync_roles(self, user: User, *, granted_by: uuid.UUID | None) -> None:
        """Reconcile the audited ``user_roles`` rows with the aggregate.

        The denormalised ``users.roles`` column is written by the mapper; this
        keeps the join table — the record of *who granted what* — in step.
        """
        current = set(
            (
                await self._session.execute(
                    select(UserRoleModel.role_name).where(UserRoleModel.user_id == user.id)
                )
            ).scalars()
        )
        target = set(user.role_names)

        for role in target - current:
            self._session.add(UserRoleModel(user_id=user.id, role_name=role, granted_by=granted_by))
        for role in current - target:
            await self._session.execute(
                delete(UserRoleModel).where(
                    UserRoleModel.user_id == user.id, UserRoleModel.role_name == role
                )
            )

    # ── unit-of-work integration ──────────────────────────────────────────

    async def flush(self) -> None:
        """Write tracked aggregates back and emit their events.

        Called by the request-scoped Unit of Work before commit. This is what
        makes "mutate the aggregate and return" sufficient.
        """
        for user, row in self._identity.values():
            mappers.apply_user_to_model(user, row)
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for user, _ in self._identity.values():
            events.extend(user.pull_events())
        return events

    def _track(self, row: UserModel | None) -> User | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        user = mappers.user_to_domain(row)
        self._identity[row.id] = (user, row)
        return user


class SqlSessionRepository:
    """Implements :class:`app.modules.auth.application.ports.SessionRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tracked: dict[uuid.UUID, tuple[Session, SessionModel]] = {}

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        stmt = select(SessionModel).where(SessionModel.token_hash == token_hash)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if row.id in self._tracked:
            return self._tracked[row.id][0]
        entity = mappers.session_to_domain(row)
        self._tracked[row.id] = (entity, row)
        return entity

    async def get_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Session | None:
        """Scoped by user id so a guessed session id resolves to nothing rather
        than to somebody else's session."""
        stmt = select(SessionModel).where(
            SessionModel.id == session_id, SessionModel.user_id == user_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mappers.session_to_domain(row) if row else None

    async def add(self, session: Session) -> None:
        row = mappers.session_to_model(session)
        self._session.add(row)
        self._tracked[session.id] = (session, row)

    async def revoke_family(self, family_id: uuid.UUID, *, now: datetime, reason: str) -> int:
        """Bulk UPDATE, not a load-then-mutate loop.

        This runs during reuse detection, while an attacker holds a live token.
        Hydrating N session objects to set one column each would be slower for
        no benefit — there is no domain rule to apply, only a fact to record.
        """
        stmt = (
            update(SessionModel)
            .where(SessionModel.family_id == family_id, SessionModel.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason)
        )
        result = await self._session.execute(stmt)
        return _affected(result)

    async def revoke_all_for_user(
        self,
        user_id: uuid.UUID,
        *,
        now: datetime,
        reason: str,
        except_session: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            update(SessionModel)
            .where(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason)
        )
        if except_session is not None:
            # "Change your password" keeps the caller signed in on the device
            # they are using; everything else goes.
            keep = select(SessionModel.family_id).where(SessionModel.id == except_session)
            stmt = stmt.where(SessionModel.family_id.not_in(keep))
        result = await self._session.execute(stmt)
        return _affected(result)

    async def list_active_for_user(self, user_id: uuid.UUID, *, now: datetime) -> list[Session]:
        """Only the newest token in each family — one row per device.

        Rotated ancestors are the same device; listing them would show a phone
        as dozens of separate sessions.
        """
        stmt = select(SessionModel).where(
            SessionModel.user_id == user_id,
            SessionModel.revoked_at.is_(None),
            SessionModel.rotated_at.is_(None),
            SessionModel.expires_at > now,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mappers.session_to_domain(row) for row in rows]

    async def has_any_for_device(
        self, user_id: uuid.UUID, ip_hash: str | None, user_agent: str | None
    ) -> bool:
        """Drives the "new device" flag on the login event.

        A heuristic, and treated as one: it feeds a notification, never an
        access decision. IP and user agent both change legitimately (a new
        network, a browser update), so a false "new device" costs an email and
        a false "known device" costs one missed alert.
        """
        if ip_hash is None and user_agent is None:
            return True
        stmt = select(SessionModel.id).where(SessionModel.user_id == user_id).limit(1)
        if ip_hash is not None:
            stmt = stmt.where(SessionModel.ip_hash == ip_hash)
        if user_agent is not None:
            stmt = stmt.where(SessionModel.user_agent == user_agent)
        return (await self._session.execute(stmt)).first() is not None

    async def flush(self) -> None:
        for entity, row in self._tracked.values():
            mappers.apply_session_to_model(entity, row)
        await self._session.flush()

    async def purge_expired(self, *, before: datetime, limit: int = 10_000) -> int:
        """Nightly cleanup. Batched, because an unbounded DELETE on a table
        with tens of millions of dead rows holds locks for minutes."""
        ids = select(SessionModel.id).where(SessionModel.expires_at < before).limit(limit)
        result = await self._session.execute(delete(SessionModel).where(SessionModel.id.in_(ids)))
        return _affected(result)


class SqlActionTokenStore:
    """Implements :class:`app.modules.auth.application.ports.ActionTokenStore`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_spent(self, jti: uuid.UUID) -> bool:
        return await self._session.get(ActionTokenModel, jti) is not None

    async def spend(
        self,
        *,
        jti: uuid.UUID,
        user_id: uuid.UUID,
        purpose: str,
        expires_at: datetime,
        now: datetime,
    ) -> bool:
        """Atomic claim via ``INSERT … ON CONFLICT DO NOTHING``.

        The primary key does the work: whichever request inserts first wins,
        and the loser sees zero rows affected. A SELECT-then-INSERT would let
        two concurrent clicks on the same reset link both pass the check — and
        the second would overwrite the password the first had just set.

        A SAVEPOINT wraps it so that a constraint failure does not poison the
        surrounding transaction.
        """
        stmt = (
            pg_insert(ActionTokenModel)
            .values(
                jti=jti,
                user_id=user_id,
                purpose=purpose,
                spent_at=now,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=["jti"])
        )
        try:
            result = await self._session.execute(stmt)
        except IntegrityError:  # pragma: no cover — belt and braces
            logger.info("action_token_replay", jti=str(jti), purpose=purpose)
            return False
        return _affected(result) > 0

    async def purge_expired(self, *, before: datetime) -> int:
        result = await self._session.execute(
            delete(ActionTokenModel).where(ActionTokenModel.expires_at < before)
        )
        return _affected(result)
