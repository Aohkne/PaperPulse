"""Maximal Marginal Relevance (MMR) selection — SPEC 2.0 §Step ④⑤.

Balances relevance to a query against diversity among already-selected
candidates, so the chosen set covers different angles of a topic instead
of clustering around the single most relevant point.

    MMR(d) = lambda * Sim(d, query) - (1 - lambda) * max_{s in selected} Sim(d, s)

Greedy: each round picks the candidate with the highest MMR score given
the candidates already chosen. Round 1 always picks the most relevant
candidate (pure relevance, no diversity term yet).
"""

from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    # Embeddings from different models aren't comparable even at the same
    # nominal length, but a length mismatch is the cheap, certain case to catch:
    # zip() would otherwise silently truncate to the shorter vector for the dot
    # product while norm_a/norm_b still sum over each vector's full (different)
    # length — producing a number that looks like a cosine score but isn't one.
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def mmr_select(
    query_vec: list[float],
    candidates: list[tuple[str, list[float]]],
    k: int,
    lambda_mult: float = 0.5,
    fetch_k: int | None = None,
) -> list[str]:
    """Return up to `k` candidate ids selected via greedy MMR.

    Args:
        query_vec: query embedding.
        candidates: [(id, embedding), ...] pool to select from.
        k: number of ids to return.
        lambda_mult: relevance/diversity trade-off (1.0 = pure relevance,
            0.0 = pure diversity). SPEC default 0.5.
        fetch_k: pre-filter `candidates` to this many highest-relevance
            items (by cosine vs query) before running the greedy MMR loop.
            Defaults to the full candidate pool.
    """
    if not candidates or k <= 0:
        return []

    scored = [(cid, vec, cosine_similarity(query_vec, vec)) for cid, vec in candidates]
    scored.sort(key=lambda t: t[2], reverse=True)

    pool = scored[:fetch_k] if fetch_k else scored
    if not pool:
        return []

    # Round 1: highest relevance to query (no diversity term yet)
    selected: list[tuple[str, list[float], float]] = [pool[0]]
    remaining = pool[1:]

    while remaining and len(selected) < k:
        best_idx = 0
        best_score = -math.inf
        for i, (_cid, vec, rel) in enumerate(remaining):
            max_sim_to_selected = max(cosine_similarity(vec, s_vec) for _, s_vec, _ in selected)
            mmr_score = lambda_mult * rel - (1 - lambda_mult) * max_sim_to_selected
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return [cid for cid, _vec, _rel in selected[:k]]
