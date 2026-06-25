"""SynthesizerNode — Phase 4 (Narrative Generation), final pipeline node.

Takes ``verified_gaps``, applies a configurable confidence floor (so gaps
weakened by compounding penalties are demoted to a short "weak signals"
list rather than discarded), generates an academic Vietnamese narrative
with inline citations (REQ-G02, REQ-G14), and assembles the final
``GapReport``.

The narrative is produced by the LLM (reusing ``chat_completion`` with the
extractor's call + single-retry style).  Because this is the LAST node,
it MUST never leave the pipeline empty: on LLM failure it falls back to a
deterministic template narrative.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from backend.agent.gap_detection.novelty import compute_novelty_score
from backend.agent.gap_detection.quality_scorer import rank_gaps_by_quality
from backend.agent.gap_detection.schemas import (
    GapDetectionState,
    GapItem,
    GapOrigin,
    GapQuery,
    GapReport,
    GapStatus,
    GapType,
    PaperRef,
)
from backend.agent.gap_detection.settings import get_intent_off_penalty, get_top_k_gaps
from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────────

# Gaps with confidence below this floor are demoted to "weak signals".
MIN_CONFIDENCE_FOR_MAIN = 0.25

# Narrative ordering: easy → hard, matching the detector pipeline.
_TYPE_ORDER: dict[GapType, int] = {
    GapType.TOPICAL: 0,
    GapType.METHODOLOGICAL: 1,
    GapType.CONTRADICTION: 2,
}

_STATUS_TAGS: dict[GapStatus, str] = {
    GapStatus.OPEN: "[OPEN GAP]",
    GapStatus.PARTIALLY_FILLED: "[PARTIALLY FILLED]",
    GapStatus.NEEDS_RESOLUTION: "[NEEDS RESOLUTION]",
}

# Downstream action hooks (REQ-G12) — suggestion text only, no engine here.
_ACTION_HOOKS = (
    "---\n"
    "Suggested next steps: you can request \"find more papers for this gap\" "
    "to strengthen the evidence, or \"export Research Gap section\" to insert "
    "it directly into your manuscript."
)

_EMPTY_MESSAGE = (
    "No clear research gaps were detected from the current paper set. "
    "Consider expanding the search scope or adding more papers for a "
    "deeper analysis."
)


# ── Rejection gate ──────────────────────────────────────────────────

_PLACEHOLDER_LOWER: frozenset[str] = frozenset({
    "", "n/a", "none", "not specified", "not applicable", "unknown", "tbd",
})


def _is_emittable(gap: GapItem) -> bool:
    """Return True if gap should appear in the final report."""
    if gap.origin == GapOrigin.EXPLICIT:
        return True

    def _real(s: str | None) -> bool:
        return bool(s and s.strip().lower() not in _PLACEHOLDER_LOWER)

    return _real(gap.suggested_method) or _real(gap.falsifiability_condition)


# ── Intent re-score helpers (TIP-402) ───────────────────────────────


def _gap_aligned_with_intent(gap: GapItem, user_intent: str) -> bool:
    """True if any word-stem from the intent label appears in the gap statement.

    Uses 5-char prefix stems to handle morphological variants (e.g. "optim"
    matches "optimization", "optimized", "optimal").  Tokens ≤3 chars are
    skipped to avoid matching prepositions.  On empty token list returns True
    (cannot determine -> assume aligned, no penalty).
    """
    tokens = [t for t in re.split(r"[_\-\s]+", user_intent.lower()) if len(t) > 3]
    if not tokens:
        return True
    stems = [t[:5] for t in tokens]
    gap_text = (gap.statement or "").lower()
    return any(stem in gap_text for stem in stems)


def _intent_rescore(
    gaps: list[GapItem],
    user_intent: str,
    penalty: float,
) -> list[GapItem]:
    """Re-sort gaps using quality_score × penalty for off-intent gaps.

    quality_score on each GapItem is NOT mutated — the penalty only affects
    the sort key used for top-k selection.
    """
    def _key(g: GapItem) -> float:
        base = g.quality_score or 0.0
        return base if _gap_aligned_with_intent(g, user_intent) else base * penalty

    return sorted(gaps, key=_key, reverse=True)


# ── Unicode normalization ────────────────────────────────────────────

def normalize_vi(text: str) -> str:
    """Normalize Unicode NFD → NFC to fix split Vietnamese diacritics.

    LLMs sometimes return text in NFD (decomposed) form where combining
    diacritics appear as separate characters, causing garbled display.
    NFC re-composes them into the expected precomposed form.

    Pure function: never raises, returns text unchanged if falsy.
    """
    if not text:
        return text
    return unicodedata.normalize("NFC", text)


# ── LLM prompt ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an academic research assistant helping researchers write the "
    "'Research Gap' section. Write in a clear, academic English style. "
    "You MUST NOT fabricate citations — use only the citation tokens "
    "provided for each gap."
)

_USER_PROMPT_TMPL = """\
Below is a list of verified research gaps in the order they should be presented:

