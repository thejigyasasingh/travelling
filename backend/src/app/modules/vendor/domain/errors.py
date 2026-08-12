"""Vendor domain errors."""

from __future__ import annotations

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class InvalidVendorDetailsError(BusinessRuleViolationError):
    code = "VENDOR_DETAILS_INVALID"

    def __init__(self, field: str, problem: str) -> None:
        super().__init__(f"{field.replace('_', ' ')} {problem}.", details={"field": field})


class InvalidVendorTransitionError(BusinessRuleViolationError):
    code = "VENDOR_TRANSITION_INVALID"

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"A {current} vendor cannot become {target}.",
            details={"current": current, "target": target},
        )


class MissingVendorDocumentError(BusinessRuleViolationError):
    """Approval needs the documents the platform is legally required to hold."""

    code = "VENDOR_DOCUMENT_MISSING"

    def __init__(self, document: str) -> None:
        super().__init__(
            f"This vendor cannot be approved without a {document.upper()} on file.",
            details={"document": document},
        )


class VendorNotFoundError(DomainError):
    code = "VENDOR_NOT_FOUND"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Vendor not found.")


class VendorAccessDeniedError(DomainError):
    """Not this user's vendor account.

    404, not 403 — confirming that a vendor id exists lets someone enumerate
    the platform's supplier list.
    """

    code = "VENDOR_NOT_FOUND"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Vendor not found.")
