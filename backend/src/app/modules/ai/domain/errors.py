"""AI module errors.

Most of these are programming errors surfaced at a boundary — a model returned
something outside the shape it was asked for. They exist as named types so the
metric "how often does the model go out of contract" is countable, which is the
number that tells you a model version has regressed before a guest does.

The user-facing ones say what the guest can do next. "The assistant is
unavailable" is a complete sentence; "LLM_ERROR" is not.
"""

from __future__ import annotations

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class UnknownAspectError(DomainError):
    code = "AI_ASPECT_UNKNOWN"
    status_code = 500

    def __init__(self, aspect: str) -> None:
        super().__init__(f"Not a known review aspect: {aspect!r}", details={"aspect": aspect})


class InvalidAspectScoreError(DomainError):
    code = "AI_ASPECT_SCORE_INVALID"
    status_code = 500

    def __init__(self, score: int) -> None:
        super().__init__("An aspect score must be -1, 0 or 1.", details={"score": score})


class InvalidConfidenceError(DomainError):
    code = "AI_CONFIDENCE_INVALID"
    status_code = 500

    def __init__(self, value: float) -> None:
        super().__init__("Confidence must be between 0 and 1.", details={"value": value})


class ModelUnavailableError(DomainError):
    """The provider is down, timed out, or the feature is switched off.

    A 503 with a retry hint rather than a 500: nothing is broken here, and the
    caller should try again rather than report a bug. Every feature that can
    raise this has a path that does not.
    """

    code = "AI_UNAVAILABLE"
    status_code = 503

    def __init__(self, detail: str = "The assistant is unavailable right now.") -> None:
        super().__init__(detail)


class ModelResponseInvalidError(DomainError):
    """The model answered, but not in the shape it was required to.

    Distinct from unavailability because the remedy is different: this one is
    ours to fix, and retrying the same prompt will usually fail the same way.
    """

    code = "AI_RESPONSE_INVALID"
    status_code = 502

    def __init__(self, why: str) -> None:
        super().__init__("The assistant returned something unusable.", details={"why": why})


class AIBudgetExceededError(BusinessRuleViolationError):
    """This user has spent their allowance for the period.

    A business rule, not an outage — hence 429 and a stated reset, so a client
    can back off intelligently instead of hammering.
    """

    code = "AI_BUDGET_EXCEEDED"
    status_code = 429

    def __init__(self, what: str, resets_in_seconds: int) -> None:
        super().__init__(
            f"You have reached today's limit for {what}. Please try again later.",
            details={"resource": what, "retry_after_seconds": resets_in_seconds},
        )


class NothingToRecommendError(DomainError):
    """Retrieval found no candidates at all.

    Its own error rather than an empty list because the causes are worth
    separating in the logs: a city with no published properties is a catalogue
    problem, while a filter combination nobody can satisfy is a product one.
    """

    code = "AI_NO_CANDIDATES"
    status_code = 404

    def __init__(self, context: str) -> None:
        super().__init__(
            "We do not have enough to suggest anything here yet.", details={"context": context}
        )