{gap_blocks}

Write an academic English narrative presenting each gap in the given order. Requirements:
- Frame each gap as "Although <X> has been extensively studied, <Y> remains unaddressed...".
- BEGIN each gap with the exact status tag provided (e.g. [OPEN GAP]).
- Insert the provided citation tokens INLINE within the sentence — do not fabricate any.
- For contradiction-type gaps: mention BOTH conflicting papers and present the given
  context_explanation to explain the source of disagreement.
- Do not add a conclusion or action suggestions (those will be added separately).

Return only the narrative, no extra headings."""


# ── Node entry point ────────────────────────────────────────────────


async def synthesizer_node(
    state: GapDetectionState,
    *,
    min_confidence: float = MIN_CONFIDENCE_FOR_MAIN,
) -> dict[str, Any]:
    """LangGraph node: build the final ``GapReport`` from verified gaps.

    Reads ``state["verified_gaps"]`` and ``state["session_papers"]``;
    returns ``{"final_report": GapReport(...)}``.  Never crashes — uses a
    template fallback when the LLM narrative fails.
    """
    verified: list[GapItem] = state.get("verified_gaps", [])
    papers_analyzed = len(state.get("session_papers", []))
    baseline_triggered = bool(state.get("baseline_triggered", False))
    total_count = len(verified)

    # TIP-401: wire novelty scores (compute_novelty_score was defined but never called)
    for gap in verified:
        if gap.novelty_score is None:
            gap.novelty_score = await compute_novelty_score(gap.statement)

    # TIP-401: rejection gate — LIMITATION/INFERRED need ≥1 enrichment field
    emittable = [g for g in verified if _is_emittable(g)]
    if len(emittable) < len(verified):
        logger.info(
            "synthesizer_node: rejection gate filtered %d/%d gaps (no enrichment fields)",
            len(verified) - len(emittable),
            len(verified),
        )

    # Phase 3: rank by quality; intent re-score BEFORE top-k cut (TIP-402).
    try:
        all_ranked = rank_gaps_by_quality(emittable, top_k=len(emittable))
    except Exception:
        logger.warning("synthesizer_node: rank_gaps_by_quality failed — using fallback ordering")
        all_ranked = sorted(emittable, key=lambda g: -g.confidence)

    gap_query: GapQuery | None = state.get("gap_query")  # type: ignore[assignment]
    if gap_query is not None and gap_query.user_intent is not None:
        penalty = get_intent_off_penalty()
        off_count = sum(
            1 for g in all_ranked if not _gap_aligned_with_intent(g, gap_query.user_intent)
        )
        all_ranked = _intent_rescore(all_ranked, gap_query.user_intent, penalty)
        logger.info(
            "synthesizer_node: intent re-score applied (intent=%r, penalty=%.2f, off_intent=%d/%d)",
            gap_query.user_intent, penalty, off_count, len(all_ranked),
        )

    all_ranked = _dedup_gaps_by_jaccard(all_ranked)
    top_gaps = all_ranked[:get_top_k_gaps()]
    ordered = sorted(top_gaps, key=lambda g: (_TYPE_ORDER.get(g.gap_type, 99), -(g.quality_score or g.confidence)))
    main_gaps = [g for g in ordered if g.confidence >= min_confidence]
    weak_gaps = [g for g in ordered if g.confidence < min_confidence]

    # Phase 3.15: populate per-gap analysis — None when no enrichment fields
    for gap in ordered:
        gap.analysis = _build_gap_analysis(gap)

    # Build summary narrative (template — no LLM)
    k = len(ordered)
    if k == 0:
        narrative = _EMPTY_MESSAGE
    elif total_count > k:
        narrative = (
            f"Showing top {k}/{total_count} research gaps by quality "
            f"(from {total_count} gaps detected). "
            f"See details in each gap card below."
        )
    else:
        narrative = f"Detected {k} research gap(s). See details in each gap card below."
    logger.debug("synthesizer_node: narrative repr[:60]=%r", narrative[:60])

    report = GapReport(
        papers_analyzed=papers_analyzed,
        gaps=[*main_gaps, *weak_gaps],
        narrative=narrative,
        baseline_triggered=baseline_triggered,
    )
    logger.info(
        "synthesizer_node: %d main gap(s), %d weak gap(s), %d papers analysed",
        len(main_gaps),
        len(weak_gaps),
        papers_analyzed,
    )
    return {"final_report": report}


# ── Narrative assembly ──────────────────────────────────────────────


async def _build_narrative(
    main_gaps: list[GapItem],
    weak_gaps: list[GapItem],
    total_count: int = 0,
) -> str:
    """Assemble the full narrative: ranking prefix + main analysis + weak signals + hooks."""
    if not main_gaps and not weak_gaps:
        return f"{_EMPTY_MESSAGE}\n\n{_ACTION_HOOKS}"

    k = len(main_gaps) + len(weak_gaps)
    prefix = (
        f"Showing top {k}/{total_count} research gaps by quality "
        f"(from {total_count} gaps detected):"
    ) if total_count > k else ""

    if main_gaps:
        main_text = await _generate_main_narrative(main_gaps)
        if main_text is None:
            logger.warning("synthesizer_node: LLM narrative failed — using template fallback")
            main_text = _fallback_narrative(main_gaps)
    else:
        # Everything was demoted — keep the report meaningful.
        main_text = (
            "All detected gaps have low confidence; "
            "see the Weak Signals section below for your own assessment."
        )

    sections = [s for s in [prefix, main_text] if s]
    weak_section = _build_weak_section(weak_gaps)
    if weak_section:
        sections.append(weak_section)
    sections.append(_ACTION_HOOKS)
    return "\n\n".join(sections)


async def _generate_main_narrative(main_gaps: list[GapItem]) -> str | None:
    """LLM-generate the main narrative, retrying once. ``None`` on failure."""
    gap_blocks = "\n\n".join(_gap_prompt_block(i, g) for i, g in enumerate(main_gaps, 1))
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_PROMPT_TMPL.format(gap_blocks=gap_blocks)},
    ]

    for attempt in range(2):  # try + 1 retry
        try:
            raw = await chat_completion(messages)
            text = (raw or "").strip()
            if not text:
                raise ValueError("empty narrative")
            return text
        except Exception:
            if attempt == 0:
                logger.warning("synthesizer_node: narrative generation failed, retrying…", exc_info=True)
            else:
                logger.warning(
                    "synthesizer_node: narrative generation failed after retry — falling back to template",
                    exc_info=True,
                )
    return None


def _fallback_narrative(main_gaps: list[GapItem]) -> str:
    """Deterministic template narrative (no LLM) listing the main gaps."""
    lines = ["## Detected Research Gaps"]
    for i, gap in enumerate(main_gaps, 1):
        tag = _STATUS_TAGS.get(gap.status, "")
        cites = _format_citations(gap.supporting_papers)
        line = f"{i}. {tag} [{gap.gap_type.value}] {gap.statement} {cites}".strip()
        lines.append(line)
        if gap.gap_type == GapType.CONTRADICTION and gap.context_explanation:
            lines.append(f"   Context: {gap.context_explanation}")
    return "\n".join(lines)


def _build_weak_section(weak_gaps: list[GapItem]) -> str:
    """Short, un-analysed listing of low-confidence gaps."""
    if not weak_gaps:
        return ""
    lines = [
        "## Weak Signals (low confidence)",
        "Some lower-confidence signals that may warrant further review:",
    ]
    for gap in weak_gaps:
        tag = _STATUS_TAGS.get(gap.status, "")
        cites = _format_citations(gap.supporting_papers)
        lines.append(
            f"- {tag} ({gap.gap_type.value}, confidence {gap.confidence:.2f}) {gap.statement} {cites}".strip()
        )
    return "\n".join(lines)


# ── Jaccard dedup ────────────────────────────────────────────────────────────


def _jaccard(a: set[str], b: set[str]) -> float:
    """Compute Jaccard overlap on supporting-paper ID sets."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _dedup_gaps_by_jaccard(gaps: list[GapItem], threshold: float = 0.6) -> list[GapItem]:
    """Keep the best gap per Jaccard cluster and merge evidence quotes."""
    if not gaps:
        return []

    ordered = sorted(gaps, key=lambda g: (g.quality_score or g.confidence), reverse=True)
    kept: list[GapItem] = []
    for gap in ordered:
        current_ids = {p.paper_id for p in gap.supporting_papers if p.paper_id}
        merged = False
        for kept_gap in kept:
            kept_ids = {p.paper_id for p in kept_gap.supporting_papers if p.paper_id}
            if _jaccard(current_ids, kept_ids) >= threshold:
                for quote in gap.evidence_quotes:
                    if quote not in kept_gap.evidence_quotes:
                        kept_gap.evidence_quotes.append(quote)
                merged = True
                break
        if not merged:
            kept.append(gap)
    return kept


