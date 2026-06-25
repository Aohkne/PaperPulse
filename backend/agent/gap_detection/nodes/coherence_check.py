"""Stage D — Coherence Gate (D-a), Coverage Estimate (D-b), Density Readiness (D-c).

D-a: Clusters papers by SPECTER2 cosine similarity, detects grab-bag corpora,
     and warns when the paper set is too topically scattered.

D-b: coverage_estimate — heuristic saturation rate for the paper corpus.

D-c: density_readiness — per-cell density for co-occurrence trustworthiness.
     Per §5 "ma trận chỉ tin khi hàng+cột đủ dày": a cell (method, domain)
     is trusted only when both its method-row AND domain-column contain
     ≥ DENSITY_MIN_PAPERS papers.

check_coherence() is async (fetches SPECTER2 vectors from Supabase pgvector
via gap_specter_store.get_vectors_by_ids) — no LLM/embed calls though.
All exceptions are caught internally: check_coherence() never raises.
"""

from __future__ import annotations

import logging
import math

from backend.shared.models.paper import Paper

logger = logging.getLogger(__name__)

# ── Stage D-a: Coherence ─────────────────────────────────────────────

# Average pairwise cosine similarity below this → corpus is a grab-bag.
COHERENCE_THRESHOLD = 0.3

# Minimum papers in corpus before we bother checking.
MIN_PAPERS_TO_CHECK = 5

# When filtering a grab-bag, keep at most this many core papers.
_MAX_CORE_PAPERS = 15

# When computing avg pairwise similarity, check at most this many
# neighbours per vector to keep O(n) rather than O(n²).
_MAX_NEIGHBOURS = 5

# ── Stage D-b/D-c: Coverage + Density ───────────────────────────────

# ≥N papers in both method-row AND domain-column → cell trusted for co-occurrence.
DENSITY_MIN_PAPERS = 3

# Corpus size at which coverage heuristic ≈ saturated (linear proxy).
_SATURATION_TARGET = 20

# Ordered method keywords for heuristic extraction from Paper abstracts.
_METHOD_KEYWORDS: list[str] = [
    "deep learning", "neural network", "transformer", "bert",
    "large language model", "llm", "machine learning", "reinforcement learning",
    "convolutional", "cnn", "recurrent", "rnn", "lstm", "graph neural", "gnn",
    "attention mechanism", "diffusion model", "contrastive learning",
    "random forest", "support vector", "svm", "clustering",
    "retrieval-augmented", "rag", "few-shot", "zero-shot",
    "fine-tuning", "pre-training", "self-supervised", "meta-learning",
    "generative model", "classification", "regression", "optimization",
]


# ── Stage D-a helpers ────────────────────────────────────────────────


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Manual cosine similarity — no numpy dependency."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _get_specter_vectors(papers: list[Paper]) -> dict[str, list[float]]:
    """Fetch SPECTER2 vectors from gap_specter_store for the given papers.

    Returns an empty dict when the store is empty, the IDs are absent,
    or any exception occurs — coherence check then skips gracefully.
    """
    try:
        from backend.agent.gap_detection.gap_specter_store import get_vectors_by_ids

        paper_ids = [p.paper_id for p in papers if p.paper_id]
        if not paper_ids:
            return {}

        return await get_vectors_by_ids(paper_ids)
    except Exception:
        logger.debug("coherence_check: could not fetch SPECTER2 vectors", exc_info=True)
        return {}


def _average_pairwise_similarity(vectors: list[list[float]]) -> float:
    """Estimate avg pairwise cosine similarity using a sliding window.

    Checks at most _MAX_NEIGHBOURS neighbours per vector (not all pairs)
    to keep the computation bounded for large corpora.

    Returns 1.0 when fewer than 2 vectors are provided (safe default).
    """
    if len(vectors) < 2:
        return 1.0
    total, count = 0.0, 0
    for i in range(len(vectors)):
        for j in range(i + 1, min(i + 1 + _MAX_NEIGHBOURS, len(vectors))):
            total += _cosine_sim(vectors[i], vectors[j])
            count += 1
    return total / count if count > 0 else 1.0


