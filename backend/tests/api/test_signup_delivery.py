"""Can a person actually create an account?

Nothing asked this before, and the answer was no — for the entire history of
the system. Registration returned `202 unverified`, emitted
``EmailVerificationRequested``, committed it to the outbox, and there the
journey ended: the relay had no scheduler entry, no Celery task was registered
in any process, the dispatch table had no row for the event, and no code
existed anywhere that could send an email. Four independent breaks in one path,
each invisible on its own, and every dashboard green throughout.

That is not four bugs. It is one missing test, and this is it.

**What is real here and what is not.** The API, the database, the outbox, the
event dispatch table, the template rendering and the notification log are all
real. Only the SMTP socket is replaced — by a capturing sender, so the
assertion is on the message that *would have gone out*, byte for byte. A real
socket would make this a test of Mailpit's uptime.

The relay is driven by hand rather than by Beat. Beat's schedule is asserted
separately in `tests/unit/test_task_registry.py`; waiting two seconds per test
for a scheduler tick would buy nothing and cost a slow suite.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
from sqlalchemy import text

from .conftest import EMAIL_DOMAIN, PASSWORD, unique

pytestmark = pytest.mark.integration


class CapturingSender:
    """Stands in for the SMTP socket, and records what it was handed."""

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, text: str, html: str) -> str | None:
        self.messages.append({"to": to, "subject": subject, "text": text, "html": html})
        return f"<{uuid.uuid4().hex}@test>"

    def to(self, address: str) -> list[dict[str, str]]:
        return [m for m in self.messages if m["to"] == address]


@pytest.fixture
async def mailbox(api_client: Any) -> Any:
    """Swap the SMTP socket and switch delivery on.

    Both substitutions reach into the process-wide container the running app
    built during its lifespan — constructing a second one would leave the
    notification task, three hops away, still holding the real adapter.

    Mail is off for the suite as a whole, correctly: a test run must never open
    a socket to anything. Turning it on against the capturing fake is what
    exercises the *sent* path rather than the suppressed one.
    """
    from app.container import get_container

    container = await get_container()
    sender = CapturingSender()

    original_sender = container.email_sender
    original_enabled = container.settings.email.enabled
    container.email_sender = sender  # type: ignore[assignment]
    object.__setattr__(container.settings.email, "enabled", True)
    try:
        yield sender
    finally:
        container.email_sender = original_sender
        object.__setattr__(container.settings.email, "enabled", original_enabled)


@pytest.fixture(autouse=True)
async def _quiet_outbox(db: Any) -> None:
    """Retire events left by other tests before this one starts.

    The outbox is append-only and shared, so a full-suite run leaves hundreds
    of unprocessed rows. Retiring them costs one statement and keeps each test
    looking only at what it caused.
    """
    await db.execute(text("UPDATE outbox SET processed_at = now() WHERE processed_at IS NULL"))
    await db.commit()


async def deliver(db: Any) -> None:
    """Carry every pending event to its consumer, the way the workers do.

    **Where the seam is, and why it is here.** A Celery task body is
    synchronous and bridges into async through `run_async`, which is correct
    for a worker process and impossible from inside a running event loop —
    `asyncio` refuses, with `Cannot run the event loop while another loop is
    running`. Eager mode does not help either: `send_task` ignores it outright
    (`AlwaysEagerIgnored`) and publishes to the broker regardless.

    So this awaits the task's **async body** directly, and skips only the sync
    wrapper around it. Everything that decides anything is real: the outbox
    rows, the `SUBSCRIPTIONS` table read below — remove the subscription and
    these tests fail — the use case, the repository, the templates and the
    notification log.

    What is *not* covered here is that the wrapper is registered under the
    right name and on the right queue. That is asserted in
    `tests/unit/test_task_registry.py`, which exists because it was not.
    """
    from app.infrastructure.queue.event_dispatch import SUBSCRIPTIONS
    from app.modules.notification.infrastructure import tasks as notification_tasks

    notify = "app.modules.notification.tasks.send_notification"

    rows = (
        await db.execute(
            text(
                "SELECT id, event_type, payload FROM outbox "
                " WHERE processed_at IS NULL ORDER BY created_at"
            )
        )
    ).all()

    for row in rows:
        if notify in SUBSCRIPTIONS.get(row.event_type, ()):
            await notification_tasks._send(row.event_type, str(row.id), row.payload)
    await db.execute(text("UPDATE outbox SET processed_at = now() WHERE processed_at IS NULL"))
    await db.commit()


def token_in(message: dict[str, str], path: str) -> str:
    """Pull the token out of the link, the way a person's browser would."""
    match = re.search(rf"{re.escape(path)}\?token=([A-Za-z0-9._\-]+)", message["text"])
    assert match, f"no {path} link in:\n{message['text']}"
    return match.group(1)


# ══════════════════════════════════════════════════════════════════════════
# The path that was broken
# ══════════════════════════════════════════════════════════════════════════


async def test_registering_sends_a_verification_email(
    api_client: Any, mailbox: CapturingSender, db: Any
) -> None:
    """**The** test. Every layer between the form and the inbox, in one go."""
    email = f"{unique('signup')}@{EMAIL_DOMAIN}"

    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    assert response.status_code in (200, 201, 202), response.text

    await deliver(db)

    assert mailbox.to(email), "registered, and no verification mail was produced"


