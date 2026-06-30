"""Structural (non-LLM) checks for gap cards.

Each check returns: {"check": str, "passed": bool, "detail": str}
"""

from __future__ import annotations

import asyncio

from backend.agent.gap_detection.s2_client import get_paper_detail
from backend.agent.gap_detection.schemas import GapItem

_MIN_STATEMENT_WORDS = 15


async def _check_paper_existence(gap: GapItem) -> dict:
    """Verify every supporting paper_id resolves on Semantic Scholar."""
    missing: list[str] = []
    tasks = [get_paper_detail(p.paper_id) for p in gap.supporting_papers]
    results = await asyncio.gather(*tasks)
    for paper, result in zip(gap.supporting_papers, results):
        if result is None:
            missing.append(paper.paper_id)
    passed = len(missing) == 0
    detail = "all papers found" if passed else f"not found on S2: {', '.join(missing)}"
    return {"check": "paper_existence", "passed": passed, "detail": detail}


def _check_statement_length(gap: GapItem) -> dict:
    """Statement must be at least 15 words."""
    word_count = len(gap.statement.split())
    passed = word_count >= _MIN_STATEMENT_WORDS
    detail = f"{word_count} words" if passed else f"only {word_count} words (min {_MIN_STATEMENT_WORDS})"
    return {"check": "statement_length", "passed": passed, "detail": detail}


def _check_has_supporting_papers(gap: GapItem) -> dict:
    """Gap must have at least 1 supporting paper."""
    passed = len(gap.supporting_papers) >= 1
    detail = f"{len(gap.supporting_papers)} supporting papers" if passed else "no supporting papers"
    return {"check": "has_supporting_papers", "passed": passed, "detail": detail}


def _check_quality_score_present(gap: GapItem) -> dict:
    """quality_score must not be None (synthesizer ran fully)."""
    passed = gap.quality_score is not None
    detail = f"quality_score={gap.quality_score}" if passed else "quality_score is None — synthesizer may have failed"
    return {"check": "quality_score_present", "passed": passed, "detail": detail}


async def check_gap_structural(gap: GapItem) -> list[dict]:
    """Run all structural checks on a single GapItem.

    Returns list of 4 result dicts, one per check.
    paper_existence is skipped (returns pass) when there are no supporting
    papers — has_supporting_papers already catches that case.
    """
    sync_results = [
        _check_statement_length(gap),
        _check_has_supporting_papers(gap),
        _check_quality_score_present(gap),
    ]
    if gap.supporting_papers:
        paper_result = await _check_paper_existence(gap)
    else:
        paper_result = {
            "check": "paper_existence",
            "passed": True,
            "detail": "skipped (no papers to check)",
        }
    return [paper_result, *sync_results]


def check_empty_on_nonsense(gaps: list[GapItem], expect_empty: bool) -> dict:
    """Hallucination guard for nonsense topics.

    When expect_empty=False, always passes (not a nonsense topic).
    When expect_empty=True, passes only if gaps==[].
    """
    if not expect_empty:
        return {
            "check": "empty_on_nonsense",
            "passed": True,
            "detail": "not a nonsense topic — check skipped",
        }
    passed = len(gaps) == 0
    detail = "correctly returned 0 gaps" if passed else f"hallucination: returned {len(gaps)} gaps for nonsense topic"
    return {"check": "empty_on_nonsense", "passed": passed, "detail": detail}
