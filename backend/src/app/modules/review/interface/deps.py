"""Review wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.interface.api.deps import ContainerDep
from app.modules.review.application.use_cases import (
    EditReview,
    FlagReview,
    ModerateReview,
    ReplyToReview,
    WriteReview,
)
from app.modules.review.infrastructure.unit_of_work import ReviewUow


async def get_review_uow(container: ContainerDep) -> AsyncIterator[ReviewUow]:
    """The primary. A review moves a property's public rating, and that write
    has to be in the same transaction."""
    async with container.database.write_session() as session:
        uow = ReviewUow(session)
        yield uow
        await uow.flush()


ReviewUowDep = Annotated[ReviewUow, Depends(get_review_uow)]


def write_review_uc(container: ContainerDep, uow: ReviewUowDep) -> WriteReview:
    return WriteReview(
        reviews=uow.reviews,
        bookings=uow.bookings,
        ratings=uow.ratings,
        clock=container.clock,
    )


def edit_review_uc(container: ContainerDep, uow: ReviewUowDep) -> EditReview:
    return EditReview(reviews=uow.reviews, ratings=uow.ratings, clock=container.clock)


def reply_uc(container: ContainerDep, uow: ReviewUowDep) -> ReplyToReview:
    return ReplyToReview(reviews=uow.reviews, clock=container.clock)


def flag_uc(container: ContainerDep, uow: ReviewUowDep) -> FlagReview:
    return FlagReview(reviews=uow.reviews, clock=container.clock)


def moderate_uc(container: ContainerDep, uow: ReviewUowDep) -> ModerateReview:
    return ModerateReview(reviews=uow.reviews, ratings=uow.ratings, clock=container.clock)