async def test_the_verification_link_actually_verifies(
    api_client: Any, mailbox: CapturingSender, db: Any
) -> None:
    """Following the link has to finish the job.

    A mail that arrives with a link that does not work is the same outcome as
    no mail, one step later.
    """
    email = f"{unique('verify')}@{EMAIL_DOMAIN}"
    await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    await deliver(db)

    token = token_in(mailbox.to(email)[0], "/verify-email")
    response = await api_client.post("/api/v1/auth/email/verify", json={"token": token})

    assert response.status_code in (200, 204), response.text


async def test_a_verified_account_can_sign_in(
    api_client: Any, mailbox: CapturingSender, db: Any
) -> None:
    """Signup, mail, verify, log in — the whole journey, unassisted by SQL.

    Before this work every one of these steps needed a hand-written `UPDATE`.
    """
    email = f"{unique('journey')}@{EMAIL_DOMAIN}"
    await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    await deliver(db)
    token = token_in(mailbox.to(email)[0], "/verify-email")
    await api_client.post("/api/v1/auth/email/verify", json={"token": token})

    login = await api_client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})

    assert login.status_code == 200, login.text
    assert login.json()["tokens"]["access_token"]


async def test_a_forgotten_password_produces_a_reset_email(
    api_client: Any, mailbox: CapturingSender, db: Any
) -> None:
    """The other dead end. `/password/forgot` answered 202 and did nothing."""
    email = f"{unique('forgot')}@{EMAIL_DOMAIN}"
    await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    await deliver(db)
    mailbox.messages.clear()

    response = await api_client.post("/api/v1/auth/password/forgot", json={"email": email})
    assert response.status_code in (200, 202, 204), response.text
    await deliver(db)

    messages = mailbox.to(email)
    assert messages, "asked to reset a password and no mail was produced"
    assert "reset" in messages[0]["subject"].lower()
    assert token_in(messages[0], "/reset-password")


async def test_a_reset_for_an_unknown_address_sends_nothing(
    api_client: Any, mailbox: CapturingSender, db: Any
) -> None:
    """The endpoint answers 202 either way — it must not disclose whether an
    address has an account. That is exactly why the *mailbox* has to be
    checked: the response body cannot tell you this worked.
    """
    stranger = f"{unique('stranger')}@{EMAIL_DOMAIN}"

    response = await api_client.post("/api/v1/auth/password/forgot", json={"email": stranger})
    await deliver(db)

    assert response.status_code in (200, 202, 204)
    assert mailbox.to(stranger) == []


# ══════════════════════════════════════════════════════════════════════════
# The notification log
# ══════════════════════════════════════════════════════════════════════════


async def test_the_send_is_recorded(api_client: Any, mailbox: CapturingSender, db: Any) -> None:
    """Support's first question is "did they get it?", and this row is the
    answer."""
    email = f"{unique('logged')}@{EMAIL_DOMAIN}"
    await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    await deliver(db)

    row = (
        await db.execute(
            text(
                "SELECT status, channel, template, subject, provider_message_id "
                "  FROM notifications WHERE recipient = :email"
            ),
            {"email": email},
        )
    ).one()

    assert row.status == "sent"
    assert row.channel == "email"
    assert row.template == "auth.email_verification"
    assert row.subject
    assert row.provider_message_id


async def test_the_stored_context_has_no_token(
    api_client: Any, mailbox: CapturingSender, db: Any
) -> None:
    """The context is kept so a failed send can be replayed. Keeping the token
    with it would leave a live credential in a queryable table."""
    email = f"{unique('redacted')}@{EMAIL_DOMAIN}"
    await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    await deliver(db)

    context = (
        await db.execute(
            text("SELECT context FROM notifications WHERE recipient = :email"),
            {"email": email},
        )
    ).scalar_one()

    assert context["token"] == "[REDACTED]"


async def test_redelivering_the_event_does_not_send_a_second_mail(
    api_client: Any, mailbox: CapturingSender, db: Any
) -> None:
    """**The** at-least-once test, end to end.

    The relay redelivers anything it is not certain reached the broker — that
    is what makes it survive a Redis restart, and it means a duplicate dispatch
    is normal rather than exceptional. Only the dedupe claim stops that
    becoming a second email with a token the first one already invalidated.
    """
    email = f"{unique('redeliver')}@{EMAIL_DOMAIN}"
    await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    await deliver(db)
    assert len(mailbox.to(email)) == 1

    # Put the event back the way a redelivery does, and drain again.
    await db.execute(
        text(
            "UPDATE outbox SET processed_at = NULL "
            " WHERE event_type = 'auth.email.verification_requested'"
            "   AND payload->>'email' = :email"
        ),
        {"email": email},
    )
    await db.commit()
    await deliver(db)

    assert len(mailbox.to(email)) == 1, "a redelivered event sent a second mail"
    count = (
        await db.execute(
            text("SELECT count(*) FROM notifications WHERE recipient = :email"),
            {"email": email},
        )
    ).scalar_one()
    assert count == 1


# ══════════════════════════════════════════════════════════════════════════
# Degraded delivery
# ══════════════════════════════════════════════════════════════════════════


async def test_a_disabled_mailer_records_the_suppression(api_client: Any, db: Any) -> None:
    """With email off — the suite's normal state — the row still appears,
    marked `suppressed`.

    This is the whole operability argument for the module. The old behaviour
    was to drop the event with no trace, so "signups are broken" looked
    identical to "nobody has signed up today".
    """
    email = f"{unique('suppressed')}@{EMAIL_DOMAIN}"

    await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "New Person"},
    )
    await deliver(db)

    status = (
        await db.execute(
            text("SELECT status FROM notifications WHERE recipient = :email"),
            {"email": email},
        )
    ).scalar_one()

    assert status == "suppressed"
