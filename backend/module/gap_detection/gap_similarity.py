"""Helpers for embedding and clustering semantically similar research gaps."""

from __future__ import annotations

import logging

import numpy as np

from backend.module.gap_detection.schemas import GapItem
from backend.module.gap_detection.services.embedding import embed_text
from backend.module.gap_detection.settings import get_gap_diversity_threshold

logger = logging.getLogger(__name__)

_EMBED_CACHE: dict[str, list[float] | None] = {}


async def embed_gap(gap: GapItem) -> list[float] | None:
    """Embed a gap statement via the gap-owned NIM embed_text helper.

    Uses a simple statement-keyed cache so repeated clustering passes do not
    re-embed identical text within the same process.
    """
    statement = (gap.statement or "").strip()
    if not statement:
        return None

    if statement in _EMBED_CACHE:
        return _EMBED_CACHE[statement]

    try:
        vector = await embed_text(statement)
    except Exception:
        logger.warning("embed_gap: embed_text failed", exc_info=True)
        vector = None

    _EMBED_CACHE[statement] = vector
    return vector


def gap_similarity(vec_a: list[float] | None, vec_b: list[float] | None) -> float:
    """Return cosine similarity between two vectors.

    Missing vectors, empty vectors, shape mismatch, or zero norms all return 0.0.
    """
    if vec_a is None or vec_b is None:
        return 0.0
    if len(vec_a) == 0 or len(vec_b) == 0 or len(vec_a) != len(vec_b):
        return 0.0

    arr_a = np.asarray(vec_a, dtype=float)
    arr_b = np.asarray(vec_b, dtype=float)
    norm_a = float(np.linalg.norm(arr_a))
    norm_b = float(np.linalg.norm(arr_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = float(np.dot(arr_a, arr_b) / (norm_a * norm_b))
    return max(-1.0, min(1.0, similarity))


async def cluster_gaps(gaps: list[GapItem], threshold: float | None = None) -> list[list[int]]:
    """Cluster gaps by single-linkage cosine similarity over embedded statements.

    Cluster order and member order are stable with respect to the input list.
    Gaps with missing embeddings become singleton clusters.
    """
    if not gaps:
        return []
    if len(gaps) == 1:
        return [[0]]

    threshold_value = get_gap_diversity_threshold() if threshold is None else threshold
    vectors = [await embed_gap(gap) for gap in gaps]

    clusters: list[list[int]] = []
    for index, vector in enumerate(vectors):
        if vector is None:
            clusters.append([index])
            continue

        placed = False
        for cluster in clusters:
            if any(gap_similarity(vector, vectors[member_index]) >= threshold_value for member_index in cluster):
                cluster.append(index)
                placed = True
                break

        if not placed:
            clusters.append([index])

    return clusters
