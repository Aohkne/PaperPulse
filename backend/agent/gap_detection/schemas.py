"""Data models for the Gap Detection pipeline.

Defines Pydantic v2 models, enums, and LangGraph state for the
research-gap detection workflow.
"""

from __future__ import annotations

import warnings
from enum import StrEnum
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ── Enums ────────────────────────────────────────────────────────────


class GapType(StrEnum):
    """Category of a detected research gap."""

    TOPICAL = "topical"
    METHODOLOGICAL = "methodological"
    CONTRADICTION = "contradiction"


class GapOrigin(StrEnum):
    """How the gap was discovered — determines citation rules.

    EXPLICIT    → gap stated verbatim by authors as future work / open problem.
    LIMITATION  → gap extracted from an explicit limitation statement;
                  the resulting GapItem MUST cite the limitation source.
    INFERRED    → gap inferred from cross-paper comparison or contradiction;
                  the resulting GapItem cites the evidence papers.
    """

    EXPLICIT = "explicit"
    LIMITATION = "limitation"
    INFERRED = "inferred"


class GapStatus(StrEnum):
    """Resolution status of a gap."""

    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    NEEDS_RESOLUTION = "needs_resolution"


# ── Data Models ──────────────────────────────────────────────────────


class PaperRef(BaseModel):
    """Lightweight snapshot of a paper used as a citation reference."""

    model_config = ConfigDict(populate_by_name=True)

    paper_id: str
    title: str
    year: int | None = None
    url: str | None = None
    abstract: str | None = None
    source: str | None = None


class ExtractedPaperData(BaseModel):
    """Structured data extracted from a single paper by the ExtractorNode."""

    model_config = ConfigDict(populate_by_name=True)

    paper_ref: PaperRef
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    methodology: str | None = None
    dataset: str | None = None
    population: str | None = None
    metrics: list[str] = Field(default_factory=list)
    key_claims: list[str] = Field(default_factory=list)
    limitation_statements: list[str] = Field(default_factory=list)
    pdf_url: str | None = None
    extraction_source: str = "abstract"  # "abstract" | "fulltext"
    # Raw abstract from Semantic Scholar (persisted by extractor, TIP-G06-R).
    # Independent from LLM-extracted fields — used by verifier Case C so that
    # verification source does not circularly contain the limitation_statements
    # that produced the gap being verified.
    abstract: str | None = None


class GapItem(BaseModel):
    """A single detected research gap with provenance and confidence."""

    model_config = ConfigDict(populate_by_name=True)

    # --- Phase 2 fields (preserved) ---
    gap_type: GapType
    origin: GapOrigin = GapOrigin.INFERRED
    status: GapStatus = GapStatus.OPEN
    statement: str
    supporting_papers: list[PaperRef] = Field(default_factory=list)
    context_explanation: str | None = None
    limitation_origin: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_score: float | None = None
    false_gap_flag: bool = False
    verified: bool = False

    # --- Phase 3 fields (all optional with defaults — backward compat) ---
    falsifiability_condition: str | None = None
    suggested_method: str | None = None
    quality_score: float | None = None
    quality_breakdown: dict[str, float] | None = None
    evidence_quotes: list[str] = Field(default_factory=list)
    analysis: str | None = None  # NFC-normalized per-gap narrative from synthesizer

    @model_validator(mode="after")
    def _warn_empty_limitation_citations(self) -> GapItem:
        """Emit a warning when origin=LIMITATION but no citations provided.

        Validation logic lives in the node layer; the schema only warns.
        """
        if self.origin == GapOrigin.LIMITATION and len(self.supporting_papers) == 0:
            warnings.warn(
                "GapItem with origin=LIMITATION has no supporting_papers. "
                "The producing node should attach the limitation source.",
                UserWarning,
                stacklevel=2,
            )
        return self


class GapReport(BaseModel):
    """Final output of the gap-detection pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    papers_analyzed: int
    gaps: list[GapItem] = Field(default_factory=list)
    narrative: str = ""
    baseline_triggered: bool = False


# ── TIP-404: Source resolution layer ────────────────────────────────


class CorpusRole(StrEnum):
    """Role of a paper in the gap-detection corpus.

    USER       — retrieved in response to the user's query (primary signal).
    BACKGROUND — broad background pool fetched independently (context signal).
    """

    USER = "user"
    BACKGROUND = "background"


class CanonicalPaper(BaseModel):
    """A paper resolved from one or more raw source records.

    Produced by ``source_resolution.resolve_papers()``.  Multiple raw records
    that share the same DOI, normalised title, or S2 paperId are merged into
    a single CanonicalPaper so downstream nodes never process duplicates.

    Fields mirror ``Paper`` (shared/models/paper.py) plus resolution metadata.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Resolution identity
    id: str  # "doi:<norm>" | "title:<norm>" | "s2:<paper_id>"
    sources: list[str] = Field(default_factory=list)   # e.g. ["s2", "arxiv"]
    corpus_role: CorpusRole = CorpusRole.USER
    fulltext_available: bool = False

    # Paper metadata (merged, fulltext-record wins on conflict)
    title: str
    abstract: str | None = None
    fulltext: str | None = None
    year: int | None = None
    citation_count: int | None = None
    authors: list[str] = Field(default_factory=list)
    url: str | None = None
    open_access_pdf: str | None = None
    external_ids: dict = Field(default_factory=dict)
    s2_paper_id: str | None = None   # S2 paperId (paper_id in Paper model)
    is_influential: bool = False


# ── Stage A output ──────────────────────────────────────────────────


class GapQuery(BaseModel):
    """Structured query object from Stage A — Query Analyzer.

    Produced by 1 LLM call that converts a raw topic string (Vietnamese or English)
    into faceted search parameters.
    """

    model_config = ConfigDict(populate_by_name=True)

    core_topic: str
    facets: list[str] = Field(default_factory=list)
    year_range: tuple[int, int] = (2019, 2026)
    field_of_study: str = "Computer Science"
    recency_bias: bool = True
    seminal_bias: bool = True
    user_intent: str | None = None


# ── LangGraph State ─────────────────────────────────────────────────


class GapDetectionState(TypedDict, total=False):
    """LangGraph state dictionary for the gap-detection graph.

    Using ``total=False`` so every key is optional — nodes populate
    fields incrementally as the graph executes.
    """

    session_papers: list[PaperRef]
    baseline_triggered: bool
    extracted_data: list[ExtractedPaperData]
    candidate_gaps: list[GapItem]
    verified_gaps: list[GapItem]
    final_report: GapReport | None
    gap_query: GapQuery | None
