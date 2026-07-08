"""novelty.py — Calculate novelty score for a gap statement."""

from __future__ import annotations

import logging

from backend.module.gap_detection.gap_nim_store import query_with_distances_nim
from backend.module.gap_detection.services.embedding import embed_text

logger = logging.getLogger(__name__)


async def compute_novelty_score(gap_statement: str) -> float | None:
    """
    novelty_score = mean cosine distance (gap vs top-10 core corpus trong nim_store).
    Cao = novel (gap xa với corpus hiện có).
    Fail safe: trả None nếu store rỗng hoặc embed fail.
    """
    try:
        vec = await embed_text(gap_statement)
        if not vec:
            return None

        results = await query_with_distances_nim(vec, top_k=10)
        if not results:
            return None

        distances = [d for _, d in results]
        mean_distance = sum(distances) / len(distances)
        return round(float(mean_distance), 4)  # 0=familiar, ~2=novel (cosine distance)

    except Exception:
        logger.warning("compute_novelty_score: failed", exc_info=True)
        return None
