"""Shared helpers for the Phase-2 detector nodes.

Extracted (TIP-G06 refactor) from ``topical_detector``,
``method_detector`` and ``contradiction_detector`` to remove duplication.
Behaviour is unchanged — only the home of the code moved.

NOTE: ``call_llm_with_retry`` takes the LLM callable as an argument rather
than importing ``chat_completion`` here.  Each detector keeps its own
``from ...llm_client import chat_completion`` import and passes it in, so
tests that patch ``<detector_module>.chat_completion`` keep working.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

# Re-exported JSON helpers (originally defined on the extractor) so detectors
# have a single import surface for shared utilities.
from backend.module.gap_detection.nodes.extractor import _ensure_list as ensure_list
from backend.module.gap_detection.nodes.extractor import _parse_llm_json as parse_llm_json
from backend.module.gap_detection.schemas import PaperRef

logger = logging.getLogger(__name__)

__all__ = ["call_llm_with_retry", "ensure_list", "map_papers", "parse_llm_json"]

# Type of the ``chat_completion`` callable a detector passes in.
LLMCallable = Callable[[list[dict[str, str]]], Awaitable[str]]


def map_papers(ids: list[str], index: dict[str, PaperRef]) -> list[PaperRef]:
    """Map LLM-returned paper ids to real ``PaperRef`` objects.

    Unknown ids are dropped (never fabricate a paper); duplicates removed
    while preserving order.
    """
    refs: list[PaperRef] = []
    seen: set[str] = set()
    for pid in ids:
        ref = index.get(str(pid))
        if ref is not None and ref.paper_id not in seen:
            refs.append(ref)
            seen.add(ref.paper_id)
    return refs


async def call_llm_with_retry(
    messages: list[dict[str, str]],
    *,
    llm: LLMCallable,
    label: str,
) -> dict | None:
    """Call *llm* and parse the JSON response, retrying once on malformed
    output.

    Returns the parsed dict, or ``None`` when both attempts fail (the caller
    then leaves its candidate list unchanged).  *label* is only used for log
    messages so each node remains identifiable.
    """
    for attempt in range(2):  # try + 1 retry
        try:
            raw = await llm(messages)
            parsed = parse_llm_json(raw)
            if not isinstance(parsed, dict):
                raise ValueError("LLM JSON is not an object")
            return parsed
        except Exception:
            if attempt == 0:
                logger.warning("%s: LLM parse failed, retrying…", label, exc_info=True)
            else:
                logger.warning(
                    "%s: LLM parse failed after retry — skipping gaps",
                    label,
                    exc_info=True,
                )
    return None
