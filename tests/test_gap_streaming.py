"""Tests for streaming.py and GET /gap/stream."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection import router as gap_router
from backend.auth.dependencies import get_current_user
from backend.main import app

_STREAM = "backend.agent.gap_detection.streaming"
_ROUTER_STREAM = "backend.agent.gap_detection.router"
_ORCHESTRATOR = "backend.agent.gap_detection.orchestrator"


async def _override_user():
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000001", email="test@example.com")


@pytest.fixture(autouse=True)
def _override_gap_dependencies(monkeypatch):
    app.dependency_overrides[get_current_user] = _override_user
    monkeypatch.setattr(gap_router.billing_db, "start_session", AsyncMock(return_value={}))
    monkeypatch.setattr(gap_router.billing_db, "refund_session", AsyncMock(return_value={}))
    yield
    app.dependency_overrides.clear()


def _make_report_dict(narrative: str = "narrative") -> dict:
    from backend.agent.gap_detection.schemas import GapReport

    return GapReport(papers_analyzed=5, gaps=[], narrative=narrative).model_dump()


@pytest.mark.asyncio
async def test_stream_emits_node_start_events() -> None:
    """node_start SSE events are emitted for monitored nodes."""
    from backend.agent.gap_detection.schemas import PaperRef
    from backend.agent.gap_detection.streaming import stream_gap_detection

    mock_events = [
        {"event": "on_chain_start", "metadata": {"langgraph_node": "extractor"}, "data": {}},
        {"event": "on_chain_start", "metadata": {"langgraph_node": "synthesizer"}, "data": {}},
        {
            "event": "on_chain_end",
            "metadata": {"langgraph_node": "synthesizer"},
            "data": {"output": {"final_report": _make_report_pydantic("ok")}},
        },
    ]

    async def _fake_astream(*args, **kwargs):
        for ev in mock_events:
            yield ev

    papers = [PaperRef(paper_id="p0", title="T0")]
    with patch(f"{_STREAM}.build_gap_detection_graph") as mock_build:
        mock_graph = AsyncMock()
        mock_graph.astream_events = _fake_astream
        mock_build.return_value = mock_graph

        events = []
        async for chunk in stream_gap_detection(papers, "test topic"):
            assert chunk.startswith("data: ")
            assert chunk.endswith("\n\n")
            events.append(json.loads(chunk[len("data: ") :].strip()))

    types = [e["type"] for e in events]
    assert "node_start" in types
    assert "done" in types

    node_starts = [e for e in events if e["type"] == "node_start"]
    assert any(e["node"] == "extractor" for e in node_starts)
    assert any(e["node"] == "synthesizer" for e in node_starts)


@pytest.mark.asyncio
async def test_stream_done_event_has_report() -> None:
    """done event contains the GapReport dict."""
    from backend.agent.gap_detection.schemas import PaperRef
    from backend.agent.gap_detection.streaming import stream_gap_detection

    report_obj = _make_report_pydantic("test narrative")

    async def _fake_astream(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "metadata": {"langgraph_node": "synthesizer"},
            "data": {"output": {"final_report": report_obj}},
        }

    papers = [PaperRef(paper_id="p1", title="T1")]
    with patch(f"{_STREAM}.build_gap_detection_graph") as mock_build:
        mock_graph = AsyncMock()
        mock_graph.astream_events = _fake_astream
        mock_build.return_value = mock_graph

        events = []
        async for chunk in stream_gap_detection(papers, "topic"):
            events.append(json.loads(chunk[len("data: ") :].strip()))

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["report"]["narrative"] == "test narrative"


@pytest.mark.asyncio
async def test_stream_error_does_not_raise() -> None:
    """Unhandled exception in astream_events yields error event, never raises."""
    from backend.agent.gap_detection.schemas import PaperRef
    from backend.agent.gap_detection.streaming import stream_gap_detection

    async def _boom(*args, **kwargs):
        raise RuntimeError("S2 exploded")
        yield

    papers = [PaperRef(paper_id="p2", title="T2")]
    with patch(f"{_STREAM}.build_gap_detection_graph") as mock_build:
        mock_graph = AsyncMock()
        mock_graph.astream_events = _boom
        mock_build.return_value = mock_graph

        events = []
        async for chunk in stream_gap_detection(papers, "topic"):
            events.append(json.loads(chunk[len("data: ") :].strip()))

    assert len(events) == 1
    assert events[0]["type"] == "error"


@pytest.mark.asyncio
async def test_stream_unknown_nodes_not_emitted() -> None:
    """Events for unknown nodes are silently skipped."""
    from backend.agent.gap_detection.schemas import PaperRef
    from backend.agent.gap_detection.streaming import stream_gap_detection

    async def _fake_astream(*args, **kwargs):
        yield {"event": "on_chain_start", "metadata": {"langgraph_node": "unknown_node"}, "data": {}}
        yield {
            "event": "on_chain_end",
            "metadata": {"langgraph_node": "synthesizer"},
            "data": {"output": {"final_report": _make_report_pydantic("done")}},
        }

    papers = [PaperRef(paper_id="p3", title="T3")]
    with patch(f"{_STREAM}.build_gap_detection_graph") as mock_build:
        mock_graph = AsyncMock()
        mock_graph.astream_events = _fake_astream
        mock_build.return_value = mock_graph

        events = []
        async for chunk in stream_gap_detection(papers, "topic"):
            events.append(json.loads(chunk[len("data: ") :].strip()))

    node_starts = [e for e in events if e["type"] == "node_start"]
    assert all(e["node"] != "unknown_node" for e in node_starts)


@pytest.mark.asyncio
async def test_gap_stream_short_topic_422(client) -> None:
    """GET /gap/stream?topic=ab -> 422 (min_length=3)."""
    resp = await client.get("/api/gap/stream?topic=ab")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_gap_stream_returns_sse_content_type(client) -> None:
    """GET /gap/stream with valid topic -> Content-Type: text/event-stream."""

    async def _fake_stream(*args, **kwargs) -> AsyncGenerator[str, None]:
        yield 'data: {"type":"node_start","node":"extractor","label":"test"}\n\n'
        yield f"data: {json.dumps({'type': 'done', 'report': _make_report_dict()})}\n\n"

    with (
        patch(f"{_ROUTER_STREAM}.clean_query", new=AsyncMock(return_value="transformer attention")),
        patch(f"{_ROUTER_STREAM}.retrieval.search", new=AsyncMock(return_value=_fake_papers(6))),
        patch(f"{_ROUTER_STREAM}.retrieval.snowball", new=AsyncMock(return_value=_fake_papers(6))),
        patch(f"{_ROUTER_STREAM}.retrieval.rank", new=AsyncMock(return_value=_fake_papers(6))),
        patch(f"{_ROUTER_STREAM}.stream_gap_detection", return_value=_fake_stream()),
    ):
        resp = await client.get("/api/gap/stream?topic=transformer+attention")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_gap_stream_insufficient_papers(client) -> None:
    """Thin corpus -> SSE event type=insufficient, no crash."""

    with (
        patch(
            f"{_ROUTER_STREAM}.analyze_query",
            new=AsyncMock(return_value=SimpleNamespace(is_research_topic=True, reject_reason=None)),
        ),
        patch(f"{_ROUTER_STREAM}.clean_query", new=AsyncMock(return_value="q")),
        patch(f"{_ROUTER_STREAM}.retrieval.search", new=AsyncMock(return_value=[])),
        patch(f"{_ROUTER_STREAM}.retrieval.snowball", new=AsyncMock(return_value=[])),
        patch(f"{_ROUTER_STREAM}.retrieval.rank", new=AsyncMock(return_value=[])),
    ):
        resp = await client.get("/api/gap/stream?topic=very+niche+topic+xyz")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    body = resp.text
    assert "insufficient" in body


@pytest.mark.asyncio
async def test_post_gap_not_regressed(client) -> None:
    """POST /gap still returns 200 + GapReport (regression check)."""
    from backend.agent.gap_detection.schemas import GapReport

    report = GapReport(papers_analyzed=5, gaps=[], narrative="ok")
    with patch(f"{_ROUTER_STREAM}.cold_start", new=AsyncMock(return_value=report)):
        resp = await client.post("/api/gap", json={"topic": "transformer attention"})

    assert resp.status_code == 200
    data = resp.json()
    assert "narrative" in data
    assert "gaps" in data


def _make_report_pydantic(narrative: str = "narrative"):
    from backend.agent.gap_detection.schemas import GapReport

    return GapReport(papers_analyzed=5, gaps=[], narrative=narrative)


def _fake_papers(n: int):
    from backend.shared.models.paper import Paper

    return [Paper(paperId=f"p{i}", title=f"Paper {i}", year=2020) for i in range(n)]
