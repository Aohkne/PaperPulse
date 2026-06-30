"""Tests for TIP-P3-15 — Narrative-in-Card + Unicode NFD fix.

Covers:
- GapItem.analysis field: default None, backward compat
- normalize_vi(): NFD → NFC, falsy passthrough, idempotent
- _build_gap_analysis(): non-empty text, includes statement and origin
- synthesizer_node: populates gap.analysis for each gap
- synthesizer_node: narrative is template summary (not LLM text)
- synthesizer_node: narrative summary vs empty message cases
"""

from __future__ import annotations

import unicodedata
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


# ── Helpers ───────────────────────────────────────────────────────────


def _make_gap(
    statement: str = "test gap",
    origin: GapOrigin = GapOrigin.INFERRED,
    confidence: float = 0.8,
    quality_score: float | None = 0.7,
    suggested_method: str | None = None,
    falsifiability_condition: str | None = None,
    evidence_quotes: list[str] | None = None,
    false_gap_flag: bool = False,
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
        )


# ── Schema: GapItem.analysis field ───────────────────────────────────


def test_gapitem_analysis_field_default_none():
    """GapItem without analysis field → defaults to None (backward compat)."""
    item = GapItem(gap_type=GapType.TOPICAL, statement="old gap")
    assert item.analysis is None


def test_gapitem_analysis_field_accepts_string():
    """GapItem.analysis accepts a string value."""
    item = GapItem(gap_type=GapType.TOPICAL, statement="gap", analysis="Some analysis text")
    assert item.analysis == "Some analysis text"


def test_gapitem_phase2_json_still_parses():
    """JSON from Phase 2 (no analysis field) can be parsed without error."""
    data = {"gap_type": "topical", "statement": "old gap", "confidence": 0.9}
    item = GapItem(**data)
    assert item.analysis is None
    assert item.statement == "old gap"


# ── normalize_vi() ────────────────────────────────────────────────────


def test_normalize_vi_nfd_to_nfc():
    """NFD decomposed Vietnamese text → NFC precomposed."""
    from backend.agent.gap_detection.nodes.synthesizer import normalize_vi

    # Build NFD string manually: "đồng" decomposed
    nfd_text = unicodedata.normalize("NFD", "đồng nhất")
    assert unicodedata.is_normalized("NFD", nfd_text)

    result = normalize_vi(nfd_text)
    assert unicodedata.is_normalized("NFC", result)
    assert result == "đồng nhất"


def test_normalize_vi_nfc_input_unchanged():
    """NFC input → same output (idempotent)."""
    from backend.agent.gap_detection.nodes.synthesizer import normalize_vi

    text = "đồng nhất nghiên cứu"
    assert normalize_vi(text) == text


def test_normalize_vi_empty_string_passthrough():
    """Empty string → returned as-is."""
    from backend.agent.gap_detection.nodes.synthesizer import normalize_vi

    assert normalize_vi("") == ""


def test_normalize_vi_none_passthrough():
    """None → returned as None (no crash)."""
    from backend.agent.gap_detection.nodes.synthesizer import normalize_vi

    assert normalize_vi(None) is None


def test_normalize_vi_ascii_unchanged():
    """ASCII text → unchanged."""
    from backend.agent.gap_detection.nodes.synthesizer import normalize_vi

    assert normalize_vi("research gap analysis") == "research gap analysis"


# ── _build_gap_analysis() ─────────────────────────────────────────────


def test_build_gap_analysis_returns_none_when_no_enrichment():
    """Gap with no enrichment fields → returns None (FE hides toggle)."""
    from backend.agent.gap_detection.nodes.synthesizer import _build_gap_analysis

    gap = _make_gap("Gap about attention mechanisms")
    assert _build_gap_analysis(gap) is None


def test_build_gap_analysis_returns_nonempty_when_enrichment():
    """Gap with at least one enrichment field → returns non-empty string."""
    from backend.agent.gap_detection.nodes.synthesizer import _build_gap_analysis

    gap = _make_gap("Gap statement", suggested_method="Apply BEIR benchmark")
    result = _build_gap_analysis(gap)
    assert result
    assert "Apply BEIR benchmark" in result


def test_build_gap_analysis_no_prose_wrapping():
    """_build_gap_analysis does NOT wrap statement in prose or dump origin field."""
    from backend.agent.gap_detection.nodes.synthesizer import _build_gap_analysis

    gap = _make_gap("My gap statement", suggested_method="A method")
    result = _build_gap_analysis(gap)
    assert result is not None
    assert "Mặc dù" not in result
    assert "Nguồn gốc:" not in result


def test_build_gap_analysis_includes_suggested_method():
    """suggested_method appears with 💡 marker."""
    from backend.agent.gap_detection.nodes.synthesizer import _build_gap_analysis

    gap = _make_gap(suggested_method="Thử nghiệm BEIR benchmark")
    result = _build_gap_analysis(gap)
    assert "💡" in result
    assert "Thử nghiệm BEIR benchmark" in result


def test_build_gap_analysis_includes_falsifiability():
    """falsifiability_condition appears with ❓ marker."""
    from backend.agent.gap_detection.nodes.synthesizer import _build_gap_analysis

    gap = _make_gap(falsifiability_condition="If paper Y exists")
    result = _build_gap_analysis(gap)
    assert "❓" in result
    assert "If paper Y exists" in result


def test_build_gap_analysis_false_gap_only_returns_none():
    """false_gap_flag alone is not an enrichment field → returns None."""
    from backend.agent.gap_detection.nodes.synthesizer import _build_gap_analysis

    gap = _make_gap(false_gap_flag=True)
    assert _build_gap_analysis(gap) is None


