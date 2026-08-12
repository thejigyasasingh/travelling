"""Authentication, over HTTP.

The response *shapes* here are load-bearing in a way the use-case tests cannot
see. Two real bugs came from exactly this gap: `/auth/refresh` returns
`{tokens, user}` rather than a flat token, and `/auth/register` returns 202 with
no tokens at all — and the web client had been written against a guess for
both, with a test fixture that encoded the same guess.

So these tests assert on the envelope as much as the behaviour. If a field is
renamed, three clients break, and this is the file that says so first.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.api.conftest import PASSWORD, Actor, register_and_login, unique

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ══════════════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════════════


async def test_registration_returns_202_and_no_tokens(api_client: Any) -> None:
    """**202, not 201, and no session.**

    The account exists but the address is unverified, so registering does not
    sign you in. A client that reads `tokens` from this response gets
    `undefined` and then sends `Bearer undefined` on every subsequent request
    while believing it is authenticated — which is precisely what happened.
    """
    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": f"{unique('new')}@example.com", "password": PASSWORD},
    )

    assert response.status_code == 202, response.text
    assert "tokens" not in response.json()


async def test_registering_the_same_address_twice_does_not_reveal_it(
    api_client: Any,
) -> None:
    """Account enumeration.

    A different status or message for "already registered" turns this endpoint
    into a way to test whether an address has an account here — which, for a
    travel site, is a way to learn where someone has been.
    """
    email = f"{unique('dup')}@example.com"
    body = {"email": email, "password": PASSWORD}

    first = await api_client.post("/api/v1/auth/register", json=body)
    second = await api_client.post("/api/v1/auth/register", json=body)

    assert first.status_code == second.status_code
    assert first.json() == second.json()


@pytest.mark.parametrize("password", ["short", "1234567", ""])
async def test_a_weak_password_is_refused(api_client: Any, password: str) -> None:
    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": f"{unique('weak')}@example.com", "password": password},
    )
    assert response.status_code == 422


async def test_a_malformed_address_is_refused(api_client: Any) -> None:
    response = await api_client.post(
        "/api/v1/auth/register", json={"email": "not-an-address", "password": PASSWORD}
    )
    assert response.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# Sign-in
# ══════════════════════════════════════════════════════════════════════════


async def test_login_returns_tokens_and_user(api_client: Any, guest: Actor) -> None:
    """The exact shape three clients depend on."""
    response = await api_client.post(
        "/api/v1/auth/login", json={"email": guest.email, "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"tokens", "user"}
    assert set(body["tokens"]) >= {"access_token", "expires_in"}
    assert body["user"]["email"] == guest.email
    # The web client stores this in memory and refreshes on it.
    assert isinstance(body["tokens"]["expires_in"], int)


async def test_the_refresh_token_is_an_httponly_cookie_not_a_field(
    api_client: Any, guest: Actor
) -> None:
    """**The** session-security decision.

    The refresh token is the long-lived credential. In a response body it would
    have to live in JavaScript's reach, where any XSS reads it; as an HttpOnly
    cookie scoped to the auth path it does not, and the access token in memory
    dies with the tab.
    """
    response = await api_client.post(
        "/api/v1/auth/login", json={"email": guest.email, "password": PASSWORD}
    )

    cookie = response.headers.get("set-cookie", "")
    assert "rw_refresh=" in cookie, "the browser credential must be a cookie"
    assert "HttpOnly" in cookie, "JavaScript, and therefore XSS, must not read it"
    # Scoped to the auth path: it is never attached to an ordinary API call, so
    # a CSRF against `/bookings` cannot carry it.
    assert "Path=/api/v1/auth" in cookie
    assert "samesite=lax" in cookie.lower()

    # The body *also* carries it, for the Flutter client, which has no cookie
    # jar and keeps its refresh token in the platform keystore. Asserted rather
    # than wished away: a browser gets a token in a place JavaScript can read,
    # even though the web client ignores it in favour of the cookie. Narrowing
    # that to non-browser clients is a worthwhile change and a behavioural one,
    # so it does not belong in a test.
    assert response.json()["tokens"]["refresh_token"]


async def test_a_wrong_password_is_refused_without_saying_why(
    api_client: Any, guest: Actor
) -> None:
    """ "No such account" and "wrong password" must be indistinguishable, or
    the endpoint answers "does this person have an account here"."""
    wrong = await api_client.post(
        "/api/v1/auth/login", json={"email": guest.email, "password": "wrong-" + PASSWORD}
    )
    unknown = await api_client.post(
        "/api/v1/auth/login",
        json={"email": f"{unique('nobody')}@example.com", "password": PASSWORD},
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"]
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


# ══════════════════════════════════════════════════════════════════════════
# Refresh
# ══════════════════════════════════════════════════════════════════════════


async def test_refresh_returns_tokens_and_user_not_a_bare_token(
    api_client: Any, guest: Actor
) -> None:
    """The exact bug this file exists for.

    Every client reads `data.tokens.access_token` from here. A flat
    `access_token` at the top level — which is what all three clients originally
    assumed — yields `undefined`, and the app then sends `Bearer undefined`
    while showing a signed-in UI.
    """
    await api_client.post("/api/v1/auth/login", json={"email": guest.email, "password": PASSWORD})
    # The client keeps the cookie, exactly as a browser does. Passing it by
    # hand would test httpx rather than the endpoint.
    response = await api_client.post("/api/v1/auth/refresh", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert "tokens" in body, "clients read data.tokens.access_token"
    assert body["tokens"]["access_token"]
    assert "access_token" not in body, "a flat token here would be a silent client break"


async def test_refresh_without_a_cookie_is_unauthorised(api_client: Any) -> None:
    response = await api_client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════
# The authenticated surface
# ══════════════════════════════════════════════════════════════════════════


async def test_me_returns_the_signed_in_user(api_client: Any, guest: Actor) -> None:
    response = await api_client.get("/api/v1/auth/me", headers=guest.auth)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == guest.email
    assert "roles" in body and "permissions" in body
    # The host portal gates on this being present. Null for a plain traveller.
    assert "vendor_id" in body


async def test_me_never_returns_a_password_hash(api_client: Any, guest: Actor) -> None:
    """Serialising the ORM row directly instead of a DTO is a one-line mistake
    that ships the hash of every user's password to their browser."""
    body = await api_client.get("/api/v1/auth/me", headers=guest.auth)
    serialised = body.text.lower()

    # `has_password` is a legitimate boolean — the profile page uses it to
    # decide whether to offer "set a password" to a Google-only account. What
    # must never appear is the hash itself.
    for leaked in ("$argon2", "password_hash", "secret", "token"):
        assert leaked not in serialised, f"{leaked!r} must not appear in /auth/me"


