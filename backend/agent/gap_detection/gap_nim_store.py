"""gap_nim_store.py — ChromaDB collection cho NVIDIA NIM embeddings (dim = 4096).

Dùng cho:
  - HyDE query vector: ``embed_text(hyde_abstract)`` → query papers trong NIM space
  - False-gap query (P2-08): ``embed_text(gap_statement)`` vs background corpus NIM vectors
  - Paper upsert: ``embed_text(paper.abstract)`` → NIM vector

KHÔNG dùng cho SPECTER2 paper-paper cosine (→ ``gap_specter_store.py``, 768d).
KHÔNG đụng ``services/vector_store.py``.

Isolation guarantee: client riêng, collection riêng "gap_papers_nim". Không cross-query
giữa NIM store và SPECTER2 store → không có dim-mismatch.
"""

from __future__ import annotations

import logging

import chromadb

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "gap_papers_nim"
_NIM_DIM = 4096  # NVIDIA nv-embed-v1 output dimension

# Module-level singleton (in-memory, process-scoped).
_client: chromadb.EphemeralClient | None = None
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    """Lazy-create the NIM ChromaDB collection (EphemeralClient, cosine, 4096d)."""
    global _client, _collection
    if _client is None:
        _client = chromadb.EphemeralClient()
    if _collection is None:
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "dim": _NIM_DIM},
        )
    return _collection


def get_nim_collection() -> chromadb.Collection:
    """Public alias — returns the 4096-dim cosine collection, creating if absent."""
    return _get_collection()


def upsert_papers_nim(papers_with_vectors: list[dict]) -> int:
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

    col = _get_collection()
    ids = [p["paper_id"] for p in valid]
    vectors = [p["vector"] for p in valid]
    metas = [
        {"title": str(p.get("title") or ""), "year": int(p.get("year") or 0)}
        for p in valid
    ]

    try:
        col.upsert(ids=ids, embeddings=vectors, metadatas=metas)
        logger.debug("gap_nim_store: upserted %d NIM vectors", len(ids))
        return len(ids)
    except Exception:
        logger.warning("gap_nim_store: upsert failed", exc_info=True)
        return 0


def query_by_vector_nim(vector: list[float], top_k: int) -> list[str]:
    """Query nearest neighbours by cosine similarity in NIM space.

    Args:
        vector: 4096-dim NIM query embedding.
        top_k:  Maximum number of results to return.

    Returns:
        List of ``paper_id`` strings ordered by descending cosine similarity.
        Returns ``[]`` when the collection is empty or the query fails.
    """
    col = _get_collection()
    count = col.count()
    if count == 0:
        logger.debug("gap_nim_store.query_by_vector_nim: collection empty — returning []")
        return []

    n = min(top_k, count)
    try:
        results = col.query(query_embeddings=[vector], n_results=n)
        return list(results.get("ids", [[]])[0])
    except Exception:
        logger.warning("gap_nim_store: query_by_vector_nim failed", exc_info=True)
        return []


def query_with_distances_nim(vector: list[float], top_k: int) -> list[tuple[str, float]]:
    """Query nearest neighbours and return (paper_id, distance) pairs.

    Used by false-gap threshold check (P2-08): high cosine distance → gap may
    already be covered.

    Args:
        vector: 4096-dim NIM query embedding.
        top_k:  Maximum number of results to return.

    Returns:
        List of ``(paper_id, distance)`` tuples (ascending distance = closer).
        Returns ``[]`` on empty collection or failure.
    """
    col = _get_collection()
    count = col.count()
    if count == 0:
        return []

    n = min(top_k, count)
    try:
        results = col.query(
            query_embeddings=[vector],
            n_results=n,
            include=["distances"],
        )
        ids = results.get("ids", [[]])[0]
        dists = results.get("distances", [[]])[0]
        return list(zip(ids, dists))
    except Exception:
        logger.warning("gap_nim_store: query_with_distances_nim failed", exc_info=True)
        return []


def clear_nim_collection() -> None:
    """Reset the in-memory NIM collection (for tests and session refresh)."""
    global _client, _collection
    if _client is not None:
        try:
            _client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass
    _collection = None
    logger.debug("gap_nim_store: NIM collection cleared")
