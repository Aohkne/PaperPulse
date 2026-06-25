"""Step P1 — Parse → Structured Document. Dispatches by `input_format` (PLAN §7 Phase 1/2)."""

from __future__ import annotations

import logging
import os
import re
from glob import glob
from pathlib import Path

from backend.config import get_settings
from backend.module.pdf_agent.graph.state import Figure, PDFAgentState
from backend.module.pdf_agent.services import mineru_client, pdf_parser, tex_parser, zip_bundle

logger = logging.getLogger(__name__)


class PageLimitExceededError(Exception):
    pass


def _doc_dir(doc_id: str) -> Path:
    return Path(get_settings().pdf_agent_output_dir) / doc_id


async def parse_document_node(state: PDFAgentState) -> dict:
    input_format = state["input_format"]
    if input_format == "tex_bundle":
        return await _parse_tex_bundle(state)
    if input_format == "tex":
        return _parse_bare_tex(state)
    if input_format == "pdf":
        return await _parse_pdf(state)
    raise ValueError(f"Unknown input_format: {input_format}")


def _parse_bare_tex(state: PDFAgentState) -> dict:
    with open(state["raw_file_path"], encoding="utf-8", errors="ignore") as f:
        content = f.read()

    sections = tex_parser.extract_sections(content)
    raw_citations = tex_parser.extract_citations(content)
    figures = tex_parser.extract_figures(content)
    # Bare .tex has no accompanying files — every \includegraphics target is unresolvable.
    for fig in figures:
        fig["missing"] = True

    return {"sections": sections, "raw_citations": raw_citations, "figures": figures}


async def _parse_tex_bundle(state: PDFAgentState) -> dict:
    doc_dir = _doc_dir(state["doc_id"])
    extract_dir = doc_dir / "extracted"
    figures_out = doc_dir / "figures"
    figures_out.mkdir(parents=True, exist_ok=True)

    zip_bundle.extract_zip_safe(state["raw_file_path"], str(extract_dir))
    main_tex_src = zip_bundle.find_main_tex(str(extract_dir))
    with open(main_tex_src, encoding="utf-8", errors="ignore") as f:
        content = f.read()

    bib_entries: dict = {}
    bib_files = glob(f"{extract_dir}/**/*.bib", recursive=True)
    if bib_files:
        try:
            with open(bib_files[0], encoding="utf-8", errors="ignore") as f:
                bib_entries = tex_parser.parse_bib_file(f.read())
        except OSError:
            logger.warning("Failed to read .bib file %s", bib_files[0], exc_info=True)

    sections = tex_parser.extract_sections(content)
    raw_citations = tex_parser.extract_citations(content, bib_entries)
    figures = tex_parser.extract_figures(content)

    main_tex_dir = os.path.dirname(main_tex_src)
    for fig in figures:
        resolved = zip_bundle.resolve_relative(main_tex_dir, fig["image_path"])
        if os.path.isfile(resolved):
            dest = figures_out / os.path.basename(resolved)
            dest.write_bytes(Path(resolved).read_bytes())
            fig["image_path"] = str(dest)
            fig["missing"] = False
        else:
            fig["missing"] = True

    return {"sections": sections, "raw_citations": raw_citations, "figures": figures}


async def _parse_pdf(state: PDFAgentState) -> dict:
    settings = get_settings()
    page_count = pdf_parser.get_pdf_page_count(state["raw_file_path"])
    if page_count > settings.pdf_agent_max_pages:
        raise PageLimitExceededError(
            f"PDF có {page_count} trang, vượt giới hạn {settings.pdf_agent_max_pages} trang"
        )

    doc_dir = _doc_dir(state["doc_id"])
    figures_out = doc_dir / "figures"
    result = await _run_pdf_extraction(state["raw_file_path"], str(figures_out))

    figures: list[Figure] = result["figures"]
    raw_citations = await pdf_parser.parse_references_with_llm(result["raw_reference_lines"])
    sections = [s for s in result["sections"] if not re.match(r"(?i)^(references?|bibliography)$", s["title"].strip())]

    return {"sections": sections, "raw_citations": raw_citations, "figures": figures}


async def _run_pdf_extraction(pdf_path: str, figures_out: str) -> dict:
    """MinerU first (matches PLAN's chosen tech), falls back to PyMuPDF if the
    `mineru` binary isn't installed in this environment or the subprocess fails —
    see mineru_client.py's module docstring for why this isn't a hard dependency.
    """
    if mineru_client.is_available():
        try:
            return await mineru_client.extract_structure_from_pdf(pdf_path, figures_out)
        except (mineru_client.MinerUTimeoutError, mineru_client.MinerUExecutionError):
            logger.warning("MinerU failed, falling back to PyMuPDF", exc_info=True)
    else:
        logger.info("mineru binary not found on PATH — using PyMuPDF fallback")
    return await pdf_parser.extract_structure_from_pdf(pdf_path, figures_out)