async def check_coherence(papers: list[Paper]) -> dict:
    """Check topical coherence of a paper corpus using SPECTER2 similarity.

    Also computes Stage D-b coverage estimate and D-c density readiness
    and includes them in the returned dict for state seeding.

    Args:
        papers: List of Paper objects to assess.

    Returns:
        {
            "coherent":       bool,
            "warning":        str | None,
            "papers":         list[Paper],
            "density_signal": dict,        # from density_readiness(); empty on error
            "coverage":       float | None,
        }

    Behaviour:
    - Fewer than MIN_PAPERS_TO_CHECK papers → coherent=True (no check).
    - SPECTER2 vectors unavailable or sparse → coherent=True (no check).
    - avg pairwise sim >= COHERENCE_THRESHOLD → coherent=True.
    - avg pairwise sim <  COHERENCE_THRESHOLD → coherent=False, papers
      filtered to the _MAX_CORE_PAPERS most similar to the seed centroid.
    - Any internal exception → coherent=True, warning=None (fail-safe).
    """
    try:
        result = await _check_coherence_impl(papers)
        kept = result["papers"]
        result["density_signal"] = density_readiness(kept)
        result["coverage"] = coverage_estimate(kept, rounds=1)
        return result
    except Exception:
        logger.warning("coherence_check: unexpected error — skipping check", exc_info=True)
        return {
            "coherent": True,
            "warning": None,
            "papers": papers,
            "density_signal": {},
            "coverage": None,
        }


async def _check_coherence_impl(papers: list[Paper]) -> dict:
    """Core coherence logic (called by check_coherence with exception guard)."""
    if len(papers) < MIN_PAPERS_TO_CHECK:
        return {"coherent": True, "warning": None, "papers": papers}

    vectors_dict = await _get_specter_vectors(papers)
    if len(vectors_dict) < MIN_PAPERS_TO_CHECK:
        # Too few vectors to make a meaningful judgement → assume coherent.
        return {"coherent": True, "warning": None, "papers": papers}

    # Map paper_id → paper for ordered access.
    id_to_paper: dict[str, Paper] = {p.paper_id: p for p in papers if p.paper_id}

    # Use only the papers that have vectors, in original order.
    ordered_ids = [pid for pid in id_to_paper if pid in vectors_dict]
    vectors_list = [vectors_dict[pid] for pid in ordered_ids]

    avg_sim = _average_pairwise_similarity(vectors_list)

    if avg_sim >= COHERENCE_THRESHOLD:
        return {"coherent": True, "warning": None, "papers": papers}

    # Grab-bag detected — keep papers closest to the seed centroid.
    seed_ids = ordered_ids[:3]
    seed_vectors = [vectors_dict[pid] for pid in seed_ids]

    centroid = [
        sum(v[i] for v in seed_vectors) / len(seed_vectors)
        for i in range(len(seed_vectors[0]))
    ]

    scored: list[tuple[float, Paper]] = []
    for pid in ordered_ids:
        paper = id_to_paper.get(pid)
        if paper:
            sim = _cosine_sim(vectors_dict[pid], centroid)
            scored.append((sim, paper))
    scored.sort(key=lambda x: x[0], reverse=True)

    core_papers = [p for _, p in scored[:_MAX_CORE_PAPERS]]

    warning = (
        f"Corpus phân tán (avg_similarity={avg_sim:.2f} < {COHERENCE_THRESHOLD}). "
        f"Giữ {len(core_papers)} papers gần chủ đề nhất."
    )
    logger.warning("coherence_check: %s", warning)
    return {"coherent": False, "warning": warning, "papers": core_papers}


# ── Stage D-b: Coverage Estimate ─────────────────────────────────────


