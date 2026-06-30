"""TIP-UF-06 — unit tests: raw paper IDs must not appear in gap statements."""

import re

from backend.agent.gap_detection.nodes.synthesizer import _normalize_statement_citations
from backend.agent.gap_detection.schemas import GapItem, GapOrigin, GapStatus, GapType, PaperRef


def _has_raw_id(text: str) -> bool:
    return bool(re.search(r"\b[0-9a-f]{16,}\b", text))


# ── _normalize_statement_citations ───────────────────────────────────────────


class TestNormalizeStatementCitations:
    def test_paper_prefix_replaced(self):
        pid = "e38d4fbfdf13532f7f58e5831cf7bc6d7d291c1a"
        stmt = f"Paper {pid} states that RAG does not outperform standard prompting."
        result = _normalize_statement_citations(stmt, {pid: 1})
        assert "[1]" in result
        assert pid not in result
        assert not _has_raw_id(result)

    def test_paper_prefix_case_insensitive(self):
        pid = "7423e5c903fb2befaf471cae64e2530f7c1d0404"
        stmt = f"paper {pid} reports accuracy improvements."
        result = _normalize_statement_citations(stmt, {pid: 2})
        assert "[2]" in result
        assert pid not in result

    def test_bare_id_replaced(self):
        pid = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        stmt = f"As shown by {pid}, the method fails on low-resource tasks."
        result = _normalize_statement_citations(stmt, {pid: 3})
        assert "[3]" in result
        assert pid not in result

    def test_two_ids_replaced(self):
        pid_a = "e38d4fbfdf13532f7f58e5831cf7bc6d7d291c1a"
        pid_b = "7423e5c903fb2befaf471cae64e2530f7c1d0404"
        stmt = (
            f"Paper {pid_a} states that advanced prompting methods do not outperform "
            f"standard prompting, whereas paper {pid_b} reports that adding RAG to "
            "GPT-4 raised answer accuracy from 80.1% to 91.4%."
        )
        id2cite = {pid_a: 1, pid_b: 2}
        result = _normalize_statement_citations(stmt, id2cite)
        assert "[1]" in result
        assert "[2]" in result
        assert pid_a not in result
        assert pid_b not in result
        assert not _has_raw_id(result)
        # Meaning preserved
        assert "advanced prompting methods" in result
        assert "accuracy from 80.1% to 91.4%" in result

    def test_no_ids_in_map_noop(self):
        stmt = "There is a gap in applying transformers to biomedical NLP."
        result = _normalize_statement_citations(stmt, {})
        assert result == stmt

    def test_no_ids_in_statement_noop(self):
        stmt = "There is a gap in applying transformers to biomedical NLP."
        result = _normalize_statement_citations(stmt, {"abc123": 1})
        assert result == stmt

    def test_content_preserved_after_replace(self):
        pid = "e38d4fbfdf13532f7f58e5831cf7bc6d7d291c1a"
        stmt = f"Paper {pid} demonstrates that contrastive learning improves representation quality."
        result = _normalize_statement_citations(stmt, {pid: 1})
        assert "demonstrates that contrastive learning improves representation quality" in result


# ── Integration: synthesizer assigns citation_index + normalizes ──────────────


class TestStatementNormalizationIntegration:
    def test_gap_statement_after_citation_index_assign(self):
        """Simulate synthesizer citation_index assignment + normalize step."""
        pid_a = "e38d4fbfdf13532f7f58e5831cf7bc6d7d291c1a"
        pid_b = "7423e5c903fb2befaf471cae64e2530f7c1d0404"

        gap = GapItem(
            gap_type=GapType.CONTRADICTION,
            origin=GapOrigin.INFERRED,
            statement=(
                f"Paper {pid_a} states advanced prompting does not help, "
                f"whereas paper {pid_b} shows RAG improves accuracy."
            ),
            supporting_papers=[
                PaperRef(paper_id=pid_a, title="Study A", year=2023),
                PaperRef(paper_id=pid_b, title="Study B", year=2024),
            ],
        )

        # Simulate fixed synthesizer logic (model_copy — no shared mutation)
        gap.supporting_papers = [
            p.model_copy(update={"citation_index": i + 1}) for i, p in enumerate(gap.supporting_papers)
        ]
        id2cite = {p.paper_id: p.citation_index for p in gap.supporting_papers}
        gap.statement = _normalize_statement_citations(gap.statement, id2cite)

        assert not _has_raw_id(gap.statement), f"Raw ID found: {gap.statement}"
        assert "[1]" in gap.statement
        assert "[2]" in gap.statement
        assert gap.supporting_papers[0].citation_index == 1
        assert gap.supporting_papers[1].citation_index == 2


# ── UF-08: multi-gap aliasing — shared PaperRef must not corrupt citation_index ─


def _run_synthesizer_citation_step(gaps: list[GapItem]) -> None:
    """Apply the fixed synthesizer citation_index assignment step."""
    for gap in gaps:
        gap.supporting_papers = [
            p.model_copy(update={"citation_index": i + 1}) for i, p in enumerate(gap.supporting_papers)
        ]
        id2cite = {p.paper_id: p.citation_index for p in gap.supporting_papers}
        if id2cite:
            gap.statement = _normalize_statement_citations(gap.statement, id2cite)


