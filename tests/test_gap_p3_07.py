"""Tests for TIP-P3-07 — Synthesizer v2: top-k ranking, origin labels, Phase 3 narrative.

Covers:
- confidence default = 0.0 (schema change)
- rank_gaps_by_quality wired: 15 gaps → top 7 in final_report.gaps
- gaps sorted by quality_score descending in output
- LangGraph state output key = "final_report" (unchanged)
- EXPLICIT origin in narrative block
- suggested_method 💡 shown when set / absent when None
- false_gap_flag ⚠️ preserved from Phase 2
- rank_gaps_by_quality exception → graceful fallback
"""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.schemas import (
    GapItem,
    GapOrigin,
    GapType,
    PaperRef,
)

_SYNTH = "backend.agent.gap_detection.nodes.synthesizer"


def _make_gap(
    statement: str,
    origin: GapOrigin = GapOrigin.INFERRED,
    confidence: float = 1.0,
    quality_score: float | None = None,
    suggested_method: str | None = None,
    falsifiability_condition: str | None = None,
    evidence_quotes: list[str] | None = None,
    false_gap_flag: bool = False,
    novelty_score: float | None = None,
    n_papers: int = 1,
) -> GapItem:
    papers = [PaperRef(paper_id=f"p{i}", title=f"Paper {i}", year=2023) for i in range(n_papers)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return GapItem(
            gap_type=GapType.TOPICAL,
            origin=origin,
            statement=statement,
            confidence=confidence,
            quality_score=quality_score,
            supporting_papers=papers,
            suggested_method=suggested_method,
            falsifiability_condition=falsifiability_condition,
            evidence_quotes=evidence_quotes or [],
            false_gap_flag=false_gap_flag,
            novelty_score=novelty_score,
        )


# ── Schema: confidence default = 0.0 ─────────────────────────────────


def test_confidence_default_is_zero():
    """GapItem created without explicit confidence → 0.0 (schema default changed)."""
    item = GapItem(gap_type=GapType.TOPICAL, statement="test gap")
    assert item.confidence == 0.0


# ── Synthesizer: top-k ranking ────────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesizer_top_k_ranking():
    """15 gaps → final_report.gaps contains ≤ 7 (TOP_K_GAPS=7), sorted by quality."""
    gaps = [_make_gap(f"Gap {i}", confidence=1.0, quality_score=float(i) / 15) for i in range(15)]
    state = {"verified_gaps": gaps, "session_papers": [], "baseline_triggered": False}

    with (
        patch(f"{_SYNTH}.chat_completion", new_callable=AsyncMock) as mock_llm,
        patch(f"{_SYNTH}.get_top_k_gaps", return_value=7),
    ):
        mock_llm.return_value = "narrative text"
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    report = result["final_report"]
    assert len(report.gaps) <= 7
    # Gaps should be sorted quality descending within the main set
    quality_scores = [g.quality_score for g in report.gaps if g.quality_score is not None]
    assert quality_scores == sorted(quality_scores, reverse=True) or len(quality_scores) <= 1


@pytest.mark.asyncio
async def test_synthesizer_output_key_is_final_report():
    """LangGraph state output key must be 'final_report' — FE depends on this."""
    gaps = [_make_gap("A gap", confidence=1.0)]
    state = {"verified_gaps": gaps, "session_papers": [], "baseline_triggered": False}

    with patch(f"{_SYNTH}.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "narrative"
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    assert "final_report" in result
    assert "gap_report" not in result  # old key — must not appear


# ── Narrative content: Phase 3 fields ────────────────────────────────


def test_gap_prompt_block_explicit_origin():
    """EXPLICIT gap shows origin label in prompt block."""
    from backend.agent.gap_detection.nodes.synthesizer import _gap_prompt_block

    gap = _make_gap("Future work should explore X", origin=GapOrigin.EXPLICIT, confidence=1.0)
    gap.quality_score = 0.85
    block = _gap_prompt_block(1, gap)
    assert "explicit" in block.lower() or "tường minh" in block.lower()


def test_gap_prompt_block_suggested_method_shown():
    """suggested_method present → 💡 line in prompt block."""
    from backend.agent.gap_detection.nodes.synthesizer import _gap_prompt_block

    gap = _make_gap("Gap X", suggested_method="Thử nghiệm với benchmark Y")
    gap.quality_score = 0.5
    block = _gap_prompt_block(1, gap)
    assert "💡" in block
    assert "Thử nghiệm với benchmark Y" in block


def test_gap_prompt_block_no_suggested_method():
    """suggested_method=None → no 💡 in prompt block."""
    from backend.agent.gap_detection.nodes.synthesizer import _gap_prompt_block

    gap = _make_gap("Gap X", suggested_method=None)
    gap.quality_score = 0.3
    block = _gap_prompt_block(1, gap)
    assert "💡" not in block


def test_gap_prompt_block_false_gap_warning_preserved():
    """false_gap_flag=True → ⚠️ warning preserved from Phase 2."""
    from backend.agent.gap_detection.nodes.synthesizer import _gap_prompt_block

    gap = _make_gap("Gap X", false_gap_flag=True)
    gap.quality_score = 0.4
    block = _gap_prompt_block(1, gap)
    assert "⚠️" in block


def test_gap_prompt_block_falsifiability_shown():
    """falsifiability_condition set → ❓ line present."""
    from backend.agent.gap_detection.nodes.synthesizer import _gap_prompt_block

    gap = _make_gap("Gap X", falsifiability_condition="Resolved if paper Y exists")
    gap.quality_score = 0.6
    block = _gap_prompt_block(1, gap)
    assert "❓" in block
    assert "Resolved if paper Y exists" in block


def test_gap_prompt_block_evidence_quotes_shown():
    """evidence_quotes set → first quote in prompt block (max 200 chars)."""
    from backend.agent.gap_detection.nodes.synthesizer import _gap_prompt_block

    gap = _make_gap("Gap X", evidence_quotes=["Authors state no study exists", "Second quote"])
    gap.quality_score = 0.7
    block = _gap_prompt_block(1, gap)
    assert "Authors state no study exists" in block
    assert "Second quote" not in block  # only first quote


# ── Synthesizer: ranking fallback ────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesizer_ranking_fallback_on_exception():
    """rank_gaps_by_quality throws → graceful fallback, node does not crash."""
    gaps = [_make_gap(f"Gap {i}", confidence=float(i) / 5) for i in range(5)]
    state = {"verified_gaps": gaps, "session_papers": [], "baseline_triggered": False}

    with (
        patch(f"{_SYNTH}.rank_gaps_by_quality", side_effect=RuntimeError("scorer broken")),
        patch(f"{_SYNTH}.chat_completion", new_callable=AsyncMock) as mock_llm,
        patch(f"{_SYNTH}.get_top_k_gaps", return_value=3),
    ):
        mock_llm.return_value = "fallback narrative"
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    assert "final_report" in result
    assert len(result["final_report"].gaps) <= 3
