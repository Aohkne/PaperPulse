"""VerifierNode — Phase 3 (Verify & Validate), step 1 of 2.

Grounds each candidate gap against the project's citation verifier
(``backend.shared.services.citation_verifier.verify_claims``), applying the
origin-dependent rule from REQ-G10:

* ``origin == LIMITATION`` → the limitation MUST be verifiable in at least
  one supporting paper, otherwise the gap is a hallucination and is
  dropped.  A *system* failure (timeout/exception) keeps the gap with
  ``verified=False`` so we never drop a real gap because of infra errors.
* ``origin == INFERRED`` → no per-limitation grounding required; the gap
  is verified when it cites real supporting papers.

NOTE (Level-2 deviation): TIP-G04 assumed ``services/verify.py`` with a
``verify(claim_text, paper_id)`` signature.  No such module exists.  The
real, reusable verifier that takes claim_text + paper_id is
``citation_verifier.verify_claims(list[Claim])`` (it runs
``search_snippet`` + LLM classification end-to-end).  ``agent/verifier.py``
is only a classifier (``run(claim, snippet)``) and needs a pre-fetched
snippet, so reusing it would mean re-implementing the snippet
orchestration — forbidden by the TIP.  We therefore reuse
``verify_claims`` intact, wrapping ``statement`` + ``paper_id`` into
``Claim`` objects.  See the completion report.

TIP-P2-05: Atomic-NLI decomposition added.
  - ``_decompose_claim(claim_text)`` breaks complex statements into atomic
    sub-claims via LLM (fallback: return [claim_text] on any failure, or
    when claim is short < 50 chars).
  - ``_most_restrictive_status(statuses)`` picks the worst status across
    all sub-claim verdicts.
  - ``_verify_limitation`` now decomposes ``gap.statement`` and verifies
    each sub-claim against each supporting paper, then maps the most
    restrictive combined status to ``_CONFIRMED/_PARTIAL/_NOT_CONFIRMED``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.agent.gap_detection.explicit_detector import detect_origin
from backend.agent.gap_detection.schemas import (
    GapDetectionState,
    GapItem,
    GapOrigin,
)
from backend.shared.models.claim import Claim
from backend.shared.services.citation_verifier import verify_claims
from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# A LIMITATION gap is only grounded when a supporting paper FULLY supports
# the statement.  "partial" is treated as a weak signal (keep but penalise).
_CONFIRMING_STATUSES = {"supported"}
_PARTIAL_STATUSES = {"partial"}

# Confidence multiplier applied to a LIMITATION gap grounded only by a
# "partial" verdict (no full "supported" match).
PARTIAL_CONFIDENCE_PENALTY = 0.6

# TIP-414: Evidence-based confidence constants — grounding axis no longer flat 1.0.
_CONF_EXPLICIT = 1.0               # Author explicitly stated this gap
_CONF_LIMITATION_CONFIRMED = 0.85  # NLI confirmed limitation statement
_CONF_LIMITATION_PARTIAL = 0.50    # NLI only partially supports limitation
_CONF_FALLBACK = 0.60              # NLI system error — cautious, not 1.0
_CONF_INFERRED_BASE = 0.40         # Base confidence when NLI is unavailable
_CONF_INFERRED_MAX = 0.85          # INFERRED never as certain as EXPLICIT

# Outcomes of attempting to ground a LIMITATION gap.
_CONFIRMED = "confirmed"  # ≥1 supporting paper → "supported"
_PARTIAL = "partial"  # no "supported" but ≥1 "partial"
_NOT_CONFIRMED = "not_confirmed"  # only "unsupported"/"uncertain"
_ERROR = "error"  # verifier system failure (exception)

# Atomic-NLI: status severity order (lower = more restrictive).
# Used by _most_restrictive_status() to collapse sub-claim verdicts.
_STATUS_ORDER: dict[str, int] = {
    "unsupported": 0,
    "partial": 1,
    "uncertain": 2,
    "supported": 3,
}

# Claims shorter than this skip decomposition (already atomic).
_MIN_CLAIM_LEN_FOR_DECOMPOSE = 50


async def verifier_node(state: GapDetectionState) -> dict[str, Any]:
    """LangGraph node: ground candidate gaps and produce ``verified_gaps``.

    Reads ``state["candidate_gaps"]``; returns the filtered/annotated list
    under ``verified_gaps``.  Never raises on external verifier failure.
    """
    candidates: list[GapItem] = state.get("candidate_gaps", [])
    verified: list[GapItem] = []

    # Build paper_abstracts from extracted_data so verify_claims Case C can
    # use the abstract text instead of always falling back to "uncertain".
    # ExtractedPaperData has no raw abstract field; we synthesise a proxy
    # from the fields that contain the paper's textual content.
    extracted_data_map = _build_abstracts_map(state)

    for gap in candidates:
        # Pre-annotation: upgrade INFERRED gaps that match explicit/limitation
        # patterns.  Gaps already marked LIMITATION by a detector are left alone.
        if gap.origin == GapOrigin.INFERRED:
            detected_origin, detected_conf = detect_origin(gap.statement)
            if detected_origin != GapOrigin.INFERRED:
                gap.origin = detected_origin
                gap.confidence = detected_conf

        # EXPLICIT: author stated this gap verbatim — bypass NLI, full confidence.
        if gap.origin == GapOrigin.EXPLICIT:
            gap.confidence = _CONF_EXPLICIT
            gap.verified = True
            verified.append(gap)
            continue

        if gap.origin == GapOrigin.INFERRED:
            # TIP-415: confidence now comes from atomic-NLI entailment strength,
            # not supporting-paper count. Paper count stays reserved for corpus_evidence.
            gap.confidence = await _inferred_confidence(gap, extracted_data_map)
            gap.verified = bool(gap.supporting_papers)
            verified.append(gap)
            continue

        # origin == LIMITATION → mandatory grounding.
        outcome = await _verify_limitation(gap, extracted_data_map)
        if outcome == _CONFIRMED:
            # TIP-414: NLI-confirmed limitation — high but not 1.0.
            gap.verified = True
            gap.confidence = _CONF_LIMITATION_CONFIRMED
            verified.append(gap)
        elif outcome == _PARTIAL:
            # TIP-414: weakly grounded — direct assignment, not a multiplier.
            gap.verified = False
            gap.confidence = _CONF_LIMITATION_PARTIAL
            verified.append(gap)
        elif outcome == _ERROR:
            # TIP-414: system failure — cautious fallback (was 1.0, now 0.60).
            gap.verified = False
            gap.confidence = _CONF_FALLBACK
            verified.append(gap)
        else:  # _NOT_CONFIRMED → hallucinated limitation, drop it.
            logger.info(
                "verifier_node: dropping unverifiable LIMITATION gap: %s",
                gap.statement[:80],
            )

    logger.info(
        "verifier_node: %d/%d candidate gaps retained",
        len(verified),
        len(candidates),
    )
    return {"verified_gaps": verified}


# ── Helpers ──────────────────────────────────────────────────────────


def _build_abstracts_map(state: GapDetectionState) -> dict[str, str]:
    """Build ``{paper_id → abstract_text}`` from ``state["extracted_data"]``.

    Priority (TIP-G06-R):
    1. **Raw abstract** (``item.abstract``) — persisted directly from Semantic
       Scholar by the extractor node.  Independent from LLM extraction, so it
       cannot circularly contain the ``limitation_statements`` that generated
       the gap being verified.
    2. **Proxy fallback** — concatenation of ``key_claims``,
       ``limitation_statements``, and ``methodology`` — used ONLY when the raw
       abstract is None or empty (e.g. older papers with no S2 abstract).

    Papers whose abstract text (raw or proxy) is empty are omitted; Case C in
    ``verify_claims`` silently skips keys that are absent from the dict.
    """
    extracted: list = state.get("extracted_data", []) or []
    result: dict[str, str] = {}
    for item in extracted:
        pid = item.paper_ref.paper_id if item.paper_ref else None
        if not pid:
            continue

        # 1. Prefer raw abstract (non-circular, independent of LLM extraction).
        if item.abstract and item.abstract.strip():
            result[pid] = item.abstract.strip()
            continue

        # 2. Fallback proxy from LLM-extracted fields (used only when raw is absent).
        parts: list[str] = []
        if item.key_claims:
            parts.append(" ".join(item.key_claims))
        if item.limitation_statements:
            parts.append(" ".join(item.limitation_statements))
        if item.methodology:
            parts.append(item.methodology)
        proxy = " ".join(parts).strip()
        if proxy:
            result[pid] = proxy
    return result


async def _verify_limitation(gap: GapItem, paper_abstracts: dict[str, str]) -> str:
    """Attempt to ground a LIMITATION gap in its supporting papers.

    TIP-P2-05: atomic-NLI decomposition.
    The gap statement is first decomposed into atomic sub-claims via
    :func:`_decompose_claim`.  Each sub-claim is then verified against every
    supporting paper.  The most restrictive status across all
    (sub-claim, paper) pairs determines the overall outcome:

    Returns:
        ``_CONFIRMED``     — ≥1 (sub-claim, paper) pair is fully supported.
        ``_PARTIAL``       — no full support, but ≥1 "partial" verdict.
        ``_NOT_CONFIRMED`` — only "unsupported"/"uncertain" verdicts.
        ``_ERROR``         — verifier system failure (gap kept, not penalised).
    """
    if not gap.supporting_papers:
        # A LIMITATION gap with no citation cannot be grounded.
        return _NOT_CONFIRMED

    # ── P2-05: Decompose statement into atomic sub-claims ──
    sub_claim_texts = await _decompose_claim(gap.statement)

    # Build per-gap abstracts subset (only supporting paper IDs).
    gap_abstracts = {
        ref.paper_id: paper_abstracts[ref.paper_id]
        for ref in gap.supporting_papers
        if ref.paper_id in paper_abstracts
    }

    # Verify each (sub-claim, supporting paper) pair.
    all_statuses: list[str] = []
    try:
        for sc_text in sub_claim_texts:
            claims = [
                Claim(text=sc_text, paper_id=ref.paper_id)
                for ref in gap.supporting_papers
            ]
            results = await verify_claims(claims, paper_abstracts=gap_abstracts or None)
            all_statuses.extend(c.status for c in results)
    except Exception:
        logger.warning(
            "verifier_node: verify_claims failed for LIMITATION gap (%s) — keeping with verified=False",
            gap.statement[:80],
            exc_info=True,
        )
        return _ERROR

    # Map most-restrictive sub-claim status to outcome.
    worst = _most_restrictive_status(
        [s for s in all_statuses if s not in ("pending",)]
    )
    if worst in _CONFIRMING_STATUSES:
        return _CONFIRMED
    if worst in _PARTIAL_STATUSES:
        return _PARTIAL
    return _NOT_CONFIRMED


def _clamp(value: float) -> float:
    """Clamp a confidence value to the valid [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))


