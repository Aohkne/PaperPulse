"""Step P4 — Build Annotation Store from P3's 3 parallel results (PLAN §7 Phase 5).

`warning` annotations NEVER get `suggested_fix` (hard invariant — Non-goals: no
auto-fix for citations, no implied "Accept" affordance on the frontend).
"""

from __future__ import annotations

from uuid import uuid4

from backend.module.pdf_agent.graph.state import Annotation, PDFAgentState, Section
from backend.module.pdf_agent.services.text_quote_selector import build_anchor

_VERDICT_ASPECT = {"Metadata Mismatch": "metadata_mismatch", "Not Found": "citation_not_found"}
_VERDICT_COMMENT = {
    "Metadata Mismatch": "Found a closely matching paper, but its metadata (year/authors) doesn't fully match the original citation.",
    "Not Found": "Could not find this source on Semantic Scholar/OpenAlex/arXiv — it may be fabricated, or it may be a rare/unindexed source such as a book. Not a definitive conclusion.",
}


def _section_by_title(sections: list[Section], title: str) -> Section | None:
    for s in sections:
        if s["title"] == title:
            return s
    return None


def _suggest_annotations(state: PDFAgentState) -> list[Annotation]:
    out: list[Annotation] = []
    for entry in state.get("critic_results") or []:
        section = _section_by_title(state["sections"], entry["section_title"])
        if section is None:
            continue
        for issue in entry["issues"]:
            quote = issue.get("quote", "")
            pos = section["raw_latex"].find(quote)
            if pos == -1:
                continue
            anchor = build_anchor(section["raw_latex"], pos, pos + len(quote))
            out.append(
                {
                    "id": str(uuid4()),
                    "type": "suggest",
                    "anchor": anchor,
                    "aspect": issue.get("aspect", "clarity"),
                    "comment": issue.get("comment", ""),
                    "suggested_fix": issue.get("suggested_fix"),
                    "evidence": None,
                    "status": "pending",
                }
            )
    return out


def _citation_warning_annotations(state: PDFAgentState) -> list[Annotation]:
    out: list[Annotation] = []
    citations = state["raw_citations"]
    verdicts = state.get("citation_verdicts") or []
    for citation, verdict in zip(citations, verdicts):
        label = verdict.get("verdict")
        if label not in _VERDICT_ASPECT:
            continue  # "Verified" — no warning
        key = citation.get("key")
        anchor = {
            "exact": citation["raw_text"],
            "prefix": rf"\bibitem{{{key}}} " if key else "",
            "suffix": "",
        }
        out.append(
            {
                "id": str(uuid4()),
                "type": "warning",
                "anchor": anchor,
                "aspect": _VERDICT_ASPECT[label],
                "comment": _VERDICT_COMMENT[label],
                "suggested_fix": None,
                "evidence": verdict.get("evidence"),
                "status": "pending",
            }
        )
    return out


def _link_warning_annotations(state: PDFAgentState) -> list[Annotation]:
    out: list[Annotation] = []
    for link in state.get("link_results") or []:
        if link.get("alive"):
            continue
        section = _section_by_title(state["sections"], link["section_title"])
        url = link["url"]
        if section is None:
            continue
        pos = section["raw_latex"].find(url)
        if pos == -1:
            continue
        anchor = build_anchor(section["raw_latex"], pos, pos + len(url))
        status = link.get("status_code")
        out.append(
            {
                "id": str(uuid4()),
                "type": "warning",
                "anchor": anchor,
                "aspect": "broken_link",
                "comment": (f"This link returned HTTP {status}" if status else "This link did not respond")
                + " — please check the URL.",
                "suggested_fix": None,
                "evidence": {"url": url, "status_code": status},
                "status": "pending",
            }
        )
    return out


def _missing_asset_annotations(state: PDFAgentState) -> list[Annotation]:
    out: list[Annotation] = []
    for fig in state.get("figures") or []:
        if not fig.get("missing") or not fig.get("anchor"):
            continue
        out.append(
            {
                "id": str(uuid4()),
                "type": "warning",
                "anchor": fig["anchor"],
                "aspect": "missing_asset",
                "comment": "This figure is referenced but its file is missing. Please re-upload as a .zip including the image folder.",
                "suggested_fix": None,
                "evidence": None,
                "status": "pending",
            }
        )
    return out


async def build_annotations_node(state: PDFAgentState) -> dict:
    annotations = (
        _suggest_annotations(state)
        + _citation_warning_annotations(state)
        + _link_warning_annotations(state)
        + _missing_asset_annotations(state)
    )
    return {"annotations": annotations}
