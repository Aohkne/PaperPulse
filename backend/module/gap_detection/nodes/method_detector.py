"""MethodDetectorNode — Phase 2 (Analyze), step 2 of 3.

Builds a method × domain matrix from the extracted papers (which method
was applied to which domain/dataset) and asks the LLM to find plausible
method-domain combinations that are MISSING from the set.  Also mines
explicit ``limitation_statements`` ("we did not try method X").

Each detected gap is emitted as a ``GapItem`` with
``gap_type=METHODOLOGICAL``; ``origin=LIMITATION`` when the gap derives
from a limitation statement, otherwise ``origin=INFERRED``.

Reuses the extractor's plain-JSON-prompt + parse + single-retry pattern
(``_parse_llm_json``).  No LangChain structured output.

TIP-P2-04: Co-occurrence filtering wired in.  Before sending to the LLM
the matrix row is annotated with underexplored status so the LLM focuses
on pairs that are genuinely missing (co_occurrence < CO_OCCURRENCE_THRESHOLD)
rather than fabricating gaps for well-covered pairs.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.module.gap_detection.co_occurrence import (
    build_co_occurrence,
    collect_corpus_vocab,
    find_underexplored_pairs,
)
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
    "Given a method × domain matrix describing which methods have been "
    "applied to which domains/datasets, you identify plausible but UNTRIED "
    "method-domain combinations, and you surface methodological gaps that "
    "the authors themselves flag in their limitation statements."
)

_USER_PROMPT_TMPL = """\
Below is a method × domain matrix for {n} papers, followed by explicit
limitation statements the authors made.

Method × domain matrix (per paper):
{matrix}

Limitation statements (per paper):
{limitations}

Find METHODOLOGICAL gaps:
1. Method-domain combinations that are reasonable to try but are MISSING
   from the matrix (e.g. method A works well, domain B is studied, yet
   A has not been applied to B).
2. Methodological gaps the authors explicitly state in their limitations
   (e.g. "we did not try method X").

For each gap, set "from_limitation" to true ONLY when the gap comes
directly from a limitation statement, otherwise false. List paper ids in
"supporting_paper_ids" using ONLY the ids above.
In the "statement" field, write a natural narrative describing the gap — do NOT include raw paper ids in the statement text.

Return a JSON object with EXACTLY this shape:
{{
  "gaps": [
    {{
      "statement": "<narrative describing the methodological gap>",
      "from_limitation": false,
      "supporting_paper_ids": ["<relevant paper id>"],
      "suggested_method": "<specific, actionable method or technique to address this gap — null if none is evident>",
      "falsifiability_condition": "<what result would show this methodological gap is already closed — null if not applicable>"
    }}
  ]
}}

