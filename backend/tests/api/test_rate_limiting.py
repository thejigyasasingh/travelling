"""Rate limiting, against a real app with limiting switched on.

The rest of the API suite runs with ``RATELIMIT__ENABLED=false``, and it has to:
every test signs in, the limiter allows five logins per fifteen minutes per IP,
and every test arrives from the same address. With it on, the sixth test to run
fails — and which test that is depends on collection order. That is the kind of
flake that gets a whole suite marked ``xfail`` and then deleted.

So this module builds its **own** application with limiting enabled, and each
test picks a fresh identity by spoofing ``X-Forwarded-For``. Precise, and
immune to whatever the rest of the suite did beforehand.

What is actually being defended:

* **Credential stuffing.** ``/auth/login`` at five per fifteen minutes per IP is
  the only brake on someone working through a leaked password list. It is
  bucketed by IP rather than by account precisely because the attacker chooses
  which account to target.
* **Cost.** ``GET /search`` hits Postgres with a scoring query. Anonymous
  traffic is capped per minute so one scraper cannot spend the database budget.
* **Availability.** A Redis outage must not take the API down — so most routes
  fail *open*. Auth routes fail *closed*, because silently removing the brake on
  password guessing is worse than a sign-in outage.

That last pair is the one worth reading twice: the two halves are deliberately
opposite, and a well-meaning "consistency" refactor would break one of them.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from .conftest import EMAIL_DOMAIN, PASSWORD, register_and_login, unique

pytestmark = pytest.mark.integration


def from_ip(ip: str) -> dict[str, str]:
    """Headers that place a request at a given address.

    The middleware trusts ``X-Forwarded-For`` because uvicorn runs behind our
    own proxy with ``--proxy-headers``. In-process there is no proxy, so this
    is simply how a test chooses its bucket — and it is why each test below can
    start from a clean count without flushing Redis.
    """
    return {"X-Forwarded-For": ip}


def fresh_ip() -> str:
    """An address no other test in this run will use."""
    raw = uuid.uuid4().int
    return f"198.51.{raw % 254 + 1}.{raw // 254 % 254 + 1}"


@pytest.fixture(scope="module")
def limited_settings(integration_settings: Any) -> Any:
    """The integration settings, but with limiting on.

    A copy rather than a mutation: `integration_settings` is session-scoped and
    every other module depends on it staying as it is.
    """
    return integration_settings.model_copy(
        update={"ratelimit": integration_settings.ratelimit.model_copy(update={"enabled": True})},
        deep=True,
    )


@pytest_asyncio.fixture
async def limited_client(limited_settings: Any, migrated_database: Any) -> AsyncIterator[Any]:
    """A second application, built with limiting enabled."""
    import httpx
    from asgi_lifespan import LifespanManager

    from app.interface.api.app import create_app

    app = create_app(limited_settings)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def attempt_login(client: Any, ip: str, *, email: str = "nobody@example.com") -> Any:
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-password-entirely"},
        headers=from_ip(ip),
    )


# ══════════════════════════════════════════════════════════════════════════
# Login: the credential-stuffing brake
# ══════════════════════════════════════════════════════════════════════════


async def test_repeated_failed_logins_are_eventually_refused(limited_client: Any) -> None:
    """**The** reason rate limiting exists on this API.

    Five attempts per fifteen minutes. An attacker with a leaked password list
    gets five guesses per address, which makes the list worthless without a
    botnet — and a botnet is a different, more visible problem.

    Note what is asserted: that a 429 arrives *eventually*, and that the
    attempts before it were answered normally. Pinning the exact attempt number
    would make this test a restatement of the config value rather than a check
    that the mechanism runs at all.
    """
    ip = fresh_ip()

    statuses = [(await attempt_login(limited_client, ip)).status_code for _ in range(8)]

    assert 429 in statuses, f"login was never throttled: {statuses}"
    assert statuses[0] != 429, "the very first attempt was throttled"


async def test_a_throttled_response_says_when_to_come_back(limited_client: Any) -> None:
    """A 429 with no ``Retry-After`` tells a client to guess, and clients guess
    badly — usually by retrying immediately, in a loop."""
    ip = fresh_ip()

    response = None
    for _ in range(10):
        response = await attempt_login(limited_client, ip)
        if response.status_code == 429:
            break

    assert response is not None and response.status_code == 429
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) > 0


async def test_a_throttled_response_uses_the_standard_error_envelope(
    limited_client: Any,
) -> None:
    """Every other error on this API is ``{"error": {code, message, ...}}``.

    A 429 produced by middleware sits outside the exception handlers that build
    that envelope, so it is the one response shape that can silently drift —
    and a client switching on ``error.code`` would see `undefined` for the one
    status it most needs to handle.
    """
    ip = fresh_ip()

    response = None
    for _ in range(10):
        response = await attempt_login(limited_client, ip)
        if response.status_code == 429:
            break

    assert response is not None and response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["message"]
    assert body["error"]["details"]["retry_after_seconds"] > 0


async def test_one_address_being_throttled_does_not_throttle_another(
    limited_client: Any,
) -> None:
    """The blast radius of the login limit is one address.

    Without this the limit is a denial-of-service tool: an attacker who can get
    themselves throttled would lock out every other user of the API.
    """
    attacker = fresh_ip()
    for _ in range(10):
        await attempt_login(limited_client, attacker)

    innocent = await attempt_login(limited_client, fresh_ip())

    assert innocent.status_code != 429


async def test_a_successful_login_still_counts_against_the_limit(
    limited_client: Any,
) -> None:
    """Counting only *failures* would let an attacker with one valid account
    reset their budget between guesses at everyone else's."""
    ip = fresh_ip()
    email = f"{unique('rl-user')}@{EMAIL_DOMAIN}"
    await limited_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Rate Limited",
        },
        headers=from_ip(fresh_ip()),
    )

    statuses = []
    for _ in range(8):
        response = await limited_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": PASSWORD},
            headers=from_ip(ip),
        )
        statuses.append(response.status_code)

    assert 429 in statuses, f"successful logins were not counted: {statuses}"


