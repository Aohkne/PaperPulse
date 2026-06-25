"""novelty.py — Calculate novelty score for a gap statement."""

from __future__ import annotations

import logging
from backend.agent.gap_detection.gap_nim_store import get_nim_collection
from backend.agent.gap_detection.services.embedding import embed_text

logger = logging.getLogger(__name__)

async def compute_novelty_score(gap_statement: str) -> float | None:
    """
    novelty_score = mean cosine distance (gap vs top-10 core corpus trong nim_store).
    Cao = novel (gap xa với corpus hiện có).
    Fail safe: trả None nếu store rỗng hoặc embed fail.
    """
    try:
        col = get_nim_collection()
        if col.count() == 0:
            return None
            
        vec = await embed_text(gap_statement)
        if not vec:
            return None
            
        results = col.query(
            query_embeddings=[vec],
            n_results=min(10, col.count()),
            include=["distances"],
        )
        
        distances = results["distances"][0] if results.get("distances") else []
        if not distances:
            return None
            
        mean_distance = sum(distances) / len(distances)
        return round(float(mean_distance), 4)  # 0=familiar, ~2=novel (cosine distance)
        
    except Exception:
        logger.warning("compute_novelty_score: failed", exc_info=True)
        return None
