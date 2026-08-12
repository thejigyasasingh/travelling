"""Refresh-token rotation and reuse detection.

The most security-critical mechanism in the module. A refresh token lives 30
days on a device we do not control; if it leaks, signature checks cannot help
because the token *is* valid. Rotation plus reuse detection is what converts a
silent month-long compromise into one failed request and an alert.

The grace window is the part that makes it survivable in production: a mobile
client that loses a response looks exactly like a replay, and treating that as
theft would log out honest users constantly and bury the real signal.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.auth.domain import errors
from app.modules.auth.domain.entities import Session, _WithinRotationGrace

pytestmark = pytest.mark.unit

NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
GRACE = 10


def make_session(**kw: object) -> Session:
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "token_hash": "a" * 64,
        "family_id": uuid.uuid4(),
        "issued_at": NOW,
        "expires_at": NOW + timedelta(days=30),
    }
    return Session.start(**{**defaults, **kw})  # type: ignore[arg-type]


class TestUsability:
    def test_a_fresh_session_is_usable(self) -> None:
        make_session().assert_usable(NOW, grace_seconds=GRACE)

    def test_expired_session_is_rejected(self) -> None:
        session = make_session(expires_at=NOW - timedelta(seconds=1))
        with pytest.raises(errors.SessionExpiredError):
            session.assert_usable(NOW, grace_seconds=GRACE)

    def test_revoked_session_is_rejected(self) -> None:
        session = make_session()
        session.revoke(now=NOW, reason="user_logout")
        with pytest.raises(errors.SessionExpiredError):
            session.assert_usable(NOW, grace_seconds=GRACE)

    def test_revoking_twice_keeps_the_first_reason(self) -> None:
        # The first reason is the interesting one — "token_reuse_detected"
        # must not be overwritten by a later "user_logout".
        session = make_session()
        session.revoke(now=NOW, reason="token_reuse_detected")
        session.revoke(now=NOW + timedelta(minutes=1), reason="user_logout")
        assert session.revoked_reason == "token_reuse_detected"


class TestRotation:
    def test_rotation_produces_a_linked_successor(self) -> None:
        parent = make_session()
        child = parent.rotate(new_token_hash="b" * 64, now=NOW, expires_at=NOW + timedelta(days=30))
        assert child.parent_id == parent.id
        assert child.family_id == parent.family_id
        assert child.token_hash != parent.token_hash

    def test_the_parent_is_marked_spent_not_deleted(self) -> None:
        # A deleted parent cannot be recognised on replay — the lookup would
        # simply miss, and the theft would go undetected.
        parent = make_session()
        parent.rotate(new_token_hash="b" * 64, now=NOW, expires_at=NOW + timedelta(days=30))
        assert parent.is_rotated
        assert parent.rotated_at == NOW

    def test_device_details_carry_forward(self) -> None:
        parent = make_session(device_label="Priya's iPhone", user_agent="RW-iOS/2.1")
        child = parent.rotate(new_token_hash="b" * 64, now=NOW, expires_at=NOW + timedelta(days=30))
        assert child.device_label == "Priya's iPhone"
        assert child.user_agent == "RW-iOS/2.1"

    def test_a_changed_ip_updates_the_successor(self) -> None:
        parent = make_session(ip_hash="old")
        child = parent.rotate(
            new_token_hash="b" * 64,
            now=NOW,
            expires_at=NOW + timedelta(days=30),
            ip_hash="new",
        )
        assert child.ip_hash == "new"


class TestReuseDetection:
    def test_replaying_a_spent_token_is_treated_as_theft(self) -> None:
        parent = make_session()
        parent.rotate(new_token_hash="b" * 64, now=NOW, expires_at=NOW + timedelta(days=30))

        # Well past the grace window: the legitimate client holds the newest
        # token, so anyone presenting this one is not the legitimate client.
        later = NOW + timedelta(seconds=GRACE + 1)
        with pytest.raises(errors.RefreshTokenReuseError) as exc:
            parent.assert_usable(later, grace_seconds=GRACE)
        assert exc.value.details["family_id"] == str(parent.family_id)

    def test_replay_inside_the_grace_window_is_a_lost_response(self) -> None:
        """A phone on a flaky connection rotates, loses the response, retries.

        Indistinguishable from a replay by signature alone. Without this
        window, every dropped connection logs the user out and raises a false
        security alert — which is how a real alert gets ignored.
        """
        parent = make_session()
        parent.rotate(new_token_hash="b" * 64, now=NOW, expires_at=NOW + timedelta(days=30))

        with pytest.raises(_WithinRotationGrace):
            parent.assert_usable(NOW + timedelta(seconds=GRACE - 1), grace_seconds=GRACE)

    def test_the_grace_boundary_is_inclusive(self) -> None:
        parent = make_session()
        parent.rotate(new_token_hash="b" * 64, now=NOW, expires_at=NOW + timedelta(days=30))
        with pytest.raises(_WithinRotationGrace):
            parent.assert_usable(NOW + timedelta(seconds=GRACE), grace_seconds=GRACE)

    def test_grace_never_applies_to_a_revoked_token(self) -> None:
        # Once the family is burned, nothing in it comes back — including the
        # token that was rotated moments before the theft was noticed.
        parent = make_session()
        parent.rotate(new_token_hash="b" * 64, now=NOW, expires_at=NOW + timedelta(days=30))
        parent.revoke(now=NOW, reason="token_reuse_detected")
        with pytest.raises(errors.SessionExpiredError):
            parent.assert_usable(NOW + timedelta(seconds=1), grace_seconds=GRACE)

    def test_a_long_chain_keeps_one_family(self) -> None:
        # Family identity is what makes "revoke everything descended from this
        # sign-in" a single indexed UPDATE.
        session = make_session()
        family = session.family_id
        moment = NOW
        for i in range(20):
            moment += timedelta(hours=1)
            session = session.rotate(
                new_token_hash=f"{i:064d}", now=moment, expires_at=moment + timedelta(days=30)
            )
        assert session.family_id == family
        session.assert_usable(moment, grace_seconds=GRACE)