If there are no clear methodological gaps, return {{"gaps": []}}.
Respond with ONLY the JSON object, no extra text."""


# ── Node entry point ────────────────────────────────────────────────


async def method_detector_node(state: GapDetectionState) -> dict[str, Any]:
    """LangGraph node: detect METHODOLOGICAL gaps.

    Reads ``state["extracted_data"]`` and appends any new methodological
    gaps to ``state["candidate_gaps"]``.  On insufficient data (<2 papers)
    or malformed LLM output (after one retry) the candidate list is
    returned unchanged.
    """
    extracted: list[ExtractedPaperData] = state.get("extracted_data", [])
    existing: list[GapItem] = state.get("candidate_gaps", [])

    if len(extracted) < 2:
        logger.info(
            "method_detector_node: only %d paper(s) — need ≥2 to compare, skipping",
            len(extracted),
        )
        return {"candidate_gaps": existing}

    paper_index = {epd.paper_ref.paper_id: epd.paper_ref for epd in extracted}

    # ── Co-occurrence filtering (TIP-P2-04) ──────────────────────────
    # Build the co-occurrence matrix and collect all corpus-level method/domain
    # tokens, then find under-explored pairs (count < CO_OCCURRENCE_THRESHOLD).
    # Pass this information to the LLM prompt so it avoids flagging well-covered
    # pairs as gaps.
    co_matrix = build_co_occurrence(extracted)
    all_methods, all_domains = collect_corpus_vocab(extracted)
    underexplored = set(find_underexplored_pairs(co_matrix, all_methods, all_domains))

    density_signal = state.get("density_signal")
    trusted_cells = set((density_signal or {}).get("trusted_cells", []) or [])
    if density_signal is not None:
        underexplored = {pair for pair in underexplored if f"{pair[0]}|{pair[1]}" in trusted_cells}

    matrix = _build_method_matrix(extracted, underexplored)
    limitations = _build_limitations_block(extracted)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _USER_PROMPT_TMPL.format(n=len(extracted), matrix=matrix, limitations=limitations),
        },
    ]

    parsed = await call_llm_with_retry(messages, llm=chat_completion, label="method_detector_node")
    if parsed is None:
        return {"candidate_gaps": existing}

    new_gaps: list[GapItem] = []
    for raw_gap in parsed.get("gaps", []) or []:
        if not isinstance(raw_gap, dict):
            continue
        statement = (raw_gap.get("statement") or "").strip()
        if not statement:
            continue
        from_limitation = bool(raw_gap.get("from_limitation"))
        origin = GapOrigin.LIMITATION if from_limitation else GapOrigin.INFERRED
        supporting = map_papers(ensure_list(raw_gap.get("supporting_paper_ids")), paper_index)
        sm = (raw_gap.get("suggested_method") or "").strip() or None
        fc = (raw_gap.get("falsifiability_condition") or "").strip() or None
        new_gaps.append(
            GapItem(
                gap_type=GapType.METHODOLOGICAL,
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

    logger.info("method_detector_node: detected %d methodological gap(s)", len(new_gaps))
    return {"candidate_gaps": [*existing, *new_gaps]}


# ── Helpers ──────────────────────────────────────────────────────────


def _build_method_matrix(extracted: list[ExtractedPaperData], underexplored: set | None = None) -> str:
    """Render a per-paper method/domain/dataset listing for the prompt.

    When *underexplored* is provided (a set of ``(method, domain)`` tuples from
    the co-occurrence filter), each method-domain combination in the listing is
    annotated with ``[UNDEREXPLORED]`` if the pair is below the coverage
    threshold, or ``[COVERED]`` otherwise.  This guides the LLM to focus on
    genuinely missing combinations rather than well-studied ones.
    """
    lines: list[str] = []
    for epd in extracted:
        method = epd.methodology or "(unspecified)"
        domain = ", ".join(epd.topics) or "(unspecified)"
        dataset = epd.dataset or "(unspecified)"

        # Annotate coverage status when co-occurrence filter is available.
        coverage_note = ""
        if underexplored is not None and epd.methodology and epd.topics:
            method_tok = epd.methodology.strip().lower()
            # Check if the primary method token has any underexplored domain pairs.
            has_underexplored = any((method_tok, d.strip().lower()) in underexplored for d in epd.topics)
            coverage_note = " [UNDEREXPLORED domains exist]" if has_underexplored else " [COVERED]"

        lines.append(
            f"- id={epd.paper_ref.paper_id} | title={epd.paper_ref.title}\n"
            f"    method: {method}{coverage_note}\n"
            f"    domain/topics: {domain}\n"
            f"    dataset: {dataset}"
        )
    return "\n".join(lines)


def _build_limitations_block(extracted: list[ExtractedPaperData]) -> str:
    """Render per-paper limitation statements; '(none)' if there are none."""
    lines: list[str] = []
    for epd in extracted:
        if not epd.limitation_statements:
            continue
        joined = "; ".join(epd.limitation_statements)
        lines.append(f"- id={epd.paper_ref.paper_id}: {joined}")
    return "\n".join(lines) if lines else "(none)"
