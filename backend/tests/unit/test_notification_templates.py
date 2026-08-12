"""The two messages that gate getting into the product.

A verification mail is not decoration: until it arrives and its link works,
the account does not exist as far as the person is concerned. So the
assertions here are about the things that make a mail *usable* rather than
about its wording — a broken link, a missing plain-text part or an HTML-escaped
token all produce a message that looks fine in a preview and fails for a real
person.
"""

from __future__ import annotations

import pytest

from app.modules.notification.domain import templates

pytestmark = pytest.mark.unit

WEB = "https://roamingwandering.com"

VERIFICATION_CTX = {
    "user_id": "019feb81-2ac3-7413-841b-590fb56b7157",
    "email": "guest@example.com",
    "token": "tok-abc123",
    "expires_in_seconds": 86_400,
    "locale": "en",
}

RESET_CTX = {
    "user_id": "019feb81-2ac3-7413-841b-590fb56b7157",
    "email": "guest@example.com",
    "token": "reset-xyz789",
    "expires_in_seconds": 3_600,
    "requested_ip_hash": "abc123",
    "locale": "en",
}


def render(template: str, ctx: dict[str, object]) -> templates.RenderedMessage:
    return templates.render(template, dict(ctx), web_base_url=WEB)


# ══════════════════════════════════════════════════════════════════════════
# Rules that hold for every message
# ══════════════════════════════════════════════════════════════════════════

ALL = [
    (templates.EMAIL_VERIFICATION, VERIFICATION_CTX),
    (templates.PASSWORD_RESET, RESET_CTX),
]


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_every_message_has_all_three_parts(template: str, ctx: dict[str, object]) -> None:
    message = render(template, ctx)

    assert message.subject.strip()
    assert message.text.strip()
    assert message.html.strip()


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_every_message_has_a_plain_text_part_with_the_link(
    template: str, ctx: dict[str, object]
) -> None:
    """Text-first is not politeness.

    HTML-only mail scores worse with spam filters, and a filtered verification
    mail is indistinguishable from a broken signup. The link has to be *in* the
    text part, not only in the HTML.
    """
    message = render(template, ctx)

    assert WEB in message.text
    assert str(ctx["token"]) in message.text


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_the_link_is_visible_as_well_as_clickable(template: str, ctx: dict[str, object]) -> None:
    """A client that strips anchors, a forwarded plain-text copy, a screenshot
    sent to support — in all three the printed URL is the only way through."""
    message = render(template, ctx)
    token = str(ctx["token"])

    assert message.html.count(token) >= 2, "the URL is linked but never shown"


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_no_subject_identifies_the_recipient(template: str, ctx: dict[str, object]) -> None:
    """Subjects appear on lock screens, in shared inboxes and in notification
    shades."""
    message = render(template, ctx)

    assert str(ctx["email"]) not in message.subject
    assert str(ctx["token"]) not in message.subject


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_the_token_is_not_html_escaped_inside_the_url(
    template: str, ctx: dict[str, object]
) -> None:
    """**The** silent breakage.

    Escaping the whole URL turns `?token=x&y` into `?token=x&amp;y`, and the
    link 404s for everyone while looking perfect in review. Tokens are
    URL-safe base64 here, so the raw value must survive into the href.
    """
    message = render(template, ctx)

    assert f"token={ctx['token']}" in message.html


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_the_expiry_is_stated_in_units_a_person_uses(template: str, ctx: dict[str, object]) -> None:
    message = render(template, ctx)

    assert str(ctx["expires_in_seconds"]) not in message.text, "raw seconds shown to a person"


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_a_preview_is_produced_for_the_log(template: str, ctx: dict[str, object]) -> None:
    """Support recognises a row by this. The body is deliberately never
    stored — see the model docstring."""
    message = render(template, ctx)

    assert message.preview.strip()
    assert len(message.preview) <= 200


@pytest.mark.parametrize(("template", "ctx"), ALL)
def test_no_message_leaks_the_token_into_the_preview(template: str, ctx: dict[str, object]) -> None:
    """The preview is persisted. A token in it is a credential in a queryable
    table, which is exactly what the log was designed to avoid."""
    message = render(template, ctx)

    assert str(ctx["token"]) not in message.preview


# ══════════════════════════════════════════════════════════════════════════
# Per-message specifics
# ══════════════════════════════════════════════════════════════════════════


def test_the_verification_link_points_at_the_web_app() -> None:
    """Not the API. A person opens this in a browser; an API host shows JSON."""
    message = render(templates.EMAIL_VERIFICATION, VERIFICATION_CTX)

    assert f"{WEB}/verify-email?token=tok-abc123" in message.text


def test_the_reset_link_points_at_the_web_app() -> None:
    message = render(templates.PASSWORD_RESET, RESET_CTX)

    assert f"{WEB}/reset-password?token=reset-xyz789" in message.text


def test_the_verification_mail_says_what_to_do_if_it_was_not_you() -> None:
    """Someone typo'd their address into a signup form. The mail lands with a
    stranger, who needs to know that ignoring it is sufficient."""
    message = render(templates.EMAIL_VERIFICATION, VERIFICATION_CTX)

    assert "did not create an account" in message.text.lower()


def test_the_reset_mail_says_the_password_has_not_changed() -> None:
    """**The** sentence on this message.

    Someone who did not request it reads "reset your password" as "someone is
    in my account". Saying otherwise costs one line and prevents a panicked
    support call — and a user changing a password they did not need to.
    """
    message = render(templates.PASSWORD_RESET, RESET_CTX)

    assert "has not changed" in message.text.lower()


def test_the_reset_mail_does_not_expose_the_requester_ip() -> None:
    """The context carries a hashed IP for auditing. Putting anything derived
    from it in front of a reader tells one person about another's network."""
    message = render(templates.PASSWORD_RESET, RESET_CTX)

    assert "abc123" not in message.text
    assert "abc123" not in message.html


# ══════════════════════════════════════════════════════════════════════════
# Durations
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (86_400, "24 hours"),
        (7_200, "2 hours"),
        (3_600, "1 hour"),
        (1_800, "30 minutes"),
        (30, "a few moments"),
    ],
)
def test_durations_read_like_english(seconds: int, expected: str) -> None:
    assert templates._hours(seconds) == expected


# ══════════════════════════════════════════════════════════════════════════
# Failure modes
# ══════════════════════════════════════════════════════════════════════════


def test_an_unknown_template_raises_its_own_error() -> None:
    """Typed so the caller can record a permanent failure instead of retrying
    a name that will never start existing."""
    with pytest.raises(templates.UnknownTemplateError):
        render("auth.telepathy", VERIFICATION_CTX)


@pytest.mark.parametrize("missing", ["token", "expires_in_seconds"])
def test_a_missing_variable_raises_rather_than_rendering_a_gap(missing: str) -> None:
    """An empty span where a link belongs is a mail that looks delivered and
    is useless. Failing loudly means it is recorded as failed and visible."""
    ctx = {k: v for k, v in VERIFICATION_CTX.items() if k != missing}

    with pytest.raises(KeyError):
        render(templates.EMAIL_VERIFICATION, ctx)


def test_the_registry_and_the_constants_agree() -> None:
    assert templates.known_templates() == {
        templates.EMAIL_VERIFICATION,
        templates.PASSWORD_RESET,
    }
