"""The Anthropic Messages API, behind the :class:`LanguageModel` port.

Written against the HTTP API through the project's own
:class:`~app.infrastructure.external.http_client.HttpClient` rather than the
vendor SDK, for the same reasons the payment gateway is: the circuit breaker,
the correlation headers, the timeout policy and the outbound logging are
already there and already tested, and an SDK brings its own retry loop that
fights with ours.

**Structured output is forced tool use, not JSON-in-prose.** The model is given
exactly one tool whose input schema is the shape we need and is told it must
call it. Asking for "JSON only" in the prompt and parsing the reply works until
the day the model prefixes it with "Here's the JSON:", and that day arrives in
production rather than in a test.
"""

from __future__ import annotations

import base64
from typing import Any, Final

import httpx

from app.core.config import AISettings
from app.core.logging import get_logger
from app.infrastructure.external.http_client import HttpClient
from app.infrastructure.external.resilience.circuit_breaker import CircuitBreakerConfig
from app.modules.ai.domain import errors

logger = get_logger(__name__)

#: Generation is slow by nature, so the read timeout is long — but the connect
#: timeout is not. A provider that cannot be reached should fail in seconds; a
#: provider that is thinking should be allowed to think.
_TIMEOUT_CONNECT: Final = 5.0

#: Opened after a run of failures, because every AI feature has a path that
#: works without the model. Holding a request open to retry a dead provider
#: costs a guest their page load for something they never asked for.
_BREAKER: Final = CircuitBreakerConfig(failure_threshold=5, reset_timeout_seconds=30.0)


