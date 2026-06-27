"""orchestrator.py — Cold-start entry point for gap detection.

Implements the 6-step cold-start flow (TIP-G04, updated G11):

  ① clean_query  — VN→EN, strip meta-words            (query_cleaner.py)
  ② search       — Semantic Scholar keyword search     (retrieval.py)
  ②b fallback    — retry with raw topic if search < 3  (G11.2, in-zone)
  ③ snowball      — citation graph expansion            (retrieval.py)
  ④ rank          — embedding-free deterministic top-K  (retrieval.py)
  ⑤ gate          — insufficient-paper early return
  ⑥ run_gap_detection — full LangGraph pipeline         (graph.py)

Cô lập hoàn toàn: chỉ import nội bộ gap_detection.  Không import services.
"""

from __future__ import annotations

import asyncio
import logging

from backend.agent.gap_detection import retrieval
from backend.agent.gap_detection.background_corpus import build_background_corpus
from backend.agent.gap_detection.graph import run_gap_detection
from backend.agent.gap_detection.nodes.coherence_check import check_coherence
from backend.agent.gap_detection.nodes.query_analyzer import analyze_query
from backend.agent.gap_detection.nodes.relevance_gate import run_relevance_gate
from backend.agent.gap_detection.query_cleaner import clean_query
from backend.agent.gap_detection.schemas import GapQuery, GapReport, PaperRef
from backend.agent.gap_detection.settings import (
    get_max_papers_for_gap,
    get_min_papers_cold_start,
    is_query_analyzer_enabled,
)

logger = logging.getLogger(__name__)

# Narrative returned when the corpus is too thin to produce useful gaps.
_INSUFFICIENT_NARRATIVE = (
    "Not enough literature was found for this topic. "
    "The system found too few related papers after the search and snowball steps. "
    "Please try again with a broader topic or a direct English search phrase."
)


