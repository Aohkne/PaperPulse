"""PaperCheckNode — Phase 0 of the gap-detection pipeline.

Collects the papers already present in a chat session and decides whether
a baseline search is needed (fewer than ``MIN_SESSION_PAPERS`` papers).

The node only *flags* ``baseline_triggered`` — it never searches itself;
running the baseline search and merging results is the caller's job (see
``chat_integration.run_gap_detection_chat``).

Session-paper source (see TIP-G07 completion report): the chat layer
currently exchanges ``{role, content}`` messages with no ``papers_cited``
field, so the live signal is the project's inline ``(Source: PAPER_ID)``
citation convention (same as ``claim_extractor``).  ``collect_session_papers``
also accepts a structured ``papers_cited`` list per message if/when the
chat layer starts attaching one, so it is forward-compatible.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.agent.gap_detection.schemas import GapDetectionState, PaperRef

logger = logging.getLogger(__name__)

# Minimum papers needed to run gap detection without a baseline search.
MIN_SESSION_PAPERS = 5

# Inline citation convention used across the project: "(Source: PAPER_ID)".
_SOURCE_RE = re.compile(r"\(Source:\s*([A-Za-z0-9]+)\)")


def collect_session_papers(messages: list[Any]) -> list[PaperRef]:
    """Extract the session's cited papers from chat *messages*, deduped.

    Handles two sources, in priority order, per message:
      1. A structured ``papers_cited`` list (dicts with ``paper_id``/``paperId``
         + optional ``title``/``year``/``url``) — DB/JSONB-style metadata.
      2. Inline ``(Source: PAPER_ID)`` citations in the message ``content``.

    Deduplicates by ``paper_id`` across all messages, preserving first-seen
    order.  Accepts both dict messages and pydantic-style objects.
    """
    papers: list[PaperRef] = []
    seen: set[str] = set()

    for message in messages or []:
        # 1. Structured papers_cited metadata (forward-compatible).
        for raw in _structured_citations(message):
            pid = raw.get("paper_id") or raw.get("paperId")
            if pid and pid not in seen:
                seen.add(pid)
                papers.append(
                    PaperRef(
                        paper_id=str(pid),
                        title=raw.get("title") or str(pid),
                        year=raw.get("year"),
                        url=raw.get("url"),
                        abstract=raw.get("abstract"),
                        source=raw.get("source"),
                    )
                )

        # 2. Inline (Source: ID) citations in the message content.
        for pid in _SOURCE_RE.findall(_content_of(message)):
            if pid not in seen:
                seen.add(pid)
                papers.append(PaperRef(paper_id=pid, title=pid))

    return papers


async def paper_check_node(state: GapDetectionState) -> dict[str, Any]:
    """LangGraph/Phase-0 node: flag whether a baseline search is needed.

    Reads ``state["session_papers"]``; returns ``{"baseline_triggered": bool}``.
    ``True`` when there are fewer than ``MIN_SESSION_PAPERS`` papers (the
    caller should run a baseline search before gap detection).
    """
    papers: list[PaperRef] = state.get("session_papers", [])
    triggered = len(papers) < MIN_SESSION_PAPERS
    logger.info(
        "paper_check_node: %d session paper(s) → baseline_triggered=%s",
        len(papers),
        triggered,
    )
    return {"baseline_triggered": triggered}


# ── Helpers ──────────────────────────────────────────────────────────


def _content_of(message: Any) -> str:
    """Return a message's text content (dict or object)."""
    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", "") or ""


def _structured_citations(message: Any) -> list[dict]:
    """Return a message's ``papers_cited`` list, or [] if absent/malformed."""
    if isinstance(message, dict):
        cited = message.get("papers_cited")
    else:
        cited = getattr(message, "papers_cited", None)
    if isinstance(cited, list):
        return [c for c in cited if isinstance(c, dict)]
    return []