# ── Citation guard ──────────────────────────────────────────────────

# Matches any bracketed token, e.g. "[Deep Nets, 2020]", "[p3]", "[OPEN GAP]".
_BRACKET_TOKEN_RE = re.compile(r"\[[^\[\]]+\]")

# Inserted in place of a citation that cannot be matched to a real paper.
_UNVERIFIED_MARKER = "[unverified citation]"


def _validate_citations(narrative: str, allowed_papers: list[PaperRef]) -> str:
    """Strip citation tokens the LLM invented (REQ-G14 guard).

    Keeps a bracketed token only when it is either a protected tag
    (status / gap-type) or an exact citation token for one of
    *allowed_papers*.  Any other bracketed token — a citation that does
    not match a real supporting paper — is replaced with a soft marker and
    logged.  Analysis prose (non-bracketed text) is never touched.
    """
    allowed = {_format_citation(p) for p in allowed_papers}
    protected = set(_STATUS_TAGS.values()) | {f"[{gap_type.value}]" for gap_type in GapType}
    protected.add(_UNVERIFIED_MARKER)

    removed: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in protected or token in allowed:
            return token
        removed.append(token)
        return _UNVERIFIED_MARKER

    cleaned = _BRACKET_TOKEN_RE.sub(_replace, narrative)
    if removed:
        logger.warning(
            "synthesizer_node: removed %d unverified citation token(s): %s",
            len(removed),
            removed,
        )
    return cleaned