# ══════════════════════════════════════════════════════════════════════════
# Headers, and the routes that must never be throttled
# ══════════════════════════════════════════════════════════════════════════


async def test_limit_headers_are_present_before_anything_is_throttled(
    limited_client: Any,
) -> None:
    """A client should be able to back off *before* it is throttled.

    Headers only on the 429 mean the only way to discover the budget is to
    exhaust it, which is precisely the behaviour the limit is trying to
    discourage.
    """
    response = await limited_client.get("/api/v1/search", headers=from_ip(fresh_ip()))

    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


async def test_the_remaining_count_goes_down(limited_client: Any) -> None:
    """A constant `Remaining` is worse than none: a client trusting it would
    never back off, and would be surprised by every 429."""
    ip = fresh_ip()

    first = await limited_client.get("/api/v1/search", headers=from_ip(ip))
    second = await limited_client.get("/api/v1/search", headers=from_ip(ip))

    assert int(second.headers["X-RateLimit-Remaining"]) < int(
        first.headers["X-RateLimit-Remaining"]
    )


async def test_health_is_never_throttled(limited_client: Any) -> None:
    """A throttled health check gets the pod killed by Kubernetes.

    Which is to say: rate limiting the liveness probe converts a traffic spike
    into a rolling restart, in the middle of the traffic spike.

    150 calls: well past the 100/min default that would otherwise apply, so a
    regression that dropped the exemption fails here rather than in an
    incident.
    """
    ip = fresh_ip()

    statuses = {
        (await limited_client.get("/health/live", headers=from_ip(ip))).status_code
        for _ in range(150)
    }

    assert statuses == {200}


async def test_metrics_is_never_throttled(limited_client: Any) -> None:
    """Prometheus scrapes on a fixed interval and does not back off. Throttling
    it produces gaps in exactly the graphs used to diagnose the load that
    caused the throttling."""
    ip = fresh_ip()

    statuses = {
        (await limited_client.get("/metrics", headers=from_ip(ip))).status_code for _ in range(150)
    }

    assert statuses <= {200, 404}, statuses
    assert 429 not in statuses


# ══════════════════════════════════════════════════════════════════════════
# Identity
# ══════════════════════════════════════════════════════════════════════════


async def test_authenticated_traffic_is_bucketed_by_user_not_by_address(
    limited_client: Any,
) -> None:
    """**The** identity rule, and the one with the largest user-visible cost if
    it is wrong.

    Rate limiting authenticated users by IP punishes everyone behind one
    corporate NAT or one mobile carrier gateway. In India a single carrier
    address can front tens of thousands of legitimate users, so an IP bucket
    would throttle a whole city because one person was enthusiastic.

    Asserted by having two different users share one address and checking that
    neither is charged for the other's traffic.
    """
    shared_ip = fresh_ip()

    # Each registration and its login run from their *own* address, so the
    # setup does not spend the shared bucket the assertion depends on.
    async def token_for(label: str) -> str:
        actor = await register_and_login(
            _PinnedClient(limited_client, from_ip(fresh_ip())),
            f"{unique(label)}@{EMAIL_DOMAIN}",
        )
        return actor.token

    first = await token_for("nat-a")
    second = await token_for("nat-b")

    # Spend most of the first user's per-minute budget from the shared address.
    for _ in range(40):
        await limited_client.get(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {first}", **from_ip(shared_ip)},
        )

    response = await limited_client.get(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {second}", **from_ip(shared_ip)},
    )

    assert response.status_code != 429, "a second user behind the same NAT was throttled"


async def test_login_is_bucketed_by_address_even_though_it_carries_credentials(
    limited_client: Any,
) -> None:
    """The deliberate exception to the rule above.

    At login there is no authenticated user yet, and the attacker chooses which
    account to name — so bucketing by the submitted email would let them cycle
    accounts and never hit a limit. IP is the only identity available, and it
    is the right one here.
    """
    ip = fresh_ip()

    statuses = [
        (
            await attempt_login(limited_client, ip, email=f"{unique('victim')}@{EMAIL_DOMAIN}")
        ).status_code
        for _ in range(8)
    ]

    assert 429 in statuses, f"cycling the target account evaded the limit: {statuses}"


async def test_the_bucket_key_does_not_contain_a_raw_address() -> None:
    """Bucket keys reach Redis and log lines, and a raw IP is personal data
    under the DPDP and GDPR regimes this runs in.

    Asserted against the shared helper rather than the middleware's private
    method: the access log now uses the same function, and having one
    implementation is what stops the two drifting apart again — which is
    exactly what had happened.
    """
    from app.core.privacy import client_fingerprint

    fingerprint = client_fingerprint("203.0.113.9", salt="pepper")

    assert "203.0.113.9" not in fingerprint
    assert len(fingerprint) == 16


class _PinnedClient:
    """A client whose every request carries a fixed set of headers.

    `register_and_login` makes two calls and takes no header argument. Rather
    than duplicate it here just to add `X-Forwarded-For`, this wraps the client
    so both calls land in the same chosen bucket.
    """

    def __init__(self, client: Any, headers: dict[str, str]) -> None:
        self._client = client
        self._headers = headers

    async def post(self, url: str, **kwargs: Any) -> Any:
        kwargs["headers"] = {**self._headers, **kwargs.get("headers", {})}
        return await self._client.post(url, **kwargs)
