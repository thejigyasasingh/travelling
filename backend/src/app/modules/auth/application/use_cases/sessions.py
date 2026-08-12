"""Session management — "where you're signed in", and ending one remotely.

Worth having for its own sake: it is the only way a user who lost a phone can
act before we notice anything is wrong. It is also the user-visible payoff of
storing refresh tokens as rows rather than making them stateless.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.auth.application.dto import SessionInfo
from app.modules.auth.application.ports import SessionRepository
from app.modules.auth.domain import errors
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)


@dataclass(slots=True)
class ListSessionsUseCase:
    sessions: SessionRepository
    clock: Clock

    async def execute(self, _: None, actor: Actor) -> list[SessionInfo]:
        """Live sessions for the caller, newest first.

        Only the *newest* token in each family is returned — the rotated
        ancestors are the same device and would otherwise show as dozens of
        entries per phone.
        """
        if actor.user_id is None:  # pragma: no cover — route requires auth
            raise errors.InvalidCredentialsError

        now = self.clock.now()
        rows = await self.sessions.list_active_for_user(actor.user_id, now=now)

        return [
            SessionInfo(
                id=row.id,
                device_label=row.device_label,
                user_agent=row.user_agent,
                created_at=row.issued_at,
                last_used_at=row.last_used_at,
                expires_at=row.expires_at,
                # Lets the UI render "this device" and warn before someone
                # signs themselves out of the browser they are looking at.
                is_current=row.id == actor.session_id,
            )
            for row in sorted(rows, key=lambda r: r.issued_at, reverse=True)
        ]


@dataclass(slots=True)
class RevokeSessionUseCase:
    sessions: SessionRepository
    clock: Clock

    async def execute(self, session_id: uuid.UUID, actor: Actor) -> None:
        """End one session by id.

        The lookup is scoped to the caller's own user id, so a guessed or
        leaked session id belonging to someone else resolves to "not found"
        rather than revoking a stranger's session.

        Revokes the whole family: the target device may have rotated since the
        list was rendered, and revoking only the row the user clicked would
        leave the newer token working.
        """
        if actor.user_id is None:  # pragma: no cover
            raise errors.InvalidCredentialsError

        session = await self.sessions.get_for_user(session_id, actor.user_id)
        if session is None:
            raise EntityNotFoundError("Session", session_id)

        revoked = await self.sessions.revoke_family(
            session.family_id, now=self.clock.now(), reason="revoked_by_user"
        )
        logger.info(
            "session_revoked_by_user",
            user_id=str(actor.user_id),
            session_id=str(session_id),
            sessions_revoked=revoked,
        )
