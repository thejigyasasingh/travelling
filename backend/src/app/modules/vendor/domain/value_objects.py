"""Vendor value objects."""

from __future__ import annotations

from enum import StrEnum


class VendorStatus(StrEnum):
    """Where an application stands.

    `under_review` exists so two reviewers do not work the same queue item, and
    so "how long does approval take?" is answerable from data rather than
    guessed.
    """

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"

    @property
    def is_terminal(self) -> bool:
        return self is VendorStatus.REJECTED

    @property
    def is_actionable(self) -> bool:
        """Whether an admin still has something to decide."""
        return self in (VendorStatus.PENDING, VendorStatus.UNDER_REVIEW)
