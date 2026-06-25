"""gap_nim_store.py — Supabase pgvector store for NVIDIA NIM embeddings (dim = 4096).

Dùng cho:
  - HyDE query vector: ``embed_text(hyde_abstract)`` → query papers trong NIM space
  - False-gap query (P2-08): ``embed_text(gap_statement)`` vs background corpus NIM vectors
  - Paper upsert: ``embed_text(paper.abstract)`` → NIM vector

KHÔNG dùng cho SPECTER2 paper-paper cosine (→ ``gap_specter_store.py``, 768d).
KHÔNG đụng ``services/vector_store.py`` (research_agent's pgvector store, khác bảng).

Backed by Supabase Postgres (table ``gap_nim_embeddings``, supabase/schema.sql §17)
via PostgREST/RPC — cùng convention với research_agent/services/vector_store.py.
Migrated from ChromaDB's EphemeralClient (in-memory, process-scoped); semantics
giữ nguyên 1:1 — ``clear_nim_collection()`` vẫn được gọi mỗi lần ``retrieval.rank()``
chạy để reset candidate pool, chỉ đổi storage backend.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_NIM_DIM = 4096  # NVIDIA nv-embed-v1 output dimension
_UPSERT_CONCURRENCY = 10


def _rest_headers() -> dict:
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def upsert_papers_nim(papers_with_vectors: list[dict]) -> int:
    """Upsert NIM-embedded paper vectors into the gap NIM store.

    Args:
        papers_with_vectors: List of dicts with keys:
            - ``paper_id`` (str)   — Semantic Scholar paper ID
            - ``vector``   (list[float])  — 4096-dim NIM embedding
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
    url = f"{settings.supabase_url}/rest/v1/rpc/upsert_gap_nim_embedding"
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
                logger.warning("gap_nim_store: upsert failed for paper_id=%s", p["paper_id"], exc_info=True)
                return False

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_upsert_one(client, p) for p in valid])
    n = sum(results)
    logger.debug("gap_nim_store: upserted %d/%d NIM vectors", n, len(valid))
    return n


async def _match(vector: list[float], top_k: int) -> list[dict]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/match_gap_nim_papers",
                json={"query_embedding": vector, "match_count": top_k},
                headers=_rest_headers(),
                timeout=30.0,
            )
        res.raise_for_status()
        return res.json()
    except Exception:
        logger.warning("gap_nim_store: query failed", exc_info=True)
        return []


async def query_by_vector_nim(vector: list[float], top_k: int) -> list[str]:
    """Query nearest neighbours by cosine similarity in NIM space.

    Args:
        vector: 4096-dim NIM query embedding.
        top_k:  Maximum number of results to return.

    Returns:
        List of ``paper_id`` strings ordered by ascending cosine distance
        (closest first). Returns ``[]`` when the store is empty or the query fails.
    """
    rows = await _match(vector, top_k)
    return [r["paper_id"] for r in rows]


async def query_with_distances_nim(vector: list[float], top_k: int) -> list[tuple[str, float]]:
    """Query nearest neighbours and return (paper_id, distance) pairs.

    Used by false-gap threshold check (P2-08): high cosine distance → gap may
    already be covered.

    Args:
        vector: 4096-dim NIM query embedding.
        top_k:  Maximum number of results to return.

    Returns:
        List of ``(paper_id, distance)`` tuples (ascending distance = closer).
        Returns ``[]`` on empty store or failure.
    """
    rows = await _match(vector, top_k)
    return [(r["paper_id"], r["distance"]) for r in rows]


async def clear_nim_collection() -> None:
    """Reset the NIM store (for tests and session refresh)."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/clear_gap_nim_embeddings",
                json={},
                headers=_rest_headers(),
                timeout=15.0,
            )
        res.raise_for_status()
        logger.debug("gap_nim_store: NIM store cleared")
    except Exception:
        logger.warning("gap_nim_store: clear_nim_collection failed", exc_info=True)
