"""AI wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.interface.api.deps import ContainerDep
from app.modules.ai.application.use_cases.chat import Chat
from app.modules.ai.application.use_cases.itinerary import GenerateItinerary
from app.modules.ai.application.use_cases.recommend import (
    ExplainRecommendations,
    RecommendForYou,
    RecommendSimilar,
    SuggestDestinations,
)
from app.modules.ai.infrastructure.budget import Budget, RedisBudget
from app.modules.ai.infrastructure.unit_of_work import AIUow


async def get_ai_uow(container: ContainerDep) -> AsyncIterator[AIUow]:
    """Write session for derived rows, read replica for retrieval.

    Both are opened for every request even when only one is used. The
    alternative — two dependencies and each endpoint choosing — puts the
    read/write decision in twelve places instead of one, and the connection
    pool is sized for it.
    """
    async with (
        container.database.write_session() as session,
        container.database.read_session() as read_session,
    ):
        uow = AIUow(session, read_session=read_session)
        yield uow
        await uow.flush()


AIUowDep = Annotated[AIUow, Depends(get_ai_uow)]


def get_budget(container: ContainerDep) -> Budget:
    return RedisBudget(container.redis.cache)


BudgetDep = Annotated[Budget, Depends(get_budget)]


def explain_uc(container: ContainerDep) -> ExplainRecommendations:
    return ExplainRecommendations(model=container.language_model)


ExplainDep = Annotated[ExplainRecommendations, Depends(explain_uc)]


def similar_uc(uow: AIUowDep, explain: ExplainDep) -> RecommendSimilar:
    return RecommendSimilar(candidates=uow.candidates, explain=explain)


def for_you_uc(uow: AIUowDep, explain: ExplainDep) -> RecommendForYou:
    return RecommendForYou(candidates=uow.candidates, explain=explain)


def destinations_uc(container: ContainerDep, uow: AIUowDep) -> SuggestDestinations:
    return SuggestDestinations(candidates=uow.candidates, model=container.language_model)


def itinerary_uc(container: ContainerDep, uow: AIUowDep) -> GenerateItinerary:
    return GenerateItinerary(
        candidates=uow.candidates,
        model=container.language_model,
        clock=container.clock,
        cache_days=container.settings.ai.itinerary_cache_days,
    )


def chat_uc(container: ContainerDep, uow: AIUowDep) -> Chat:
    return Chat(candidates=uow.candidates, model=container.language_model)
