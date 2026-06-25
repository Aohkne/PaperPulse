"""ChromaDB operations — upsert, query, and retrieve papers."""

from __future__ import annotations

import logging
from collections import Counter

import chromadb

from backend.config import get_settings
from backend.shared.models.paper import Paper
from backend.shared.models.review import LiteratureReview

_client: chromadb.PersistentClient | chromadb.HttpClient | None = None
_collection = None
_COLLECTION_NAME = "papers"

# In-memory store for the assembled literature review (single session)
_current_review: LiteratureReview | None = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        settings = get_settings()
        if settings.chroma_mode == "http":
            # Talks to a chroma server (e.g. the official `chromadb/chroma`
            # Docker image) — lets the backend run natively without installing
            # ChromaDB's own embedded storage deps.
            _client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        else:
            _client = chromadb.PersistentClient(path=settings.chroma_persist_path)
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


async def upsert_papers(papers: list[Paper]) -> int:
    """Insert or update papers in ChromaDB. Returns count of stored papers.

    Multi-source papers (SPEC 2.0) may carry embeddings from different
    models — SPECTER v2 (768-dim, from the S2 batch API) for S2-sourced
    papers vs. the local/API fallback model (different dim) for
    OpenAlex/arXiv/PubMed papers without one. ChromaDB requires every vector
    in a collection to share one dimension, so a mixed batch would otherwise
    crash the *entire* upsert. We only store papers matching the collection's
    established dimension and skip (with a warning) the rest, rather than
    losing the whole batch.
    """
    col = _get_collection()
    to_store = [p for p in papers if p.embedding]
    if not to_store:
        return 0

    target_dim = _collection_dim(col)
    if target_dim is None:
        # Empty collection — adopt whichever dimension is most common in this batch.
        target_dim = Counter(len(p.embedding) for p in to_store).most_common(1)[0][0]

    matching = [p for p in to_store if len(p.embedding) == target_dim]
    skipped = len(to_store) - len(matching)
    if skipped:
        logging.warning(
            "upsert_papers: skipped %d/%d papers with embedding dim != %d "
            "(mixed embedding models — not comparable in the same ChromaDB collection)",
            skipped, len(to_store), target_dim,
        )
    if not matching:
        return 0

    col.upsert(
        ids=[p.paper_id for p in matching],
        embeddings=[p.embedding for p in matching],
        metadatas=[
            {
                "paperId": p.paper_id,
                "title": p.title or "",
                "year": p.year or 0,
                "citationCount": p.citation_count or 0,
                "abstract": (p.abstract or "")[:1000],
            }
            for p in matching
        ],
    )
    return len(matching)


def _collection_dim(col) -> int | None:
    """Return the embedding dimension already stored in `col`, or None if empty."""
    if col.count() == 0:
        return None
    peeked = col.peek(limit=1)
    vectors = peeked.get("embeddings")
    if vectors is not None and len(vectors) > 0:
        return len(vectors[0])
    return None


async def query_by_vector(embedding: list[float], top_k: int = 10) -> list[dict]:
    """Return top-k papers by cosine similarity."""
    col = _get_collection()
    results = col.query(query_embeddings=[embedding], n_results=top_k, include=["metadatas", "distances"])
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    return [{"metadata": m, "score": 1 - d} for m, d in zip(metadatas, distances)]


async def get_papers_by_ids(paper_ids: list[str]) -> list[Paper]:
    """Retrieve Paper objects stored in ChromaDB by their IDs."""
    col = _get_collection()
    results = col.get(ids=paper_ids, include=["metadatas"])
    papers = []
    for meta in results.get("metadatas", []):
        papers.append(
            Paper(
                paperId=meta["paperId"],
                title=meta.get("title", ""),
                abstract=meta.get("abstract"),
                year=meta.get("year"),
                citationCount=meta.get("citationCount"),
            )
        )
    return papers


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
    col = _get_collection()
    results = col.get(include=["metadatas"])
    return results.get("metadatas") or []