def test_build_gap_analysis_evidence_quote_first_only():
    """Only the first evidence quote included (max 200 chars)."""
    from backend.agent.gap_detection.nodes.synthesizer import _build_gap_analysis

    gap = _make_gap(evidence_quotes=["First quote here", "Second quote not shown"])
    result = _build_gap_analysis(gap)
    assert "First quote here" in result
    assert "Second quote not shown" not in result


# ── synthesizer_node: populates gap.analysis + template narrative ─────


@pytest.mark.asyncio
async def test_synthesizer_populates_gap_analysis():
    """synthesizer_node: enriched gaps keep analysis; plain inferred gaps are filtered by rejection gate."""
    enriched = _make_gap("Enriched gap", suggested_method="Apply BEIR benchmark")
    plain = _make_gap("Plain gap")  # no enrichment fields
    gaps = [enriched, plain]
    state = {"verified_gaps": gaps, "session_papers": [], "baseline_triggered": False}

    with patch(f"{_SYNTH}.rank_gaps_by_quality", return_value=gaps), patch(f"{_SYNTH}.get_top_k_gaps", return_value=7):
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    report = result["final_report"]
    analyses = [g.analysis for g in report.gaps]
    statements = [g.statement for g in report.gaps]
    assert any(a is not None and len(a) > 0 for a in analyses), "enriched gap should have analysis"
    assert "Enriched gap" in statements
    assert "Plain gap" not in statements, "plain inferred gap should be filtered by rejection gate"


@pytest.mark.asyncio
async def test_synthesizer_narrative_is_template_not_llm():
    """GapReport.narrative is now a template summary (not LLM-generated text)."""
    gaps = [_make_gap(f"Gap {i}") for i in range(3)]
    state = {"verified_gaps": gaps, "session_papers": [], "baseline_triggered": False}

    with (
        patch(f"{_SYNTH}.rank_gaps_by_quality", return_value=gaps),
        patch(f"{_SYNTH}.get_top_k_gaps", return_value=7),
        patch(f"{_SYNTH}.chat_completion", new_callable=AsyncMock) as mock_llm,
    ):
        mock_llm.return_value = "SHOULD NOT APPEAR"
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    narrative = result["final_report"].narrative
    assert "SHOULD NOT APPEAR" not in narrative
    assert narrative  # non-empty


@pytest.mark.asyncio
async def test_synthesizer_narrative_summary_when_top_k_equals_total():
    """When total gaps == top_k: narrative says 'Phát hiện N gap'."""
    gaps = [_make_gap(f"Gap {i}") for i in range(3)]
    state = {"verified_gaps": gaps, "session_papers": [], "baseline_triggered": False}

    with patch(f"{_SYNTH}.rank_gaps_by_quality", return_value=gaps), patch(f"{_SYNTH}.get_top_k_gaps", return_value=7):
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    narrative = result["final_report"].narrative
    assert "3" in narrative
    assert "gap" in narrative.lower()


@pytest.mark.asyncio
async def test_synthesizer_narrative_prefix_when_more_than_top_k():
    """When total > top_k: narrative has 'top N/M' prefix."""
    # Assumes TIP-401 rejection gating + TIP-403 Jaccard dedup are active.
    all_gaps = [
        _make_gap(
            f"Gap {i}",
            confidence=float(i) / 15,
            suggested_method=f"Method {i}",
        )
        for i in range(15)
    ]
    for i, gap in enumerate(all_gaps):
        gap.supporting_papers = [PaperRef(paper_id=f"p{i}", title=f"Paper {i}", year=2023)]
    top_gaps = all_gaps[:7]
    state = {"verified_gaps": all_gaps, "session_papers": [], "baseline_triggered": False}

    with (
        patch(f"{_SYNTH}.rank_gaps_by_quality", return_value=top_gaps),
        patch(f"{_SYNTH}.get_top_k_gaps", return_value=7),
    ):
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    narrative = result["final_report"].narrative
    assert "7" in narrative
    assert "15" in narrative


@pytest.mark.asyncio
async def test_synthesizer_narrative_empty_when_no_gaps():
    """When no verified gaps → narrative is _EMPTY_MESSAGE."""
    state = {"verified_gaps": [], "session_papers": [], "baseline_triggered": False}

    with patch(f"{_SYNTH}.rank_gaps_by_quality", return_value=[]), patch(f"{_SYNTH}.get_top_k_gaps", return_value=7):
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    narrative = result["final_report"].narrative
    assert "no clear research gaps" in narrative.lower()


@pytest.mark.asyncio
async def test_synthesizer_analysis_is_nfc_normalized():
    """gap.analysis is NFC-normalized even if enrichment fields arrive in NFD."""
    nfd_method = unicodedata.normalize("NFD", "Thử nghiệm BEIR benchmark")
    assert not unicodedata.is_normalized("NFC", nfd_method)  # pre-condition: truly NFD

    gap = _make_gap("gap", suggested_method=nfd_method)
    state = {"verified_gaps": [gap], "session_papers": [], "baseline_triggered": False}

    with patch(f"{_SYNTH}.rank_gaps_by_quality", return_value=[gap]), patch(f"{_SYNTH}.get_top_k_gaps", return_value=7):
        from backend.agent.gap_detection.nodes.synthesizer import synthesizer_node

        result = await synthesizer_node(state)

    analysis = result["final_report"].gaps[0].analysis
    assert analysis is not None
    assert unicodedata.is_normalized("NFC", analysis)
