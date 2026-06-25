"""Self-tests for TIP-G01 — Gap Detection schemas."""

import warnings

import pytest

from backend.agent.gap_detection.schemas import (
    ExtractedPaperData,
    GapDetectionState,
    GapItem,
    GapOrigin,
    GapReport,
    GapStatus,
    GapType,
    PaperRef,
)

# ── AC-1: Basic construction with defaults ───────────────────────────


def test_gap_item_topical_inferred_defaults() -> None:
    """GapItem with TOPICAL + INFERRED has correct defaults."""
    item = GapItem(
        gap_type=GapType.TOPICAL,
        origin=GapOrigin.INFERRED,
        statement="No study compares X and Y",
    )
    assert item.gap_type == GapType.TOPICAL
    assert item.origin == GapOrigin.INFERRED
    assert item.status == GapStatus.OPEN
    assert item.supporting_papers == []
    assert item.context_explanation is None
    assert item.confidence == 0.0
    assert item.verified is False


# ── AC-2: LIMITATION origin + empty citations → warning ──────────────


def test_gap_item_limitation_empty_papers_warns() -> None:
    """origin=LIMITATION without supporting_papers emits UserWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        item = GapItem(
            gap_type=GapType.METHODOLOGICAL,
            origin=GapOrigin.LIMITATION,
            statement="Authors note limited sample size",
        )
        assert len(w) == 1
        assert "LIMITATION" in str(w[0].message)
    # Object should still be valid
    assert item.supporting_papers == []


def test_gap_item_limitation_with_papers_no_warning() -> None:
    """origin=LIMITATION WITH supporting_papers → no warning."""
    ref = PaperRef(paper_id="p1", title="Paper 1")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        item = GapItem(
            gap_type=GapType.METHODOLOGICAL,
            origin=GapOrigin.LIMITATION,
            statement="Authors note limited sample size",
            supporting_papers=[ref],
        )
        assert len(w) == 0
    assert len(item.supporting_papers) == 1


# ── Additional: model integrity ──────────────────────────────────────


def test_paper_ref_optional_fields() -> None:
    ref = PaperRef(paper_id="abc123", title="Test Paper")
    assert ref.year is None
    assert ref.url is None


def test_extracted_paper_data_defaults() -> None:
    ref = PaperRef(paper_id="p1", title="P1")
    data = ExtractedPaperData(paper_ref=ref)
    assert data.topics == []
    assert data.keywords == []
    assert data.methodology is None
    assert data.dataset is None
    assert data.population is None
    assert data.metrics == []
    assert data.key_claims == []
    assert data.limitation_statements == []


def test_gap_report_defaults() -> None:
    report = GapReport(papers_analyzed=0)
    assert report.gaps == []
    assert report.narrative == ""
    assert report.baseline_triggered is False


def test_gap_detection_state_is_typed_dict() -> None:
    """GapDetectionState is a TypedDict (total=False) — all keys optional."""
    state: GapDetectionState = {}
    assert isinstance(state, dict)


def test_confidence_bounds() -> None:
    """confidence must be 0.0–1.0."""
    with pytest.raises(Exception):
        GapItem(
            gap_type=GapType.TOPICAL,
            origin=GapOrigin.INFERRED,
            statement="test",
            confidence=1.5,
        )
    with pytest.raises(Exception):
        GapItem(
            gap_type=GapType.TOPICAL,
            origin=GapOrigin.INFERRED,
            statement="test",
            confidence=-0.1,
        )


def test_enum_values() -> None:
    """Enum string values match spec."""
    assert GapType.TOPICAL.value == "topical"
    assert GapType.METHODOLOGICAL.value == "methodological"
    assert GapType.CONTRADICTION.value == "contradiction"

    assert GapOrigin.EXPLICIT.value == "explicit"
    assert GapOrigin.LIMITATION.value == "limitation"
    assert GapOrigin.INFERRED.value == "inferred"

    assert GapStatus.OPEN.value == "open"
    assert GapStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert GapStatus.NEEDS_RESOLUTION.value == "needs_resolution"


# ── Phase 3: backward compat + new fields ────────────────────────────


def test_gapitem_phase2_json_backward_compat() -> None:
    """Phase 2 JSON (no Phase 3 fields) → Phase 3 defaults applied."""
    data = {"statement": "No study compares X and Y", "gap_type": "topical"}
    item = GapItem(**data)
    assert item.origin == GapOrigin.INFERRED
    assert item.confidence == 0.0
    assert item.falsifiability_condition is None
    assert item.suggested_method is None
    assert item.quality_score is None
    assert item.evidence_quotes == []


def test_gapitem_phase3_fields_full() -> None:
    """GapItem with all Phase 3 fields set correctly."""
    item = GapItem(
        gap_type=GapType.METHODOLOGICAL,
        origin=GapOrigin.EXPLICIT,
        statement="No RCT exists for this intervention",
        falsifiability_condition="Gap is resolved if a paper conducts an RCT on this population",
        suggested_method="Randomized controlled trial with N>200",
        quality_score=0.85,
        evidence_quotes=["Authors state 'no RCT exists'", "Limited to observational studies"],
    )
    assert item.origin == GapOrigin.EXPLICIT
    assert item.falsifiability_condition == "Gap is resolved if a paper conducts an RCT on this population"
    assert item.suggested_method == "Randomized controlled trial with N>200"
    assert item.quality_score == 0.85
    assert item.evidence_quotes == ["Authors state 'no RCT exists'", "Limited to observational studies"]


def test_gapitem_invalid_origin_raises() -> None:
    """origin only accepts EXPLICIT, LIMITATION, INFERRED — invalid value → ValidationError."""
    with pytest.raises(Exception):
        GapItem(
            gap_type=GapType.TOPICAL,
            origin="INVALID_VALUE",  # type: ignore[arg-type]
            statement="test",
        )


def test_gapitem_phase2_fields_preserved() -> None:
    """Phase 2 fields (novelty_score, false_gap_flag) survive round-trip unchanged."""
    item = GapItem(
        gap_type=GapType.CONTRADICTION,
        origin=GapOrigin.INFERRED,
        statement="Papers A and B contradict on method Z",
        novelty_score=0.5,
        false_gap_flag=True,
    )
    data = item.model_dump()
    restored = GapItem(**data)
    assert restored.novelty_score == 0.5
    assert restored.false_gap_flag is True


def test_package_import() -> None:
    """All public names are importable from gap_detection package __init__."""
    import backend.agent.gap_detection as pkg

    expected = {
        "GapType",
        "GapOrigin",
        "GapStatus",
        "PaperRef",
        "ExtractedPaperData",
        "GapItem",
        "GapReport",
        "GapDetectionState",
    }
    assert expected.issubset(set(pkg.__all__))
    for name in expected:
        assert hasattr(pkg, name), f"{name} missing from package"

