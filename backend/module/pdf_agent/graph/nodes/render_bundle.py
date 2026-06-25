"""Step P2 — Render Editable .tex → `.zip` bundle (PLAN §7 Phase 3)."""

from __future__ import annotations

from pathlib import Path

from backend.config import get_settings
from backend.module.pdf_agent.graph.state import PDFAgentState
from backend.module.pdf_agent.services import bundle_exporter


async def render_bundle_node(state: PDFAgentState) -> dict:
    doc_dir = Path(get_settings().pdf_agent_output_dir) / state["doc_id"]
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Clean once here and persist back into state — batch_analysis (P3) and
    # build_annotations (P4) must operate on the SAME text that ends up in main.tex,
    # otherwise an annotation could anchor to a missing-figure block that this step
    # strips out, making it permanently un-actionable.
    cleaned_sections = bundle_exporter.clean_sections(state["sections"], state["figures"])

    result = bundle_exporter.render_editable_bundle(
        sections=cleaned_sections,
        figures=state["figures"],
        raw_citations=state["raw_citations"],
        output_dir=str(doc_dir),
    )
    return {
        "sections": cleaned_sections,
        "bundle_path": result["bundle_path"],
        "main_tex_path": result["main_tex_path"],
    }
