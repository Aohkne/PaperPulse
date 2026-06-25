"""gap_specter_store.py — Isolated ChromaDB store for gap-detection SPECTER2 vectors (TIP-P2-06).

Maintains a dedicated in-memory ChromaDB collection ``gap_papers_specter``
(768-dim, cosine similarity) used exclusively by the gap-detection module.

ISOLATION GUARANTEE:
    This module is the ONLY place in ``gap_detection`` that touches ChromaDB.
    It does NOT import or use ``services/vector_store.py`` — the existing
    research-pipeline store.  The collection lives in a separate in-memory
    client instance scoped to the gap module.

ChromaDB version: 1.5.9 (EphemeralClient / in-memory).

Usage pattern:
    1. ``upsert_papers(papers_with_vectors)`` — populate from SPECTER2 fetch.
    2. ``query_by_vector(hyde_vec, top_k)``   — semantic nearest-neighbour lookup.
    3. ``clear_collection()``                 — for tests / session reset.
"""

from __future__ import annotations

import logging

import chromadb

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "gap_papers_specter"
_DIM = 768  # SPECTER2 embedding dimensionality

# Module-level singleton client + collection (in-memory, process-scoped).
# Using EphemeralClient (in-memory) so we don't need a persistent directory
# and avoid conflicts with any server-mode ChromaDB used elsewhere.
_client: chromadb.EphemeralClient | None = None
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    """Return (and lazily create) the gap-papers ChromaDB collection."""
    global _client, _collection
    if _client is None:
        _client = chromadb.EphemeralClient()
    if _collection is None:
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "dim": _DIM},
        )
    return _collection


def get_specter_collection() -> chromadb.Collection:
    """Public alias — returns the 768-dim cosine collection, creating if absent."""
    return _get_collection()


def upsert_papers(papers_with_vectors: list[dict]) -> int:
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

    col = _get_collection()
    ids = [p["paper_id"] for p in valid]
    vectors = [p["vector"] for p in valid]
    metas = [
        {"title": str(p.get("title") or ""), "year": int(p.get("year") or 0)}
        for p in valid
    ]

    try:
        col.upsert(ids=ids, embeddings=vectors, metadatas=metas)
        logger.debug("gap_specter_store: upserted %d vectors", len(ids))
        return len(ids)
    except Exception:
        logger.warning("gap_specter_store: upsert failed", exc_info=True)
        return 0


def query_by_vector(vector: list[float], top_k: int) -> list[str]:
    """Query nearest neighbours by cosine similarity.

    Args:
        vector: 768-dim query embedding (typically from HyDE).
        top_k:  Maximum number of results to return.

    Returns:
        List of ``paper_id`` strings ordered by descending cosine similarity.
        Returns ``[]`` when the collection is empty or the query fails.
    """
    col = _get_collection()
    count = col.count()
    if count == 0:
        logger.debug("gap_specter_store.query_by_vector: collection is empty — returning []")
        return []

    n = min(top_k, count)
    try:
        results = col.query(query_embeddings=[vector], n_results=n)
        ids = results.get("ids", [[]])[0]
        return list(ids)
    except Exception:
        logger.warning("gap_specter_store: query_by_vector failed", exc_info=True)
        return []


def clear_collection() -> None:
    """Reset the in-memory collection (for tests and session refresh)."""
    global _client, _collection
    if _client is not None:
        try:
            _client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass
    _collection = None
    logger.debug("gap_specter_store: collection cleared")
