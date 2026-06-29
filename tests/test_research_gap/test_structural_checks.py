"""Unit tests for structural_checks.py — no real S2 or LLM calls."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from backend.agent.gap_detection.schemas import GapItem, GapType, GapOrigin, GapStatus, PaperRef
from tests.test_research_gap.structural_checks import check_gap_structural, check_empty_on_nonsense


def _make_gap(
    statement: str = "There is a gap in applying X to Y for Z task with benchmark W",
    paper_ids: list[str] | None = None,
    quality_score: float | None = 0.75,
) -> GapItem:
    papers = [PaperRef(paper_id=pid, title=f"Paper {pid}") for pid in (paper_ids if paper_ids is not None else ["abc123"])]
    return GapItem(
        gap_type=GapType.TOPICAL,
        origin=GapOrigin.INFERRED,
        status=GapStatus.OPEN,
        statement=statement,
        supporting_papers=papers,
        quality_score=quality_score,
        suggested_method="Apply method X to domain Y",
    )


@pytest.mark.asyncio
async def test_structural_all_pass():
    """A well-formed gap with a real paper passes all checks."""
    gap = _make_gap()
    with patch(
        "tests.test_research_gap.structural_checks.get_paper_detail",
        new=AsyncMock(return_value={"paperId": "abc123", "title": "Real Paper"}),
    ):
        results = await check_gap_structural(gap)

    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]
    assert len(failed) == 0, f"Unexpected failures: {failed}"
    assert len(passed) == 4


@pytest.mark.asyncio
async def test_structural_paper_not_found():
    """A gap whose paper_id returns None from S2 fails the paper existence check."""
    gap = _make_gap(paper_ids=["fake_id_xyz"])
    with patch(
        "tests.test_research_gap.structural_checks.get_paper_detail",
        new=AsyncMock(return_value=None),
    ):
        results = await check_gap_structural(gap)

    paper_check = next(r for r in results if r["check"] == "paper_existence")
    assert not paper_check["passed"]
    assert "fake_id_xyz" in paper_check["detail"]


@pytest.mark.asyncio
async def test_structural_statement_too_short():
    """A gap with a statement under 15 words fails the length check."""
    gap = _make_gap(statement="Gap exists.")
    with patch(
        "tests.test_research_gap.structural_checks.get_paper_detail",
        new=AsyncMock(return_value={"paperId": "abc123"}),
    ):
        results = await check_gap_structural(gap)

    length_check = next(r for r in results if r["check"] == "statement_length")
    assert not length_check["passed"]


@pytest.mark.asyncio
async def test_structural_no_supporting_papers():
    """A gap with no supporting papers fails the has_papers check."""
    gap = _make_gap(paper_ids=[])
    results = await check_gap_structural(gap)

    papers_check = next(r for r in results if r["check"] == "has_supporting_papers")
    assert not papers_check["passed"]


@pytest.mark.asyncio
async def test_structural_missing_quality_score():
    """A gap with quality_score=None fails the quality_score_present check."""
    gap = _make_gap(quality_score=None)
    with patch(
        "tests.test_research_gap.structural_checks.get_paper_detail",
        new=AsyncMock(return_value={"paperId": "abc123"}),
    ):
        results = await check_gap_structural(gap)

    qs_check = next(r for r in results if r["check"] == "quality_score_present")
    assert not qs_check["passed"]


def test_empty_on_nonsense_pass():
    """expect_empty=True and gaps=[] → passes."""
    result = check_empty_on_nonsense(gaps=[], expect_empty=True)
    assert result["passed"]


def test_empty_on_nonsense_fail():
    """expect_empty=True but gaps non-empty → hallucination detected."""
    gap = _make_gap()
    result = check_empty_on_nonsense(gaps=[gap], expect_empty=True)
    assert not result["passed"]
    assert "hallucination" in result["detail"].lower()


def test_empty_on_nonsense_not_expected():
    """expect_empty=False → check is skipped (always passes)."""
    result = check_empty_on_nonsense(gaps=[], expect_empty=False)
    assert result["passed"]
