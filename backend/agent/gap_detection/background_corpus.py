"""background_corpus.py — Broad recall background pool fetching for gap-detection."""

from __future__ import annotations

import asyncio
import logging

from backend.agent.gap_detection import retrieval
from backend.agent.gap_detection.gap_nim_store import upsert_papers_nim
from backend.agent.gap_detection.gap_specter_store import upsert_papers
from backend.agent.gap_detection.services.embedding import embed_text
from backend.agent.gap_detection.settings import (
    get_background_batch_size,
    get_background_pool_size,
    get_specter_backoff_base,
    get_specter_retry_max,
)
from backend.shared.services.semantic_scholar import get_embeddings_batch

logger = logging.getLogger(__name__)


async def _embed_batch_specter_with_retry(
    paper_ids: list[str],
    retry: int = 0,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> dict[str, list[float]]:
    try:
        return await get_embeddings_batch(paper_ids)
    except Exception as e:
        if "429" not in str(e):
            logger.error(f"SPECTER2 batch failed (non-429): {e}")
            return {}
        if retry >= max_retries:
            logger.error(f"SPECTER2 batch 429: đã retry {max_retries} lần, skip {len(paper_ids)} papers")
            return {}
        delay = backoff_base ** (retry + 1)
        logger.warning(f"SPECTER2 batch 429, retry {retry + 1}/{max_retries} sau {delay}s")
        await asyncio.sleep(delay)
        if retry == 0 and len(paper_ids) > 10:
            mid = len(paper_ids) // 2
            left = await _embed_batch_specter_with_retry(
                paper_ids[:mid],
                retry=max_retries - 1,
                max_retries=max_retries,
                backoff_base=backoff_base,
            )
            right = await _embed_batch_specter_with_retry(
                paper_ids[mid:],
                retry=max_retries - 1,
                max_retries=max_retries,
                backoff_base=backoff_base,
            )
            return {**left, **right}
        return await _embed_batch_specter_with_retry(
            paper_ids,
            retry=retry + 1,
            max_retries=max_retries,
            backoff_base=backoff_base,
        )


async def build_background_corpus(clean_query: str) -> int:
    """
    Broad recall → SPECTER2 → upsert vào gap_specter_store.
    Trả số papers đã upsert thành công.
    KHÔNG extract/LLM — chỉ dùng search+snowball+SPECTER2.
    """
    pool_size = get_background_pool_size()  # default 100
    pool = await retrieval.search(clean_query, limit=pool_size)
    merged = await retrieval.snowball(pool)

    # SPECTER2 batch với retry (default batch 25 để giảm áp lực 429)
    batch_size = get_background_batch_size()
    upserted = 0
    for i in range(0, len(merged), batch_size):
        batch = merged[i : i + batch_size]
        paper_ids = [p.paper_id for p in batch if p.paper_id]
        if not paper_ids:
            continue
        try:
            vectors = await _embed_batch_specter_with_retry(
                paper_ids,
                max_retries=get_specter_retry_max(),
                backoff_base=get_specter_backoff_base(),
            )
            papers_with_vec = [
                {"paper_id": p.paper_id, "title": p.title or "", "year": p.year, "vector": vectors.get(p.paper_id)}
                for p in batch
                if p.paper_id and vectors.get(p.paper_id)
            ]
            if papers_with_vec:
                await upsert_papers(papers_with_vec)
                upserted += len(papers_with_vec)
        except Exception:
            logger.warning(f"build_background_corpus: batch {i} failed, skipping", exc_info=True)
            continue  # batch fail → skip, tiếp batch sau

        # Thêm NIM upsert (fire-and-forget per paper, không block batch):
        for p in batch:
            if not p.paper_id or not p.abstract:
                continue
            try:
                nim_vec = await embed_text(p.abstract)
                if nim_vec:
                    await upsert_papers_nim(
                        [
                            {
                                "paper_id": p.paper_id,
                                "title": p.title or "",
                                "year": p.year or 0,
                                "vector": nim_vec,
                            }
                        ]
                    )
            except Exception:
                pass  # fire-and-forget, không crash batch

    logger.info("build_background_corpus: upserted %d papers for query %r", upserted, clean_query[:80])
    return upserted
