"""Tests for TIP-P3-05 — explicit_detector + verifier EXPLICIT routing.

Covers:
- detect_origin() pattern matching (EXPLICIT / LIMITATION / INFERRED)
- verifier_node: EXPLICIT gaps bypass NLI (confidence=1.0, verified=True)
- verifier_node: INFERRED gaps go through existing logic unchanged
- verifier_node: LIMITATION gaps go through NLI unchanged
- Pre-annotation: INFERRED gap upgraded to EXPLICIT if statement matches
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.explicit_detector import detect_origin
from backend.agent.gap_detection.schemas import (
    GapItem,
    GapOrigin,
    GapStatus,
    GapType,
    PaperRef,
)


# ── detect_origin unit tests ─────────────────────────────────────────


def test_detect_origin_explicit_future_work():
    """'Future work should explore X' → EXPLICIT, confidence=1.0"""
    origin, conf = detect_origin("Future work should explore long-context attention")
    assert origin == GapOrigin.EXPLICIT
    assert conf == 1.0


def test_detect_origin_explicit_open_question():
    """'remains an open problem' → EXPLICIT"""
    origin, conf = detect_origin("This remains an open problem in the field")
    assert origin == GapOrigin.EXPLICIT
    assert conf == 1.0


def test_detect_origin_explicit_further_investigation():
    """'warrants further investigation' → EXPLICIT"""
    origin, conf = detect_origin("This area warrants further investigation by the community")
    assert origin == GapOrigin.EXPLICIT
    assert conf == 1.0


def test_detect_origin_limitation_limited_to():
    """'Our method is limited to short sequences' → LIMITATION, confidence=0.9"""
    origin, conf = detect_origin("Our method is limited to sequences under 512 tokens")
    assert origin == GapOrigin.LIMITATION
    assert conf == 0.9


def test_detect_origin_limitation_key_limitation():
    """'A key limitation is...' → LIMITATION"""
    origin, conf = detect_origin("A key limitation of this study is the small sample size")
    assert origin == GapOrigin.LIMITATION
    assert conf == 0.9


def test_detect_origin_inferred_no_match():
    """No pattern match → INFERRED, confidence=0.0"""
    origin, conf = detect_origin("No paper combines X and Y for the Z task")
    assert origin == GapOrigin.INFERRED
    assert conf == 0.0


def test_detect_origin_inferred_empty():
    """Empty statement → INFERRED"""
    origin, conf = detect_origin("")
    assert origin == GapOrigin.INFERRED
    assert conf == 0.0


def test_detect_origin_limitation_wins_over_explicit_in_statement():
    """Statement with both limitation + future-work signals → LIMITATION (statement-level limit wins)."""
    # Statement itself contains 'limitation', so LIMITATION wins even if
    # paper_text has future-work language.
    origin, conf = detect_origin(
        "A key limitation of our approach",
        paper_text="Future work should address this",
    )
    assert origin == GapOrigin.LIMITATION
    assert conf == 0.9


def test_detect_origin_paper_text_used_for_extra_signal():
    """Pattern in paper_text (not statement) still triggers EXPLICIT."""
    origin, conf = detect_origin(
        "No study combines these methods",
        paper_text="Future research directions include combining these approaches",
    )
    assert origin == GapOrigin.EXPLICIT
    assert conf == 1.0


# ── verifier_node routing tests ───────────────────────────────────────

_VERIFIER = "backend.agent.gap_detection.nodes.verifier"


def _make_gap(
    statement: str,
    origin: GapOrigin = GapOrigin.INFERRED,
    n_papers: int = 0,
    confidence: float = 1.0,
) -> GapItem:
    import warnings
    papers = [PaperRef(paper_id=f"p{i}", title=f"P{i}") for i in range(n_papers)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return GapItem(
            gap_type=GapType.TOPICAL,
            origin=origin,
            statement=statement,
            supporting_papers=papers,
            confidence=confidence,
        )


@pytest.mark.asyncio
async def test_verifier_explicit_bypasses_nli():
    """EXPLICIT gap → NLI not called, confidence=1.0, verified=True."""
    gap = _make_gap("Future work should explore X", origin=GapOrigin.EXPLICIT, n_papers=1)
    state = {"candidate_gaps": [gap], "extracted_data": []}

    with patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mock_verify:
        from backend.agent.gap_detection.nodes.verifier import verifier_node
        result = await verifier_node(state)

    mock_verify.assert_not_called()
    assert len(result["verified_gaps"]) == 1
    out = result["verified_gaps"][0]
    assert out.confidence == 1.0
    assert out.verified is True
    assert out.origin == GapOrigin.EXPLICIT


@pytest.mark.asyncio
async def test_verifier_inferred_goes_through_existing_logic():
    """INFERRED gap with supporting papers → verified=True, NLI not called."""
    gap = _make_gap("No study compares X and Y", origin=GapOrigin.INFERRED, n_papers=2)
    state = {"candidate_gaps": [gap], "extracted_data": []}

    with patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mock_verify:
        from backend.agent.gap_detection.nodes.verifier import verifier_node
        result = await verifier_node(state)

    mock_verify.assert_not_called()
    assert result["verified_gaps"][0].verified is True


@pytest.mark.asyncio
async def test_verifier_preannotates_inferred_to_explicit():
    """INFERRED gap whose statement matches EXPLICIT pattern → upgraded before routing."""
    gap = _make_gap(
        "Future work should explore long-context attention",
        origin=GapOrigin.INFERRED,
        n_papers=1,
    )
    state = {"candidate_gaps": [gap], "extracted_data": []}

    with patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mock_verify:
        from backend.agent.gap_detection.nodes.verifier import verifier_node
        result = await verifier_node(state)

    mock_verify.assert_not_called()
    out = result["verified_gaps"][0]
    assert out.origin == GapOrigin.EXPLICIT
    assert out.confidence == 1.0
    assert out.verified is True


@pytest.mark.asyncio
async def test_verifier_limitation_still_goes_through_nli():
    """LIMITATION gap → NLI IS called (existing behavior preserved)."""
    gap = _make_gap(
        "A key limitation is sample size",
        origin=GapOrigin.LIMITATION,
        n_papers=1,
    )
    paper_ref = gap.supporting_papers[0]
    state = {
        "candidate_gaps": [gap],
        "extracted_data": [],
    }

    mock_claim = type("Claim", (), {"status": "supported"})()

    with patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mock_verify, \
         patch(f"{_VERIFIER}._decompose_claim", new_callable=AsyncMock) as mock_decompose:
        mock_verify.return_value = [mock_claim]
        mock_decompose.return_value = [gap.statement]

        from backend.agent.gap_detection.nodes.verifier import verifier_node
        result = await verifier_node(state)

    mock_verify.assert_called_once()


@pytest.mark.asyncio
async def test_verifier_limitation_not_overwritten_by_preannotation():
    """LIMITATION gap set by detector is NOT overwritten by detect_origin."""
    # Statement has no limitation pattern — but origin is already LIMITATION
    # because method_detector set it. Should NOT be changed to INFERRED.
    gap = _make_gap(
        "Combining BERT with CNN has not been studied in medical imaging",
        origin=GapOrigin.LIMITATION,
        n_papers=1,
    )
    state = {"candidate_gaps": [gap], "extracted_data": []}

    mock_claim = type("Claim", (), {"status": "supported"})()
    with patch(f"{_VERIFIER}.verify_claims", new_callable=AsyncMock) as mock_verify, \
         patch(f"{_VERIFIER}._decompose_claim", new_callable=AsyncMock) as mock_decompose:
        mock_verify.return_value = [mock_claim]
        mock_decompose.return_value = [gap.statement]

        from backend.agent.gap_detection.nodes.verifier import verifier_node
        result = await verifier_node(state)

    # NLI was called (LIMITATION routing, not EXPLICIT bypass)
    mock_verify.assert_called_once()
    # Origin unchanged
    assert result["verified_gaps"][0].origin == GapOrigin.LIMITATION
