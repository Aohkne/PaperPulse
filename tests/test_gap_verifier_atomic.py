"""Tests for TIP-P2-05 — atomic-NLI: _decompose_claim + _most_restrictive_status + verifier wire.

Verifies:
- _decompose_claim() splits complex claims into sub-claims
- _decompose_claim() falls back to [claim_text] on LLM failure
- _decompose_claim() skips LLM for short claims (< 50 chars)
- _most_restrictive_status() returns "unsupported" for mixed statuses
- _most_restrictive_status() returns "uncertain" for empty list
- _verify_limitation() uses decomposition and maps outcome correctly
- Regression: test_gap_* all pass
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────

_VERIFIER = "backend.agent.gap_detection.nodes.verifier"


def _make_gap(statement: str, n_papers: int = 1, origin="LIMITATION"):
    from backend.agent.gap_detection.schemas import (
        GapItem,
        GapOrigin,
        GapStatus,
        GapType,
        PaperRef,
    )

    papers = [PaperRef(paper_id=f"p{i}", title=f"P{i}") for i in range(n_papers)]
    return GapItem(
        gap_type=GapType.TOPICAL,
        origin=GapOrigin.LIMITATION if origin == "LIMITATION" else GapOrigin.INFERRED,
        status=GapStatus.OPEN,
        statement=statement,
        supporting_papers=papers,
        confidence=1.0,
    )


# ── Part 1: _decompose_claim ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decompose_claim_splits_complex_claim() -> None:
    """AC: complex claim → ≥2 sub-claims."""
    from backend.agent.gap_detection.nodes.verifier import _decompose_claim

    sub_claims = ["X achieves SOTA on Y", "X has not been tested on W"]
    llm_response = json.dumps(sub_claims)

    with patch(f"{_VERIFIER}.chat_completion", new=AsyncMock(return_value=llm_response)):
        result = await _decompose_claim(
            "X achieves SOTA on Y and Z but has not been tested on W"  # len > 50
        )

    assert len(result) >= 2
    assert all(isinstance(s, str) for s in result)


@pytest.mark.asyncio
async def test_decompose_claim_fallback_on_llm_exception() -> None:
    """AC: LLM raises exception → returns [claim_text], no raise."""
    from backend.agent.gap_detection.nodes.verifier import _decompose_claim

    claim = "X achieves SOTA on Y and Z but has not been tested on W"
    with patch(f"{_VERIFIER}.chat_completion", side_effect=RuntimeError("LLM down")):
        result = await _decompose_claim(claim)

    assert result == [claim]


@pytest.mark.asyncio
async def test_decompose_claim_fallback_on_invalid_json() -> None:
    """LLM returns invalid JSON → returns [claim_text]."""
    from backend.agent.gap_detection.nodes.verifier import _decompose_claim

    claim = "X achieves SOTA on Y and Z but has not been tested on W"
    with patch(f"{_VERIFIER}.chat_completion", new=AsyncMock(return_value="not json at all")):
        result = await _decompose_claim(claim)

    assert result == [claim]


@pytest.mark.asyncio
async def test_decompose_claim_skips_llm_for_short_claim() -> None:
    """Claim < 50 chars → no LLM call, returns [claim_text]."""
    from backend.agent.gap_detection.nodes.verifier import _decompose_claim

    short_claim = "X is missing."  # len < 50
    mock_llm = AsyncMock()

    with patch(f"{_VERIFIER}.chat_completion", new=mock_llm):
        result = await _decompose_claim(short_claim)

    mock_llm.assert_not_called()
    assert result == [short_claim]


@pytest.mark.asyncio
async def test_decompose_claim_strips_markdown_fences() -> None:
    """LLM wraps JSON in ```json...``` → still parsed correctly."""
    from backend.agent.gap_detection.nodes.verifier import _decompose_claim

    sub_claims = ["Claim A", "Claim B"]
    llm_response = f"```json\n{json.dumps(sub_claims)}\n```"

    with patch(f"{_VERIFIER}.chat_completion", new=AsyncMock(return_value=llm_response)):
        result = await _decompose_claim("A sufficiently long claim that needs to be decomposed into parts")

    assert result == ["Claim A", "Claim B"]


@pytest.mark.asyncio
async def test_decompose_claim_fallback_on_empty_llm_response() -> None:
    """LLM returns empty string → returns [claim_text]."""
    from backend.agent.gap_detection.nodes.verifier import _decompose_claim

    claim = "X achieves SOTA on Y and Z but has not been tested on W"
    with patch(f"{_VERIFIER}.chat_completion", new=AsyncMock(return_value="")):
        result = await _decompose_claim(claim)

    assert result == [claim]


# ── Part 2: _most_restrictive_status ─────────────────────────────────────────


def test_most_restrictive_status_mixed() -> None:
    """AC: ['supported', 'partial', 'unsupported'] → 'unsupported'."""
    from backend.agent.gap_detection.nodes.verifier import _most_restrictive_status

    result = _most_restrictive_status(["supported", "partial", "unsupported"])
    assert result == "unsupported"


def test_most_restrictive_status_empty() -> None:
    """AC: empty list → 'uncertain'."""
    from backend.agent.gap_detection.nodes.verifier import _most_restrictive_status

    assert _most_restrictive_status([]) == "uncertain"


def test_most_restrictive_status_all_supported() -> None:
    """All supported → 'supported'."""
    from backend.agent.gap_detection.nodes.verifier import _most_restrictive_status

    assert _most_restrictive_status(["supported", "supported"]) == "supported"


def test_most_restrictive_status_partial_beats_supported() -> None:
    """['supported', 'partial'] → 'partial' (partial is more restrictive)."""
    from backend.agent.gap_detection.nodes.verifier import _most_restrictive_status

    assert _most_restrictive_status(["supported", "partial"]) == "partial"


def test_most_restrictive_status_uncertain_is_middle() -> None:
    """['uncertain', 'partial'] → 'partial'."""
    from backend.agent.gap_detection.nodes.verifier import _most_restrictive_status

    assert _most_restrictive_status(["uncertain", "partial"]) == "partial"


def test_most_restrictive_status_unknown_status_maps_to_uncertain() -> None:
    """Unknown status string treated as 'uncertain' (default score=2)."""
    from backend.agent.gap_detection.nodes.verifier import _most_restrictive_status

    # unknown_status score=2 (uncertain), unsupported score=0 → min=unsupported
    result = _most_restrictive_status(["unknown_status", "unsupported"])
    assert result == "unsupported"


# ── Part 3: _verify_limitation wire ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_limitation_unsupported_subclaim_downgrades_gap() -> None:
    """AC: sub-claim with 'unsupported' → overall NOT_CONFIRMED (gap dropped)."""
    from backend.agent.gap_detection.nodes.verifier import _NOT_CONFIRMED, _verify_limitation

    gap = _make_gap("X achieves SOTA on Y and Z but has not been tested on W")

    sub_claims_json = json.dumps(["X achieves SOTA on Y", "X has not been tested on W"])

    # LLM returns 2 sub-claims; verify_claims returns 'unsupported' for one
    def _mock_verify(claims, **kwargs):
        results = []
        for c in claims:
            mc = MagicMock()
            mc.status = "unsupported"
            results.append(mc)
        return results

    with (
        patch(f"{_VERIFIER}.chat_completion", new=AsyncMock(return_value=sub_claims_json)),
        patch(f"{_VERIFIER}.verify_claims", new=AsyncMock(side_effect=_mock_verify)),
    ):
        outcome = await _verify_limitation(gap, {})

    assert outcome == _NOT_CONFIRMED


@pytest.mark.asyncio
async def test_verify_limitation_all_supported_confirms_gap() -> None:
    """All sub-claims supported → CONFIRMED."""
    from backend.agent.gap_detection.nodes.verifier import _CONFIRMED, _verify_limitation

    gap = _make_gap("X achieves SOTA on Y and Z but has not been tested on W")

    sub_claims_json = json.dumps(["Sub-claim 1", "Sub-claim 2"])

    def _mock_verify(claims, **kwargs):
        results = []
        for c in claims:
            mc = MagicMock()
            mc.status = "supported"
            results.append(mc)
        return results

    with (
        patch(f"{_VERIFIER}.chat_completion", new=AsyncMock(return_value=sub_claims_json)),
        patch(f"{_VERIFIER}.verify_claims", new=AsyncMock(side_effect=_mock_verify)),
    ):
        outcome = await _verify_limitation(gap, {})

    assert outcome == _CONFIRMED


@pytest.mark.asyncio
async def test_verify_limitation_no_supporting_papers_not_confirmed() -> None:
    """Gap with no supporting papers → _NOT_CONFIRMED immediately."""
    from backend.agent.gap_detection.nodes.verifier import _NOT_CONFIRMED, _verify_limitation
    from backend.agent.gap_detection.schemas import GapItem, GapOrigin, GapStatus, GapType

    gap = GapItem(
        gap_type=GapType.TOPICAL,
        origin=GapOrigin.LIMITATION,
        status=GapStatus.OPEN,
        statement="A claim with no papers",
        supporting_papers=[],
    )
    outcome = await _verify_limitation(gap, {})
    assert outcome == _NOT_CONFIRMED


@pytest.mark.asyncio
async def test_verify_limitation_verify_exception_returns_error() -> None:
    """verify_claims raises → _ERROR (gap not dropped)."""
    from backend.agent.gap_detection.nodes.verifier import _ERROR, _verify_limitation

    gap = _make_gap("X achieves SOTA on Y and Z but has not been tested on W")

    with (
        patch(f"{_VERIFIER}.chat_completion", new=AsyncMock(return_value=json.dumps(["Sub A"]))),
        patch(f"{_VERIFIER}.verify_claims", side_effect=RuntimeError("S2 exploded")),
    ):
        outcome = await _verify_limitation(gap, {})

    assert outcome == _ERROR
