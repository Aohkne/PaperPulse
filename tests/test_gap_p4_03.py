from __future__ import annotations

import importlib

from backend.agent.gap_detection.schemas import GapItem, GapOrigin, GapStatus, GapType, PaperRef


def _gap(statement: str, quality: float, paper_ids: list[str], quotes: list[str] | None = None) -> GapItem:
    return GapItem(
        gap_type=GapType.TOPICAL,
        origin=GapOrigin.INFERRED,
        status=GapStatus.OPEN,
        statement=statement,
        supporting_papers=[PaperRef(paper_id=pid, title=pid) for pid in paper_ids],
        confidence=0.5,
        quality_score=quality,
        evidence_quotes=quotes or [],
    )


def test_jaccard_computes_overlap_on_supporting_paper_ids() -> None:
    mod = importlib.import_module("backend.agent.gap_detection.nodes.synthesizer")
    assert mod._jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert mod._jaccard(set(), set()) == 1.0


def test_dedup_gaps_by_jaccard_keeps_best_gap_per_cluster() -> None:
    mod = importlib.import_module("backend.agent.gap_detection.nodes.synthesizer")
    gaps = [
        _gap("gap-a", quality=0.9, paper_ids=["p1", "p2"], quotes=["q1"]),
        _gap("gap-b", quality=0.8, paper_ids=["p1", "p2"], quotes=["q2"]),
        _gap("gap-c", quality=0.7, paper_ids=["p9"], quotes=["q3"]),
    ]

    deduped = mod._dedup_gaps_by_jaccard(gaps, threshold=0.6)

    assert len(deduped) == 2
    assert deduped[0].statement == "gap-a"
    assert deduped[0].evidence_quotes == ["q1", "q2"]
    assert deduped[1].statement == "gap-c"

