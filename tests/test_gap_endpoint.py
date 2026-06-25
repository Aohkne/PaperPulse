"""Tests for the /api/gap endpoint — cold-start contract (TIP-G12).

After TIP-G05 the endpoint accepts {topic: str} and routes to
``orchestrator.cold_start``.  These tests cover the router contract:
  - request validation (topic min_length=3, missing field, wrong shape)
  - response shape (GapReport)
  - insufficient-paper happy path (gaps=[], narrative)
  - internal error -> 500 with safe message (no stack trace in body)

``cold_start`` is mocked — pipeline internals are covered by test_gap_e2e.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.schemas import GapReport

# Mock target: cold_start as imported in the router module
_COLD_START = "backend.agent.gap_detection.router.cold_start"


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_report(**kwargs) -> GapReport:
    defaults = dict(papers_analyzed=5, narrative="Gaps found", gaps=[])
    return GapReport(**{**defaults, **kwargs})


# ── Test cases ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_topic(client) -> None:
    """AC: valid topic -> 200 + GapReport shape."""
    report = _make_report(papers_analyzed=8, narrative="Research gaps detected", gaps=[])
    with patch(_COLD_START, new=AsyncMock(return_value=report)) as mock_cs:
        resp = await client.post("/api/gap", json={"topic": "transformer attention"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["narrative"] == "Research gaps detected"
    assert data["papers_analyzed"] == 8
    assert data["gaps"] == []
    mock_cs.assert_awaited_once_with("transformer attention")


@pytest.mark.asyncio
async def test_topic_too_short(client) -> None:
    """AC: topic < 3 chars -> 422 (Pydantic min_length=3)."""
    resp = await client.post("/api/gap", json={"topic": "ab"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_empty_topic(client) -> None:
    """AC: empty topic string -> 422."""
    resp = await client.post("/api/gap", json={"topic": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_topic_field(client) -> None:
    """AC: body without 'topic' field -> 422."""
    resp = await client.post("/api/gap", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_old_warm_shape_rejected(client) -> None:
    """AC: old warm-start shape {papers:[...]} -> 422 (topic field missing)."""
    old_payload = {
        "papers": [
            {"paper_id": "p1", "title": "Some paper", "year": 2024}
        ]
    }
    resp = await client.post("/api/gap", json=old_payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_insufficient_papers(client) -> None:
    """AC: cold_start returns gaps=[] narrative -> 200 + gaps empty, narrative present."""
    report = _make_report(
        papers_analyzed=2,
        narrative="Không đủ tài liệu cho chủ đề này.",
        gaps=[],
    )
    with patch(_COLD_START, new=AsyncMock(return_value=report)) as mock_cs:
        resp = await client.post("/api/gap", json={"topic": "obscure niche topic here"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["gaps"] == []
    assert "Không đủ" in data["narrative"]
    mock_cs.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_error(client) -> None:
    """AC: cold_start raises Exception -> 500, body does NOT contain stack trace."""
    with patch(_COLD_START, new=AsyncMock(side_effect=RuntimeError("boom: internal detail"))):
        resp = await client.post("/api/gap", json={"topic": "valid topic here"})

    assert resp.status_code == 500
    body_text = resp.text
    # Safe message present
    assert "Gap detection" in body_text or "thất bại" in body_text
    # Stack trace NOT leaked
    assert "boom" not in body_text
    assert "Traceback" not in body_text
    assert "RuntimeError" not in body_text
