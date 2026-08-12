"""SMTP delivery.

SMTP rather than a provider SDK, deliberately. It is the one interface every
provider speaks — SES, Postmark, Mailgun and a local Mailpit are all a host,
a port and a credential — so switching providers is an environment change
rather than a code change, and local development uses the same path production
does instead of a mock nobody exercises.

The cost is no webhook for bounces or complaints. That is a real gap and it is
the right next step here; it is not a reason to couple the send path to one
vendor's client library today.

**A new connection per message, not a pooled one.** Message volume at this
stage is a handful per signup, SMTP connections drop silently when idle behind
a NAT, and a stale pooled connection fails the *next* message rather than
reconnecting. Per-message costs a TLS handshake and removes an entire class of
intermittent failure. Revisit at bulk volume, not before.
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import EmailSettings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SmtpEmailSender:
    def __init__(self, settings: EmailSettings) -> None:
        self._s = settings

    def _build(self, *, to: str, subject: str, text: str, html: str) -> tuple[EmailMessage, str]:
        message = EmailMessage()
        message["From"] = formataddr((self._s.from_name, self._s.from_address))
        message["To"] = to
        message["Subject"] = subject
        if self._s.reply_to:
            message["Reply-To"] = self._s.reply_to

        # Generated here rather than left to the server so the id can be
        # recorded against the notification row before the send is attempted —
        # which is what makes a message traceable through a provider's logs
        # even when the send failed.
        message_id = make_msgid(domain=self._s.from_address.rpartition("@")[2] or None)
        message["Message-ID"] = message_id

        # Order matters: `set_content` writes the plain part, `add_alternative`
        # appends the HTML as the *preferred* rendering. Reversing them sends
        # the plain text as the alternative and HTML-only clients show nothing.
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        return message, message_id

    async def send(self, *, to: str, subject: str, text: str, html: str) -> str | None:
        # Imported at call time, not at module import. The module is imported
        # by the container on every boot including in tests that never send;
        # a missing optional dependency should fail the send, not the process.
        import aiosmtplib

        message, message_id = self._build(to=to, subject=subject, text=text, html=html)

        await aiosmtplib.send(
            message,
            hostname=self._s.host,
            port=self._s.port,
            username=self._s.username,
            password=self._s.password.get_secret_value() if self._s.password else None,
            # `use_tls` is TLS from the first byte (465); `start_tls` upgrades a
            # plaintext connection (587). Passing both is a configuration error
            # the library reports at connect time.
            use_tls=self._s.tls,
            start_tls=self._s.start_tls if not self._s.tls else False,
            timeout=self._s.timeout_seconds,
        )
        return message_id


class NullEmailSender:
    """Accepts and discards, for tests and for a deliberately mail-less env.

    Distinct from `EMAIL__ENABLED=false`, which records the notification as
    `suppressed` and warns. This one reports success — it exists so a test can
    exercise the sent path without a socket, and it must never be wired in a
    deployed environment.
    """

    async def send(self, *, to: str, subject: str, text: str, html: str) -> str | None:
        logger.debug("email_discarded", subject=subject)
        return None
