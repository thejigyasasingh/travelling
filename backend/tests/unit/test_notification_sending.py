"""Sending one notification: ordering, idempotency, and what gets recorded.

The interesting behaviour is not "does it send" — it is what happens around
the send:

* a redelivered event must not produce a second mail;
* a message that cannot be built must fail **permanently**, not five times;
* a transport failure must fail **transiently**, so Celery retries it;
* a token must never reach the notification log.

Each of those is a different row in the `notifications` table and a different
outcome for the person waiting, so each has a test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.clock import FrozenClock
from app.modules.notification.application.use_cases import SendNotificationUseCase
from app.modules.notification.domain import templates

pytestmark = pytest.mark.unit

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

CTX = {
    "user_id": "019feb81-2ac3-7413-841b-590fb56b7157",
    "email": "guest@example.com",
    "token": "tok-secret-value",
    "expires_in_seconds": 86_400,
    "locale": "en",
}


class FakeLog:
    """The notification table, in memory.

    `claim` models the unique index on `dedupe_key` — which is the entire
    once-only guarantee, so a fake that let two claims through would make the
    duplicate test pass for the wrong reason.
    """

    def __init__(self) -> None:
        self.claimed: dict[str, uuid.UUID] = {}
        self.rows: dict[uuid.UUID, dict[str, Any]] = {}

    async def claim(
        self, *, dedupe_key: str, context: dict[str, Any], **kwargs: Any
    ) -> uuid.UUID | None:
        if dedupe_key in self.claimed:
            return None
        notification_id = uuid.uuid4()
        self.claimed[dedupe_key] = notification_id
        self.rows[notification_id] = {"status": "queued", "context": context, **kwargs}
        return notification_id

    async def mark_sent(self, notification_id: uuid.UUID, **kwargs: Any) -> None:
        self.rows[notification_id] |= {"status": "sent", **kwargs}

    async def mark_failed(self, notification_id: uuid.UUID, **kwargs: Any) -> None:
        self.rows[notification_id] |= {"status": "failed", **kwargs}

    async def mark_suppressed(self, notification_id: uuid.UUID, **kwargs: Any) -> None:
        self.rows[notification_id] |= {"status": "suppressed", **kwargs}

    @property
    def only(self) -> dict[str, Any]:
        assert len(self.rows) == 1, f"expected one row, got {len(self.rows)}"
        return next(iter(self.rows.values()))


class FakeSender:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, text: str, html: str) -> str | None:
        if self.fails:
            raise ConnectionRefusedError("smtp down")
        self.sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return "<msg-1@test>"


def build(
    *, log: FakeLog | None = None, sender: FakeSender | None = None, enabled: bool = True
) -> tuple[SendNotificationUseCase, FakeLog, FakeSender]:
    log = log or FakeLog()
    sender = sender or FakeSender()
    use_case = SendNotificationUseCase(
        log=log,
        sender=sender,
        clock=FrozenClock(NOW),
        web_base_url="https://roamingwandering.com",
        enabled=enabled,
    )
    return use_case, log, sender


async def send(
    use_case: SendNotificationUseCase,
    *,
    template: str = templates.EMAIL_VERIFICATION,
    dedupe_key: str = "auth.email_verification:evt-1",
    ctx: dict[str, Any] | None = None,
) -> Any:
    return await use_case.execute(
        template=template,
        recipient="guest@example.com",
        context=dict(ctx or CTX),
        dedupe_key=dedupe_key,
    )


# ══════════════════════════════════════════════════════════════════════════
# The happy path
# ══════════════════════════════════════════════════════════════════════════


async def test_a_message_is_sent_and_recorded() -> None:
    use_case, log, sender = build()

    result = await send(use_case)

    assert result.status == "sent"
    assert len(sender.sent) == 1
    assert log.only["status"] == "sent"


async def test_the_recipient_and_subject_reach_the_transport() -> None:
    use_case, _, sender = build()

    await send(use_case)

    assert sender.sent[0]["to"] == "guest@example.com"
    assert sender.sent[0]["subject"] == "Confirm your email address"


async def test_the_provider_message_id_is_recorded() -> None:
    """Support traces a "did they get it?" question through this id."""
    use_case, log, _ = build()

    await send(use_case)

    assert log.only["provider_message_id"] == "<msg-1@test>"


# ══════════════════════════════════════════════════════════════════════════
# Once only
# ══════════════════════════════════════════════════════════════════════════


async def test_a_redelivered_event_does_not_send_twice() -> None:
    """**The** idempotency test.

    The outbox relay is at-least-once by construction — that is what makes it
    survive a lost Redis message. Without the dedupe claim, every redelivery is
    a second mail, and a guest who reset their password once gets three
    identical links with only one of them live.
    """
    use_case, log, sender = build()

    first = await send(use_case)
    second = await send(use_case)

    assert first.status == "sent"
    assert second.status == "duplicate"
    assert len(sender.sent) == 1
    assert len(log.rows) == 1


async def test_a_second_genuine_request_is_not_a_duplicate() -> None:
    """The other half, and the reason the key is the *event* id rather than the
    user id: a person who asks for two resets must receive two mails."""
    use_case, _, sender = build()

    await send(use_case, dedupe_key="auth.email_verification:evt-1")
    await send(use_case, dedupe_key="auth.email_verification:evt-2")

    assert len(sender.sent) == 2


async def test_the_claim_happens_before_the_send() -> None:
    """Ordering, asserted through the observable consequence: a send that
    raises still leaves a claimed row, so the retry is deduplicated rather than
    starting over."""
    use_case, log, _ = build(sender=FakeSender(fails=True))

    with pytest.raises(ConnectionRefusedError):
        await send(use_case)

    assert len(log.rows) == 1


# ══════════════════════════════════════════════════════════════════════════
# Failures, and which kind they are
# ══════════════════════════════════════════════════════════════════════════


async def test_a_transport_failure_propagates_so_celery_retries() -> None:
    """Transient. A refused connection now may well succeed in thirty
    seconds, and the retry policy is Celery's job — swallowing it here would
    drop the message silently."""
    use_case, log, _ = build(sender=FakeSender(fails=True))

    with pytest.raises(ConnectionRefusedError):
        await send(use_case)

    assert log.only["status"] == "failed"
    assert "ConnectionRefusedError" in log.only["error"]


async def test_an_unrenderable_message_fails_without_raising() -> None:
    """Permanent. An unknown template does not start existing on the fifth
    attempt, so raising would burn five retries to reach the same place."""
    use_case, log, sender = build()

    result = await send(use_case, template="auth.telepathy")

    assert result.status == "failed"
    assert log.only["status"] == "failed"
    assert sender.sent == []


async def test_a_missing_variable_fails_permanently_too() -> None:
    use_case, log, sender = build()
    ctx = {k: v for k, v in CTX.items() if k != "token"}

    result = await send(use_case, ctx=ctx)

    assert result.status == "failed"
    assert sender.sent == []
    assert "render" in log.only["error"]


# ══════════════════════════════════════════════════════════════════════════
# Disabled
# ══════════════════════════════════════════════════════════════════════════


async def test_a_disabled_mailer_records_suppression_rather_than_dropping() -> None:
    """**The** operability rule, and the whole reason this module exists.

    The previous behaviour was to drop these events with no record at all, so
    signups failed silently for the system's entire history. A `suppressed` row
    with a reason is the difference between an operator being able to see that
    and not.
    """
    use_case, log, sender = build(enabled=False)

    result = await send(use_case)

    assert result.status == "suppressed"
    assert log.only["status"] == "suppressed"
    # `reason` on the port; the SQL adapter writes it into the `error` column,
    # so an operator reading the table sees why without knowing the port shape.
    assert log.only["reason"] == "email disabled"
    assert sender.sent == []


async def test_suppression_still_claims_the_dedupe_key() -> None:
    """Otherwise turning the mailer on would flood every user with the backlog
    of everything suppressed while it was off."""
    use_case, log, _ = build(enabled=False)

    await send(use_case)
    second = await send(use_case)

    assert second.status == "duplicate"
    assert len(log.rows) == 1


# ══════════════════════════════════════════════════════════════════════════
# What lands in the log
# ══════════════════════════════════════════════════════════════════════════


async def test_the_token_never_reaches_the_notification_log() -> None:
    """**The** data-protection rule here.

    The context is stored so a failed send can be replayed. Stored verbatim it
    would put a live password-reset token in a queryable table for the life of
    the row — and a replay mints a fresh token anyway, so keeping it buys
    nothing at all.
    """
    use_case, log, _ = build()

    await send(use_case)

    assert log.only["context"]["token"] == "[REDACTED]"


async def test_the_non_secret_context_is_kept() -> None:
    """Redaction has to be surgical. Losing the locale or the user id would
    make a replay impossible, which is what the stored context is for."""
    use_case, log, _ = build()

    await send(use_case)

    assert log.only["context"]["locale"] == "en"
    assert log.only["context"]["user_id"] == CTX["user_id"]


async def test_the_body_is_never_stored() -> None:
    """Only a preview. A rendered confirmation contains an address and a
    booking reference; a table of them grows forever for no benefit."""
    use_case, log, _ = build()

    await send(use_case)

    row = log.only
    assert "text" not in row
    assert "html" not in row
    assert len(row["preview"]) <= 200