async def _inferred_confidence(gap: GapItem, paper_abstracts: dict[str, str]) -> float:
    """Atomic-NLI confidence for INFERRED gaps.

    Confidence is driven by entailment strength across the gap statement's
    atomic sub-claims, then modulated by the origin tier floor/cap.
    If NLI is unavailable or fails, fall back to a safe origin-tier default.
    """
    if not gap.supporting_papers:
        return _CONF_INFERRED_BASE

    try:
        sub_claim_texts = await _decompose_claim(gap.statement)
        if not sub_claim_texts:
            return _CONF_INFERRED_BASE

        gap_abstracts = {
            ref.paper_id: paper_abstracts[ref.paper_id]
            for ref in gap.supporting_papers
            if ref.paper_id in paper_abstracts
        }
        if not gap_abstracts:
            return _CONF_INFERRED_BASE

        statuses: list[str] = []
        for sc_text in sub_claim_texts:
            claims = [Claim(text=sc_text, paper_id=ref.paper_id) for ref in gap.supporting_papers]
            results = await verify_claims(claims, paper_abstracts=gap_abstracts or None)
            statuses.extend(c.status for c in results)

        worst = _most_restrictive_status([s for s in statuses if s not in ("pending",)])
        status_score = {
            "supported": 1.0,
            "partial": 0.66,
            "uncertain": 0.46,
            "unsupported": 0.22,
        }.get(worst, 0.46)
        paper_bonus = min(len(gap.supporting_papers) / 20.0, 0.12)
        raw = _CONF_INFERRED_BASE + (0.45 * status_score) + paper_bonus
        return _clamp(min(raw, _CONF_INFERRED_MAX))
    except Exception:
        logger.warning(
            "verifier_node: inferred NLI confidence failed for gap (%s) — using fallback",
            gap.statement[:80],
            exc_info=True,
        )
        return _CONF_INFERRED_BASE


