"""Wrapper for Semantic Scholar API - paper search, references, citations, snippets."""

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.shared.models.paper import Paper
from backend.shared.services.s2_rate_limiter import s2_acquire

BASE_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS = (
    "paperId,title,abstract,year,citationCount,authors,url,externalIds,openAccessPdf,publicationVenue,journal,venue"
)
# externalIds needed for ArXiv ID (Step 8 in 3-tier verify) and DOI (Step 10 PDF links)
SNOWBALL_FIELDS = "contexts,intents,isInfluential,citationCount,year,externalIds,openAccessPdf,paperId,title,abstract,authors,url,publicationVenue,journal,venue"

logger = logging.getLogger(__name__)


def _headers() -> dict:
    key = get_settings().semantic_scholar_api_key
    return {"x-api-key": key} if key else {}


async def _get(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    await s2_acquire()
    for attempt in range(3):
        try:
            r = await client.get(url, params=params, headers=_headers(), timeout=60)
            r.raise_for_status()
            return r.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException):
            if attempt < 2:
                await asyncio.sleep(2**attempt)
            else:
                logger.warning("S2 _get: timeout after 3 attempts for %s - returning empty", url)
                return {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                await asyncio.sleep(2**attempt)
            else:
                raise
    logger.warning("S2 _get: all retries exhausted for %s - returning empty (rate-limit or API down)", url)
    return {}


async def search_papers(
    query: str,
    limit: int = 100,
    fields_of_study: list[str] | None = None,
) -> list[Paper]:
    """Search papers by query string.

    Args:
        query: Search query string.
        limit: Max results (S2 hard-caps at 100).
        fields_of_study: If set, restricts results to these fields (e.g. ["Computer Science"]).
            Passed as comma-separated string to S2 ``fieldsOfStudy`` param.
    """
    params: dict = {"query": query, "fields": FIELDS, "limit": limit}
    if fields_of_study:
        params["fieldsOfStudy"] = ",".join(fields_of_study)

    # No search cache: the LangGraph checkpointer already persists ResearchState
    # per thread_id (retry within a session needs no cache), and cross-session
    # hit-rate is low since the LLM generates different sub_queries each time.
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE_URL}/paper/search", params)

    return [_to_paper(p) for p in (data.get("data") or []) if p and p.get("paperId")]


async def _get_single(client: httpx.AsyncClient, id_str: str) -> dict | None:
    """GET /paper/{id} - single-paper lookup by a prefixed external id (DOI:.../ARXIV:...).

    Unlike `_get()`, a 404 here means "not found" (not a transient error) - return
    None instead of raising so callers (PDF Agent citation lookup) can fall through
    to the next source in the waterfall.
    """
    await s2_acquire()
    for attempt in range(3):
        try:
            r = await client.get(
                f"{BASE_URL}/paper/{id_str}", params={"fields": FIELDS}, headers=_headers(), timeout=30
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            if e.response.status_code == 429:
                await asyncio.sleep(2**attempt)
            else:
                raise
    return None


async def lookup_by_doi(doi: str) -> Paper | None:
    """Single-paper lookup by DOI - PDF Agent citation verification (mode "lookup 1 paper")."""
    async with httpx.AsyncClient() as client:
        data = await _get_single(client, f"DOI:{doi}")
    return _to_paper(data) if data and data.get("paperId") else None


async def lookup_by_arxiv_id(arxiv_id: str) -> Paper | None:
    """Single-paper lookup by arXiv id via Semantic Scholar's id-resolution endpoint."""
    async with httpx.AsyncClient() as client:
        data = await _get_single(client, f"ARXIV:{arxiv_id}")
    return _to_paper(data) if data and data.get("paperId") else None


async def get_references(paper_id: str, limit: int = 100) -> list[dict]:
    """Fetch references (backward snowball) with full snowball fields."""
    async with httpx.AsyncClient() as client:
        data = await _get(
            client, f"{BASE_URL}/paper/{paper_id}/references", {"fields": SNOWBALL_FIELDS, "limit": limit}
        )
    return [
        {
            "paper": _to_paper(r["citedPaper"]),
            "isInfluential": bool(r.get("isInfluential")),
            "intents": r.get("intents") or [],
        }
        for r in (data.get("data") or [])
        if r.get("citedPaper") and r["citedPaper"].get("paperId")
    ]


async def get_citations(paper_id: str, limit: int = 100) -> list[dict]:
    """Fetch citing papers (forward snowball) with full snowball fields."""
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE_URL}/paper/{paper_id}/citations", {"fields": SNOWBALL_FIELDS, "limit": limit})
    return [
        {
            "paper": _to_paper(r["citingPaper"]),
            "isInfluential": bool(r.get("isInfluential")),
            "intents": r.get("intents") or [],
        }
        for r in (data.get("data") or [])
        if r.get("citingPaper") and r["citingPaper"].get("paperId")
    ]


