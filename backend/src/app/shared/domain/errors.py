"""Domain-level failures.

Separate from ``app.core.errors`` on purpose. ``app.core.errors`` carries HTTP
status codes; the domain must not know that HTTP exists, or the same rule
cannot be reused by a Celery worker, a CLI command or an admin script.

The interface layer maps these to their transport representation. Everything
here is a business outcome, never a bug.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base for all rule violations. Carries a stable ``code`` that the
    interface layer translates into the public error contract."""

    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class BusinessRuleViolationError(DomainError):
    """An invariant was about to be broken. The state is unchanged."""

    code = "BUSINESS_RULE_VIOLATION"


class InvariantError(DomainError):
    """An aggregate found itself in a state that should be unreachable.

    Distinct from :class:`BusinessRuleViolationError`: that one means the *user*
    asked for something invalid, this one means *we* have a bug. It should
    page someone.
    """

    code = "INVARIANT_VIOLATION"


class ConcurrencyError(DomainError):
    """Optimistic lock lost — another writer committed first.

    Retryable: reload the aggregate, reapply, retry. The interface layer maps
    it to 409 with a retry hint.
    """

    code = "CONCURRENT_MODIFICATION"


class EntityNotFoundError(DomainError):
    code = "ENTITY_NOT_FOUND"

    def __init__(self, entity: str, identifier: Any) -> None:
        super().__init__(f"{entity} not found", details={"entity": entity, "id": str(identifier)})
