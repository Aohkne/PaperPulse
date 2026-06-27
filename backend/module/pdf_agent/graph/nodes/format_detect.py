"""Step P0 — Upload + Format Detection (PLAN §7 Phase 1)."""

from __future__ import annotations

from typing import Literal

from backend.module.pdf_agent.graph.state import PDFAgentState


class UnsupportedFormatError(Exception):
    pass


def detect_format(raw_bytes: bytes) -> Literal["pdf", "tex", "tex_bundle"]:
    if raw_bytes.startswith(b"%PDF"):
        return "pdf"
    if raw_bytes.startswith(b"PK"):  # zip magic bytes
        return "tex_bundle"
    text_head = raw_bytes[:2000].decode("utf-8", errors="ignore")
    if r"\documentclass" in text_head or r"\begin{document}" in text_head:
        return "tex"
    raise UnsupportedFormatError("Unrecognized file format — only .pdf, .tex, and .zip (tex_bundle) are supported")


async def format_detect_node(state: PDFAgentState) -> dict:
    with open(state["raw_file_path"], "rb") as f:
        head = f.read(2000)
    input_format = detect_format(head)
    return {"input_format": input_format}