class AnthropicLanguageModel:
    """Implements :class:`app.modules.ai.application.ports.LanguageModel`."""

    def __init__(self, settings: AISettings) -> None:
        self._settings = settings
        self._client: HttpClient | None = None
        if settings.enabled and settings.api_key is not None:
            self._client = HttpClient(
                name="anthropic",
                base_url=settings.base_url,
                timeout=httpx.Timeout(
                    connect=_TIMEOUT_CONNECT,
                    read=settings.request_timeout_seconds,
                    write=10.0,
                    pool=5.0,
                ),
                headers={
                    "x-api-key": settings.api_key.get_secret_value(),
                    "anthropic-version": settings.api_version,
                    "content-type": "application/json",
                },
                max_connections=20,
                breaker_config=_BREAKER,
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    # ── the two calls ─────────────────────────────────────────────────────

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        tool_name: str,
        max_tokens: int | None = None,
        fast: bool = False,
    ) -> dict[str, Any]:
        return await self._call(
            system=system,
            content=[{"type": "text", "text": self._clamp(user)}],
            schema=schema,
            tool_name=tool_name,
            max_tokens=max_tokens,
            model=self._settings.fast_model if fast else self._settings.model,
        )

    async def describe_image(
        self,
        *,
        system: str,
        user: str,
        image_bytes: bytes,
        media_type: str,
        schema: dict[str, Any],
        tool_name: str,
    ) -> dict[str, Any]:
        return await self._call(
            system=system,
            content=[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    },
                },
                {"type": "text", "text": self._clamp(user)},
            ],
            schema=schema,
            tool_name=tool_name,
            max_tokens=None,
            # Tagging is high volume and narrow; the cheap model is the right
            # tool and the quality difference on "is there a pool in this
            # photograph" is not measurable.
            model=self._settings.fast_model,
        )

    # ── internals ─────────────────────────────────────────────────────────

    def _clamp(self, text: str) -> str:
        """Last line of defence on prompt size.

        The use cases already truncate their untrusted inputs. This catches the
        case where several bounded pieces add up to something unbounded, which
        is how a prompt-size limit is usually breached in practice.
        """
        limit = self._settings.max_input_chars
        if len(text) <= limit:
            return text
        logger.warning("prompt_truncated", length=len(text), limit=limit)
        return text[:limit]

    async def _call(
        self,
        *,
        system: str,
        content: list[dict[str, Any]],
        schema: dict[str, Any],
        tool_name: str,
        max_tokens: int | None,
        model: str,
    ) -> dict[str, Any]:
        if self._client is None:
            raise errors.ModelUnavailableError

        body = {
            "model": model,
            "max_tokens": max_tokens or self._settings.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": content}],
            "tools": [
                {
                    "name": tool_name,
                    "description": "Return the result in this exact structure.",
                    "input_schema": schema,
                }
            ],
            # The whole point: the model cannot answer in prose even if it
            # would rather explain itself first.
            "tool_choice": {"type": "tool", "name": tool_name},
        }

        try:
            response = await self._client.post("/v1/messages", json=body)
        except Exception as exc:  # transport, timeout, or an open breaker
            logger.warning("llm_call_failed", model=model, tool=tool_name, error=str(exc)[:200])
            raise errors.ModelUnavailableError from exc

        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            # The provider's own limit. Surfaced as unavailable rather than as
            # the caller's fault: our user did nothing wrong, and our per-user
            # budget is enforced separately and earlier.
            logger.warning("llm_rate_limited", model=model)
            raise errors.ModelUnavailableError("The assistant is busy. Try again shortly.")

        if response.status_code >= httpx.codes.BAD_REQUEST:
            # Logged with the body because a 400 here is our bug — a malformed
            # schema, an oversized image — and the message says which.
            logger.error(
                "llm_rejected_request",
                model=model,
                status=response.status_code,
                body=response.text[:400],
            )
            raise errors.ModelResponseInvalidError(f"provider returned {response.status_code}")

        return self._extract(response.json(), tool_name=tool_name, model=model)

    @staticmethod
    def _extract(payload: dict[str, Any], *, tool_name: str, model: str) -> dict[str, Any]:
        """Pull the tool input out of the response.

        ``stop_reason == "max_tokens"`` is checked first and treated as a hard
        failure. A truncated tool call deserialises into a *plausible but
        incomplete* object — an itinerary missing its last two days, a review
        analysis missing its negative aspects — and nothing downstream can tell
        that apart from a genuine answer.
        """
        if payload.get("stop_reason") == "max_tokens":
            logger.warning("llm_output_truncated", model=model, tool=tool_name)
            raise errors.ModelResponseInvalidError("output truncated at max_tokens")

        for block in payload.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                result = block.get("input")
                if isinstance(result, dict):
                    usage = payload.get("usage", {})
                    logger.info(
                        "llm_call",
                        model=model,
                        tool=tool_name,
                        input_tokens=usage.get("input_tokens"),
                        output_tokens=usage.get("output_tokens"),
                    )
                    return result

        # Reached when the model declined — a refusal, or a safety stop. The
        # response body is not logged: it can contain the user's own text.
        logger.warning(
            "llm_no_tool_call", model=model, tool=tool_name, stop=payload.get("stop_reason")
        )
        raise errors.ModelResponseInvalidError("model did not call the required tool")


class DisabledLanguageModel:
    """What the container installs when AI is switched off.

    A null object rather than ``None``: every call site would otherwise need a
    None check, and the one that gets forgotten is an ``AttributeError`` in a
    request path instead of a feature quietly not appearing.
    """

    @property
    def available(self) -> bool:
        return False

    async def structured(self, **_: Any) -> dict[str, Any]:
        raise errors.ModelUnavailableError

    async def describe_image(self, **_: Any) -> dict[str, Any]:
        raise errors.ModelUnavailableError


def build_language_model(settings: AISettings) -> Any:
    """Pick an implementation. Called once, at container construction."""
    if not settings.enabled or settings.api_key is None:
        logger.info("ai_disabled")
        return DisabledLanguageModel()
    logger.info("ai_enabled", model=settings.model, fast_model=settings.fast_model)
    return AnthropicLanguageModel(settings)


def json_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """Build a tool input schema.

    ``additionalProperties: false`` is not decoration. Without it a model that
    wants to add commentary adds a field, the field is stored, and six months
    later something reads it.
    """
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
