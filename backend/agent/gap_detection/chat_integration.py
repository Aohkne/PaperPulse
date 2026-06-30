"""Chat ↔ gap-detection bridge (TIP-G07, Part 4).

Orchestrates the gap-detection branch of the chat agent WITHOUT touching
the normal conversational flow:

    collect_session_papers → paper_check (flag baseline) →
        [baseline search + merge if < MIN_SESSION_PAPERS] →
            run_gap_detection → return narrative (REQ-G13, inline chat).

The baseline search reuses the retrieval adapter
(``gap_detection.retrieval.search``) — it is NOT reimplemented here.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.agent.gap_detection import retrieval
from backend.agent.gap_detection.graph import run_gap_detection
from backend.agent.gap_detection.nodes.paper_check import (
    collect_session_papers,
    paper_check_node,
)
from backend.agent.gap_detection.schemas import GapDetectionState, PaperRef
from backend.shared.models.paper import Paper

logger = logging.getLogger(__name__)

# How many papers to pull in a baseline top-up search.
BASELINE_SEARCH_LIMIT = 10


async def run_gap_detection_chat(messages: list[Any]) -> str:
    """Run the gap-detection branch for a chat conversation.

    Collects the session's cited papers, runs the Phase-0 check, performs a
    baseline search when there are too few papers, then runs the pipeline
    and returns the narrative to render inline as an assistant message.
    """
    papers = collect_session_papers(messages)

    state: GapDetectionState = {"session_papers": papers}
    check = await paper_check_node(state)

    if check.get("baseline_triggered"):
        query = _last_user_text(messages)
        papers = await _baseline_topup(papers, query)

    report = await run_gap_detection(papers)
    return report.narrative


# ── Helpers ──────────────────────────────────────────────────────────


async def _baseline_topup(existing: list[PaperRef], query: str) -> list[PaperRef]:
    """Reuse the existing search to add related papers, merged + deduped.

    Failures are non-fatal: on search error the original papers are
    returned unchanged so the pipeline still runs (and degrades to the
    synthesizer's polite "no gaps" path if empty).
    """
    if not query.strip():
        return existing

    try:
        found: list[Paper] = await retrieval.search(query, limit=BASELINE_SEARCH_LIMIT)
    except Exception:
        logger.warning(
            "run_gap_detection_chat: baseline search failed — proceeding with existing papers", exc_info=True
        )
        return existing

    merged = list(existing)
    seen = {ref.paper_id for ref in existing}
    for paper in found:
        if paper.paper_id and paper.paper_id not in seen:
            seen.add(paper.paper_id)
            merged.append(
                PaperRef(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    year=paper.year,
                    url=paper.url,
                )
            )
    logger.info("run_gap_detection_chat: baseline added %d paper(s)", len(merged) - len(existing))
    return merged


def _last_user_text(messages: list[Any]) -> str:
    """Return the content of the last user message (for the baseline query)."""
    for message in reversed(messages or []):
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role == "user":
            return message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
    return ""
