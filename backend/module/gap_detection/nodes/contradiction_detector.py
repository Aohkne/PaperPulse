"""ContradictionDetectorNode — Phase 2 (Analyze), step 3 of 3.

Cross-compares the ``key_claims`` of every paper and asks the LLM to find
pairs of CONTRADICTORY claims (paper A asserts X, paper B asserts ¬X on
the same question).  For each contradiction it also produces a
``context_explanation`` (REQ-G11) — the plausible reason behind the
disagreement (different dataset, year, scope, …).

Each detected gap is emitted as a ``GapItem`` with
``gap_type=CONTRADICTION``, ``origin=INFERRED``,
``status=NEEDS_RESOLUTION`` and BOTH papers in ``supporting_papers``.

Reuses the extractor's plain-JSON-prompt + parse + single-retry pattern
(``_parse_llm_json``).  No LangChain structured output.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.module.gap_detection.nodes._detector_common import call_llm_with_retry
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
    "Given the key claims made by a set of papers, you find pairs of "
    "papers whose claims CONTRADICT each other on the same question, and "
    "you explain the plausible reason for each disagreement."
)

_USER_PROMPT_TMPL = """\
Below are the key claims of {n} papers.

Claims (per paper):
{claims}

Find pairs of papers whose claims CONTRADICT one another on the same
underlying question (paper A asserts something, paper B asserts the
opposite). For each contradiction, write a context_explanation: the
plausible reason for the disagreement (e.g. different dataset, different
year, different study scope or population).

For the "paper_id_a" and "paper_id_b" fields: use ONLY the paper ids listed above.
The two ids MUST be different papers.
In the "statement" narrative text: refer to papers by their title (e.g. "Smith et al.") — NEVER write raw paper ids in the statement.

Return a JSON object with EXACTLY this shape:
{{
  "contradictions": [
    {{
      "statement": "<narrative describing the contradiction>",
      "paper_id_a": "<id of first paper>",
      "paper_id_b": "<id of second, conflicting paper>",
      "context_explanation": "<plausible reason for the disagreement>",
      "suggested_method": "<specific method to resolve or investigate this contradiction — null if none is evident>",
      "falsifiability_condition": "<what finding would resolve the contradiction in favour of one side — null if not applicable>"
    }}
  ]
}}

If there are no contradictions, return {{"contradictions": []}}.
Respond with ONLY the JSON object, no extra text."""


# ── Node entry point ────────────────────────────────────────────────


async def contradiction_detector_node(state: GapDetectionState) -> dict[str, Any]:
    """LangGraph node: detect CONTRADICTION gaps between paper claims.

    Reads ``state["extracted_data"]`` and appends any new contradiction
    gaps to ``state["candidate_gaps"]``.  On insufficient data (<2 papers)
    or malformed LLM output (after one retry) the candidate list is
    returned unchanged.  A contradiction is only kept when BOTH cited
    papers resolve to real papers in the set.
    """
    extracted: list[ExtractedPaperData] = state.get("extracted_data", [])
    existing: list[GapItem] = state.get("candidate_gaps", [])

    if len(extracted) < 2:
        logger.info(
            "contradiction_detector_node: only %d paper(s) — need ≥2 to compare, skipping",
            len(extracted),
        )
        return {"candidate_gaps": existing}

    paper_index = {epd.paper_ref.paper_id: epd.paper_ref for epd in extracted}
    claims = _build_claims_block(extracted)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_PROMPT_TMPL.format(n=len(extracted), claims=claims)},
    ]

    parsed = await call_llm_with_retry(messages, llm=chat_completion, label="contradiction_detector_node")
    if parsed is None:
        return {"candidate_gaps": existing}

    new_gaps: list[GapItem] = []
    for raw_gap in parsed.get("contradictions", []) or []:
        if not isinstance(raw_gap, dict):
            continue
        statement = (raw_gap.get("statement") or "").strip()
        explanation = (raw_gap.get("context_explanation") or "").strip()
        ref_a = paper_index.get(str(raw_gap.get("paper_id_a")))
        ref_b = paper_index.get(str(raw_gap.get("paper_id_b")))

        # Require a real, distinct pair of papers and a non-empty narrative.
        if not statement or ref_a is None or ref_b is None or ref_a.paper_id == ref_b.paper_id:
            continue
        if not explanation:
            continue

        sm = (raw_gap.get("suggested_method") or "").strip() or None
        fc = (raw_gap.get("falsifiability_condition") or "").strip() or None
        new_gaps.append(
            GapItem(
                gap_type=GapType.CONTRADICTION,
                origin=GapOrigin.INFERRED,
                status=GapStatus.NEEDS_RESOLUTION,
                statement=statement,
                supporting_papers=[ref_a, ref_b],
                context_explanation=explanation,
                confidence=1.0,
                verified=False,
                suggested_method=sm,
                falsifiability_condition=fc,
            )
        )

    logger.info("contradiction_detector_node: detected %d contradiction gap(s)", len(new_gaps))
    return {"candidate_gaps": [*existing, *new_gaps]}


# ── Helpers ──────────────────────────────────────────────────────────


def _build_claims_block(extracted: list[ExtractedPaperData]) -> str:
    """Render a per-paper key-claims listing for the prompt."""
    lines: list[str] = []
    for epd in extracted:
        if epd.key_claims:
            claims = "; ".join(epd.key_claims)
        else:
            claims = "(no explicit claims)"
        lines.append(f"- id={epd.paper_ref.paper_id} | title={epd.paper_ref.title}\n    claims: {claims}")
    return "\n".join(lines)
