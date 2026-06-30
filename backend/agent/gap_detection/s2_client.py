"""Semantic Scholar client for gap detection — owns get_paper_detail.

Self-contained: copied the minimal S2 helpers (BASE_URL, headers, retry-GET)
so the gap module doesn't import private symbols from semantic_scholar.py.
The baseline semantic_scholar.py retains search_papers / get_references /
get_citations / search_snippet which the gap nodes still call directly.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import httpx

from backend.config import get_settings
from backend.shared.services.s2_rate_limiter import s2_acquire

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1"
_DETAIL_FIELDS = "paperId,title,abstract,year,url,tldr,openAccessPdf,fieldsOfStudy,publicationTypes,venue,authors"


def _s2_headers() -> dict:
    key = get_settings().semantic_scholar_api_key
    return {"x-api-key": key} if key else {}


async def _s2_get(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    await s2_acquire()
    for attempt in range(3):
        try:
            r = await client.get(url, params=params, headers=_s2_headers(), timeout=10)  # G10.3: 10s fast-fail
            r.raise_for_status()
            return r.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException):
            if attempt < 2:
                await asyncio.sleep(2**attempt)
            else:
                logger.warning("s2_client._s2_get: timeout after 3 attempts for %s — returning {}", url)
                return {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                await asyncio.sleep(2**attempt)
            else:
                raise
    return {}


async def get_paper_detail(paper_id: str) -> dict | None:
    """Fetch extended metadata for a single paper.

    Returns the raw API response dict, or *None* on any error (404,
    timeout, rate-limit exhaustion).  The caller decides what to do.

    ``paper_id`` is URL-encoded so DOI identifiers containing ``/``
    are handled correctly.
    """
    encoded_id = quote(paper_id, safe="")
    try:
        async with httpx.AsyncClient() as client:
            data = await _s2_get(
                client,
                f"{_BASE_URL}/paper/{encoded_id}",
                {"fields": _DETAIL_FIELDS},
            )
        return data if data else None
    except Exception:
        logger.warning("get_paper_detail failed for %s", paper_id, exc_info=True)
        return None