@pytest.mark.parametrize(
    "header",
    [
        None,
        "Bearer not-a-token",
        "Bearer ",
        "Basic dXNlcjpwYXNz",
        # The literal string a broken client sends after reading the wrong
        # field off a refresh response. It must be rejected, not crash.
        "Bearer undefined",
    ],
)
async def test_a_bad_authorization_header_is_401_not_500(
    api_client: Any, header: str | None
) -> None:
    headers = {"Authorization": header} if header else {}
    response = await api_client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"]


async def test_signing_out_invalidates_the_refresh_cookie(api_client: Any, guest: Actor) -> None:
    await api_client.post("/api/v1/auth/login", json={"email": guest.email, "password": PASSWORD})
    logout = await api_client.post(
        "/api/v1/auth/logout", json={"all_devices": False}, headers=guest.auth
    )
    assert logout.status_code in (200, 204)

    after = await api_client.post("/api/v1/auth/refresh", json={})
    assert after.status_code == 401, "a signed-out session must not refresh"


async def test_two_accounts_cannot_see_each_other(
    api_client: Any, guest: Actor, other_guest: Actor
) -> None:
    """The most basic authorisation property, asserted rather than assumed."""
    mine = await api_client.get("/api/v1/auth/me", headers=guest.auth)
    theirs = await api_client.get("/api/v1/auth/me", headers=other_guest.auth)

    assert mine.json()["id"] != theirs.json()["id"]
    assert mine.json()["email"] == guest.email


async def test_a_token_from_a_deleted_session_stops_working(api_client: Any, db: Any) -> None:
    """Sign out everywhere means everywhere.

    Access tokens are stateless and short-lived, but the session row is what
    lets a compromised account be cut off — and if revoking it does not stop
    the refresh, "sign out all devices" is a button that does nothing.
    """
    from sqlalchemy import text

    actor = await register_and_login(api_client)
    await api_client.post("/api/v1/auth/login", json={"email": actor.email, "password": PASSWORD})

    await db.execute(text("DELETE FROM auth_sessions WHERE user_id = :u"), {"u": actor.id})
    await db.commit()

    response = await api_client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 401
