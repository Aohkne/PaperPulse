"""arXiv keyword search via the arxiv PyPI package.

The arxiv client is synchronous; we run it in a ThreadPoolExecutor so it
doesn't block the event loop. This module is distinct from arxiv_fetcher.py
(which fetches ar5iv HTML for claim verification) — this one performs
keyword search and returns Paper objects for the multi-source pipeline.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor

from backend.config import get_settings
from backend.shared.models.paper import Paper

_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=get_settings().arxiv_search_max_workers,
            thread_name_prefix="arxiv_search",
        )
    return _executor


# `arxiv.Client` exposes no timeout option and its underlying `requests.Session`
# can hang indefinitely on a stalled connection — since these calls run in a
# 2-worker pool shared by every caller, one hang would eventually exhaust the
# pool for the rest of the process's lifetime. Patch a timeout onto the
# session's own `request()` method (scoped to this one Client instance only —
# NOT `socket.setdefaulttimeout()`, which would also affect unrelated
# concurrent httpx connections on other threads).
_HTTP_TIMEOUT_S = 15


def _client_with_timeout():
    import arxiv

    client = arxiv.Client()
    client._session.request = functools.partial(client._session.request, timeout=_HTTP_TIMEOUT_S)
    return client


def _sync_search(query: str, max_results: int) -> list[Paper]:
    try:
        import arxiv
    except ImportError:
        logging.warning("arxiv package not installed — arXiv search unavailable")
        return []

    client = _client_with_timeout()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers: list[Paper] = []
    for result in client.results(search):
        entry_id = result.entry_id or ""
        # entry_id format: "http://arxiv.org/abs/2301.12345v2"
        arxiv_id_raw = entry_id.split("/")[-1]
        # Strip version suffix for stable ID
        arxiv_id = arxiv_id_raw.split("v")[0] if "v" in arxiv_id_raw else arxiv_id_raw

        authors = [str(a) for a in (result.authors or [])]
        doi = result.doi or ""

        external_ids: dict[str, str] = {}
        if arxiv_id:
            external_ids["ArXiv"] = arxiv_id
        if doi:
            external_ids["DOI"] = doi

        papers.append(
            Paper(
                paperId=f"arxiv_{arxiv_id}" if arxiv_id else entry_id,
                title=result.title or "",
                abstract=result.summary or None,
                year=result.published.year if result.published else None,
                citationCount=None,
                authors=authors,
                url=entry_id or None,
                openAccessPdf=result.pdf_url or None,
                openAccessPdfStatus="GOLD",  # arXiv PDFs are always open access
                externalIds=external_ids,
                source="arxiv",
            )
        )

    return papers


async def search_arxiv(query: str, limit: int = 50) -> list[Paper]:
    """Search arXiv and return Paper objects (async wrapper)."""
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_get_executor(), _sync_search, query, limit)
    except Exception as exc:
        logging.warning("arXiv search failed: %s", exc)
        return []


def _sync_lookup_by_id(arxiv_id: str) -> Paper | None:
    try:
        import arxiv
    except ImportError:
        logging.warning("arxiv package not installed — arXiv lookup unavailable")
        return None

    client = _client_with_timeout()
    try:
        result = next(client.results(arxiv.Search(id_list=[arxiv_id])), None)
    except Exception:
        logging.warning("arXiv lookup_by_id failed for %s", arxiv_id, exc_info=True)
        return None
    if result is None:
        return None

    authors = [str(a) for a in (result.authors or [])]
    doi = result.doi or ""
    external_ids: dict[str, str] = {"ArXiv": arxiv_id}
    if doi:
        external_ids["DOI"] = doi

    return Paper(
        paperId=f"arxiv_{arxiv_id}",
        title=result.title or "",
        abstract=result.summary or None,
        year=result.published.year if result.published else None,
        citationCount=None,
        authors=authors,
        url=result.entry_id or None,
        openAccessPdf=result.pdf_url or None,
        openAccessPdfStatus="GOLD",
        externalIds=external_ids,
        source="arxiv",
    )


async def lookup_by_arxiv_id(arxiv_id: str) -> Paper | None:
    """Single-paper lookup by arXiv id — PDF Agent citation verification waterfall."""
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_get_executor(), _sync_lookup_by_id, arxiv_id)
    except Exception as exc:
        logging.warning("arXiv lookup_by_id failed: %s", exc)
        return None
