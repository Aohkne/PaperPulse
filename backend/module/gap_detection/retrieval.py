"""retrieval.py — Adapter seam: wraps shared retrieval services for gap cold-start.

This is the ONLY file in ``gap_detection`` that may import services.*
retrieval services (``semantic_scholar``, ``snowball``).  Three public async
functions expose the three pipeline stages (A, C, E) to ``orchestrator.py``
and any future caller — keeping the gap module decoupled from service
internals.

Ranking mechanism (``rank()``)
-------------------------------
TIP-P2-06: Hybrid BM25 + HyDE SPECTER2 semantic rerank.

  1. **SPECTER2 fetch** — call ``get_embeddings_batch`` for all paper IDs;
     upsert into ``gap_specter_store`` (isolated 768-dim cosine ChromaDB).
  2. **HyDE vector** — ``generate_hyde_vector`` asks the LLM to write a
     hypothetical abstract for the query, then embeds it via ``embed_text``
     (SPECTER2-compatible endpoint if configured).
  3. **Semantic score** — cosine rank from ``query_by_vector`` (inverted-rank
     proxy: ``1 - rank/N``).
  4. **BM25 composite** (MVP) — term overlap + log-citation + recency.
  5. **Hybrid** — ``SPECTER2_WEIGHT * sem + (1 - SPECTER2_WEIGHT) * bm25``.

Fallback: when ``hyde_vec`` is ``None`` (LLM/embed not configured or failed),
``w_sem=0`` automatically — ranking degrades gracefully to pure BM25.

No network I/O, no embed_text, no ChromaDB access inside the scoring helpers.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime

from backend.module.gap_detection.gap_nim_store import (
    clear_nim_collection,
    query_by_vector_nim,
)
from backend.module.gap_detection.gap_specter_store import (
    clear_collection,
    upsert_papers,
)
from backend.module.gap_detection.hyde import generate_hyde_vector_nim, upsert_paper_to_nim_store
from backend.module.gap_detection.schemas import CanonicalPaper, CorpusRole
from backend.module.gap_detection.services.openalex import openalex_search
from backend.module.gap_detection.services.snowball import run_snowball, select_seeds
from backend.module.gap_detection.settings import (
    get_default_fields_of_study,
    get_nim_upsert_concurrency,
    get_openalex_search_limit,
    get_specter2_weight,
    is_openalex_enabled,
)
from backend.module.gap_detection.source_resolution import RawRecord, resolve_papers
from backend.shared.models.paper import Paper
from backend.shared.services.semantic_scholar import get_embeddings_batch, search_papers

logger = logging.getLogger(__name__)

_CURRENT_YEAR: int = datetime.now().year

# Pre-compiled for speed — matches lowercase alphanumeric tokens.
_TOKEN_RE: re.Pattern[str] = re.compile(r"[a-z0-9]+")

# ── Query cleaning (TIP-P3-03) ────────────────────────────────────────────────

_META_PATTERNS: list[re.Pattern[str]] = [
    # Action verbs: "Tìm ...", "find ...", "search ...", "phát hiện ..."
    # \b prevents matching "search" inside "research"
    re.compile(r"\b(?:tìm|find|search|phát\s+hiện)\s+", re.IGNORECASE),
    # Gap-related phrases — \s* at end so "research gap" (no trailing space) still matches
    re.compile(
        r"\b(?:"
        r"research\s+gaps?(?:\s+(?:in|about|on|for|về))?"
        r"|khoảng\s+trống(?:\s+nghiên\s+cứu)?(?:\s+(?:về|trong|on))?"
        r"|gaps?(?:\s+(?:in|about|on|for|về))?"
        r")\s*",
        re.IGNORECASE,
    ),
    # "literature review (về/on/for)?"
    re.compile(r"\bliterature\s+review(?:\s+(?:về|on|for))?\s*", re.IGNORECASE),
    # Trailing prepositions
    re.compile(r"\s*\b(?:về|in|for|on|about)\s*$", re.IGNORECASE),
]


def clean_query(raw: str) -> str:
    """Strip Vietnamese/English meta-words, keep the real topic. Pure stdlib, no LLM.

    Examples:
        "Tìm research gap về transformer long-context" → "transformer long-context"
        "research gaps in federated learning"          → "federated learning"
        "tìm research gap" (no real topic)             → "tìm research gap" (fallback)
    """
    cleaned = raw.strip()
    for pat in _META_PATTERNS:
        cleaned = pat.sub("", cleaned).strip()
    return cleaned if cleaned else raw


# ── Input validation helper (G10.1 defensive filter) ──────────────────────────


def _valid_papers(papers: list[Paper], stage: str = "") -> list[Paper]:
    """Drop papers with empty/None paper_id or empty title before they reach
    extractor (G10.1 — defensive filter against S2 returning malformed edge data).

    Root cause (CLASS A, baseline): ``services/semantic_scholar.py::_to_paper``
    passes ``paperId=raw.get('paperId', '')`` — empty string when S2 omits paperId.
    ValidationError is raised when paperId=None (caught upstream), but paperId=''
    (empty string) slips through the model and would cause extractor to call
    ``get_paper_detail('')`` → guaranteed 404 → yield loss.

    This filter is the in-zone mitigation; gốc (baseline _to_paper) is CLASS A
    ngoài zone — ESCALATED to Chủ thầu (see report).
    """
    valid = [p for p in papers if p.paper_id and p.title]
    dropped = len(papers) - len(valid)
    if dropped:
        logger.warning(
            "retrieval._valid_papers [%s]: dropped %d paper(s) with empty paper_id or title",
            stage,
            dropped,
        )
    return valid


async def search(query: str, limit: int = 100) -> list[Paper]:
    """Stage A — Keyword search via Semantic Scholar + OpenAlex supplement.

    Runs S2 and OpenAlex searches in parallel when OPENALEX_ENABLED=true; merges
    and deduplicates results via resolve_papers() (DOI → title → S2 paperId).
    OpenAlex timeout/error is non-fatal — pipeline continues with S2-only results.

    Args:
        query: Raw or pre-cleaned topic string.
        limit: Maximum S2 papers; OpenAlex limit is set via OPENALEX_SEARCH_LIMIT env.

    Returns:
        ``list[Paper]`` ordered by S2 internal relevance score (S2 first, then
        OpenAlex-only additions). Deduplication removes double-counted papers.
    """
    cleaned = clean_query(query)
    fields = get_default_fields_of_study()

    tasks: list = [search_papers(cleaned, limit=limit, fields_of_study=fields)]
    tags: list[str] = ["s2"]
    if is_openalex_enabled():
        tasks.append(openalex_search(cleaned, limit=get_openalex_search_limit()))
        tags.append("openalex")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    s2_result = results[0]
    if isinstance(s2_result, BaseException):
        logger.warning("retrieval.search: S2 search failed: %s", s2_result)
        s2_result = []
    s2_papers: list[Paper] = s2_result

    supp_papers: list[Paper] = []
    for tag, result in zip(tags[1:], results[1:]):
        if isinstance(result, BaseException):
            logger.warning("retrieval.search: %s search failed: %s", tag, result)
        else:
            supp_papers.extend(result)

    # Merge + dedup via source resolution (DOI → title → paperId).
    # Only run resolution when supplementary sources returned results.
    if supp_papers:
        records: list[RawRecord] = [
            RawRecord(paper=p, corpus_role=CorpusRole.USER, source_name="s2") for p in s2_papers
        ] + [RawRecord(paper=p, corpus_role=CorpusRole.USER, source_name="openalex") for p in supp_papers]
        canonical = resolve_papers(records)
        papers = [_canonical_to_paper(cp) for cp in canonical]
        logger.info(
            "retrieval.search: raw='%s' cleaned='%s' → s2=%d openalex=%d merged=%d",
            query[:60],
            cleaned[:60],
            len(s2_papers),
            len(supp_papers),
            len(papers),
        )
    else:
        papers = s2_papers
        logger.info(
            "retrieval.search: raw='%s' cleaned='%s' → s2=%d (OpenAlex disabled/empty)",
            query[:60],
            cleaned[:60],
            len(papers),
        )

    return _valid_papers(papers, stage="search")


def _canonical_to_paper(cp: CanonicalPaper) -> Paper:
    """Convert a merged CanonicalPaper back to Paper for downstream compatibility.

    Uses S2 paperId when available (enables SPECTER2 embedding lookup).
    Falls back to canonical key (doi:… / title:… / openalex:…) for OpenAlex-only papers.
    """
    paper_id = cp.s2_paper_id or cp.id
    return Paper(
        paperId=paper_id,
        title=cp.title,
        abstract=cp.abstract,
        year=cp.year,
        citationCount=cp.citation_count,
        authors=cp.authors,
        url=cp.url,
        openAccessPdf=cp.open_access_pdf,
        externalIds=cp.external_ids,
        isInfluential=cp.is_influential,
        source=",".join(sorted(cp.sources)) if cp.sources else None,
    )


async def snowball(pool: list[Paper], depth: int = 1) -> list[Paper]:
    """Stage C — Expand corpus via citation snowballing.

    ``select_seeds`` picks dual-pool seeds (top-N by raw citationCount +
    top-N by citationCount/age).  ``run_snowball`` fetches backward
    (references) + forward (citations) for each seed and returns ONLY
    the *new* papers (seeds are excluded internally).

    This function merges ``pool ∪ new_papers``, deduplicated by ``paperId``.

    Args:
        pool: Existing corpus, typically the result of ``search()``.
        depth: Snowball traversal depth (default 1).

    Returns:
        ``list[Paper]`` — pool + snowballed papers, deduped; pool order
        preserved first.
    """
    if not pool:
        logger.info("retrieval.snowball: empty pool — skipping")
        return []

    seed_ids = select_seeds(pool, pool_size=5)
    if not seed_ids:
        logger.info("retrieval.snowball: no valid seeds (missing citationCount?) — returning pool")
        return pool

    new_papers = await run_snowball(seed_ids, depth=depth)
    new_papers = _valid_papers(new_papers, stage="snowball")

    # Merge pool + new, dedup by paperId (pool order preserved first).
    seen: set[str] = set()
    merged: list[Paper] = []
    for paper in pool + new_papers:
        if paper.paper_id and paper.paper_id not in seen:
            seen.add(paper.paper_id)
            merged.append(paper)

    logger.info(
        "retrieval.snowball: %d seeds → +%d new → %d total (deduped)",
        len(seed_ids),
        len(new_papers),
        len(merged),
    )
    return merged


async def rank(clean_query: str, papers: list[Paper], top_k: int) -> list[Paper]:
    """Stage E — Hybrid BM25 + HyDE NIM semantic ranking (TIP-P2-06-FIX).

    Combined architecture (dim-safe):

    * **SPECTER2 arm** (gap_specter_store, 768d): fetch SPECTER2 vectors for
      candidate papers via S2 API; upsert for future paper-paper cosine (P2-07/P2-08).
      NOT used for querying arbitrary text.

    * **NIM semantic arm** (gap_nim_store, 4096d, weight ``SPECTER2_WEIGHT`` 0.4):
      - Embed each paper's abstract via ``embed_text`` (NIM) → upsert into gap_nim_store.
      - Generate HyDE query vector via ``generate_hyde_vector_nim`` (NIM, 4096d).
      - Query gap_nim_store → semantic ranking (same embedding space, no dim mismatch).

    * **BM25 arm** (weight ``1 - SPECTER2_WEIGHT`` 0.6): term overlap +
      log-citation + recency (MVP composite).

    Fallback: when ``hyde_vec`` is ``None`` (LLM/NIM not configured or failed),
    ``w_sem = 0`` automatically → pure BM25, no crash.

    Args:
        clean_query: Topic string used as vocabulary reference for term overlap.
        papers: Corpus to rank (typically the output of ``snowball()``).
        top_k: Number of top papers to return.

    Returns:
        ``list[Paper]`` of length ``min(top_k, len(valid_papers))``, hybrid-ranked.
    """
    valid = _valid_papers(papers, stage="rank")
    if not valid:
        return []

    # ── SPECTER2: fetch + upsert into gap_specter_store (for future P2-07/P2-08) ──
    await clear_collection()  # reset SPECTER2 store (768d) each call
    try:
        paper_ids = [p.paper_id for p in valid if p.paper_id]
        specter_map: dict[str, list[float]] = await get_embeddings_batch(paper_ids)
        if specter_map:
            specter_papers = [
                {
                    "paper_id": pid,
                    "vector": vec,
                    "title": next((p.title for p in valid if p.paper_id == pid), ""),
                    "year": next((p.year for p in valid if p.paper_id == pid), None),
                }
                for pid, vec in specter_map.items()
            ]
            await upsert_papers(specter_papers)  # gap_specter_store (768d)
            logger.info(
                "retrieval.rank: upserted %d SPECTER2 vectors (768d, gap_specter_store)",
                len(specter_papers),
            )
    except Exception:
        logger.warning("retrieval.rank: SPECTER2 fetch/upsert failed — continuing", exc_info=True)

    # ── NIM: embed paper abstracts + upsert into gap_nim_store (4096d) ──────────
    await clear_nim_collection()  # reset NIM store each call
    _nim_sem = asyncio.Semaphore(get_nim_upsert_concurrency())

    async def _throttled_nim_upsert(paper_id: str, abstract: str, title: str, year: int) -> None:
        async with _nim_sem:
            await upsert_paper_to_nim_store(paper_id=paper_id, abstract=abstract, title=title, year=year)

    nim_tasks = [
        _throttled_nim_upsert(
            paper_id=p.paper_id,
            abstract=p.abstract or "",
            title=p.title or "",
            year=p.year or 0,
        )
        for p in valid
        if p.paper_id and p.abstract
    ]
    if nim_tasks:
        try:
            await asyncio.gather(*nim_tasks, return_exceptions=True)
            logger.info(
                "retrieval.rank: NIM abstract upsert attempted for %d papers (gap_nim_store)",
                len(nim_tasks),
            )
        except Exception:
            logger.warning("retrieval.rank: NIM abstract upsert failed — BM25 fallback", exc_info=True)

    # ── HyDE query vector (NIM 4096d) + semantic ranking ────────────────────────
    try:
        hyde_vec = await generate_hyde_vector_nim(clean_query)
    except Exception:
        logger.warning("retrieval.rank: HyDE NIM generation failed — BM25 fallback", exc_info=True)
        hyde_vec = None

    semantic_order: dict[str, int] = {}
    if hyde_vec is not None:
        try:
            ranked_ids = await query_by_vector_nim(hyde_vec, top_k=len(valid))  # gap_nim_store ✅
            semantic_order = {pid: i for i, pid in enumerate(ranked_ids)}
        except Exception:
            logger.warning("retrieval.rank: NIM semantic query failed — BM25 fallback", exc_info=True)

    # ── Hybrid scoring ─────────────────────────────────────────────────
    n_valid = len(valid)
    w_sem = get_specter2_weight() if hyde_vec is not None else 0.0
    w_bm25 = 1.0 - w_sem
    query_tokens = _tokenize(clean_query)

    def _key(p: Paper) -> tuple[float, float, float, str]:
        # BM25 composite (MVP)
        bm25 = _term_score(query_tokens, p) + 0.1 * _citation_score(p) + 0.001 * _recency_score(p)

        # Semantic: invert rank position to a [0,1] score.
        sem = 0.0
        if p.paper_id in semantic_order:
            sem = 1.0 - semantic_order[p.paper_id] / max(n_valid, 1)

        combined = w_sem * sem + w_bm25 * bm25
        return (
            -combined,
            -_citation_score(p),
            -_recency_score(p),
            p.paper_id or "",  # deterministic tiebreaker
        )

    ranked = sorted(valid, key=_key)
    result = ranked[:top_k]

    logger.info(
        "retrieval.rank: %d papers → top %d (query='%s', w_sem=%.2f, w_bm25=%.2f)",
        n_valid,
        len(result),
        clean_query[:60],
        w_sem,
        w_bm25,
    )
    return result


# ── Scoring helpers (private) ─────────────────────────────────────────────────


def _tokenize(text: str) -> frozenset[str]:
    """Lowercase-tokenize text; returns ``frozenset`` for O(1) set intersection."""
    return frozenset(_TOKEN_RE.findall(text.lower()))


def _term_score(query_tokens: frozenset[str], paper: Paper) -> float:
    """Fraction of unique query tokens found in ``title + abstract``.

    Returns 0.0 when query is empty or paper has no textual content.
    Range: ``[0.0, 1.0]``.
    Handles ``abstract=None`` safely.
    """
    if not query_tokens:
        return 0.0
    title: str = paper.title or ""
    abstract: str = paper.abstract or ""  # None → ""
    doc_tokens: frozenset[str] = _tokenize(title + " " + abstract)
    if not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def _citation_score(paper: Paper) -> float:
    """Log-scaled citation count to reduce outlier dominance.

    ``log(0 + 1) = 0.0`` for papers with no recorded citations.
    Always ≥ 0.
    """
    return math.log((paper.citation_count or 0) + 1)


def _recency_score(paper: Paper) -> float:
    """Raw publication year as recency proxy; 0.0 for unknown year.

    More recent year → higher score.  Using raw year value keeps units
    transparent and the comparison meaningful.
    """
    return float(paper.year) if paper.year is not None else 0.0
