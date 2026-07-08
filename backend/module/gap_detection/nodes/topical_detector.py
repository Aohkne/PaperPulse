"""TopicalDetectorNode — Phase 2 (Analyze), step 1 of 3.

Builds a topic-coverage map from all extracted papers and asks the LLM
to identify research areas that are RELATED to the covered topics but
NOT studied within this paper set.  Each detected gap is emitted as a
``GapItem`` with ``gap_type=TOPICAL`` and ``origin=INFERRED``.

Reuses the extractor's plain-JSON-prompt + parse + single-retry pattern
(``_parse_llm_json``).  No LangChain structured output.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.module.gap_detection.nodes._detector_common import (
    call_llm_with_retry,
    ensure_list,
    map_papers,
)
from backend.module.gap_detection.schemas import (
    ExtractedPaperData,
    GapDetectionState,
    GapItem,
    GapOrigin,
    GapStatus,
    GapType,
)
from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# ── LLM prompt ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a research-gap analysis assistant. "
    "Given the topics already covered by a set of papers, you identify "
    "RELATED research areas or sub-topics that are conspicuously absent "
    "from the set — promising directions the existing literature points "
    "toward but does not actually study."
)

_USER_PROMPT_TMPL = """\
Below is a topic-coverage map of {n} papers. Each entry lists the paper
id, title, and the topics/keywords that paper covers.

Topic coverage map:
{coverage_map}

Identify research areas or sub-topics that are CLOSELY RELATED to what
these papers cover but are NOT themselves studied in this set (topical
gaps). For each gap, list the relevant paper ids in "supporting_paper_ids"
using ONLY the ids above.
In the "statement" field, write a natural narrative describing the gap — do NOT include raw paper ids in the statement text.

Return a JSON object with EXACTLY this shape:
{{
  "gaps": [
    {{
      "statement": "<narrative describing the uncovered related area>",
      "supporting_paper_ids": ["<id of a paper representing a neighbouring topic>"],
      "origin": "<'explicit' ONLY if one of the cited papers directly states this area as future work or an open problem; otherwise 'inferred'>",
      "suggested_method": "<specific, actionable approach to address this gap (e.g. 'Apply contrastive learning to X using Y benchmark') — null if no clear method is evident>",
      "falsifiability_condition": "<what empirical result would show this gap already has a solution (e.g. 'If paper X demonstrates Y on Z dataset, the gap is closed') — null if not applicable>"
    }}
  ]
}}

If there are no clear topical gaps, return {{"gaps": []}}.
Respond with ONLY the JSON object, no extra text."""


# ── Node entry point ────────────────────────────────────────────────


async def topical_detector_node(state: GapDetectionState) -> dict[str, Any]:
    """LangGraph node: detect TOPICAL gaps from the topic-coverage map.

    Reads ``state["extracted_data"]`` and appends any new topical gaps to
    ``state["candidate_gaps"]``.  Returns the full candidate list under
    the ``candidate_gaps`` key.  On insufficient data (<2 papers) or
    malformed LLM output (after one retry) the candidate list is returned
    unchanged.
    """
    extracted: list[ExtractedPaperData] = state.get("extracted_data", [])
    existing: list[GapItem] = state.get("candidate_gaps", [])

    if len(extracted) < 2:
        logger.info(
            "topical_detector_node: only %d paper(s) — need ≥2 to compare, skipping",
            len(extracted),
        )
        return {"candidate_gaps": existing}

    paper_index = {epd.paper_ref.paper_id: epd.paper_ref for epd in extracted}
    coverage_map = _build_coverage_map(extracted)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _USER_PROMPT_TMPL.format(n=len(extracted), coverage_map=coverage_map),
        },
    ]

    parsed = await call_llm_with_retry(messages, llm=chat_completion, label="topical_detector_node")
    if parsed is None:
        return {"candidate_gaps": existing}

    new_gaps: list[GapItem] = []
    for raw_gap in parsed.get("gaps", []) or []:
        if not isinstance(raw_gap, dict):
            continue
        statement = (raw_gap.get("statement") or "").strip()
        if not statement:
            continue
        supporting = map_papers(ensure_list(raw_gap.get("supporting_paper_ids")), paper_index)
        origin_raw = (raw_gap.get("origin") or "inferred").strip().lower()
        origin = GapOrigin.EXPLICIT if origin_raw == "explicit" else GapOrigin.INFERRED
        sm = (raw_gap.get("suggested_method") or "").strip() or None
        fc = (raw_gap.get("falsifiability_condition") or "").strip() or None
        new_gaps.append(
            GapItem(
                gap_type=GapType.TOPICAL,
                origin=origin,
                status=GapStatus.OPEN,
                statement=statement,
                supporting_papers=supporting,
                confidence=1.0,
                verified=False,
                suggested_method=sm,
                falsifiability_condition=fc,
            )
        )

    logger.info("topical_detector_node: detected %d topical gap(s)", len(new_gaps))
    return {"candidate_gaps": [*existing, *new_gaps]}


# ── Helpers ──────────────────────────────────────────────────────────


def _build_coverage_map(extracted: list[ExtractedPaperData]) -> str:
    """Render a compact per-paper topic/keyword listing for the prompt."""
    lines: list[str] = []
    for epd in extracted:
        topics = ", ".join(epd.topics) or "(none)"
        keywords = ", ".join(epd.keywords) or "(none)"
        lines.append(
            f"- id={epd.paper_ref.paper_id} | title={epd.paper_ref.title}\n"
            f"    topics: {topics}\n"
            f"    keywords: {keywords}"
        )
    return "\n".join(lines)
