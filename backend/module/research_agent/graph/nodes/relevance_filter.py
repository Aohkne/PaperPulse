"""Step ①bis — Relevance filter (hybrid BM25 ∥ semantic → RRF).

A broad multi-source, multi-sub-query search pulls in papers from adjacent
fields (a "diffusion drafter" topic ends up with DNA-methylation / ophthalmology
/ fraud papers). This node scores every deduped paper for relevance to the
query and keeps only the top-K before clustering — so themes form from an
on-topic corpus, not a tidy clustering of off-topic noise.

Hybrid, not cascade: BM25 (lexical, exact-term) and semantic (NIM embeddings,
catches paraphrases) both rank the WHOLE corpus, then Reciprocal Rank Fusion
combines them — neither signal caps the other's recall. RRF ranks by position,
so no brittle absolute cosine threshold is needed. SPECTER can't embed a free
query, so the semantic side uses NIM (nv-embed-v1); this is separate from the
SPECTER paper↔paper embeddings used for clustering in Step ②.
"""

from __future__ import annotations

import logging
import re

from backend.config import get_settings
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.services.embedding import embed_text, embed_texts_batch
from backend.shared.models.paper import Paper

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tok(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _bm25_order(docs: list[str], query_text: str) -> list[int] | None:
    """Return paper indices ranked best-first by BM25, or None if unavailable."""
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        log.warning("rank-bm25 not installed — skipping lexical relevance signal")
        return None
    q = _tok(query_text)
    if not q:
        return None
    bm25 = BM25Okapi([_tok(d) for d in docs])
    scores = bm25.get_scores(q)
    return sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)


async def _semantic_order(query: str, docs: list[str]) -> list[int] | None:
    """Return paper indices ranked best-first by cosine(query, doc) via NIM."""
    qv = await embed_text(query, input_type="query")
    if not qv:
        return None  # NIM unavailable → RRF falls back to BM25 only

    import numpy as np

    vecs = await embed_texts_batch([d[:2000] for d in docs], input_type="passage")
    q = np.asarray(qv, dtype=float)
    qn = np.linalg.norm(q) + 1e-9
    sims = []
    for v in vecs:
        if v:
            vv = np.asarray(v, dtype=float)
            sims.append(float(q @ vv / (qn * (np.linalg.norm(vv) + 1e-9))))
        else:
            sims.append(-1.0)
    return sorted(range(len(docs)), key=lambda i: sims[i], reverse=True)


def _rrf(orderings: list[list[int] | None], n: int, k: int) -> list[int]:
    """Reciprocal Rank Fusion over the given rankings (best-first index lists)."""
    score = [0.0] * n
    for order in orderings:
        if not order:
            continue
        for rank, idx in enumerate(order):
            score[idx] += 1.0 / (k + rank + 1)
    return sorted(range(n), key=lambda i: score[i], reverse=True)


async def relevance_filter_node(state: ResearchState) -> dict:
    settings = get_settings()
    papers: list[Paper] = list(state.get("papers", []))
    refined_query = state.get("refined_query") or state.get("query", "")
    core_terms = state.get("core_terms") or {}

    # BM25 query = all core_terms (required synonyms + context), falling back to
    # the refined query if the LLM produced none.
    terms: list[str] = []
    for grp in core_terms.get("required", []):
        terms += grp
    terms += core_terms.get("context", [])
    query_text = " ".join(terms) or refined_query

    # Nothing meaningful to rank on, or already under budget → passthrough.
    if not papers or (not query_text.strip()):
        return {"papers": papers, "low_relevance": len(papers) < settings.relevance_min}

    await narrate_step(f"filtering {len(papers)} papers by relevance to {refined_query}")

    docs = [f"{p.title or ''} {p.abstract or ''}".strip() for p in papers]
    bm25_ord = _bm25_order(docs, query_text)
    try:
        sem_ord = await _semantic_order(refined_query, docs)
    except Exception as exc:
        log.warning("semantic relevance ranking failed (%s) — using BM25 only", exc)
        sem_ord = None

    if bm25_ord is None and sem_ord is None:
        # No usable signal — keep the corpus as-is (capped) rather than dropping blindly.
        kept = papers[: settings.relevance_top_k]
        return {"papers": kept, "low_relevance": len(kept) < settings.relevance_min}

    fused = _rrf([bm25_ord, sem_ord], n=len(papers), k=settings.relevance_rrf_k)
    kept = [papers[i] for i in fused[: settings.relevance_top_k]]
    low = len(kept) < settings.relevance_min
    log.info("relevance_filter: %d → %d papers (low_relevance=%s)", len(papers), len(kept), low)
    return {"papers": kept, "low_relevance": low}
