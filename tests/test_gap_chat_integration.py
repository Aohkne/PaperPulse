"""Self-tests for TIP-G07 — Phase 0 gate, intent routing, chat integration.

All LLM / S2 / pipeline calls are mocked so tests run offline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.nodes.paper_check import (
    MIN_SESSION_PAPERS,
    collect_session_papers,
    paper_check_node,
)
from backend.agent.gap_detection.schemas import GapReport, PaperRef
from backend.agent.gap_detection.intent_classifier import is_gap_detection_intent
from backend.shared.models.paper import Paper

_INTENT_LLM = "backend.agent.gap_detection.intent_classifier.chat_completion"
_CI = "backend.agent.gap_detection.chat_integration"


# ── Part 1: state field ──────────────────────────────────────────────


def test_state_has_baseline_triggered() -> None:
    """baseline_triggered is a declared (optional) GapDetectionState key."""
    from backend.agent.gap_detection.schemas import GapDetectionState

    assert "baseline_triggered" in GapDetectionState.__annotations__


# ── Part 2: collect_session_papers ───────────────────────────────────


def test_collect_inline_source_citations() -> None:
    """Inline (Source: ID) tokens are extracted into PaperRefs."""
    messages = [
        {"role": "user", "content": "Tell me about X (Source: p1) and Y (Source: p2)."},
        {"role": "assistant", "content": "Sure, see (Source: p3)."},
    ]
    papers = collect_session_papers(messages)
    assert [p.paper_id for p in papers] == ["p1", "p2", "p3"]


def test_collect_dedupes_by_paper_id() -> None:
    """AC: duplicate citations dedupe by paper_id."""
    messages = [
        {"role": "user", "content": "(Source: p1) (Source: p1) (Source: p2)"},
        {"role": "assistant", "content": "(Source: p2) again"},
    ]
    papers = collect_session_papers(messages)
    assert [p.paper_id for p in papers] == ["p1", "p2"]


def test_collect_structured_papers_cited() -> None:
    """Forward-compatible: structured papers_cited metadata is honoured + deduped with inline."""
    messages = [
        {
            "role": "assistant",
            "content": "see (Source: p2)",
            "papers_cited": [
                {"paper_id": "p1", "title": "Paper One", "year": 2020},
                {"paperId": "p2", "title": "Dup via alias"},  # dup with inline p2
            ],
        }
    ]
    papers = collect_session_papers(messages)
    ids = [p.paper_id for p in papers]
    assert ids == ["p1", "p2"]
    assert papers[0].title == "Paper One"
    assert papers[0].year == 2020


def test_collect_empty_messages() -> None:
    assert collect_session_papers([]) == []
    assert collect_session_papers(None) == []  # type: ignore[arg-type]


# ── Part 2: paper_check_node ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_paper_check_enough_papers() -> None:
    """>= MIN_SESSION_PAPERS → baseline_triggered=False."""
    papers = [PaperRef(paper_id=f"p{i}", title=f"P{i}") for i in range(MIN_SESSION_PAPERS)]
    result = await paper_check_node({"session_papers": papers})
    assert result == {"baseline_triggered": False}


@pytest.mark.asyncio
async def test_paper_check_too_few_papers() -> None:
    """< MIN_SESSION_PAPERS → baseline_triggered=True."""
    papers = [PaperRef(paper_id="p0", title="P0")]
    result = await paper_check_node({"session_papers": papers})
    assert result == {"baseline_triggered": True}


@pytest.mark.asyncio
async def test_paper_check_empty() -> None:
    result = await paper_check_node({})
    assert result == {"baseline_triggered": True}


# ── Part 3: intent classifier ────────────────────────────────────────


@pytest.mark.asyncio
async def test_intent_keyword_fastpath_no_llm() -> None:
    """Keyword trigger → True without calling the LLM."""
    mock = AsyncMock()
    with patch(_INTENT_LLM, mock):
        assert await is_gap_detection_intent("tìm khoảng trống nghiên cứu trong các paper này") is True
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_intent_english_keyword() -> None:
    mock = AsyncMock()
    with patch(_INTENT_LLM, mock):
        assert await is_gap_detection_intent("What is the research gap here?") is True
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_intent_llm_fallback_yes() -> None:
    """No keyword → LLM says yes → True."""
    with patch(_INTENT_LLM, new_callable=AsyncMock, return_value="Yes"):
        assert await is_gap_detection_intent("Những điều gì các bài báo này còn bỏ ngỏ?") is True


@pytest.mark.asyncio
async def test_intent_normal_message_false() -> None:
    """AC: normal chat message → False (LLM says no)."""
    with patch(_INTENT_LLM, new_callable=AsyncMock, return_value="no"):
        assert await is_gap_detection_intent("Summarize this paper for me please.") is False


@pytest.mark.asyncio
async def test_intent_llm_error_defaults_false() -> None:
    """LLM error → False (never hijack normal flow)."""
    with patch(_INTENT_LLM, new_callable=AsyncMock, side_effect=Exception("down")):
        assert await is_gap_detection_intent("some ambiguous message") is False


@pytest.mark.asyncio
async def test_intent_empty_false() -> None:
    assert await is_gap_detection_intent("") is False


# ── Part 4: chat integration orchestration ───────────────────────────


def _report(narrative: str = "GAP NARRATIVE") -> GapReport:
    return GapReport(papers_analyzed=5, narrative=narrative)


@pytest.mark.asyncio
async def test_chat_enough_papers_runs_pipeline_directly() -> None:
    """AC: >=5 papers → run pipeline directly (no baseline search)."""
    from backend.agent.gap_detection.chat_integration import run_gap_detection_chat

    content = " ".join(f"(Source: p{i})" for i in range(5))
    messages = [{"role": "user", "content": f"tìm khoảng trống. {content}"}]

    with (
        patch(f"{_CI}.retrieval.search", new_callable=AsyncMock) as search_mock,
        patch(f"{_CI}.run_gap_detection", new_callable=AsyncMock, return_value=_report()) as run_mock,
    ):
        reply = await run_gap_detection_chat(messages)

    assert reply == "GAP NARRATIVE"
    search_mock.assert_not_called()  # baseline not triggered
    # pipeline received the 5 collected papers
    passed_papers = run_mock.call_args[0][0]
    assert [p.paper_id for p in passed_papers] == ["p0", "p1", "p2", "p3", "p4"]


@pytest.mark.asyncio
async def test_chat_few_papers_triggers_baseline() -> None:
    """AC: <5 papers → baseline search runs, papers merged, then pipeline."""
    from backend.agent.gap_detection.chat_integration import run_gap_detection_chat

    messages = [{"role": "user", "content": "research gap? (Source: p0) (Source: p1)"}]
    found = [Paper(paperId=f"b{i}", title=f"B{i}", year=2025) for i in range(3)]

    with (
        patch(f"{_CI}.retrieval.search", new_callable=AsyncMock, return_value=found) as search_mock,
        patch(f"{_CI}.run_gap_detection", new_callable=AsyncMock, return_value=_report()) as run_mock,
    ):
        reply = await run_gap_detection_chat(messages)

    assert reply == "GAP NARRATIVE"
    search_mock.assert_awaited_once()
    passed_papers = run_mock.call_args[0][0]
    # 2 session + 3 baseline = 5, deduped, session first
    assert [p.paper_id for p in passed_papers] == ["p0", "p1", "b0", "b1", "b2"]


@pytest.mark.asyncio
async def test_chat_empty_session_baseline_then_polite() -> None:
    """AC: empty session + gap query → baseline runs; if still empty, real synthesizer polite msg."""
    from backend.agent.gap_detection.chat_integration import run_gap_detection_chat

    messages = [{"role": "user", "content": "tìm khoảng trống nghiên cứu giúp tôi"}]

    # Baseline returns nothing → run_gap_detection over [] uses the REAL pipeline.
    with patch(f"{_CI}.retrieval.search", new_callable=AsyncMock, return_value=[]):
        reply = await run_gap_detection_chat(messages)

    # The real synthesizer's empty-gaps message (no gaps detected).
    assert "no clear research gaps" in reply.lower()


@pytest.mark.asyncio
async def test_chat_baseline_search_failure_non_fatal() -> None:
    """Baseline search error → proceed with existing papers, no crash."""
    from backend.agent.gap_detection.chat_integration import run_gap_detection_chat

    messages = [{"role": "user", "content": "research gap (Source: p0)"}]
    with (
        patch(f"{_CI}.retrieval.search", new_callable=AsyncMock, side_effect=Exception("S2 down")),
        patch(f"{_CI}.run_gap_detection", new_callable=AsyncMock, return_value=_report("OK")) as run_mock,
    ):
        reply = await run_gap_detection_chat(messages)

    assert reply == "OK"
    passed_papers = run_mock.call_args[0][0]
    assert [p.paper_id for p in passed_papers] == ["p0"]  # unchanged on failure
