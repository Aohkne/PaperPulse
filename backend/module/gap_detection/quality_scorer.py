"""
Quality scoring đa chiều cho GapItem.
Công thức từ TAILIEU_TONGHOP PHẦN II:

quality = 0.3333 × grounding
        + 0.2778 × novelty_normalized
        + 0.2222 × actionable
        + 0.1667 × corpus_evidence
"""

from backend.module.gap_detection.schemas import GapItem
from backend.module.gap_detection.settings import get_top_k_gaps


def _compute_quality_breakdown(gap: GapItem) -> dict[str, float]:
    """Return the normalized axis values used by compute_quality_score."""
    grounding = max(0.0, min(1.0, gap.confidence))

    if gap.novelty_score is not None:
        novelty_n = min(gap.novelty_score / 2.0, 1.0)
    else:
        novelty_n = 0.5

    if gap.suggested_method:
        actionable = 1.0
    elif gap.falsifiability_condition:
        actionable = 0.5
    else:
        actionable = 0.0

    corpus_ev = min(len(gap.supporting_papers) / 5.0, 1.0)

    return {
        "grounding": round(grounding, 4),
        "novelty": round(novelty_n, 4),
        "actionable": round(actionable, 4),
        "corpus_evidence": round(corpus_ev, 4),
    }


def compute_quality_score(gap: GapItem) -> float:
    """
    Tính quality score [0.0, 1.0] cho 1 gap.

    Axes:
    - grounding (0.3333):  gap.confidence (0–1).
    - novelty (0.2778):    min(gap.novelty_score / 2.0, 1.0). None → 0.5 (neutral).
    - actionable (0.2222): 1.0 nếu suggested_method, 0.5 nếu falsifiability_condition, else 0.0.
    - corpus_evidence (0.1667): min(len(supporting_papers) / 5.0, 1.0).
    """
    breakdown = _compute_quality_breakdown(gap)
    grounding = breakdown["grounding"]
    novelty_n = breakdown["novelty"]
    actionable = breakdown["actionable"]
    corpus_ev = breakdown["corpus_evidence"]

    score = 0.3333 * grounding + 0.2778 * novelty_n + 0.2222 * actionable + 0.1667 * corpus_ev
    gap.quality_breakdown = breakdown
    return round(score, 4)


def rank_gaps_by_quality(
    gaps: list[GapItem],
    top_k: int | None = None,
) -> list[GapItem]:
    """
    Tính quality_score cho tất cả gaps, sort descending, trả top_k.
    Nếu top_k=None → dùng settings.get_top_k_gaps().
    KHÔNG filter cứng — mọi gap đều có quality_score, chỉ lấy top_k.
    """
    if top_k is None:
        top_k = get_top_k_gaps()

    for gap in gaps:
        gap.quality_score = compute_quality_score(gap)

    gaps.sort(key=lambda g: g.quality_score or 0.0, reverse=True)

    return gaps[:top_k]
