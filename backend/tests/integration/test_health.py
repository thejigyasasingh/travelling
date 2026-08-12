"""Health probes and the middleware stack, end to end.

These run against the real app with the real container — the point is to prove
the wiring, which no unit test can. If ``create_app`` mis-orders the middleware
or the lifespan fails to build the container, it shows up here.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


class TestLiveness:
    async def test_liveness_needs_no_dependencies(self, api_client) -> None:
        response = await api_client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    async def test_liveness_is_not_cached(self, api_client) -> None:
        # A cached probe response keeps a dead pod in rotation.
        response = await api_client.get("/health/live")
        assert "no-store" in response.headers["cache-control"]


class TestReadiness:
    async def test_reports_every_dependency(self, api_client) -> None:
        response = await api_client.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"]["postgres"]["status"] == "up"
        assert body["checks"]["redis"]["status"] == "up"

    async def test_includes_per_check_latency(self, api_client) -> None:
        # The on-call engineer needs to know *which* dependency is slow.
        checks = (await api_client.get("/health/ready")).json()["checks"]
        assert all("latency_ms" in c for c in checks.values())


class TestMiddlewareStack:
    async def test_request_id_is_echoed(self, api_client) -> None:
        response = await api_client.get("/api/v1/ping")
        assert response.headers["x-request-id"]

    async def test_supplied_request_id_is_honoured(self, api_client) -> None:
        supplied = "abcdef0123456789"
        response = await api_client.get("/api/v1/ping", headers={"X-Request-Id": supplied})
        assert response.headers["x-request-id"] == supplied

    async def test_malformed_request_id_is_replaced_not_reflected(self, api_client) -> None:
        # Reflecting attacker-controlled data into logs is log forging.
        response = await api_client.get("/api/v1/ping", headers={"X-Request-Id": "bad id\nINJECT"})
        assert "\n" not in response.headers["x-request-id"]

    async def test_security_headers_are_present(self, api_client) -> None:
        headers = (await api_client.get("/api/v1/ping")).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert "content-security-policy" in headers

    async def test_security_headers_are_present_on_errors_too(self, api_client) -> None:
        # Proves SecurityHeaders sits outside the exception handlers.
        response = await api_client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_response_time_header(self, api_client) -> None:
        assert float((await api_client.get("/api/v1/ping")).headers["x-response-time-ms"]) >= 0


class TestErrorEnvelope:
    async def test_404_uses_the_standard_envelope(self, api_client) -> None:
        # A client must never see two different error shapes.
        body = (await api_client.get("/api/v1/nope")).json()
        assert set(body["error"]) >= {"code", "message", "details", "request_id"}
        assert body["error"]["code"] == "NOT_FOUND"

    async def test_error_carries_the_request_id(self, api_client) -> None:
        response = await api_client.get("/api/v1/nope")
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]

    async def test_405_is_enveloped(self, api_client) -> None:
        response = await api_client.post("/api/v1/ping")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


class TestBodyLimit:
    async def test_oversized_json_is_rejected(self, api_client) -> None:
        oversized = "x" * (2 * 1024 * 1024)
        response = await api_client.post(
            "/api/v1/ping",
            content=f'{{"data":"{oversized}"}}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
