"""Render ParsedDocument → editable `.zip` bundle (Step P2, PLAN §7 Phase 3).

Figures are spliced into their owning section's `raw_latex` in Python
(at the figure's anchor position) before templating — Jinja2 only ever
sees flat strings, so anchor-aware placement has to happen here.
"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.module.pdf_agent.graph.state import Figure, RawCitation, Section

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

_REFERENCES_TITLE_RE = re.compile(r"^(references?|bibliography)$", re.IGNORECASE)


def _figure_block(fig: Figure) -> str:
    lines = [
        r"\begin{figure}[h]",
        r"  \centering",
        rf"  \includegraphics[width=0.8\textwidth]{{figures/{os.path.basename(fig['image_path'])}}}",
    ]
    if fig.get("caption"):
        lines.append(rf"  \caption{{{fig['caption']}}}")
    if fig.get("label"):
        lines.append(rf"  \label{{{fig['label']}}}")
    lines.append(r"\end{figure}")
    return "\n".join(lines)


def strip_missing_figures_from_sections(sections: list[Section], figures: list[Figure]) -> list[Section]:
    """Remove a missing figure's original `\\includegraphics`/`figure` block from its
    section's raw_latex (.tex/.tex_bundle branches copy source text verbatim, so the
    literal figure environment is still in there even though the referenced image
    file doesn't exist) — leaving it in would break `pdflatex` compilation.
    """
    stripped = [dict(s) for s in sections]
    for fig in figures:
        if not fig.get("missing"):
            continue
        anchor = fig.get("anchor")
        exact = anchor.get("exact") if anchor else None
        if not exact:
            continue
        for s in stripped:
            if exact in s["raw_latex"]:
                s["raw_latex"] = s["raw_latex"].replace(exact, "", 1)
                break
    return stripped


def splice_figures_into_sections(
    sections: list[Section], figures: list[Figure]
) -> tuple[list[Section], list[Figure]]:
    """Insert each figure's LaTeX block right after its anchor's exact text inside
    whichever section contains it. Figures with no match anywhere (no anchor, or the
    anchor text isn't a substring of any section — e.g. it fell inside text that got
    filtered out) become `leftover` and are rendered in a trailing "Figures" section
    instead of being silently dropped.
    """
    spliced = [dict(s) for s in sections]
    leftover: list[Figure] = []
    for fig in figures:
        if fig.get("missing"):
            continue
        anchor = fig.get("anchor")
        exact = anchor.get("exact") if anchor else None

        # tex/tex_bundle branches: tex_parser builds the anchor around the figure's
        # OWN `\begin{figure}...\includegraphics{...}...\end{figure}` block, which is
        # already verbatim inside the section's raw_latex (copied straight from the
        # source .tex) — splicing a freshly-rendered figure block on top of it would
        # duplicate the figure. Only the pdf/mineru branches (whose section text is
        # plain extracted prose with no LaTeX figure markup at all) need a block spliced
        # in. Detect "already embedded" via the anchor text itself rather than threading
        # input_format through every layer — pdf/mineru anchors are always plain prose,
        # so they can never contain a literal "\includegraphics".
        if exact and r"\includegraphics" in exact:
            continue

        block = _figure_block(fig)
        placed = False
        if exact:
            for s in spliced:
                idx = s["raw_latex"].find(exact)
                if idx != -1:
                    insert_at = idx + len(exact)
                    s["raw_latex"] = (
                        s["raw_latex"][:insert_at] + "\n\n" + block + "\n\n" + s["raw_latex"][insert_at:]
                    )
                    placed = True
                    break
        if not placed:
            leftover.append(fig)
    return spliced, leftover


def clean_sections(sections: list[Section], figures: list[Figure]) -> list[Section]:
    """Drop reference-list sections (the bibliography is regenerated separately from
    raw_citations) and strip missing-figure blocks (Phase 3 requirement: a missing
    figure's `\\includegraphics` must not appear in the rendered .tex at all).

    Callers that run analysis on section text (critic agent, annotation anchors) MUST
    use this — not the raw `sections` from parse_document — otherwise an annotation can
    anchor to text that gets stripped before the user ever sees it, making it permanently
    un-actionable (refind_anchor would never find it again).
    """
    content_sections = [s for s in sections if not _REFERENCES_TITLE_RE.match(s["title"].strip())]
    return strip_missing_figures_from_sections(content_sections, figures)


def render_editable_bundle(
    sections: list[Section],
    figures: list[Figure],
    raw_citations: list[RawCitation],
    output_dir: str,
) -> dict:
    """Render sections+figures+citations into `{output_dir}/main.tex` + `figures/` + `bundle.zip`.

    `sections` is expected to already be cleaned via `clean_sections()` — the caller
    (render_bundle_node) does this once and persists the result back into graph state so
    every later step (critic, annotations) agrees on the same final text.
    """
    bundle_dir = Path(output_dir)
    figures_out = bundle_dir / "figures"
    figures_out.mkdir(parents=True, exist_ok=True)

    spliced_sections, leftover_figures = splice_figures_into_sections(sections, figures)

    for fig in figures:
        if fig.get("missing"):
            continue
        src = Path(fig["image_path"])
        if src.exists():
            dest = figures_out / src.name
            if src.resolve() != dest.resolve():
                shutil.copy(src, dest)

    bibliography = [
        {"key": c.get("key") or f"ref{i}", "raw_text": c["raw_text"]} for i, c in enumerate(raw_citations)
    ]

    template = _env.get_template("pdf_agent_document.tex.j2")
    main_tex = template.render(
        sections=spliced_sections,
        leftover_figures=[{"block": _figure_block(f)} for f in leftover_figures],
        bibliography=bibliography,
    )

    main_tex_path = bundle_dir / "main.tex"
    main_tex_path.write_text(main_tex, encoding="utf-8")

    bundle_path = bundle_dir / "bundle.zip"
    _rezip(main_tex_path, figures_out, bundle_path)

    return {
        "bundle_path": str(bundle_path),
        "main_tex_path": str(main_tex_path),
        "figures_dir": str(figures_out),
    }


def rezip_bundle(main_tex_path: str, figures_dir: str, bundle_path: str) -> str:
    """Regenerate bundle.zip after the user edits main.tex (Accept/Apply mutate it directly)."""
    _rezip(Path(main_tex_path), Path(figures_dir), Path(bundle_path))
    return bundle_path


def _rezip(main_tex_path: Path, figures_dir: Path, bundle_path: Path) -> None:
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(main_tex_path, arcname="main.tex")
        if figures_dir.exists():
            for f in figures_dir.glob("*"):
                if f.is_file():
                    zf.write(f, arcname=f"figures/{f.name}")
