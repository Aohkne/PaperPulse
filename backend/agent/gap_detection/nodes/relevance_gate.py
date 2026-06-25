"""
Stage B+C — Multi-facet Recall + Multi-layer Filter.
Dùng GapQuery để build pool papers rộng rồi filter/rank xuống ~20–25 papers.
"""
from __future__ import annotations

import asyncio
import json as json_lib
import logging

from backend.shared.models.paper import Paper
from backend.shared.services.llm_client import chat_completion
from backend.agent.gap_detection.schemas import GapQuery
from backend.agent.gap_detection import retrieval

logger = logging.getLogger(__name__)


# ── Stage B: Multi-facet Recall ──────────────────────────────────────────────

async def broad_recall(gap_query: GapQuery, per_facet_limit: int = 20) -> list[Paper]:
    """
    Search S2 cho TỪNG facet song song, dedup theo paper_id, trả pool.
    1 facet fail → log warning, facets còn lại vẫn chạy.
    """
    tasks = [
        retrieval.search(facet, limit=per_facet_limit)
        for facet in gap_query.facets
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_ids: set[str] = set()
    pool: list[Paper] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Facet search failed: %s", result)
            continue
        for paper in result:
            pid = paper.paper_id
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                pool.append(paper)

    logger.info("Stage B recall: %d papers từ %d facets", len(pool), len(gap_query.facets))
    return pool


# ── Stage C-T1: Metadata Filter ──────────────────────────────────────────────

def metadata_filter(papers: list[Paper], gap_query: GapQuery) -> list[Paper]:
    """
    T1: Loại papers không có abstract hoặc ngoài year_range.
    Papers có year=None được giữ lại.
    Papers ngoài range nhưng citation_count >= 50 (seminal) được giữ lại.
    """
    start_year, end_year = gap_query.year_range
    filtered = []
    for p in papers:
        if not p.abstract:
            continue
        year = p.year
        if year is not None and not (start_year <= year <= end_year):
            if (p.citation_count or 0) < 50:
                continue
        filtered.append(p)
    return filtered


# ── Stage C-T3: LLM Relevance Judge ─────────────────────────────────────────

_JUDGE_PROMPT = """\
Assess the relevance of the following papers to the given research topic.

TOPIC: {core_topic}
FACETS: {facets}

PAPERS (JSON array):
{papers_json}

Return a JSON array with exactly one element per paper:
{{"paper_id": "<id>", "score": <0.0-1.0>, "rationale": "<brief rationale in English>"}}

Scoring rules:
- 0.8–1.0: Highly relevant, directly about the topic
- 0.5–0.8: Partially relevant, some overlap
- 0.0–0.5: Barely relevant or off-topic

Return only the JSON array, no extra text.\
"""


async def llm_relevance_judge(
    papers: list[Paper],
    gap_query: GapQuery,
    batch_size: int = 10,
) -> list[tuple[Paper, float, str]]:
    """
    T3: LLM judge độ liên quan theo batch (max 10/batch để tránh overflow).
    Trả list[(paper, score, rationale)] sorted descending by score.
    Batch fail → fallback score=0.5, không crash.
    """
    paper_map: dict[str, Paper] = {}
    all_scored: list[tuple[Paper, float, str]] = []

    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        batch_data = []
        for p in batch:
            pid = p.paper_id
            paper_map[pid] = p
            batch_data.append({
                "paper_id": pid,
                "title": p.title or "",
                "abstract": (p.abstract or "")[:300],
            })

        prompt = _JUDGE_PROMPT.format(
            core_topic=gap_query.core_topic,
            facets=", ".join(gap_query.facets),
            papers_json=json_lib.dumps(batch_data, ensure_ascii=False),
        )

        try:
            response = await chat_completion([{"role": "user", "content": prompt}])
            scored_list = json_lib.loads(response.strip())
            for item in scored_list:
                pid = item.get("paper_id", "")
                score = float(item.get("score", 0.0))
                rationale = item.get("rationale", "")
                if pid in paper_map:
                    all_scored.append((paper_map[pid], score, rationale))
        except Exception as e:
            logger.warning("LLM judge batch %d failed: %s", i // batch_size + 1, e)
            for p in batch:
                all_scored.append((p, 0.5, "judge failed"))

    all_scored.sort(key=lambda x: x[1], reverse=True)
    return all_scored


# ── Full Stage B+C Pipeline ──────────────────────────────────────────────────

async def run_relevance_gate(
    gap_query: GapQuery,
    max_to_judge: int = 40,
    min_score: float = 0.5,
    max_output: int = 25,
) -> list[Paper]:
    """
    Full Stage B+C pipeline:
    1. broad_recall → pool (deduped, multi-facet)
    2. metadata_filter → filtered (abstract + year range)
    3. llm_relevance_judge (top max_to_judge) → ranked
    4. filter score >= min_score → trả tối đa max_output papers

    Fail-safe: nếu toàn bộ pipeline fail → trả [], không raise.
    """
    try:
        pool = await broad_recall(gap_query)
        if not pool:
            logger.warning("Stage B: pool rỗng")
            return []

        filtered = metadata_filter(pool, gap_query)
        logger.info("Stage C-T1: %d → %d papers sau metadata filter", len(pool), len(filtered))

        if not filtered:
            return []

        to_judge = filtered[:max_to_judge]
        judged = await llm_relevance_judge(to_judge, gap_query)

        result = [p for p, score, _ in judged if score >= min_score][:max_output]
        logger.info(
            "Stage C-T3: %d judged → %d papers (score >= %s)",
            len(to_judge), len(result), min_score,
        )
        return result
    except Exception as e:
        logger.error("run_relevance_gate failed: %s", e, exc_info=True)
        return []