# ── Citation helpers ────────────────────────────────────────────────


_ORIGIN_LABELS: dict[GapOrigin, str] = {
    GapOrigin.EXPLICIT: "Explicit (stated by author)",
    GapOrigin.LIMITATION: "From acknowledged limitation",
    GapOrigin.INFERRED: "Inferred (from cross-comparison)",
}


def _build_gap_analysis(gap: GapItem) -> str | None:
    """Build enrichment-only analysis for the gap card collapsible section (no LLM).

    Only returns content when the gap has at least one enrichment field
    (suggested_method, falsifiability_condition, or evidence_quotes). Returns
    None when no enrichment exists so the FE can hide the toggle entirely.
    Statement and origin are deliberately excluded — they are already visible
    on the card and repeating them adds no value.
    """
    parts: list[str] = []

    if gap.suggested_method:
        parts.append(f"💡 Suggested method: {gap.suggested_method}")

    if gap.falsifiability_condition:
        parts.append(f"❓ This gap is refuted if: {gap.falsifiability_condition}")

    if gap.evidence_quotes:
        parts.append(f'📄 Evidence: "{gap.evidence_quotes[0]}"')

    if not parts:
        return None

    # NFC-normalize so user-provided content (suggested_method etc.) arriving in
    # NFD from the LLM renders correctly even when the labels are now English.
    return normalize_vi("\n".join(parts))


def _gap_prompt_block(index: int, gap: GapItem) -> str:
    """Render one gap as structured context for the narrative prompt."""
    quality_str = f"{gap.quality_score:.2f}" if gap.quality_score is not None else "N/A"
    lines = [
        f"Gap {index}:",
        f"  Type: {gap.gap_type.value}",
        f"  Origin: {_ORIGIN_LABELS.get(gap.origin, gap.origin.value)}",
        f"  Quality: {quality_str}",
        f"  Status tag: {_STATUS_TAGS.get(gap.status, '')}",
        f"  Statement: {gap.statement}",
        f"  Citation tokens (use ONLY these): {_format_citations(gap.supporting_papers) or '(none)'}",
    ]
    if gap.gap_type == GapType.CONTRADICTION and gap.context_explanation:
        lines.append(f"  Contradiction context: {gap.context_explanation}")

    if gap.false_gap_flag:
        lines.append("  Note: ⚠️ Related research may already exist — verify before concluding")

    if gap.novelty_score is not None and gap.novelty_score > 0.8:
        lines.append("  Assessment: ★ High-novelty gap")

    if gap.suggested_method:
        lines.append(f"  💡 Suggested method: {gap.suggested_method}")

    if gap.falsifiability_condition:
        lines.append(f"  ❓ Falsifiable if: {gap.falsifiability_condition}")

    if gap.evidence_quotes:
        lines.append(f"  Evidence: {gap.evidence_quotes[0][:200]}")

    return "\n".join(lines)


def _format_citations(papers: list[PaperRef]) -> str:
    """Join inline citation tokens for a list of papers (never fabricated)."""
    return "; ".join(_format_citation(p) for p in papers)


def _format_citation(ref: PaperRef) -> str:
    """Render a single inline citation token the frontend can link.

    Prefers ``[Title, Year]``; falls back to ``[Title]`` then ``[paper_id]``.
    """
    if ref.title and ref.year is not None:
        return f"[{ref.title}, {ref.year}]"
    if ref.title:
        return f"[{ref.title}]"
    return f"[{ref.paper_id}]"
