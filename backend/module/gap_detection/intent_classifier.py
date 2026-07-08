"""Intent classification for the chat agent.

Detects whether a user message is a research-gap request so the chat
agent can route it into the gap-detection pipeline instead of the normal
conversational flow.

Uses a cheap keyword fast-path first, then falls back to a light LLM
yes/no classification (raw ``chat_completion``, like the extractor).  On
any LLM failure it returns ``False`` — i.e. it never hijacks the normal
chat flow on error.
"""

from __future__ import annotations

import logging

from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# Cheap, high-precision triggers (Vietnamese + English). Lower-cased.
_GAP_KEYWORDS = (
    "research gap",
    "khoảng trống",
    "khoang trong",
    "hướng nghiên cứu nào còn thiếu",
    "hướng nghiên cứu còn thiếu",
    "chưa được nghiên cứu",
    "chưa được khám phá",
    "chưa explore",
    "gap nào chưa",
    "research direction",
    "điểm mâu thuẫn",
    "mâu thuẫn giữa các paper",
    "underexplored",
    "unexplored",
)

_SYSTEM = (
    "You classify whether a user's message is asking to find RESEARCH GAPS "
    "across a set of papers (e.g. unexplored topics, missing method-domain "
    "combinations, or contradictions between papers). "
    "Answer with ONLY 'yes' or 'no'."
)

_USER_TMPL = """User message:
{message}

Is the user asking to find research gaps? Reply with ONLY 'yes' or 'no'."""


async def is_gap_detection_intent(user_message: str) -> bool:
    """Return ``True`` if *user_message* is a research-gap request.

    Keyword fast-path → LLM fallback.  Returns ``False`` on empty input or
    any LLM error (so the normal chat flow is never broken by accident).
    """
    text = (user_message or "").strip().lower()
    if not text:
        return False

    if any(keyword in text for keyword in _GAP_KEYWORDS):
        return True

    try:
        verdict = await chat_completion(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _USER_TMPL.format(message=user_message)},
            ]
        )
    except Exception:
        logger.warning("is_gap_detection_intent: LLM classification failed — defaulting to False", exc_info=True)
        return False

    return verdict.strip().lower().startswith("yes")