async def cold_start(topic: str) -> GapReport:
    """Run the 6-step cold-start gap detection pipeline for *topic*.

    Args:
        topic: Research topic in any language (typically Vietnamese).
            The query cleaner translates and normalises it before search.

    Returns:
        A :class:`~backend.agent.gap_detection.schemas.GapReport` that is
        always valid and FE-renderable:

        * Happy path — full pipeline result from ``run_gap_detection``.
        * Insufficient papers — ``gaps=[]`` with a Vietnamese narrative and
          ``baseline_triggered=False``; ``run_gap_detection`` is NOT called.
    """
    # ── Stage A→D: Cold-start pre-processing (additive, every stage has fallback) ──
    cold_start_papers = None
    gap_query: GapQuery | None = None
    _density_signal: dict | None = None
    _coverage: float | None = None

    if is_query_analyzer_enabled():
        # Stage A — Query Analyzer: structured GapQuery from raw topic
        try:
            gap_query = await analyze_query(topic)
            logger.info(
                "cold_start: Stage A GapQuery: core=%r facets=%s",
                gap_query.core_topic,
                gap_query.facets,
            )
        except Exception as exc:
            logger.warning("cold_start: Stage A failed (%s) — fallback to clean_query", exc)
            _fb_clean = await clean_query(topic)
            gap_query = GapQuery(core_topic=_fb_clean, facets=[_fb_clean])

        # Stage B+C — Relevance Gate: multi-facet recall + multi-layer filter
        try:
            cold_start_papers = await run_relevance_gate(gap_query)
            logger.info("cold_start: Stage B+C: %d papers", len(cold_start_papers))
        except Exception as exc:
            logger.warning("cold_start: Stage B+C failed (%s) — fallback to default search", exc)
            cold_start_papers = None

        # Stage D — Coherence Gate: detect grab-bag corpus, warn if scattered
        if cold_start_papers:
            coherence_result = await check_coherence(cold_start_papers)
            cold_start_papers = coherence_result["papers"]
            _density_signal = coherence_result.get("density_signal") or {}
            _coverage = coherence_result.get("coverage")
            if coherence_result["warning"]:
                logger.warning("cold_start: Stage D coherence: %s", coherence_result["warning"])
            logger.info(
                "cold_start: Stage D density: %d trusted cells, %d untrusted cells",
                len(_density_signal.get("trusted_cells", [])),
                len(_density_signal.get("untrusted_cells", [])),
            )

    # ① Translate / normalise topic → English search query
    clean = await clean_query(topic)
    logger.info("cold_start: topic=%r -> clean=%r", topic[:80], clean[:80])

    if cold_start_papers:
        # Stages B+C+D produced a curated paper set — skip ②③④.
        top_k = get_max_papers_for_gap()
        top = cold_start_papers[:top_k]
        logger.info(
            "cold_start: using %d cold-start papers from Stage B+C+D (skipped search/snowball/rank)",
            len(top),
        )
    else:
        # ② Keyword search (up to 100 candidate papers)
        pool = await retrieval.search(clean, limit=100)
        logger.info("cold_start: search returned %d papers", len(pool))

        # ②b Fallback: if clean_query over-distilled and search is too thin,
        #    retry once with the raw topic (no extra LLM call, transparent to user).
        #    Threshold < 3: 1-2 papers is too narrow a seed for useful snowball;
        #    retry gives S2 a broader surface. If topic itself is also thin,
        #    the gate below will catch it as a genuinely niche topic.
        _SEARCH_FALLBACK_THRESHOLD = 3
        if len(pool) < _SEARCH_FALLBACK_THRESHOLD and clean.lower() != topic.lower():
            logger.info(
                "cold_start: search(%r)=%d < %d — retrying with raw topic",
                clean[:60],
                len(pool),
                _SEARCH_FALLBACK_THRESHOLD,
            )
            pool = await retrieval.search(topic, limit=100)
            logger.info("cold_start: fallback search(%r) returned %d papers", topic[:60], len(pool))

        # ③ Snowball: expand via citation graph (depth=1)
        merged = await retrieval.snowball(pool)
        logger.info("cold_start: after snowball: %d papers", len(merged))

        # ④ Rank and take top-K (MAX_PAPERS_FOR_GAP, cap-final=20)
        top_k = get_max_papers_for_gap()
        top = await retrieval.rank(clean or topic, merged, top_k=top_k)
        logger.info("cold_start: ranked top %d papers (pool_size=%d)", len(top), len(merged))

    # ⑤ Insufficient-paper gate
    min_papers = get_min_papers_cold_start()
    if len(top) < min_papers:
        logger.warning(
            "cold_start: only %d papers (< MIN=%d) — returning early with empty gaps",
            len(top),
            min_papers,
        )
        return GapReport(
            papers_analyzed=len(top),
            gaps=[],
            narrative=_INSUFFICIENT_NARRATIVE,
            baseline_triggered=False,
        )

    # ⑥ Map Paper → PaperRef and invoke the full LangGraph pipeline
    session_papers: list[PaperRef] = _papers_to_refs(top)

    # Background corpus (fire-and-forget, không block detection)
    asyncio.create_task(build_background_corpus(clean or topic))

    logger.info("cold_start: invoking run_gap_detection with %d papers", len(session_papers))
    return await run_gap_detection(
        session_papers,
        gap_query=gap_query,
        density_signal=_density_signal,
        coverage=_coverage,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _papers_to_refs(papers: list) -> list[PaperRef]:
    """Map ``Paper`` objects to ``PaperRef`` instances for graph consumption.

    ``Paper.paper_id``  → ``PaperRef.paper_id``
    ``Paper.title``     → ``PaperRef.title``
    ``Paper.year``      → ``PaperRef.year``      (optional)
    ``Paper.url``       → ``PaperRef.url``        (optional)

    Note: ``PaperRef`` does not have an ``abstract`` field; raw abstract is
    persisted later by ``extractor_node`` from Semantic Scholar's detail API
    (TIP-G06-R).  Carrying it here would require a schema change — forbidden
    by TIP-G04 spec ("KHÔNG thêm field mới vào model").
    """
    refs: list[PaperRef] = []
    for paper in papers:
        paper_id = getattr(paper, "paper_id", None)
        title = getattr(paper, "title", None) or ""
        if not paper_id:
            logger.warning("cold_start._papers_to_refs: skipping paper with no paper_id")
            continue
        refs.append(
            PaperRef(
                paper_id=paper_id,
                title=title,
                year=getattr(paper, "year", None),
                url=getattr(paper, "url", None),
                abstract=getattr(paper, "abstract", None),
                source=getattr(paper, "source", None),
            )
        )
    return refs
