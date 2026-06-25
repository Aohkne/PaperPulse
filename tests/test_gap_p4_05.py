"""Tests for TIP-405 — arXiv integration in retrieval.search().

Acceptance criteria:
- AC1: ARXIV_ENABLED → arXiv papers in pool (source="arxiv" in paper.source)
- AC2: Same DOI in S2 + arXiv → 1 merged paper, sources contains both
- AC3: arXiv timeout → S2-only result, no crash
- AC4: ARXIV_ENABLED=false → arxiv_search not called, S2-only

Unit helpers tested:
- _parse_arxiv_id: strips URL prefix and version suffix
- _parse_arxiv_feed: parses valid Atom XML into Paper objects; handles bad entries
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend.shared.models.paper import Paper
from backend.shared.services.arxiv_fetcher import _parse_arxiv_feed, _parse_arxiv_id


# ── Sample Atom XML ───────────────────────────────────────────────────────────

_SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2310.12345v2</id>
    <published>2023-10-18T00:00:00Z</published>
    <title>Speculative Decoding with Diffusion Models</title>
    <summary>We propose a method for speculative decoding.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <link href="http://arxiv.org/abs/2310.12345v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2310.12345v2" rel="related" type="application/pdf"/>
    <arxiv:doi xmlns:arxiv="http://arxiv.org/schemas/atom">10.1234/spec.2023</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2311.99999v1</id>
    <published>2023-11-01T00:00:00Z</published>
    <title>Federated Learning Survey</title>
    <summary>A survey of federated learning.</summary>
    <author><name>Carol Lee</name></author>
    <link href="http://arxiv.org/abs/2311.99999v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""

_EMPTY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""

_BROKEN_XML = "this is not xml <<<<"


# ── _parse_arxiv_id ───────────────────────────────────────────────────────────


def test_parse_arxiv_id_strips_url_and_version():
    assert _parse_arxiv_id("http://arxiv.org/abs/2310.12345v2") == "2310.12345"


def test_parse_arxiv_id_no_version():
    assert _parse_arxiv_id("http://arxiv.org/abs/2310.12345") == "2310.12345"


def test_parse_arxiv_id_old_format():
    assert _parse_arxiv_id("http://arxiv.org/abs/cs/0601001v1") == "cs/0601001"


def test_parse_arxiv_id_bare_id():
    # Fallback: no "/" at all → returns as-is
    result = _parse_arxiv_id("2310.12345v3")
    assert result == "2310.12345"


# ── _parse_arxiv_feed ─────────────────────────────────────────────────────────


def test_parse_arxiv_feed_returns_papers():
    papers = _parse_arxiv_feed(_SAMPLE_FEED)
    assert len(papers) == 2


def test_parse_arxiv_feed_first_paper_fields():
    papers = _parse_arxiv_feed(_SAMPLE_FEED)
    p = papers[0]
    assert p.paper_id == "arxiv:2310.12345"
    assert "Speculative Decoding" in p.title
    assert p.year == 2023
    assert "Alice Smith" in p.authors
    assert "Bob Jones" in p.authors
    assert p.external_ids.get("ArXiv") == "2310.12345"
    assert p.external_ids.get("DOI") == "10.1234/spec.2023"
    assert p.source == "arxiv"


def test_parse_arxiv_feed_second_paper_no_doi():
    papers = _parse_arxiv_feed(_SAMPLE_FEED)
    p = papers[1]
    assert p.paper_id == "arxiv:2311.99999"
    assert "DOI" not in p.external_ids
    assert p.abstract is not None


def test_parse_arxiv_feed_empty_feed():
    papers = _parse_arxiv_feed(_EMPTY_FEED)
    assert papers == []


def test_parse_arxiv_feed_broken_xml():
    papers = _parse_arxiv_feed(_BROKEN_XML)
    assert papers == []


def test_parse_arxiv_feed_open_access_pdf_set():
    papers = _parse_arxiv_feed(_SAMPLE_FEED)
    assert papers[0].open_access_pdf is not None
    assert "2310.12345" in papers[0].open_access_pdf


# ── AC1: arXiv papers appear in search() pool ─────────────────────────────────


def _make_s2_paper(doi: str | None = None) -> Paper:
    ext = {"DOI": doi} if doi else {}
    return Paper(
        paperId="s2abc123",
        title="Speculative Decoding Study",
        abstract="Abstract text",
        year=2023,
        externalIds=ext,
        source="s2",
    )


def _make_arxiv_paper(doi: str | None = None) -> Paper:
    ext = {"ArXiv": "2310.12345"}
    if doi:
        ext["DOI"] = doi
    return Paper(
        paperId="arxiv:2310.12345",
        title="Speculative Decoding with Diffusion Models",
        abstract="arXiv abstract",
        year=2023,
        externalIds=ext,
        source="arxiv",
    )


@pytest.mark.asyncio
async def test_search_includes_arxiv_papers_when_enabled():
    """AC1: ARXIV_ENABLED → arXiv papers included in result pool."""
    s2_paper = _make_s2_paper()
    arxiv_paper = _make_arxiv_paper()

    with (
        patch.dict(os.environ, {"ARXIV_ENABLED": "true"}),
        patch(
            "backend.agent.gap_detection.retrieval.search_papers",
            new_callable=AsyncMock,
            return_value=[s2_paper],
        ),
        patch(
            "backend.agent.gap_detection.retrieval.arxiv_search",
            new_callable=AsyncMock,
            return_value=[arxiv_paper],
        ),
    ):
        from backend.agent.gap_detection import retrieval
        result = await retrieval.search("speculative decoding", limit=10)

    # Both sources contributed; dedup via title → 1 or 2 papers depending on title match
    assert len(result) >= 1
    # At least one paper should carry arxiv as source
    sources_combined = " ".join(p.source or "" for p in result)
    assert "arxiv" in sources_combined


# ── AC2: Same DOI in S2 + arXiv → 1 merged CanonicalPaper ───────────────────


@pytest.mark.asyncio
async def test_search_deduplicates_same_doi():
    """AC2: S2 paper and arXiv paper with same DOI → 1 merged Paper."""
    shared_doi = "10.1234/spec.2023"
    s2_paper = _make_s2_paper(doi=shared_doi)
    arxiv_paper = _make_arxiv_paper(doi=shared_doi)

    with (
        patch.dict(os.environ, {"ARXIV_ENABLED": "true"}),
        patch(
            "backend.agent.gap_detection.retrieval.search_papers",
            new_callable=AsyncMock,
            return_value=[s2_paper],
        ),
        patch(
            "backend.agent.gap_detection.retrieval.arxiv_search",
            new_callable=AsyncMock,
            return_value=[arxiv_paper],
        ),
    ):
        from backend.agent.gap_detection import retrieval
        result = await retrieval.search("speculative decoding", limit=10)

    # Same DOI → exactly 1 paper
    assert len(result) == 1
    p = result[0]
    # Merged paper's source should contain both
    assert "s2" in (p.source or "")
    assert "arxiv" in (p.source or "")
    # S2 paperId is preferred over arxiv: prefix
    assert p.paper_id == "s2abc123"


# ── AC3: arXiv timeout → S2-only, no crash ────────────────────────────────────


@pytest.mark.asyncio
async def test_search_arxiv_timeout_falls_back_to_s2():
    """AC3: arXiv raises exception → search returns S2 results, no crash."""
    s2_paper = _make_s2_paper()

    with (
        patch.dict(os.environ, {"ARXIV_ENABLED": "true"}),
        patch(
            "backend.agent.gap_detection.retrieval.search_papers",
            new_callable=AsyncMock,
            return_value=[s2_paper],
        ),
        patch(
            "backend.agent.gap_detection.retrieval.arxiv_search",
            new_callable=AsyncMock,
            side_effect=Exception("connection timeout"),
        ),
    ):
        from backend.agent.gap_detection import retrieval
        result = await retrieval.search("speculative decoding", limit=10)

    assert len(result) == 1
    assert result[0].paper_id == "s2abc123"


# ── AC4: ARXIV_ENABLED=false → arxiv_search not called ───────────────────────


@pytest.mark.asyncio
async def test_search_arxiv_disabled_skips_arxiv():
    """AC4: ARXIV_ENABLED=false → arxiv_search not called, S2-only behaviour."""
    s2_paper = _make_s2_paper()

    with (
        patch.dict(os.environ, {"ARXIV_ENABLED": "false"}),
        patch(
            "backend.agent.gap_detection.retrieval.search_papers",
            new_callable=AsyncMock,
            return_value=[s2_paper],
        ),
        patch(
            "backend.agent.gap_detection.retrieval.arxiv_search",
            new_callable=AsyncMock,
        ) as mock_arxiv,
    ):
        from backend.agent.gap_detection import retrieval
        result = await retrieval.search("federated learning", limit=10)

    mock_arxiv.assert_not_called()
    assert len(result) == 1
    assert result[0].paper_id == "s2abc123"


# ── is_arxiv_enabled() setting getter ────────────────────────────────────────


def test_is_arxiv_enabled_default_true():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ARXIV_ENABLED", None)
        from backend.agent.gap_detection.settings import is_arxiv_enabled
        assert is_arxiv_enabled() is True


def test_is_arxiv_enabled_false_via_env():
    with patch.dict(os.environ, {"ARXIV_ENABLED": "false"}):
        from backend.agent.gap_detection.settings import is_arxiv_enabled
        assert is_arxiv_enabled() is False


def test_get_arxiv_search_limit_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ARXIV_SEARCH_LIMIT", None)
        from backend.agent.gap_detection.settings import get_arxiv_search_limit
        assert get_arxiv_search_limit() == 20


def test_get_arxiv_search_limit_custom():
    with patch.dict(os.environ, {"ARXIV_SEARCH_LIMIT": "15"}):
        from backend.agent.gap_detection.settings import get_arxiv_search_limit
        assert get_arxiv_search_limit() == 15
