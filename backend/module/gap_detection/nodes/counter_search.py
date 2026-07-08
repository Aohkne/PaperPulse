"""CounterSearchNode — Phase 3 (Verify & Validate), step 2 of 2.

For every verified gap, runs a counter-search against Semantic Scholar
(reusing ``backend.shared.services.semantic_scholar.search_papers``) to check
whether recent literature has already *addressed* the gap.  If a paper
fills the gap, the gap is downgraded to ``PARTIALLY_FILLED`` and its
confidence is penalised; the filling paper(s) are attached as related
work.  Otherwise status and confidence are left untouched.

External failures (search or LLM) never crash the pipeline: the gap is
kept unchanged and a warning is logged.

Reuses the extractor's plain-JSON-prompt + parse pattern
(``_parse_llm_json`` / ``_ensure_list``).  No LangChain structured output.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.module.gap_detection import retrieval
from backend.module.gap_detection.nodes.extractor import _ensure_list, _parse_llm_json
from backend.module.gap_detection.schemas import (
    GapDetectionState,
    GapItem,
    GapStatus,
    PaperRef,
)
from backend.shared.models.paper import Paper
from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# Limit external API load: only inspect the top-N counter-search hits.
DEFAULT_SEARCH_LIMIT = 5

# Confidence multiplier applied when a gap is found to be partially filled.
FILLED_CONFIDENCE_PENALTY = 0.5

# ── LLM prompts ─────────────────────────────────────────────────────

_QUERY_SYSTEM = (
    "You turn a research-gap description into a concise Semantic Scholar "
    "search query (keywords only, no punctuation, max 12 words)."
)
_QUERY_USER_TMPL = """Research gap:
{statement}

Return ONLY the search query, nothing else."""

_ASSESS_SYSTEM = (
    "You assess whether a research gap has already been addressed by recent "
    "literature. You are given a gap description and a list of candidate "
    "papers (id + title + abstract). Decide if any paper directly addresses "
    "the gap."
)
_ASSESS_USER_TMPL = """Research gap:
{statement}

Candidate papers:
{papers}

Does any candidate paper directly ADDRESS (study / fill) this gap?
Return a JSON object with EXACTLY this shape:
{{
  "addressed": true,
  "addressing_paper_ids": ["<id of each paper that addresses the gap>"]
}}
Use only the paper ids listed above. If none address the gap, return
{{"addressed": false, "addressing_paper_ids": []}}.
Respond with ONLY the JSON object, no extra text."""


# ── Node entry point ────────────────────────────────────────────────


async def counter_search_node(state: GapDetectionState) -> dict[str, Any]:
    """LangGraph node: counter-search each verified gap against S2.

    Reads ``state["verified_gaps"]`` and returns the updated list under
    ``verified_gaps``.  Status/confidence are adjusted in place when a gap
    is found to be (partially) filled.  Never raises on external failure.
    """
    gaps: list[GapItem] = state.get("verified_gaps", [])
    updated: list[GapItem] = []

    for gap in gaps:
        try:
            query = await _build_query(gap.statement)
            results = await retrieval.search(query, limit=DEFAULT_SEARCH_LIMIT)
        except Exception:
            logger.warning(
                "counter_search_node: S2 search failed for gap (%s) — keeping status unchanged",
                gap.statement[:80],
                exc_info=True,
            )
            updated.append(gap)
            continue

        if not results:
            updated.append(gap)
            continue

        assessment = await _assess_addressed(gap.statement, results[:DEFAULT_SEARCH_LIMIT])
        if assessment is None:
            # LLM assessment failed → safe default: leave the gap untouched.
            updated.append(gap)
            continue

        addressed, addressing_ids = assessment
        if addressed:
            _mark_partially_filled(gap, results, addressing_ids)

        updated.append(gap)

    logger.info("counter_search_node: processed %d verified gap(s)", len(gaps))
    return {"verified_gaps": updated}


# ── Helpers ──────────────────────────────────────────────────────────


async def _build_query(statement: str) -> str:
    """Build a concise S2 search query from a gap statement via the LLM.

    Falls back to a truncated statement if the LLM call fails.
    """
    messages = [
        {"role": "system", "content": _QUERY_SYSTEM},
        {"role": "user", "content": _QUERY_USER_TMPL.format(statement=statement)},
    ]
    try:
        raw = await chat_completion(messages)
        query = raw.strip().strip('"').splitlines()[0].strip()
        return query or statement[:200]
    except Exception:
        logger.warning("counter_search_node: query generation failed — using raw statement", exc_info=True)
        return statement[:200]


async def _assess_addressed(statement: str, papers: list[Paper]) -> tuple[bool, list[str]] | None:
    """Ask the LLM whether any candidate paper addresses the gap.

    Returns ``(addressed, addressing_paper_ids)`` or ``None`` when the LLM
    call/parse fails after a single retry (caller then leaves gap as-is).
    """
    listing = _render_papers(papers)
    messages = [
        {"role": "system", "content": _ASSESS_SYSTEM},
        {"role": "user", "content": _ASSESS_USER_TMPL.format(statement=statement, papers=listing)},
    ]

    for attempt in range(2):  # try + 1 retry
        try:
            raw = await chat_completion(messages)
            parsed = _parse_llm_json(raw)
            if not isinstance(parsed, dict):
                raise ValueError("LLM JSON is not an object")
            addressed = bool(parsed.get("addressed"))
            ids = _ensure_list(parsed.get("addressing_paper_ids"))
            return addressed, ids
        except Exception:
            if attempt == 0:
                logger.warning("counter_search_node: assessment parse failed, retrying…", exc_info=True)
            else:
                logger.warning(
                    "counter_search_node: assessment parse failed after retry — skipping counter-search for gap",
                    exc_info=True,
                )
    return None


def _mark_partially_filled(gap: GapItem, results: list[Paper], addressing_ids: list[str]) -> None:
    """Downgrade a gap that recent literature has addressed.

    Sets ``status=PARTIALLY_FILLED``, applies the confidence penalty
    (clamped to [0, 1]) and attaches the addressing papers as related work
    — only real search results, never fabricated.
    """
    gap.status = GapStatus.PARTIALLY_FILLED
    gap.confidence = _clamp(gap.confidence * FILLED_CONFIDENCE_PENALTY)

    addressing = {str(pid) for pid in addressing_ids}
    existing_ids = {ref.paper_id for ref in gap.supporting_papers}
    for paper in results:
        if paper.paper_id in addressing and paper.paper_id not in existing_ids:
            gap.supporting_papers.append(
                PaperRef(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    year=paper.year,
                    url=paper.url,
                )
            )
            existing_ids.add(paper.paper_id)


def _render_papers(papers: list[Paper]) -> str:
    """Render candidate papers (id + title + truncated abstract) for the prompt."""
    lines: list[str] = []
    for paper in papers:
        abstract = (paper.abstract or "").strip().replace("\n", " ")
        if len(abstract) > 300:
            abstract = abstract[:300] + "…"
        lines.append(f"- id={paper.paper_id} | title={paper.title}\n    abstract: {abstract or '(none)'}")
    return "\n".join(lines)


def _clamp(value: float) -> float:
    """Clamp a confidence value to the valid [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))
