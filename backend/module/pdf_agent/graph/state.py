"""PDFAgentState — graph riêng, KHÔNG thêm field vào `ResearchState` (PLAN §3).

Mọi nested object là TypedDict (không phải pydantic) để LangGraph's
JsonPlusSerializer checkpoint thẳng ra JSON, không cần allow-list msgpack
module như `ResearchState` phải làm với Paper/Claim/Theme.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class TextQuoteSelector(TypedDict):
    """W3C Web Annotation TextQuoteSelector — anchor bằng quote+context, không offset số."""

    exact: str
    prefix: str
    suffix: str


class Figure(TypedDict):
    image_path: str
    caption: str | None
    label: str | None
    anchor: TextQuoteSelector | None
    page_number: int | None
    missing: bool


class Section(TypedDict):
    title: str
    raw_latex: str
    paragraph_ids: list[str]


class RawCitation(TypedDict):
    key: str | None
    raw_text: str
    guessed_title: str | None
    guessed_authors: list[str] | None
    guessed_year: int | None
    guessed_doi_or_url: str | None


class Annotation(TypedDict):
    id: str
    type: Literal["suggest", "warning"]
    anchor: TextQuoteSelector
    aspect: str
    comment: str
    suggested_fix: str | None
    evidence: dict | None
    status: Literal["pending", "accepted", "rejected", "dismissed"]


class PDFAgentState(TypedDict, total=False):
    doc_id: str
    user_id: str | None
    input_format: Literal["pdf", "tex", "tex_bundle"]
    raw_file_path: str

    # ── Step P1 ──
    sections: list[Section]
    raw_citations: list[RawCitation]
    figures: list[Figure]

    # ── Step P2 ──
    bundle_path: str
    main_tex_path: str

    # ── Step P3 (intermediate — consumed by build_annotations, P4) ──
    critic_results: list[dict]  # [{"section_title", "issues": [{"aspect","quote","comment","suggested_fix"}]}]
    citation_verdicts: list[dict]  # 1:1 with raw_citations — [{"verdict","confidence","evidence"}]
    link_results: list[dict]  # [{"section_title","url","alive","status_code"}]

    # ── Step P4 ──
    annotations: list[Annotation]

    # ── Step P6 ──
    review_id: str | None

    error: str | None
