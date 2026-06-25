"""Tests for TIP-414 — evidence-based grounding axis (confidence no longer flat 1.0).

Covers:
- _inferred_confidence(): derives confidence from atomic-NLI entailment
- verifier_node: INFERRED confidence set by NLI strength, not paper count
- verifier_node: EXPLICIT stays at 1.0 (EXPLICIT > INFERRED)
- verifier_node: LIMITATION CONFIRMED → _CONF_LIMITATION_CONFIRMED (0.85)
- verifier_node: LIMITATION PARTIAL → _CONF_LIMITATION_PARTIAL (0.50)
- verifier_node: LIMITATION ERROR → _CONF_FALLBACK (0.60)
- compute_quality_score: grounding axis now contributes to variance
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agent.gap_detection.schemas import (
    GapItem,
    GapOrigin,
    GapStatus,
    GapType,
    PaperRef,
)

_VERIFIER = "backend.agent.gap_detection.nodes.verifier"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_gap(
    statement: str = "A research area has not been studied",
    origin: GapOrigin = GapOrigin.INFERRED,
    n_papers: int = 2,
    confidence: float = 1.0,
    suggested_method: str | None = "Use method X",
    falsifiability_condition: str | None = "If Y is shown, gap is closed",
) -> GapItem:
    import warnings

    papers = [PaperRef(paper_id=f"p{i}", title=f"Paper {i}") for i in range(n_papers)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return GapItem(
            gap_type=GapType.TOPICAL,
            origin=origin,
            status=GapStatus.OPEN,
            statement=statement,
            supporting_papers=papers,
            confidence=confidence,
            suggested_method=suggested_method,
            falsifiability_condition=falsifiability_condition,
        )


# ── Unit tests: _inferred_confidence ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_inferred_confidence_changes_with_nli_strength():
    """Same paper count, different NLI strength → different grounding confidence."""
    from backend.agent.gap_detection.nodes.verifier import _inferred_confidence

    strong = _make_gap(
        statement="This method has only been partially explored on this dataset in many settings, and the claim requires multiple conditions.",
        origin=GapOrigin.INFERRED,
        n_papers=2,
    )
    weak = _make_gap(
        statement="This method may be relevant but there is little direct support.",
        origin=GapOrigin.INFERRED,
        n_papers=2,
    )

    with (
        patch(f"{_VERIFIER}._decompose_claim", new=AsyncMock(side_effect=[[strong.statement], [weak.statement]])),
        patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mv,
    ):
        mv.side_effect = [
            [MagicMock(status="supported"), MagicMock(status="supported")],
            [MagicMock(status="unsupported"), MagicMock(status="uncertain")],
        ]
        strong_score = await _inferred_confidence(strong, {"p0": "abstract"})
        weak_score = await _inferred_confidence(weak, {"p0": "abstract"})

    assert strong_score > weak_score


def test_inferred_confidence_max_below_explicit():
    """_CONF_INFERRED_MAX < _CONF_EXPLICIT — INFERRED always less confident."""
    from backend.agent.gap_detection.nodes.verifier import (
        _CONF_EXPLICIT,
        _CONF_INFERRED_MAX,
    )

    assert _CONF_INFERRED_MAX < _CONF_EXPLICIT


# ── Integration tests: verifier_node confidence routing ──────────────────────


@pytest.mark.asyncio
async def test_verifier_inferred_2_papers_confidence():
    """INFERRED gap with strong NLI support → confidence is elevated."""
    gap = _make_gap(origin=GapOrigin.INFERRED, n_papers=2)
    state = {
        "candidate_gaps": [gap],
        "extracted_data": [
            type("E", (), {
                "paper_ref": PaperRef(paper_id="p0", title="P0"),
                "abstract": "Strong abstract support",
                "key_claims": [],
                "limitation_statements": [],
                "methodology": None,
            })()
        ],
    }

    with (
        patch(f"{_VERIFIER}._decompose_claim", new=AsyncMock(return_value=[gap.statement])),
        patch(f"{_VERIFIER}.verify_claims", new=AsyncMock(return_value=[MagicMock(status="supported")])),
    ):
        from backend.agent.gap_detection.nodes.verifier import verifier_node

        result = await verifier_node(state)

    out = result["verified_gaps"][0]
    assert out.confidence > 0.40


@pytest.mark.asyncio
async def test_verifier_inferred_3_papers_confidence():
    """INFERRED gap with weaker NLI support stays below stronger support."""
    gap = _make_gap(origin=GapOrigin.INFERRED, n_papers=3)
    state = {
        "candidate_gaps": [gap],
        "extracted_data": [
            type("E", (), {
                "paper_ref": PaperRef(paper_id="p0", title="P0"),
                "abstract": "Weak abstract support",
                "key_claims": [],
                "limitation_statements": [],
                "methodology": None,
            })()
        ],
    }

    with (
        patch(f"{_VERIFIER}._decompose_claim", new=AsyncMock(return_value=[gap.statement])),
        patch(f"{_VERIFIER}.verify_claims", new=AsyncMock(return_value=[MagicMock(status="partial")])),
    ):
        from backend.agent.gap_detection.nodes.verifier import verifier_node

        result = await verifier_node(state)

    out = result["verified_gaps"][0]
    assert out.confidence < 0.85


@pytest.mark.asyncio
async def test_verifier_explicit_confidence_is_1():
    """EXPLICIT gap → confidence = 1.0 (unchanged by TIP-414)."""
    gap = _make_gap(
        statement="Future work should explore multimodal extensions",
        origin=GapOrigin.EXPLICIT,
        n_papers=1,
    )
    state = {"candidate_gaps": [gap], "extracted_data": []}

    with patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock):
        from backend.agent.gap_detection.nodes.verifier import verifier_node

        result = await verifier_node(state)

    out = result["verified_gaps"][0]
    assert out.confidence == pytest.approx(1.0, abs=1e-9)


@pytest.mark.asyncio
async def test_verifier_explicit_gt_inferred_same_papers():
    """Given same paper count, EXPLICIT confidence > INFERRED confidence."""
    gap_explicit = _make_gap(
        statement="Future work should explore X",
        origin=GapOrigin.EXPLICIT,
        n_papers=2,
    )
    gap_inferred = _make_gap(
        statement="No study combines method A and domain B",
        origin=GapOrigin.INFERRED,
        n_papers=2,
    )
    state = {"candidate_gaps": [gap_explicit, gap_inferred], "extracted_data": []}

    with patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock):
        from backend.agent.gap_detection.nodes.verifier import verifier_node

        result = await verifier_node(state)

    gaps_out = result["verified_gaps"]
    explicit_out = next(g for g in gaps_out if g.origin == GapOrigin.EXPLICIT)
    inferred_out = next(g for g in gaps_out if g.origin == GapOrigin.INFERRED)
    assert explicit_out.confidence > inferred_out.confidence


@pytest.mark.asyncio
async def test_verifier_limitation_confirmed_confidence():
    """LIMITATION gap NLI-CONFIRMED → confidence = 0.85."""
    gap = _make_gap(
        statement="A key limitation is that method X was not tested on dataset Y",
        origin=GapOrigin.LIMITATION,
        n_papers=1,
    )
    state = {"candidate_gaps": [gap], "extracted_data": []}

    mock_claim = MagicMock()
    mock_claim.status = "supported"

    with (
        patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mv,
        patch(f"{_VERIFIER}._decompose_claim", new_callable=AsyncMock) as md,
    ):
        mv.return_value = [mock_claim]
        md.return_value = [gap.statement]

        from backend.agent.gap_detection.nodes.verifier import (
            _CONF_LIMITATION_CONFIRMED,
            verifier_node,
        )

        result = await verifier_node(state)

    out = result["verified_gaps"][0]
    assert out.confidence == pytest.approx(_CONF_LIMITATION_CONFIRMED, abs=1e-9)
    assert out.verified is True


@pytest.mark.asyncio
async def test_verifier_limitation_partial_confidence():
    """LIMITATION gap with partial NLI → confidence = 0.50."""
    gap = _make_gap(
        statement="A key limitation is that method X was not tested on dataset Y",
        origin=GapOrigin.LIMITATION,
        n_papers=1,
    )
    state = {"candidate_gaps": [gap], "extracted_data": []}

    mock_claim = MagicMock()
    mock_claim.status = "partial"

    with (
        patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mv,
        patch(f"{_VERIFIER}._decompose_claim", new_callable=AsyncMock) as md,
    ):
        mv.return_value = [mock_claim]
        md.return_value = [gap.statement]

        from backend.agent.gap_detection.nodes.verifier import (
            _CONF_LIMITATION_PARTIAL,
            verifier_node,
        )

        result = await verifier_node(state)

    out = result["verified_gaps"][0]
    assert out.confidence == pytest.approx(_CONF_LIMITATION_PARTIAL, abs=1e-9)
    assert out.verified is False


@pytest.mark.asyncio
async def test_verifier_limitation_error_fallback_confidence():
    """LIMITATION gap where verify_claims raises → confidence = _CONF_FALLBACK (0.60), not 1.0."""
    gap = _make_gap(
        statement="A key limitation is that method X was not tested on dataset Y",
        origin=GapOrigin.LIMITATION,
        n_papers=1,
    )
    state = {"candidate_gaps": [gap], "extracted_data": []}

    with (
        patch(f"{_VERIFIER}.verify_claims", side_effect=RuntimeError("NLI down")),
        patch(
            f"{_VERIFIER}._decompose_claim",
            new=AsyncMock(return_value=[gap.statement]),
        ),
    ):
        from backend.agent.gap_detection.nodes.verifier import (
            _CONF_FALLBACK,
            verifier_node,
        )

        result = await verifier_node(state)

    out = result["verified_gaps"][0]
    assert out.confidence == pytest.approx(_CONF_FALLBACK, abs=1e-9)
    assert out.verified is False


# ── Quality score variation test ──────────────────────────────────────────────


def test_quality_score_varies_with_confidence():
    """With different confidence values, quality_score must differ (grounding axis works)."""
    from backend.agent.gap_detection.quality_scorer import compute_quality_score

    gap_high = _make_gap(n_papers=5)  # INFERRED but many papers → confidence higher
    gap_high.confidence = 0.85

    gap_low = _make_gap(n_papers=1)
    gap_low.confidence = 0.50

    score_high = compute_quality_score(gap_high)
    score_low = compute_quality_score(gap_low)

    assert score_high > score_low, (
        f"quality score should be higher for higher confidence: {score_high} vs {score_low}"
    )


def test_quality_breakdown_is_exposed_from_scorer():
    """quality_breakdown mirrors the normalized axes used by compute_quality_score."""
    from backend.agent.gap_detection.quality_scorer import compute_quality_score

    gap = _make_gap(n_papers=4, confidence=0.77, suggested_method=None, falsifiability_condition="If Y is shown, gap is closed")
    gap.novelty_score = 1.3

    score = compute_quality_score(gap)

    assert gap.quality_breakdown is not None
    assert set(gap.quality_breakdown.keys()) == {"grounding", "novelty", "actionable", "corpus_evidence"}
    assert gap.quality_breakdown["grounding"] == pytest.approx(0.77, abs=1e-9)
    assert gap.quality_breakdown["novelty"] == pytest.approx(0.65, abs=1e-9)
    assert gap.quality_breakdown["actionable"] == pytest.approx(0.5, abs=1e-9)
    assert gap.quality_breakdown["corpus_evidence"] == pytest.approx(0.8, abs=1e-9)
    assert score == pytest.approx(0.3333 * 0.77 + 0.2778 * 0.65 + 0.2222 * 0.5 + 0.1667 * 0.8, abs=1e-4)