# ── Atomic-NLI helpers (TIP-P2-05) ─────────────────────────────────────────────


async def _decompose_claim(claim_text: str) -> list[str]:
    """Decompose a complex claim into atomic sub-claims via LLM.

    Returns a list of 1-assertion sub-claim strings.  Falls back to
    ``[claim_text]`` (no decomposition) when:

    * The claim is short (< ``_MIN_CLAIM_LEN_FOR_DECOMPOSE`` characters) —
      already atomic, no extra LLM call needed.
    * The LLM call fails for any reason (exception, empty response).
    * The LLM returns invalid JSON or a non-list value.

    This function is intentionally defensive: any failure is silent (logged
    at DEBUG level) and the caller always receives a usable list.
    """
    # Skip decomposition for short claims — already atomic.
    if len(claim_text) < _MIN_CLAIM_LEN_FOR_DECOMPOSE:
        return [claim_text]

    prompt = (
        "Break the following research claim into atomic sub-claims "
        "(each expressing exactly ONE assertion).\n"
        "Output ONLY a JSON array of strings, no preamble, no trailing text.\n\n"
        f"Claim: {claim_text}"
    )
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}])
        # Strip optional markdown fences (```json ... ```).
        cleaned = re.sub(r"```(?:json)?\s*|```", "", raw or "").strip()
        sub_claims = json.loads(cleaned)
        if isinstance(sub_claims, list) and sub_claims:
            return [str(s).strip() for s in sub_claims if str(s).strip()]
    except Exception:
        logger.debug(
            "_decompose_claim: LLM decomposition failed for claim (len=%d) — using original",
            len(claim_text),
            exc_info=True,
        )
    return [claim_text]  # fallback: treat as single atomic claim


def _most_restrictive_status(statuses: list[str]) -> str:
    """Return the most restrictive verification status from a list.

    Severity order (most → least restrictive):
      unsupported (0) > partial (1) > uncertain (2) > supported (3)

    Args:
        statuses: List of status strings from ``Claim.status``.

    Returns:
        The status with the lowest severity score.  Returns ``"uncertain"``
        when *statuses* is empty (safe default: neither confirms nor rejects).
    """
    if not statuses:
        return "uncertain"
    return min(statuses, key=lambda s: _STATUS_ORDER.get(s, 2))
