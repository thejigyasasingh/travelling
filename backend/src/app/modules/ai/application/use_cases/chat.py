"""The chat assistant.

The riskiest surface in the module, because it is the only one where an
attacker composes the input directly and a guest reads the output directly.
Three things contain it, and the prompt is the weakest of them.

**It cannot do anything.** The assistant has no tools. It cannot search, book,
cancel, refund, read another user's data, or send a message. It receives a
retrieved candidate list and returns prose plus a set of references. A
completely successful prompt injection yields a rude paragraph and some oddly
chosen hotels.

**It cannot quote money.** Prices, totals, fees and refund amounts are never put
in the prompt, so there is nothing to leak and nothing to get wrong. A guest
asking "how much" is pointed at the page that computes it. This is the single
rule most likely to be relaxed by someone adding a feature later, and the
reason it must not be: an assistant that states a price has stated a price, and
the platform will be held to it.

**It is metered.** Per user, per hour, before the call.

Retrieval is keyword-based rather than model-driven for the same reason
recommendations are ranked in SQL: letting the model decide what to fetch means
letting the input decide what to fetch.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.modules.ai.application import prompts
from app.modules.ai.application.ports import CandidateSource, LanguageModel
from app.modules.ai.application.prompts import dumps
from app.modules.ai.domain import errors
from app.modules.ai.domain.grounding import fence, make_refs, resolve_refs, sanitise
from app.modules.ai.domain.value_objects import Candidate

logger = get_logger(__name__)

MAX_MESSAGE_CHARS = 1_000
#: How much of the thread is replayed. Short on purpose: cost is linear in it,
#: and a long history is a place for an injection to sit and wait for a turn
#: where the guard happens to be weaker.
HISTORY_TURNS = 6
CANDIDATES_PER_TURN = 8

#: Questions this assistant must not attempt. Matched before the model is
#: called, so the answer is deterministic and free. A model instructed not to
#: discuss refunds still discusses refunds on the turn where someone is
#: distressed and insistent, which is exactly the turn that matters.
_ESCALATE = re.compile(
    r"\b(refund|charge[d]?\s+twice|double\s+charge|chargeback|dispute|"
    r"cancel\s+my\s+booking|money\s+back|didn'?t\s+get\s+my|fraud|scam|"
    r"police|legal|lawyer|compensat)\w*",
    re.IGNORECASE,
)

ESCALATION_REPLY = (
    "That needs a person from our team rather than me — I can't see your "
    "bookings or payments, and I don't want to guess about your money. "
    "Raise it from the booking in your trips and support will pick it up."
)

#: Rough city extraction for retrieval. Not clever, and does not need to be:
#: getting it wrong costs a less relevant candidate list, not a wrong answer.
_CITY_HINT = re.compile(r"\b(?:in|to|near|around|visit(?:ing)?)\s+([A-Z][a-zA-Z\s]{2,30})")


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ChatReply:
    reply: str
    suggested: tuple[Candidate, ...]
    follow_ups: tuple[str, ...]
    needs_human: bool
    #: True when the reply came from the escalation path and no model was
    #: called. Surfaced so the caller does not bill it against the budget.
    handled_locally: bool = False


@dataclass(slots=True)
class Chat:
    candidates: CandidateSource
    model: LanguageModel

    async def execute(
        self,
        message: str,
        *,
        history: list[ChatTurn],
        city_hint: str = "",
    ) -> ChatReply:
        cleaned = sanitise(message, limit=MAX_MESSAGE_CHARS)
        if not cleaned:
            raise errors.ModelResponseInvalidError("empty message")

        # Escalation is checked first, and on the raw message rather than after
        # any model involvement. A guest describing a double charge gets a
        # human, not a paragraph of sympathy from a language model.
        if _ESCALATE.search(cleaned):
            logger.info("assistant_escalated", reason="money_or_legal")
            return ChatReply(
                reply=ESCALATION_REPLY,
                suggested=(),
                follow_ups=(),
                needs_human=True,
                handled_locally=True,
            )

        if not self.model.available:
            raise errors.ModelUnavailableError(
                "The assistant is offline. Search and browse still work."
            )

        pool = await self._retrieve(cleaned, city_hint=city_hint)
        catalogue = make_refs(list(pool))

        result = await self.model.structured(
            system=prompts.CHAT_SYSTEM,
            user=self._build_prompt(cleaned, history=history, catalogue=catalogue),
            schema=prompts.CHAT_SCHEMA,
            tool_name="reply_to_guest",
        )

        suggested = resolve_refs(
            [str(r) for r in result.get("suggested_refs", [])],
            catalogue,
            context="assistant_reply",
        )
        return ChatReply(
            reply=str(result.get("reply", "")).strip(),
            suggested=tuple(suggested),
            follow_ups=tuple(str(f).strip() for f in result.get("follow_ups", [])[:3]),
            needs_human=bool(result.get("needs_human", False)),
        )

    # ── retrieval ─────────────────────────────────────────────────────────

    async def _retrieve(self, message: str, *, city_hint: str) -> list[Candidate]:
        """Fetch something to ground the reply in.

        Deterministic and keyword-driven. The model does not choose what is
        retrieved, so the guest's text cannot steer the query — and an empty
        result is a valid outcome that the prompt knows how to handle.
        """
        city = city_hint.strip()
        if not city:
            match = _CITY_HINT.search(message)
            if match:
                city = match.group(1).strip()

        found = await self.candidates.popular_in(city, limit=CANDIDATES_PER_TURN)
        if not found and city:
            # The named city has nothing. Fall back to anywhere rather than
            # returning empty, so the assistant can suggest an alternative
            # instead of shrugging.
            found = await self.candidates.popular_in("", limit=CANDIDATES_PER_TURN)
        return list(found)

    def _build_prompt(
        self, message: str, *, history: list[ChatTurn], catalogue: dict[str, Candidate]
    ) -> str:
        rows = [
            {
                "ref": ref,
                "name": candidate.name,
                "city": candidate.city,
                "type": candidate.property_type,
                "amenities": sorted(candidate.amenity_codes)[:6],
                **({"rating": round(candidate.review_average, 1)} if candidate.is_rated else {}),
            }
            for ref, candidate in catalogue.items()
        ]

        # The assistant's own past turns are replayed unfenced — we wrote them.
        # The guest's are fenced individually rather than as one block, so an
        # earlier message cannot appear to close the fence around a later one.
        thread = "\n".join(
            (
                f"assistant: {turn.content}"
                if turn.role == "assistant"
                else f"guest: {fence('guest_turn', turn.content, limit=600)}"
            )
            for turn in history[-HISTORY_TURNS:]
        )

        return (
            f"CANDIDATES:\n{fence('candidate_list', dumps(rows), limit=3_000)}\n\n"
            f"CONVERSATION SO FAR:\n{thread}\n\n"
            f"NEW MESSAGE:\n{fence('guest_message', message, limit=MAX_MESSAGE_CHARS)}"
        )


def new_conversation_id() -> uuid.UUID:
    from uuid_utils.compat import uuid7

    return uuid7()


def to_public(candidates: tuple[Candidate, ...]) -> list[dict[str, Any]]:
    """What a suggested property looks like in a chat response.

    No price. The assistant is forbidden from discussing money, and shipping a
    price in its response payload would let a client render one next to a
    sentence the model wrote, which produces the same problem by another route.
    """
    return [
        {
            "property_id": str(c.property_id),
            "name": c.name,
            "city": c.city,
            "property_type": c.property_type,
            "review_average": round(c.review_average, 1) if c.is_rated else None,
            "review_count": c.review_count,
        }
        for c in candidates
    ]
