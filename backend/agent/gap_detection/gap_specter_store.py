"""gap_specter_store.py — Supabase pgvector store for gap-detection SPECTER2 vectors (TIP-P2-06).

Maintains a dedicated table ``gap_specter_embeddings`` (768-dim, cosine
distance) used exclusively by the gap-detection module.

ISOLATION GUARANTEE:
    This module is the ONLY place in ``gap_detection`` that touches this
    table. It does NOT import or use ``services/vector_store.py`` — the
    existing research-pipeline store (different table, different dim).

Backed by Supabase Postgres (table ``gap_specter_embeddings``,
supabase/schema.sql §17) via PostgREST/RPC — cùng convention với
research_agent/services/vector_store.py. Migrated from ChromaDB's
EphemeralClient (in-memory, process-scoped); semantics giữ nguyên 1:1 —
``clear_collection()`` vẫn được gọi mỗi lần ``retrieval.rank()`` chạy để
reset candidate pool, chỉ đổi storage backend.

Usage pattern:
    1. ``upsert_papers(papers_with_vectors)`` — populate from SPECTER2 fetch.
    2. ``query_by_vector(hyde_vec, top_k)``   — semantic nearest-neighbour lookup.
    3. ``get_vectors_by_ids(paper_ids)``      — fetch specific vectors (coherence_check.py).
    4. ``clear_collection()``                 — for tests / session reset.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_DIM = 768  # SPECTER2 embedding dimensionality
_UPSERT_CONCURRENCY = 10


def _rest_headers() -> dict:
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def upsert_papers(papers_with_vectors: list[dict]) -> int:
    """Upsert paper vectors into the gap SPECTER2 store.

    Args:
        papers_with_vectors: List of dicts with keys:
            - ``paper_id`` (str)  — Semantic Scholar paper ID
            - ``vector``   (list[float])  — 768-dim SPECTER2 embedding
            - ``title``    (str, optional)
            - ``year``     (int, optional)

    Returns:
        Number of papers actually upserted (those with a valid vector).
    """
    valid = [p for p in papers_with_vectors if p.get("paper_id") and p.get("vector")]
    if not valid:
        return 0

    settings = get_settings()
    headers = _rest_headers()
    url = f"{settings.supabase_url}/rest/v1/rpc/upsert_gap_specter_embedding"
    sem = asyncio.Semaphore(_UPSERT_CONCURRENCY)

    async def _upsert_one(client: httpx.AsyncClient, p: dict) -> bool:
        payload = {
            "p_paper_id": p["paper_id"],
            "p_embedding": p["vector"],
            "p_title": str(p.get("title") or ""),
            "p_year": int(p.get("year") or 0),
        }
        async with sem:
            try:
                res = await client.post(url, json=payload, headers=headers, timeout=30.0)
                res.raise_for_status()
                return True
            except Exception:
                logger.warning("gap_specter_store: upsert failed for paper_id=%s", p["paper_id"], exc_info=True)
                return False

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_upsert_one(client, p) for p in valid])
    n = sum(results)
    logger.debug("gap_specter_store: upserted %d/%d vectors", n, len(valid))
    return n


async def query_by_vector(vector: list[float], top_k: int) -> list[str]:
    """Query nearest neighbours by cosine similarity.

    Args:
        vector: 768-dim query embedding (typically from HyDE).
        top_k:  Maximum number of results to return.

    Returns:
        List of ``paper_id`` strings ordered by ascending cosine distance
        (closest first). Returns ``[]`` when the store is empty or the query fails.
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/match_gap_specter_papers",
                json={"query_embedding": vector, "match_count": top_k},
                headers=_rest_headers(),
                timeout=30.0,
            )
        res.raise_for_status()
        return [r["paper_id"] for r in res.json()]
    except Exception:
        logger.warning("gap_specter_store: query_by_vector failed", exc_info=True)
        return []


async def get_vectors_by_ids(paper_ids: list[str]) -> dict[str, list[float]]:
    """Fetch stored SPECTER2 vectors for the given paper_ids.

    Used by ``nodes/coherence_check.py`` to compute pairwise similarity —
    replaces the old ``col.get(ids=..., include=["embeddings"])`` ChromaDB call.

    Returns ``{}`` when the store is empty, ids absent, or on any failure —
    callers treat that as "no vectors available, skip check gracefully".
    """
    if not paper_ids:
        return {}
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/get_gap_specter_embeddings_by_ids",
                json={"p_paper_ids": paper_ids},
                headers=_rest_headers(),
                timeout=15.0,
            )
        res.raise_for_status()
        return {row["paper_id"]: row["embedding"] for row in res.json() if row.get("embedding")}
    except Exception:
        logger.debug("gap_specter_store: get_vectors_by_ids failed", exc_info=True)
        return {}


async def clear_collection() -> None:
    """Reset the SPECTER2 store (for tests and session refresh)."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/clear_gap_specter_embeddings",
                json={},
                headers=_rest_headers(),
                timeout=15.0,
            )
        res.raise_for_status()
        logger.debug("gap_specter_store: collection cleared")
    except Exception:
        logger.warning("gap_specter_store: clear_collection failed", exc_info=True)
