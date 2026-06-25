"""TIP-G08 — End-to-end integration tests + citation-guard tests.

Exercises the full gap-detection path through ``run_gap_detection_chat``
and the chat route, plus the synthesizer citation guard.  Every external
dependency (Semantic Scholar + LLM) is mocked; no real API calls.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.chat_integration import run_gap_detection_chat
from backend.agent.gap_detection.nodes.synthesizer import (
    _UNVERIFIED_MARKER,
    _validate_citations,
)
from backend.agent.gap_detection.schemas import GapStatus, GapType, PaperRef
from backend.shared.models.paper import Paper

# Module paths to patch.
_EXTRACTOR = "backend.agent.gap_detection.nodes.extractor"
_TOPICAL = "backend.agent.gap_detection.nodes.topical_detector"
_METHOD = "backend.agent.gap_detection.nodes.method_detector"
_CONTRA = "backend.agent.gap_detection.nodes.contradiction_detector"
_VERIFIER = "backend.agent.gap_detection.nodes.verifier"
_COUNTER = "backend.agent.gap_detection.nodes.counter_search"
_SYNTH = "backend.agent.gap_detection.nodes.synthesizer"
_CI = "backend.agent.gap_detection.chat_integration"
_CHAT_API = "backend.api.chat"


# ── Mock payloads ────────────────────────────────────────────────────

_EXTRACTION_JSON = json.dumps(
    {
        "topics": ["machine learning"],
        "keywords": ["cnn"],
        "methodology": "CNN",
        "dataset": "ImageNet",
        "population": None,
        "metrics": ["accuracy"],
        "key_claims": ["Model improves accuracy"],
        "limitation_statements": [],
    }
)
_TOPICAL_JSON = json.dumps({"gaps": [{"statement": "topical gap exists", "supporting_paper_ids": ["p0"]}]})
_METHOD_JSON = json.dumps(
    {"gaps": [{"statement": "method gap exists", "from_limitation": False, "supporting_paper_ids": ["p1"]}]}
)
_CONTRA_JSON = json.dumps(
    {
        "contradictions": [
            {
                "statement": "papers disagree",
                "paper_id_a": "p0",
                "paper_id_b": "p1",
                "context_explanation": "different datasets",
            }
        ]
    }
)

# A "good" synthesizer narrative: status tag + only real citation tokens (titles = ids).
_GOOD_NARRATIVE = "[OPEN GAP] Mặc dù ML được nghiên cứu nhiều, vẫn còn topical gap [p0] và method gap [p1]."

# A "malicious" narrative: real [p0] + a fabricated citation the guard must strip.
_FABRICATED_NARRATIVE = "[OPEN GAP] Có gap [p0] nhưng cũng tham chiếu [Bịa Đặt Paper, 1999] không có thật."


def _detail() -> dict:
    return {
        "paperId": "x",
        "title": "T",
        "abstract": "This studies ML.",
        "tldr": {"text": "ML."},
        "openAccessPdf": None,  # abstract path → no PDF fetch
    }


def _source_msg(n: int) -> list[dict]:
    """A single user message citing n papers via (Source: pX), asking for gaps."""
    cites = " ".join(f"(Source: p{i})" for i in range(n))
    return [{"role": "user", "content": f"tìm khoảng trống nghiên cứu. {cites}"}]


def _patch_pipeline(
    stack: ExitStack,
    *,
    detail: dict | None,
    synth_narrative: str,
    baseline_results: list[Paper] | None = None,
) -> dict[str, AsyncMock]:
    """Patch every external dependency of the full pipeline; return key mocks."""
    mocks: dict[str, AsyncMock] = {}
    mocks["get_paper_detail"] = stack.enter_context(
        patch(f"{_EXTRACTOR}.get_paper_detail", new=AsyncMock(return_value=detail))
    )
    stack.enter_context(patch(f"{_EXTRACTOR}.chat_completion", new=AsyncMock(return_value=_EXTRACTION_JSON)))
    stack.enter_context(patch(f"{_TOPICAL}.chat_completion", new=AsyncMock(return_value=_TOPICAL_JSON)))
    stack.enter_context(patch(f"{_METHOD}.chat_completion", new=AsyncMock(return_value=_METHOD_JSON)))
    stack.enter_context(patch(f"{_CONTRA}.chat_completion", new=AsyncMock(return_value=_CONTRA_JSON)))
    stack.enter_context(patch(f"{_VERIFIER}.verify_claims", new=AsyncMock(return_value=[])))
    # After P2-01.C migration, both counter_search and chat_integration call
    # retrieval.search (same function object). Patch at source so both callers see
    # the mock. Use side_effect to return [] for counter calls and
    # baseline_results for the chat_integration baseline call.
    _baseline = baseline_results or []

    async def _retrieval_search_side_effect(query: str, limit: int = 100) -> list[Paper]:
        # counter_search always asks with limit=DEFAULT_SEARCH_LIMIT (5)
        # chat_integration asks with limit=BASELINE_SEARCH_LIMIT (10)
        if limit == 10:  # baseline call from chat_integration
            return list(_baseline)
        return []  # counter_search calls return empty

    mocks["retrieval_search"] = stack.enter_context(
        patch(
            "backend.agent.gap_detection.retrieval.search",
            new=AsyncMock(side_effect=_retrieval_search_side_effect),
        )
    )
    stack.enter_context(patch(f"{_COUNTER}.chat_completion", new=AsyncMock(return_value="q")))
    stack.enter_context(patch(f"{_SYNTH}.chat_completion", new=AsyncMock(return_value=synth_narrative)))
    # Convenience alias for baseline-specific assertions
    mocks["baseline_search"] = mocks["retrieval_search"]
    return mocks


# ── Part 1: citation guard unit tests ───────────────────────────────


def test_guard_strips_fabricated_citation() -> None:
    """AC: citation to a paper not in supporting_papers is removed/replaced + logged."""
    allowed = [PaperRef(paper_id="p0", title="Real Paper", year=2020)]
    narrative = "Gap A [Real Paper, 2020] is open, but [Ghost Paper, 1999] is fabricated."
    cleaned = _validate_citations(narrative, allowed)

    assert "[Real Paper, 2020]" in cleaned
    assert "[Ghost Paper, 1999]" not in cleaned
    assert _UNVERIFIED_MARKER in cleaned


def test_guard_keeps_all_real_citations() -> None:
    """AC: narrative with only real citations is unchanged."""
    allowed = [PaperRef(paper_id="p0", title="A", year=2020), PaperRef(paper_id="p1", title="B")]
    narrative = "[OPEN GAP] Gap with [A, 2020] and [B]."
    cleaned = _validate_citations(narrative, allowed)
    assert cleaned == narrative


def test_guard_preserves_status_and_type_tags() -> None:
    """Status tags and gap-type tags are never treated as citations."""
    narrative = (
        f"{GapStatus.OPEN.value} [OPEN GAP] [PARTIALLY FILLED] [NEEDS RESOLUTION] "
        f"[{GapType.TOPICAL.value}] [{GapType.CONTRADICTION.value}]"
    )
    cleaned = _validate_citations(narrative, [])
    assert "[OPEN GAP]" in cleaned
    assert "[PARTIALLY FILLED]" in cleaned
    assert "[NEEDS RESOLUTION]" in cleaned
    assert "[topical]" in cleaned
    assert _UNVERIFIED_MARKER not in cleaned


def test_guard_no_papers_strips_any_citation() -> None:
    """With no allowed papers, any non-tag bracket is treated as unverified."""
    cleaned = _validate_citations("Claim [Some Paper, 2021].", [])
    assert "[Some Paper, 2021]" not in cleaned
    assert _UNVERIFIED_MARKER in cleaned


# ── Part 2: full-pipeline e2e ────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_five_papers_happy_path() -> None:
    """AC: ≥5 papers → pipeline runs, gaps produced, template narrative returned, no crash.

    P3-15: narrative is now a template summary (no LLM text); gap analysis lives in
    gap.analysis per-card. Assertions updated accordingly.
    """
    with ExitStack() as stack:
        mocks = _patch_pipeline(stack, detail=_detail(), synth_narrative=_GOOD_NARRATIVE)
        narrative = await run_gap_detection_chat(_source_msg(5))

    # P3-15: narrative is a short template summary, not LLM-generated text.
    assert narrative  # non-empty
    assert _UNVERIFIED_MARKER not in narrative  # template has no fabricated citations
    # After P2-01.C: retrieval.search is shared by counter_search (limit=5) and
    # chat_integration baseline (limit=10). With 5 papers, no baseline → no limit=10 call.
    baseline_calls = [
        c for c in mocks["baseline_search"].await_args_list if c.kwargs.get("limit") == 10
    ]
    assert baseline_calls == [], "Baseline should not be triggered with 5 papers"


@pytest.mark.asyncio
async def test_e2e_citation_guard_strips_fabrication_in_pipeline() -> None:
    """AC (P3-15): synthesizer no longer calls LLM for narrative → fabricated citations
    cannot appear in narrative. Pipeline produces clean template summary.

    The citation guard unit tests (test_guard_*) still verify _validate_citations works;
    this E2E test confirms fabricated text never reaches the final narrative.
    """
    with ExitStack() as stack:
        _patch_pipeline(stack, detail=_detail(), synth_narrative=_FABRICATED_NARRATIVE)
        narrative = await run_gap_detection_chat(_source_msg(5))

    # P3-15: LLM narrative not used → fabricated citation cannot appear
    assert "[Bịa Đặt Paper, 1999]" not in narrative
    assert _UNVERIFIED_MARKER not in narrative  # template summary, no guard triggered
    assert narrative  # non-empty template summary


@pytest.mark.asyncio
async def test_e2e_few_papers_triggers_baseline() -> None:
    """AC: <5 papers → baseline search runs (baseline_triggered), then pipeline."""
    baseline = [Paper(paperId=f"b{i}", title=f"B{i}", year=2025) for i in range(3)]
    with ExitStack() as stack:
        mocks = _patch_pipeline(
            stack, detail=_detail(), synth_narrative=_GOOD_NARRATIVE, baseline_results=baseline
        )
        narrative = await run_gap_detection_chat(_source_msg(2))

    # After P2-01.C: retrieval.search is shared; baseline calls use limit=10
    baseline_calls = [
        c for c in mocks["baseline_search"].await_args_list if c.kwargs.get("limit") == 10
    ]
    assert len(baseline_calls) == 1, f"Expected 1 baseline call, got {len(baseline_calls)}"
    assert narrative  # produced a narrative, no crash


@pytest.mark.asyncio
async def test_e2e_all_external_fail_graceful() -> None:
    """AC: all external calls fail → graceful fallback narrative, no crash."""
    with ExitStack() as stack:
        # S2 detail fetch returns None for every paper → no extraction → no gaps.
        _patch_pipeline(stack, detail=None, synth_narrative="unused")
        narrative = await run_gap_detection_chat(_source_msg(5))

    # P3-15: empty-gaps message is _EMPTY_MESSAGE (no _ACTION_HOOKS appended).
    assert "no clear research gaps" in narrative.lower()
    assert narrative  # non-empty, no exception raised


# ── Part 2: chat-route intent routing ───────────────────────────────


@pytest.mark.asyncio
async def test_route_gap_intent_gated_off(client) -> None:
    """AC (CONSOLIDATE): gap branch removed from chat.py → chat always returns
    normal reply regardless of message content (pipeline moved to /api/gap)."""
    with patch(f"{_CHAT_API}.chat_completion", new=AsyncMock(return_value="normal reply")):
        resp = await client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "tìm research gap"}]},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == "normal reply"


@pytest.mark.asyncio
async def test_route_normal_chat_untouched(client) -> None:
    """AC: non-gap message → normal chat flow."""
    with patch(f"{_CHAT_API}.chat_completion", new=AsyncMock(return_value="normal reply")):
        resp = await client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "summarize this paper"}]},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == "normal reply"