async def get_embeddings_batch(paper_ids: list[str]) -> dict[str, list[float]]:
    """Fetch SPECTER v2 via POST /paper/batch (correct batch endpoint, max 500 ids/call).

    Response format: [{"paperId": "...", "embedding": {"model": "...", "vector": [...]}} | null]
    """
    result: dict[str, list[float]] = {}
    max_retries = 6  # embeddings feed clustering/themes/claims — worth waiting longer than a plain search call
    async with httpx.AsyncClient() as client:
        for i in range(0, len(paper_ids), 500):
            batch = paper_ids[i : i + 500]
            for attempt in range(max_retries):
                try:
                    await s2_acquire()
                    resp = await client.post(
                        f"{BASE_URL}/paper/batch",
                        params={"fields": "embedding.specter_v2"},
                        json={"ids": batch},
                        headers=_headers(),
                        timeout=60,
                    )
                    resp.raise_for_status()
                    for item in resp.json():
                        if not isinstance(item, dict):
                            continue
                        pid = item.get("paperId") or ""
                        emb_obj = item.get("embedding")
                        if pid and emb_obj and isinstance(emb_obj, dict):
                            vec = emb_obj.get("vector")
                            if vec:
                                result[pid] = vec
                    break
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429 and attempt < max_retries - 1:
                        # capped backoff: 1,2,4,8,16s — long enough to ride out a short-lived
                        # S2 burst limit without stalling the whole pipeline for minutes
                        await asyncio.sleep(min(2**attempt, 16))
                        continue
                    logging.warning("SPECTER v2 batch failed (chunk %d): %s", i, exc)
                    break
                except Exception as exc:
                    logging.warning("SPECTER v2 batch failed (chunk %d): %s", i, exc)
                    break
    return result


async def search_snippet(claim_text: str, paper_id: str | None = None) -> str | None:
    """Fetch full-text snippet for claim verification."""
    params: dict = {"query": claim_text, "limit": 1}
    if paper_id:
        params["paperId"] = paper_id
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE_URL}/snippet/search", params)
    snippets = data.get("data") or []
    if snippets:
        return snippets[0].get("snippet", {}).get("text")
    return None


def _to_paper(raw: dict) -> Paper:
    authors = [a["name"] for a in (raw.get("authors") or []) if a and a.get("name")]
    pdf_info = raw.get("openAccessPdf") or {}
    venue = (
        (raw.get("publicationVenue") or {}).get("name")
        or (raw.get("journal") or {}).get("name")
        or raw.get("venue")
        or None
    )
    return Paper(
        paperId=raw.get("paperId") or "",
        title=raw.get("title") or "",
        abstract=raw.get("abstract"),
        year=raw.get("year"),
        citationCount=raw.get("citationCount"),
        authors=authors,
        url=raw.get("url"),
        openAccessPdf=pdf_info.get("url"),
        openAccessPdfStatus=pdf_info.get("status"),
        externalIds=raw.get("externalIds") or {},
        source="semantic_scholar",
        venue=venue,
    )
