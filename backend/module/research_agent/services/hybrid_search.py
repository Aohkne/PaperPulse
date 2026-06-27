"""Hybrid search: Semantic (MMR over SPECTER embeddings) + BM25 keyword, merged via RRF.

Graceful degradation:
  - `papers` provided (fast path, in-memory corpus with `.embedding` set):
    pre-filter `fetch_k` candidates by cosine vs query, then greedy MMR for
    diversity (SPEC 2.0 lambda=0.5, fetch_k=50, k=10).
  - `papers` omitted: falls back to ChromaDB top-k cosine (no MMR re-rank,
    since candidate vectors aren't returned by query_by_vector).
  - Embedding endpoint unavailable: BM25-only ranking so the pipeline continues.
"""

import logging

from rank_bm25 import BM25Okapi

from backend.config import get_settings
from backend.module.research_agent.services.embedding import embed_text
from backend.module.research_agent.services.mmr import mmr_select
from backend.module.research_agent.services.vector_store import query_by_vector
from backend.shared.models.paper import Paper

_RRF_K = 60


def _bm25_rank(corpus: list[dict], query: str, top_k: int) -> list[tuple[str, float]]:
    """BM25 over title + abstract, returns (paperId, score) pairs."""
    tokenized = [(m["title"] + " " + m.get("abstract", "")).lower().split() for m in corpus]
    if not tokenized:
        return []
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(zip([m["paperId"] for m in corpus], scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


def _rrf_merge(semantic_ids: list[str], bm25_ids: list[str]) -> list[str]:
    """Reciprocal Rank Fusion — merged ranked list of paper IDs."""
    scores: dict[str, float] = {}
    for rank, pid in enumerate(semantic_ids):
        scores[pid] = scores.get(pid, 0) + 1 / (_RRF_K + rank + 1)
    for rank, pid in enumerate(bm25_ids):
        scores[pid] = scores.get(pid, 0) + 1 / (_RRF_K + rank + 1)
    return sorted(scores, key=lambda pid: scores[pid], reverse=True)


async def hybrid_search(
    query: str, corpus: list[dict], top_k: int = 10, papers: list[Paper] | None = None
) -> list[str]:
    """Return top-k paper IDs via hybrid semantic (MMR) + BM25 search.

    Args:
        papers: in-memory Paper objects with `.embedding` populated. When given,
            the semantic leg runs MMR locally instead of plain ChromaDB top-k.
    """
    settings = get_settings()
    semantic_ids: list[str] = []
    query_vec = await embed_text(query)

    if query_vec and papers:
        # Same dimension guard as outline_generator.generate_outline — skip
        # papers whose embedding model doesn't match the query vector's
        # dimension instead of feeding mismatched vectors into MMR.
        embedded = [p for p in papers if p.embedding and len(p.embedding) == len(query_vec)]
        if embedded:
            candidates = [(p.paper_id, p.embedding) for p in embedded]
            semantic_ids = mmr_select(
                query_vec,
                candidates,
                k=top_k,
                lambda_mult=settings.mmr_lambda,
                fetch_k=settings.mmr_prefetch_theme,
            )
    elif query_vec:
        try:
            semantic_results = await query_by_vector(query_vec, top_k=top_k * 2)
            semantic_ids = [r["metadata"]["paperId"] for r in semantic_results]
        except Exception as exc:
            logging.warning("hybrid_search vector query failed: %s", exc)
    else:
        logging.info("hybrid_search: embedding unavailable — BM25 only")

    # BM25 path (always runs)
    bm25_results = _bm25_rank(corpus, query, top_k=top_k * 2)
    bm25_ids = [pid for pid, _ in bm25_results]

    if not semantic_ids:
        return bm25_ids[:top_k]

    merged = _rrf_merge(semantic_ids, bm25_ids)
    return merged[:top_k]