def coverage_estimate(corpus: list, rounds: int | None = None) -> float | None:
    """Heuristic corpus saturation rate in [0.0, 1.0].

    Simple linear model: saturates at _SATURATION_TARGET papers.
    Returns None when rounds is None or corpus is empty (safe fallback per §10).

    Args:
        corpus: list[Paper] or list[ExtractedPaperData].
        rounds: Number of search/snowball rounds completed. None → returns None.

    Returns:
        float in [0.0, 1.0] clamped, or None.
    """
    if not corpus or rounds is None:
        return None
    return round(min(1.0, len(corpus) / _SATURATION_TARGET), 3)


# ── Stage D-c: Density Readiness ─────────────────────────────────────


def _paper_method_key(paper: object) -> str:
    """Normalised method key from Paper or ExtractedPaperData (duck-typed)."""
    if hasattr(paper, "methodology") and paper.methodology:  # type: ignore[union-attr]
        return paper.methodology.lower().strip()[:60]  # type: ignore[union-attr]
    text = (
        (getattr(paper, "title", "") or "").lower()
        + " "
        + (getattr(paper, "abstract", "") or "").lower()
    )
    for kw in _METHOD_KEYWORDS:
        if kw in text:
            return kw
    return "other"


def _paper_domain_key(paper: object) -> str:
    """Normalised domain key from Paper or ExtractedPaperData (duck-typed)."""
    if hasattr(paper, "topics"):
        topics = paper.topics  # type: ignore[union-attr]
        if topics:
            return topics[0].lower().strip()[:60]
    year = getattr(paper, "year", None)
    if isinstance(year, int):
        if year >= 2023:
            return "recent"
        if year >= 2020:
            return "post2020"
        return "pre2020"
    return "unknown_domain"


def density_readiness(
    corpus: list,
    *,
    min_papers: int = DENSITY_MIN_PAPERS,
) -> dict:
    """Compute density readiness for co-occurrence trustworthiness (TIP-406).

    A cell (method, domain) is trusted when BOTH its method-row count AND
    its domain-column count are ≥ min_papers ("hàng+cột đủ dày" per §5).

    Accepts list[Paper] or list[ExtractedPaperData].  Duck-typed so callers
    inside the LangGraph (after extraction) get higher-quality keys.

    Args:
        corpus:     Paper corpus. Empty list → empty result, no crash.
        min_papers: Row/column threshold (default DENSITY_MIN_PAPERS = 3).

    Returns:
        {
            "cells": {
                "<method>|<domain>": {
                    "method":       str,
                    "domain":       str,
                    "cell_count":   int,   # papers with both this method & domain
                    "method_count": int,   # papers with this method (row count)
                    "domain_count": int,   # papers with this domain (col count)
                    "trusted":      bool,  # method_count>=min AND domain_count>=min
                }
            },
            "trusted_cells":   list[str],
            "untrusted_cells": list[str],
            "min_papers":      int,
        }

    Fallback: empty corpus → all lists/dicts empty, no exception.
    """
    if not corpus:
        return {
            "cells": {},
            "trusted_cells": [],
            "untrusted_cells": [],
            "min_papers": min_papers,
        }

    method_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    cell_counts: dict[tuple[str, str], int] = {}

    for paper in corpus:
        m = _paper_method_key(paper)
        d = _paper_domain_key(paper)
        method_counts[m] = method_counts.get(m, 0) + 1
        domain_counts[d] = domain_counts.get(d, 0) + 1
        cell_counts[(m, d)] = cell_counts.get((m, d), 0) + 1

    cells: dict[str, dict] = {}
    trusted: list[str] = []
    untrusted: list[str] = []

    for (m, d), c_count in sorted(cell_counts.items()):
        m_count = method_counts[m]
        d_count = domain_counts[d]
        is_trusted = m_count >= min_papers and d_count >= min_papers
        key = f"{m}|{d}"
        cells[key] = {
            "method": m,
            "domain": d,
            "cell_count": c_count,
            "method_count": m_count,
            "domain_count": d_count,
            "trusted": is_trusted,
        }
        (trusted if is_trusted else untrusted).append(key)

    return {
        "cells": cells,
        "trusted_cells": trusted,
        "untrusted_cells": untrusted,
        "min_papers": min_papers,
    }
