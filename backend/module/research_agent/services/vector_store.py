"""Supabase pgvector operations — upsert, query, and retrieve papers.

Replaces the embedded ChromaDB "papers" collection (Cloud Run wipes local
disk on scale-to-zero, so the vector index must live in Supabase). Same
single-shared-keyspace semantics as before — upsert by paper_id, not
session-scoped — this migration only swaps the storage backend.

Uses raw httpx → PostgREST/RPC (not the `supabase-py` client) to match the
pattern already established in backend/api/admin.py — supabase-py fails on
the `sb_publishable_...` key format (see WORKLOG.md), and PostgREST can't
cast a JSON array directly to `vector` on a plain table POST anyway, so
writes/reads always go through the RPC functions defined in
supabase/schema.sql (§14).
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.shared.models.paper import Paper
from backend.shared.models.review import LiteratureReview

_TARGET_DIM = 768  # SPECTER v2 (S2 batch API) — fixed by the `vector(768)` column, see schema.sql §14
_UPSERT_CONCURRENCY = 10

# In-memory store for the assembled literature review (single session)
_current_review: LiteratureReview | None = None


def _rest_headers() -> dict:
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def upsert_papers(papers: list[Paper]) -> int:
    """Insert or update papers in Supabase pgvector. Returns count of stored papers.

    Multi-source papers (SPEC 2.0) may carry embeddings from different
    models — SPECTER v2 (768-dim, from the S2 batch API) for S2-sourced
    papers vs. the local/API fallback model (different dim) for
    OpenAlex/arXiv/PubMed papers without one. The `paper_embeddings` table
    has a fixed `vector(768)` column, so a mixed batch would otherwise fail
    on insert. We only store papers matching that dimension and skip (with a
    warning) the rest, rather than losing the whole batch.
    """
    to_store = [p for p in papers if p.embedding]
    if not to_store:
        return 0

    matching = [p for p in to_store if len(p.embedding) == _TARGET_DIM]
    skipped = len(to_store) - len(matching)
    if skipped:
        logging.warning(
            "upsert_papers: skipped %d/%d papers with embedding dim != %d "
            "(mixed embedding models — not comparable in the same pgvector column)",
            skipped,
            len(to_store),
            _TARGET_DIM,
        )
    if not matching:
        return 0

    settings = get_settings()
    headers = _rest_headers()
    url = f"{settings.supabase_url}/rest/v1/rpc/upsert_paper_embedding"
    sem = asyncio.Semaphore(_UPSERT_CONCURRENCY)

    async def _upsert_one(client: httpx.AsyncClient, p: Paper) -> None:
        payload = {
            "p_paper_id": p.paper_id,
            "p_embedding": p.embedding,
            "p_title": p.title or "",
            "p_year": p.year or 0,
            "p_citation_count": p.citation_count or 0,
            "p_abstract": (p.abstract or "")[:1000],
        }
        async with sem:
            res = await client.post(url, json=payload, headers=headers, timeout=30.0)
        res.raise_for_status()

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[_upsert_one(client, p) for p in matching])

    return len(matching)


async def query_by_vector(embedding: list[float], top_k: int = 10) -> list[dict]:
    """Return top-k papers by cosine similarity."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{settings.supabase_url}/rest/v1/rpc/match_papers",
            json={"query_embedding": embedding, "match_count": top_k},
            headers=_rest_headers(),
            timeout=30.0,
        )
    res.raise_for_status()
    rows = res.json()
    return [
        {
            "metadata": {
                "paperId": r["paper_id"],
                "title": r.get("title", ""),
                "year": r.get("year") or 0,
                "citationCount": r.get("citation_count") or 0,
                "abstract": r.get("abstract") or "",
            },
            "score": r["similarity"],
        }
        for r in rows
    ]


async def get_papers_by_ids(paper_ids: list[str]) -> list[Paper]:
    """Retrieve Paper objects stored in Supabase by their IDs."""
    if not paper_ids:
        return []
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{settings.supabase_url}/rest/v1/paper_embeddings",
            params={
                "paper_id": f"in.({','.join(paper_ids)})",
                "select": "paper_id,title,year,citation_count,abstract",
            },
            headers=_rest_headers(),
            timeout=15.0,
        )
    res.raise_for_status()
    return [
        Paper(
            paperId=row["paper_id"],
            title=row.get("title", ""),
            abstract=row.get("abstract"),
            year=row.get("year"),
            citationCount=row.get("citation_count"),
        )
        for row in res.json()
    ]


async def get_full_review() -> LiteratureReview:
    """Return the assembled literature review for export."""
    if _current_review is None:
        raise ValueError("No literature review has been generated yet.")
    return _current_review


def set_full_review(review: LiteratureReview) -> None:
    global _current_review
    _current_review = review


async def get_all_papers_metadata() -> list[dict]:
    """Return all stored paper metadata for BM25 corpus."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{settings.supabase_url}/rest/v1/paper_embeddings",
            params={"select": "paper_id,title,year,citation_count,abstract"},
            headers=_rest_headers(),
            timeout=15.0,
        )
    res.raise_for_status()
    return [
        {
            "paperId": row["paper_id"],
            "title": row.get("title", ""),
            "year": row.get("year") or 0,
            "citationCount": row.get("citation_count") or 0,
            "abstract": row.get("abstract") or "",
        }
        for row in res.json()
    ]
