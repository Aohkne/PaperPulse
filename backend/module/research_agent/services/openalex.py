"""OpenAlex REST API wrapper — multi-source search returning Paper objects.

No API key needed. Use openalex_email in settings for the polite pool
(higher rate limits via User-Agent header).

abstract_inverted_index reconstruction: OpenAlex stores abstracts as
{word: [position_1, position_2, ...]} — we sort by position and join.
"""

from __future__ import annotations

import logging

import httpx

from backend.config import get_settings
from backend.shared.models.paper import Paper

_BASE = "https://api.openalex.org"
_SELECT = "id,title,abstract_inverted_index,publication_year,cited_by_count,authorships,doi,best_oa_location,ids"


def _reconstruct_abstract(inv_index: dict | None) -> str | None:
    if not inv_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, indices in inv_index.items():
        for pos in indices:
            positions.append((pos, word))
    positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in positions)


def _to_paper(raw: dict) -> Paper:
    title = raw.get("title") or ""
    abstract = _reconstruct_abstract(raw.get("abstract_inverted_index"))
    year = raw.get("publication_year")
    citation_count = raw.get("cited_by_count")

    authors: list[str] = []
    for authorship in raw.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)

    doi = raw.get("doi") or ""
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/") :]

    external_ids: dict[str, str] = {}
    if doi:
        external_ids["DOI"] = doi

    ids = raw.get("ids") or {}
    arxiv_raw = ids.get("arxiv") or ""
    if arxiv_raw.startswith("https://arxiv.org/abs/"):
        arxiv_raw = arxiv_raw[len("https://arxiv.org/abs/") :]
    if arxiv_raw:
        external_ids["ArXiv"] = arxiv_raw

    oa_location = raw.get("best_oa_location") or {}
    oa_url: str | None = oa_location.get("pdf_url") or oa_location.get("landing_page_url")
    oa_status: str | None = "GOLD" if oa_location.get("is_oa") else None

    oa_id = raw.get("id") or ""  # "https://openalex.org/W1234567890"
    paper_id = doi or oa_id.replace("https://openalex.org/", "OA_")

    return Paper(
        paperId=paper_id,
        title=title,
        abstract=abstract,
        year=year,
        citationCount=citation_count,
        authors=authors,
        url=oa_id or None,
        openAccessPdf=oa_url,
        openAccessPdfStatus=oa_status,
        externalIds=external_ids,
        source="openalex",
    )


async def search_openalex(query: str, limit: int = 100) -> list[Paper]:
    """Search OpenAlex by keyword, return up to *limit* Paper objects."""
    settings = get_settings()
    email = getattr(settings, "openalex_email", "")

    params: dict = {
        "search": query,
        "per-page": min(limit, 200),
        "select": _SELECT,
    }
    if email:
        params["mailto"] = email

    ua = f"PaperPulse/2.0 (mailto:{email})" if email else "PaperPulse/2.0"
    headers = {"User-Agent": ua}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{_BASE}/works", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return [_to_paper(r) for r in data.get("results", [])]
    except Exception as exc:
        logging.warning("OpenAlex search failed: %s", exc)
        return []
