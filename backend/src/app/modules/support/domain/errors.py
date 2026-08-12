"""Support errors."""

from __future__ import annotations

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class InvalidTicketError(BusinessRuleViolationError):
    code = "TICKET_INVALID"

    def __init__(self, field: str, problem: str) -> None:
        super().__init__(
            f"{field.replace('_', ' ').capitalize()} {problem}.", details={"field": field}
        )


class InvalidTicketTransitionError(BusinessRuleViolationError):
    code = "TICKET_TRANSITION_INVALID"

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"A {current.replace('_', ' ')} ticket cannot become {target}.",
            details={"current": current, "target": target},
        )


class TicketClosedError(BusinessRuleViolationError):
    code = "TICKET_CLOSED"

    def __init__(self, reference: str) -> None:
        super().__init__(
            "This ticket is closed. Open a new one and reference this.",
            details={"reference": reference},
        )


class TicketNotFoundError(DomainError):
    code = "TICKET_NOT_FOUND"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Ticket not found.")


class TicketAccessDeniedError(DomainError):
    """Not this guest's ticket.

    404, not 403 — a distinguishable 403 lets someone enumerate other people's
    support conversations, which contain booking references and contact details.
    """

    code = "TICKET_NOT_FOUND"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Ticket not found.")
