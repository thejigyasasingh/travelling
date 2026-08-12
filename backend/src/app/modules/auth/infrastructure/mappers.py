"""Translation between ORM rows and domain entities.

Hand-written, not automatic. The value is precisely that it is explicit: adding
a column does not silently appear on the aggregate, and renaming a domain
attribute does not silently change the schema. When the two shapes need to
diverge — and they will — this file is where that is negotiated.

Both directions are here so the round trip is visible in one place. A field
mapped one way and forgotten the other is the classic "the value saved fine but
comes back None" bug, and side-by-side functions make it obvious.
"""

from __future__ import annotations

from app.modules.auth.domain.entities import Session, SignupMethod, User, UserStatus
from app.modules.auth.domain.rbac import DEFAULT_ROLE, Role
from app.modules.auth.domain.value_objects import Email, PhoneNumber
from app.modules.auth.infrastructure.models import SessionModel, UserModel


def _parse_roles(names: list[str] | None) -> frozenset[Role]:
    """Unknown role strings are dropped, not raised on.

    A role removed from the catalogue while rows still reference it must not
    make those users unloadable — they should simply lose that capability,
    which fails safe. Raising here would take the login endpoint down for
    everyone holding the retired role.
    """
    if not names:
        return frozenset({DEFAULT_ROLE})
    parsed = set()
    for name in names:
        try:
            parsed.add(Role(name))
        except ValueError:
            continue
    return frozenset(parsed) or frozenset({DEFAULT_ROLE})


def user_to_domain(row: UserModel) -> User:
    return User(
        entity_id=row.id,
        email=Email(row.email.lower()),
        password_hash=row.password_hash,
        full_name=row.full_name,
        phone=PhoneNumber(row.phone_e164) if row.phone_e164 else None,
        status=UserStatus(row.status),
        roles=_parse_roles(row.roles),
        signup_method=SignupMethod(row.signup_method),
        locale=row.locale,
        timezone=row.timezone,
        avatar_url=row.avatar_url,
        vendor_id=row.vendor_id,
        email_verified_at=row.email_verified_at,
        phone_verified_at=row.phone_verified_at,
        password_changed_at=row.password_changed_at,
        last_login_at=row.last_login_at,
        failed_login_attempts=row.failed_login_attempts,
        lockout_level=row.lockout_level,
        locked_until=row.locked_until,
        suspension_reason=row.suspension_reason,
        version=row.version,
    )


def user_to_model(user: User) -> UserModel:
    """New rows only. Existing rows go through :func:`apply_user_to_model`."""
    return UserModel(
        id=user.id,
        email=str(user.email),
        password_hash=user.password_hash,
        full_name=user.full_name,
        phone_e164=str(user.phone) if user.phone else None,
        status=user.status.value,
        roles=sorted(user.role_names),
        signup_method=user.signup_method.value,
        locale=user.locale,
        timezone=user.timezone,
        avatar_url=user.avatar_url,
        vendor_id=user.vendor_id,
        email_verified_at=user.email_verified_at,
        phone_verified_at=user.phone_verified_at,
        password_changed_at=user.password_changed_at,
        last_login_at=user.last_login_at,
        failed_login_attempts=user.failed_login_attempts,
        lockout_level=user.lockout_level,
        locked_until=user.locked_until,
        suspension_reason=user.suspension_reason,
    )


def apply_user_to_model(user: User, row: UserModel) -> None:
    """Copy mutable state back onto a row already in the session.

    Assignment, not merge: the row is attached to the session, so SQLAlchemy's
    change tracking turns these into an UPDATE at flush. ``id``, ``created_at``
    and ``version`` are deliberately absent — the first two are immutable and
    the third is the ORM's to increment, which is what makes the optimistic
    lock work.
    """
    row.email = str(user.email)
    row.password_hash = user.password_hash
    row.full_name = user.full_name
    row.phone_e164 = str(user.phone) if user.phone else None
    row.status = user.status.value
    row.roles = sorted(user.role_names)
    row.locale = user.locale
    row.timezone = user.timezone
    row.avatar_url = user.avatar_url
    row.vendor_id = user.vendor_id
    row.email_verified_at = user.email_verified_at
    row.phone_verified_at = user.phone_verified_at
    row.password_changed_at = user.password_changed_at
    row.last_login_at = user.last_login_at
    row.failed_login_attempts = user.failed_login_attempts
    row.lockout_level = user.lockout_level
    row.locked_until = user.locked_until
    row.suspension_reason = user.suspension_reason


def session_to_domain(row: SessionModel) -> Session:
    return Session(
        entity_id=row.id,
        user_id=row.user_id,
        family_id=row.family_id,
        token_hash=row.token_hash,
        issued_at=row.issued_at,
        expires_at=row.expires_at,
        parent_id=row.parent_id,
        rotated_at=row.rotated_at,
        revoked_at=row.revoked_at,
        revoked_reason=row.revoked_reason,
        last_used_at=row.last_used_at,
        ip_hash=row.ip_hash,
        user_agent=row.user_agent,
        device_label=row.device_label,
    )


def session_to_model(session: Session) -> SessionModel:
    return SessionModel(
        id=session.id,
        user_id=session.user_id,
        family_id=session.family_id,
        parent_id=session.parent_id,
        token_hash=session.token_hash,
        issued_at=session.issued_at,
        expires_at=session.expires_at,
        rotated_at=session.rotated_at,
        revoked_at=session.revoked_at,
        revoked_reason=session.revoked_reason,
        last_used_at=session.last_used_at,
        ip_hash=session.ip_hash,
        user_agent=session.user_agent,
        device_label=session.device_label,
    )


def apply_session_to_model(session: Session, row: SessionModel) -> None:
    row.rotated_at = session.rotated_at
    row.revoked_at = session.revoked_at
    row.revoked_reason = session.revoked_reason
    row.last_used_at = session.last_used_at
