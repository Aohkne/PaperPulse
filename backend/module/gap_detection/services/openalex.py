from __future__ import annotations

import asyncio
import logging

import httpx

from backend.module.gap_detection.settings import get_openalex_mailto
from backend.shared.models.paper import Paper

logger = logging.getLogger(__name__)

_API_BASE = "https://api.openalex.org/works"
_TIMEOUT_SECONDS = 10.0
_MIN_INTERVAL_SECONDS = 0.1  # polite pool: 10 req/s

_CACHE: dict[str, list[Paper]] = {}
_CACHE_LOCK = asyncio.Lock()
_RATE_LIMIT_LOCK = asyncio.Lock()
_LAST_CALL_AT = 0.0


async def openalex_search(query: str, limit: int = 20) -> list[Paper]:
    """Search OpenAlex for papers matching *query*.

    Returns a list of Paper objects with source="openalex" and
    paper_id="openalex:<WorkID>".  DOI is stored bare (no prefix) in
    external_ids["DOI"] so resolve_papers() can dedup against S2 records.

    Always returns a list — empty on timeout or any network/parse error so
    callers can treat it as a non-fatal supplement (mirrors arxiv_search).
    """
    cache_key = f"{query}|{limit}"
    async with _CACHE_LOCK:
        if cache_key in _CACHE:
            return _CACHE[cache_key]

    try:
        result = await _fetch_openalex(query, limit)
    except Exception:
        logger.debug("openalex_search: unexpected error for query=%r", query[:60], exc_info=True)
        result = []

    async with _CACHE_LOCK:
        _CACHE[cache_key] = result
    return result


async def _fetch_openalex(query: str, limit: int) -> list[Paper]:
    await _respect_rate_limit()
    params = {
        "search": query,
        "per_page": str(limit),
        "mailto": get_openalex_mailto(),
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(_API_BASE, params=params, timeout=_TIMEOUT_SECONDS)
        if response.status_code != 200:
            logger.debug(
                "openalex_search: HTTP %d for query=%r",
                response.status_code,
                query[:60],
            )
            return []
        data = response.json()
    except Exception:
        logger.debug("openalex_search: network/parse error for query=%r", query[:60], exc_info=True)
        return []

    papers: list[Paper] = []
    for work in data.get("results", []):
        try:
            paper = _work_to_paper(work)
            if paper is not None:
                papers.append(paper)
        except Exception:
            logger.debug("openalex_search: failed to parse work — skipping", exc_info=True)
    return papers


async def _respect_rate_limit() -> None:
    global _LAST_CALL_AT

    async with _RATE_LIMIT_LOCK:
        now = asyncio.get_running_loop().time()
        wait_seconds = _MIN_INTERVAL_SECONDS - (now - _LAST_CALL_AT)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
            now = asyncio.get_running_loop().time()
        _LAST_CALL_AT = now


def _work_to_paper(work: dict) -> Paper | None:
    """Map a single OpenAlex Work object to the shared Paper model."""
    raw_id = work.get("id") or ""
    work_id = raw_id.rstrip("/").rsplit("/", 1)[-1]  # "https://openalex.org/W123" → "W123"
    if not work_id:
        return None

    title = work.get("title") or ""
    if not title:
        return None

    doi = _normalize_doi(work.get("doi"))
    external_ids: dict[str, str | None] = {"OpenAlex": work_id}
    if doi:
        external_ids["DOI"] = doi

    authors = [
        a["author"]["display_name"]
        for a in work.get("authorships", [])
        if a.get("author") and a["author"].get("display_name")
    ]

    primary_loc = work.get("primary_location") or {}
    venue_source = primary_loc.get("source") or {}
    venue = venue_source.get("display_name") or None

    best_oa = work.get("best_oa_location") or {}
    open_access_pdf = best_oa.get("pdf_url") or None

    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

    return Paper(
        paperId=f"openalex:{work_id}",
        title=title,
        abstract=abstract,
        year=work.get("publication_year"),
        citationCount=work.get("cited_by_count"),
        authors=authors,
        url=raw_id or None,
        openAccessPdf=open_access_pdf,
        externalIds=external_ids,
        isInfluential=False,
        source="openalex",
        venue=venue,
    )


def _normalize_doi(raw: str | None) -> str:
    """Strip URL prefix and lowercase a DOI so it matches S2's bare format."""
    if not raw:
        return ""
    value = raw.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    return value.strip()


def _reconstruct_abstract(inv: dict | None) -> str | None:
    """Reconstruct a plain-text abstract from OpenAlex inverted-index encoding."""
    if not inv:
        return None
    try:
        size = max(pos for positions in inv.values() for pos in positions) + 1
        words: list[str] = [""] * size
        for word, positions in inv.items():
            for pos in positions:
                if 0 <= pos < size:
                    words[pos] = word
        text = " ".join(w for w in words if w)
        return text or None
    except Exception:
        return None


def _reset_cache_for_tests() -> None:
    global _LAST_CALL_AT
    _CACHE.clear()
    _LAST_CALL_AT = 0.0
