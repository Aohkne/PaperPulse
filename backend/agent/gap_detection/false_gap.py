"""false_gap.py — Check if a gap is likely already researched (false gap)."""

from __future__ import annotations

import logging

from backend.agent.gap_detection.gap_nim_store import query_with_distances_nim
from backend.agent.gap_detection.services.embedding import embed_text
from backend.agent.gap_detection.settings import get_false_gap_threshold

logger = logging.getLogger(__name__)


async def check_false_gap(gap_statement: str) -> bool:
    """
    Trả True nếu gap có thể đã được nghiên cứu (false gap).
    Dùng embed_text (NIM 4096d) + gap_nim_store cosine distance.
    Fail safe: trả False nếu embed/query fail.
    """
    try:
        vec = await embed_text(gap_statement)
        if not vec:
            return False

        results = await query_with_distances_nim(vec, top_k=1)
        if not results:
            return False

        # results = [(paper_id, distance)] — distance cosine (0=identical, 2=opposite)
        _, distance = results[0]
        threshold = get_false_gap_threshold()  # default 0.15

        return distance < threshold  # gần = có thể đã có nghiên cứu
    except Exception:
        logger.warning("check_false_gap: failed", exc_info=True)
        return False  # fail safe


async def batch_check_false_gaps(gaps: list) -> list:
    """Trả list GapItem với false_gap_flag được set."""
    for gap in gaps:
        gap.false_gap_flag = await check_false_gap(gap.statement)
    return gaps
