"""What each message says, as pure functions.

No template engine. Jinja would be a new dependency, a new sandbox to reason
about, and a new place for a syntax error to become a runtime failure in a
worker at 3am. There are two messages today and they are the two that gate
signing in; a function per template is typed, unit-testable in microseconds,
and a missing variable is a `TypeError` at the call site rather than an empty
span in a delivered email.

If this grows past a dozen templates or needs marketing to edit copy without a
deploy, swap in an engine behind `render()` — the rest of the module only sees
a `RenderedMessage`.

Three rules the templates below all follow, each of which is a real failure
someone has shipped:

* **Every message is text-first.** A `text/plain` part is not a courtesy: mail
  scored as HTML-only is more likely to be filtered, and a verification link
  nobody receives is indistinguishable from a broken signup.
* **The link is shown as well as linked.** A client that strips the anchor, a
  forwarded plain-text copy, a screenshot sent to support — in all three the
  visible URL is the only way through.
* **Nothing in a subject line identifies the recipient.** Subjects appear on
  lock screens.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Final, Protocol

#: Template identifiers. Strings on the wire — they are persisted in
#: `notifications.template` and appear in dedupe keys — so they are declared
#: once and never spelled inline.
EMAIL_VERIFICATION: Final = "auth.email_verification"
# Suppressed on the line rather than the file: `S105` fires because the *name*
# contains "password", and this is a template identifier, not a credential.
PASSWORD_RESET: Final = "auth.password_reset"  # noqa: S105


class UnknownTemplateError(KeyError):
    """Raised for a template name with no renderer.

    Its own type so the task can record the notification as `failed` with a
    useful reason rather than retrying a `KeyError` five times — a name that
    does not exist will not start existing on the third attempt.
    """


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    subject: str
    text: str
    html: str

    @property
    def preview(self) -> str:
        """The first line, for the notification log.

        The log deliberately stores no body — see the model docstring — but
        support still needs to recognise which message a row refers to.
        """
        first = next((line for line in self.text.splitlines() if line.strip()), "")
        return first[:200]


class Renderer(Protocol):
    def __call__(self, ctx: dict[str, Any], *, web_base_url: str) -> RenderedMessage: ...


def _hours(seconds: int) -> str:
    """A duration a person can act on.

    "expires in 86400 seconds" is technically accurate and useless.
    """
    if seconds >= 7200:
        return f"{seconds // 3600} hours"
    if seconds >= 3600:
        return "1 hour"
    if seconds >= 120:
        return f"{seconds // 60} minutes"
    return "a few moments"


def _shell(title: str, body_html: str) -> str:
    """A deliberately plain HTML shell.

    Table-based layouts and inlined CSS frameworks exist because marketing mail
    needs pixel control in Outlook. These two messages need a legible paragraph
    and a link that works everywhere, and the most reliable way to get that is
    to ask for almost nothing.
    """
    return (
        '<!doctype html><html><body style="margin:0;padding:24px;'
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        'font-size:16px;line-height:1.6;color:#1a1a1a;background:#f6f7f9">'
        '<div style="max-width:520px;margin:0 auto;background:#fff;padding:32px;'
        'border-radius:6px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{escape(title)}</h1>'
        f"{body_html}"
        '<p style="margin:32px 0 0;font-size:13px;color:#6b7280">'
        "Roaming &amp; Wandering</p>"
        "</div></body></html>"
    )


def _button(url: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{escape(url, quote=True)}" '
        'style="display:inline-block;background:#1c5a94;color:#fff;'
        'text-decoration:none;padding:12px 22px;border-radius:4px">'
        f"{escape(label)}</a></p>"
        '<p style="margin:16px 0 0;font-size:13px;color:#6b7280">'
        "Or paste this into your browser:<br>"
        f'<span style="word-break:break-all">{escape(url)}</span></p>'
    )


def _verification(ctx: dict[str, Any], *, web_base_url: str) -> RenderedMessage:
    # The token is a query parameter rather than a path segment: path segments
    # end up in more referer headers and more proxy access logs, and this one
    # is a bearer credential for the length of its life.
    url = f"{web_base_url}/verify-email?token={ctx['token']}"
    window = _hours(int(ctx["expires_in_seconds"]))
    return RenderedMessage(
        subject="Confirm your email address",
        text=(
            "Welcome to Roaming & Wandering.\n\n"
            "Confirm your email address to finish setting up your account:\n\n"
            f"{url}\n\n"
            f"This link works once and expires in {window}.\n\n"
            "If you did not create an account, you can ignore this message — "
            "nothing was set up.\n"
        ),
        html=_shell(
            "Confirm your email address",
            "<p>Welcome to Roaming &amp; Wandering. Confirm your email address "
            "to finish setting up your account.</p>"
            + _button(url, "Confirm email")
            + f'<p style="margin:24px 0 0;font-size:13px;color:#6b7280">This link '
            f"works once and expires in {escape(window)}. If you did not create an "
            "account, you can ignore this message — nothing was set up.</p>",
        ),
    )


def _password_reset(ctx: dict[str, Any], *, web_base_url: str) -> RenderedMessage:
    url = f"{web_base_url}/reset-password?token={ctx['token']}"
    window = _hours(int(ctx["expires_in_seconds"]))
    return RenderedMessage(
        subject="Reset your password",
        text=(
            "Someone asked to reset the password for this account.\n\n"
            f"{url}\n\n"
            f"This link works once and expires in {window}.\n\n"
            "If it was not you, no action is needed — your password has not "
            "changed, and whoever asked cannot see it.\n"
        ),
        html=_shell(
            "Reset your password",
            "<p>Someone asked to reset the password for this account.</p>"
            + _button(url, "Choose a new password")
            # Said explicitly because the alternative reading — that someone
            # now has access — is the one a worried person jumps to, and the
            # panicked support ticket costs more than the sentence.
            + f'<p style="margin:24px 0 0;font-size:13px;color:#6b7280">This link '
            f"works once and expires in {escape(window)}. If it was not you, no "
            "action is needed — your password has not changed, and whoever asked "
            "cannot see it.</p>",
        ),
    )


_RENDERERS: Final[dict[str, Renderer]] = {
    EMAIL_VERIFICATION: _verification,
    PASSWORD_RESET: _password_reset,
}


def render(template: str, ctx: dict[str, Any], *, web_base_url: str) -> RenderedMessage:
    try:
        renderer = _RENDERERS[template]
    except KeyError as exc:
        raise UnknownTemplateError(template) from exc
    return renderer(ctx, web_base_url=web_base_url)


def known_templates() -> frozenset[str]:
    return frozenset(_RENDERERS)