class TestMultiGapSharedPaperCitationIndex:
    """UF-08: citation_index must be independent per gap even when papers are shared."""

    def _make_paper(self, n: int) -> PaperRef:
        return PaperRef(paper_id=f"paper{n:02d}", title=f"Paper {n}")

    def test_shared_paper_gets_independent_index_in_each_gap(self):
        """Paper shared by two gaps must show different citation_index per gap."""
        p1, p2, p3 = self._make_paper(1), self._make_paper(2), self._make_paper(3)

        gap_a = GapItem(
            gap_type=GapType.TOPICAL,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.OPEN,
            confidence=0.9,
            statement="Gap A references paper01 and paper03.",
            supporting_papers=[p1, p2, p3],
        )
        gap_b = GapItem(
            gap_type=GapType.METHODOLOGICAL,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.OPEN,
            confidence=0.8,
            statement="Gap B references paper03 and paper01.",
            supporting_papers=[p3, p1],
        )

        _run_synthesizer_citation_step([gap_a, gap_b])

        # Gap A: p1=1, p2=2, p3=3
        assert gap_a.supporting_papers[0].citation_index == 1, "p1 in gap_a should be [1]"
        assert gap_a.supporting_papers[1].citation_index == 2, "p2 in gap_a should be [2]"
        assert gap_a.supporting_papers[2].citation_index == 3, "p3 in gap_a should be [3]"

        # Gap B: p3=1, p1=2
        assert gap_b.supporting_papers[0].citation_index == 1, "p3 in gap_b should be [1]"
        assert gap_b.supporting_papers[1].citation_index == 2, "p1 in gap_b should be [2]"

    def test_no_duplicate_citation_index_within_gap(self):
        """Each gap's citation_index list must be 1..n with no duplicates."""
        p1, p2, p3 = self._make_paper(1), self._make_paper(2), self._make_paper(3)
        p4 = self._make_paper(4)

        gap_a = GapItem(
            gap_type=GapType.TOPICAL,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.OPEN,
            confidence=0.9,
            statement="Gap A.",
            supporting_papers=[p1, p2, p3],
        )
        gap_b = GapItem(
            gap_type=GapType.CONTRADICTION,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.NEEDS_RESOLUTION,
            confidence=0.85,
            statement="Gap B.",
            supporting_papers=[p3, p4, p1, p2],
        )

        _run_synthesizer_citation_step([gap_a, gap_b])

        for gap in [gap_a, gap_b]:
            indices = [p.citation_index for p in gap.supporting_papers]
            assert indices == list(range(1, len(indices) + 1)), (
                f"Expected 1..n but got {indices} for gap {gap.gap_type}"
            )

    def test_no_cross_gap_contamination(self):
        """Processing gap B must not mutate citation_index of gap A's papers."""
        shared = self._make_paper(1)

        gap_a = GapItem(
            gap_type=GapType.TOPICAL,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.OPEN,
            confidence=0.9,
            statement="Gap A.",
            supporting_papers=[self._make_paper(2), self._make_paper(3), shared],
        )
        gap_b = GapItem(
            gap_type=GapType.METHODOLOGICAL,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.OPEN,
            confidence=0.8,
            statement="Gap B.",
            supporting_papers=[shared],
        )

        _run_synthesizer_citation_step([gap_a, gap_b])

        # shared paper is at index 2 in gap_a → should be [3]
        assert gap_a.supporting_papers[2].citation_index == 3
        # shared paper is at index 0 in gap_b → should be [1]
        assert gap_b.supporting_papers[0].citation_index == 1

    def test_statement_n_matches_own_gap_references(self):
        """[n] in statement must match the References list of the SAME card."""
        pid_x = "aabbccddeeff00112233445566778899aabbccdd"
        pid_y = "11223344556677889900aabbccddeeff11223344"

        px = PaperRef(paper_id=pid_x, title="Paper X")
        py = PaperRef(paper_id=pid_y, title="Paper Y")

        gap_a = GapItem(
            gap_type=GapType.TOPICAL,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.OPEN,
            confidence=0.9,
            statement=f"Gap A: {pid_x} shows X; {pid_y} shows Y.",
            supporting_papers=[px, py],
        )
        gap_b = GapItem(
            gap_type=GapType.METHODOLOGICAL,
            origin=GapOrigin.EXPLICIT,
            status=GapStatus.OPEN,
            confidence=0.8,
            statement=f"Gap B: {pid_y} is primary.",
            supporting_papers=[py],
        )

        _run_synthesizer_citation_step([gap_a, gap_b])

        # Gap A: px=[1], py=[2]
        assert "[1]" in gap_a.statement
        assert "[2]" in gap_a.statement
        assert pid_x not in gap_a.statement
        assert pid_y not in gap_a.statement
        assert gap_a.supporting_papers[0].citation_index == 1
        assert gap_a.supporting_papers[1].citation_index == 2

        # Gap B: py=[1] (independent of gap_a's index for py)
        assert "[1]" in gap_b.statement
        assert pid_y not in gap_b.statement
        assert gap_b.supporting_papers[0].citation_index == 1
