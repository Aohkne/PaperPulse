"""Tests for the /api/gap endpoint cold-start contract."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection import router as gap_router
from backend.agent.gap_detection.schemas import GapReport
from backend.auth.dependencies import get_current_user
from backend.main import app

_COLD_START = "backend.agent.gap_detection.router.cold_start"


async def _override_user():
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000001", email="test@example.com")


@pytest.fixture(autouse=True)
def _override_gap_dependencies(monkeypatch):
    app.dependency_overrides[get_current_user] = _override_user
    monkeypatch.setattr(gap_router.billing_db, "start_session", AsyncMock(return_value={}))
    monkeypatch.setattr(gap_router.billing_db, "refund_session", AsyncMock(return_value={}))
    yield
    app.dependency_overrides.clear()


def _make_report(**kwargs) -> GapReport:
    defaults = dict(papers_analyzed=5, narrative="Gaps found", gaps=[])
    return GapReport(**{**defaults, **kwargs})


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
    old_payload = {"papers": [{"paper_id": "p1", "title": "Some paper", "year": 2024}]}
    resp = await client.post("/api/gap", json=old_payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_insufficient_papers(client) -> None:
    """AC: cold_start returns gaps=[] narrative -> 200 + gaps empty, narrative present."""
    report = _make_report(
        papers_analyzed=2,
        narrative="Khong du tai lieu cho chu de nay.",
        gaps=[],
    )
    with patch(_COLD_START, new=AsyncMock(return_value=report)) as mock_cs:
        resp = await client.post("/api/gap", json={"topic": "obscure niche topic here"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["gaps"] == []
    assert "Khong du" in data["narrative"]
    mock_cs.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_error(client) -> None:
    """AC: cold_start raises Exception -> 500, body does NOT contain stack trace."""
    with patch(_COLD_START, new=AsyncMock(side_effect=RuntimeError("boom: internal detail"))):
        resp = await client.post("/api/gap", json={"topic": "valid topic here"})

    assert resp.status_code == 500
    body_text = resp.text
    assert "Gap detection" in body_text or "that bai" in body_text
    assert "boom" not in body_text
    assert "Traceback" not in body_text
    assert "RuntimeError" not in body_text
