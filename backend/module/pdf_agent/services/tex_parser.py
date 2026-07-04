""".tex parsing via `pylatexenc.latexwalker.LatexWalker` (Step P1, PLAN §7 Phase 1).

Extracts Section/RawCitation/Figure from raw LaTeX source. Wrapped in
try/except per node walk (PLAN §9 Rủi ro: "pylatexenc không parse được
macro tự định nghĩa lạ") — a parse failure degrades to a single
unstructured Section rather than blocking the whole pipeline.
"""

from __future__ import annotations

import logging
import re

from pylatexenc.latexwalker import (
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexWalker,
    get_default_latex_context_db,
)
from pylatexenc.macrospec import MacroSpec

from backend.module.pdf_agent.graph.state import Figure, RawCitation, Section
from backend.module.pdf_agent.services.text_quote_selector import build_anchor
from backend.shared.services.latex_utils import unescape_latex

logger = logging.getLogger(__name__)

_CITE_MACROS = {"cite", "citep", "citet", "citealp", "citealt", "citeauthor", "citeyear"}
_SECTION_MACROS = {"section", "subsection", "subsubsection"}


def _context_db():
    db = get_default_latex_context_db()
    db.add_context_category(
        "pdfagent",
        prepend=True,
        macros=[MacroSpec(name, "{") for name in _CITE_MACROS]
        + [MacroSpec(name, "*{") for name in _SECTION_MACROS]
        + [
            MacroSpec("includegraphics", "[{"),
            MacroSpec("caption", "{"),
            MacroSpec("label", "{"),
            MacroSpec("bibitem", "[{"),
        ],
    )
    return db


def _arg_text(content: str, arg_node) -> str | None:
    """Return the verbatim text of a macro argument node, stripped of braces."""
    if arg_node is None:
        return None
    try:
        verbatim = content[arg_node.pos : arg_node.pos + arg_node.len]
    except (AttributeError, TypeError):
        return None
    if verbatim.startswith("{") and verbatim.endswith("}"):
        return verbatim[1:-1]
    if verbatim.startswith("[") and verbatim.endswith("]"):
        return verbatim[1:-1]
    return verbatim


def _document_body(content: str) -> tuple[str, int]:
    """Slice out \\begin{document}...\\end{document}, return (body, offset_in_original)."""
    m = re.search(r"\\begin\{document\}", content)
    if not m:
        return content, 0
    start = m.end()
    end_m = re.search(r"\\end\{document\}", content)
    end = end_m.start() if end_m else len(content)
    return content[start:end], start


def _walk_top_level(nodelist):
    return [n for n in (nodelist or []) if n is not None]


def _walk_recursive(nodelist):
    """Yield every node in the tree (macros, groups, environments, their args)."""
    for node in nodelist or []:
        if node is None:
            continue
        yield node
        if isinstance(node, LatexEnvironmentNode):
            yield from _walk_recursive(node.nodelist)
        elif isinstance(node, LatexGroupNode):
            yield from _walk_recursive(node.nodelist)
        elif isinstance(node, LatexMacroNode) and node.nodeargd and node.nodeargd.argnlist:
            for arg in node.nodeargd.argnlist:
                if arg is None:
                    continue
                yield arg
                if isinstance(arg, LatexGroupNode | LatexEnvironmentNode):
                    yield from _walk_recursive(arg.nodelist)


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)[:60] or "section"


def extract_sections(content: str) -> list[Section]:
    """Split the document body into Section blocks at top-level \\section{} boundaries.

    Subsection/subsubsection headings stay inside the parent section's raw_latex
    (MVP simplification — paragraph_ids are per-paragraph regardless of nesting).
    """
    body, _offset = _document_body(content)
    # bundle_exporter regenerates a clean \thebibliography from raw_citations —
    # strip the source's own bibliography commands so it isn't duplicated.
    body = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", "", body, flags=re.S)
    body = re.sub(r"\\bibliographystyle\{[^}]*\}", "", body)
    body = re.sub(r"\\bibliography\{[^}]*\}", "", body)
    try:
        walker = LatexWalker(body, latex_context=_context_db())
        nodelist, _, _ = walker.get_latex_nodes()
    except Exception:
        logger.warning("pylatexenc failed to parse .tex body — falling back to 1 unstructured section", exc_info=True)
        return [{"title": "Document", "raw_latex": body.strip(), "paragraph_ids": ["document-p0"]}]

    boundaries: list[tuple[str, int, int]] = []  # (title, heading_end_pos, heading_start_pos)
    for node in _walk_top_level(nodelist):
        if isinstance(node, LatexMacroNode) and node.macroname in _SECTION_MACROS:
            args = node.nodeargd.argnlist if node.nodeargd else []
            title_arg = args[-1] if args else None
            title = (_arg_text(body, title_arg) or "").strip() or "(untitled)"
            boundaries.append((title, node.pos + node.len, node.pos))

    if not boundaries:
        return [{"title": "Document", "raw_latex": body.strip(), "paragraph_ids": ["document-p0"]}]

    sections: list[Section] = []
    for i, (title, body_start, _heading_start) in enumerate(boundaries):
        body_end = boundaries[i + 1][2] if i + 1 < len(boundaries) else len(body)
        raw_latex = body[body_start:body_end].strip()
        slug = _slug(title)
        paragraphs = [p for p in re.split(r"\n\s*\n", raw_latex) if p.strip()]
        paragraph_ids = [f"{slug}-p{j}" for j in range(len(paragraphs))] or [f"{slug}-p0"]
        sections.append({"title": title, "raw_latex": raw_latex, "paragraph_ids": paragraph_ids})
    return sections


def parse_thebibliography(content: str) -> dict[str, str]:
    """Extract {key: raw_bibitem_text} from a \\begin{thebibliography} block, if present."""
    m = re.search(r"\\begin\{thebibliography\}(.*?)\\end\{thebibliography\}", content, re.S)
    if not m:
        return {}
    block = m.group(1)
    entries: dict[str, str] = {}
    items = list(re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}", block))
    for i, item in enumerate(items):
        key = item.group(1).strip()
        start = item.end()
        end = items[i + 1].start() if i + 1 < len(items) else len(block)
        entries[key] = re.sub(r"\s+", " ", block[start:end]).strip()
    return entries


def _clean_bib_title(text: str | None) -> str | None:
    """Best-effort clean title from a raw \\bibitem body.

    Used as guessed_title so citation_lookup searches/scores on the TITLE, not
    the whole reference line (authors + year + \\url{} + LaTeX escapes). Without
    this, a \\bibitem like "Authors (2022). \\textit{Title}. \\url{...}" is used
    verbatim as the search query → polluted → real papers read as "Not Found".
    """
    if not text:
        return None
    # Titles are conventionally emphasised (\textit/\emph) — our LR export does
    # exactly that; grab the emphasised span when present.
    m = re.search(r"\\(?:textit|emph|textbf)\s*\{([^{}]+)\}", text)
    candidate = m.group(1) if m else text
    candidate = re.sub(r"\\url\s*\{[^{}]*\}", " ", candidate)  # drop URLs
    candidate = re.sub(r"\\[a-zA-Z@]+\*?", " ", candidate)  # strip remaining macros (not \_ / \&)
    candidate = candidate.replace("{", " ").replace("}", " ")
    candidate = unescape_latex(candidate)  # \_ → _, \& → &, ...
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,;-")
    return candidate or None


def _find_field(entry_body: str, field: str) -> str | None:
    """Find `field = {...}` or `field = "..."` inside a BibTeX entry body (brace-depth aware)."""
    m = re.search(rf"{field}\s*=\s*([{{\"])", entry_body, re.IGNORECASE)
    if not m:
        return None
    opener = m.group(1)
    closer = "}" if opener == "{" else '"'
    start = m.end()
    if opener == "{":
        depth = 1
        i = start
        while i < len(entry_body) and depth > 0:
            if entry_body[i] == "{":
                depth += 1
            elif entry_body[i] == "}":
                depth -= 1
            i += 1
        return re.sub(r"\s+", " ", entry_body[start : i - 1]).strip()
    end = entry_body.find(closer, start)
    if end == -1:
        return None
    return re.sub(r"\s+", " ", entry_body[start:end]).strip()


def parse_bib_file(bib_content: str) -> dict[str, dict]:
    """Best-effort BibTeX parser (not a full grammar parser) — {key: {title, authors, year, doi_or_url}}."""
    entries: dict[str, dict] = {}
    starts = list(re.finditer(r"@(\w+)\s*\{\s*([^,\s}]+)\s*,", bib_content))
    for i, m in enumerate(starts):
        key = m.group(2).strip()
        body_start = m.end()
        body_end = starts[i + 1].start() if i + 1 < len(starts) else len(bib_content)
        body = bib_content[body_start:body_end]
        title = _find_field(body, "title")
        author_raw = _find_field(body, "author")
        authors = [a.strip() for a in re.split(r"\s+and\s+", author_raw)] if author_raw else None
        year_raw = _find_field(body, "year")
        year = int(re.sub(r"\D", "", year_raw)[:4]) if year_raw and re.sub(r"\D", "", year_raw) else None
        doi = _find_field(body, "doi") or _find_field(body, "url")
        entries[key] = {
            "guessed_title": title,
            "guessed_authors": authors,
            "guessed_year": year,
            "guessed_doi_or_url": doi,
        }
    return entries


def extract_citations(content: str, bib_entries: dict[str, dict] | None = None) -> list[RawCitation]:
    """Inline \\cite{} keys, enriched with bibliography/.bib metadata when available.

    Without a .bib/thebibliography entry for a key, guessed_* stays None —
    citation_lookup.py falls back to a raw_text full-text search in that case.
    """
    body, _ = _document_body(content)
    bib_entries = bib_entries or {}
    bibitem_text = parse_thebibliography(content)

    try:
        walker = LatexWalker(body, latex_context=_context_db())
        nodelist, _, _ = walker.get_latex_nodes()
    except Exception:
        logger.warning("pylatexenc failed while extracting citations", exc_info=True)
        return []

    seen: dict[str, RawCitation] = {}
    for node in _walk_recursive(nodelist):
        if not (isinstance(node, LatexMacroNode) and node.macroname in _CITE_MACROS):
            continue
        args = node.nodeargd.argnlist if node.nodeargd else []
        keys_arg = args[-1] if args else None
        keys_text = _arg_text(body, keys_arg) or ""
        for key in (k.strip() for k in keys_text.split(",")):
            if not key or key in seen:
                continue
            start = max(0, node.pos - 80)
            end = min(len(body), node.pos + node.len + 80)
            context = re.sub(r"\s+", " ", body[start:end]).strip()
            enrich = bib_entries.get(key) or {}
            bib_text = bibitem_text.get(key)
            raw_text = bib_text or enrich.get("guessed_title") or context
            seen[key] = {
                "key": key,
                "raw_text": raw_text,
                # Fall back to a cleaned title from the \bibitem so lookup doesn't
                # search/score on the whole markup-laden reference line.
                "guessed_title": enrich.get("guessed_title") or _clean_bib_title(bib_text),
                "guessed_authors": enrich.get("guessed_authors"),
                "guessed_year": enrich.get("guessed_year"),
                "guessed_doi_or_url": enrich.get("guessed_doi_or_url"),
            }

    # Bibliography/.bib entries never \cite{}'d in the body still deserve verification
    # (e.g. a reading-list reference) — add the leftovers with no inline context.
    for key, text in bibitem_text.items():
        if key not in seen:
            enrich = bib_entries.get(key) or {}
            seen[key] = {
                "key": key,
                "raw_text": text,
                "guessed_title": enrich.get("guessed_title") or _clean_bib_title(text),
                "guessed_authors": enrich.get("guessed_authors"),
                "guessed_year": enrich.get("guessed_year"),
                "guessed_doi_or_url": enrich.get("guessed_doi_or_url"),
            }
    for key, enrich in bib_entries.items():
        if key not in seen:
            seen[key] = {
                "key": key,
                "raw_text": enrich.get("guessed_title") or key,
                "guessed_title": enrich.get("guessed_title"),
                "guessed_authors": enrich.get("guessed_authors"),
                "guessed_year": enrich.get("guessed_year"),
                "guessed_doi_or_url": enrich.get("guessed_doi_or_url"),
            }

    return list(seen.values())


def extract_figures(content: str) -> list[Figure]:
    """\\includegraphics{} anywhere in the body, paired with \\caption{}/\\label{} if inside a figure env.

    `image_path`/`missing` are NOT resolved here — the caller (zip_bundle /
    parse_document node) checks file existence relative to the right base dir.
    `image_path` is set to the raw \\includegraphics argument until resolved.
    """
    body, _ = _document_body(content)
    try:
        walker = LatexWalker(body, latex_context=_context_db())
        nodelist, _, _ = walker.get_latex_nodes()
    except Exception:
        logger.warning("pylatexenc failed while extracting figures", exc_info=True)
        return []

    figures: list[Figure] = []

    def _scan(nodes, in_figure_env: LatexEnvironmentNode | None):
        for node in nodes or []:
            if node is None:
                continue
            if isinstance(node, LatexEnvironmentNode):
                next_env = node if node.environmentname == "figure" else in_figure_env
                _scan(node.nodelist, next_env)
                continue
            if isinstance(node, LatexGroupNode):
                _scan(node.nodelist, in_figure_env)
                continue
            if isinstance(node, LatexMacroNode):
                if node.nodeargd and node.nodeargd.argnlist:
                    _scan(node.nodeargd.argnlist, in_figure_env)
                if node.macroname == "includegraphics":
                    args = node.nodeargd.argnlist if node.nodeargd else []
                    path_arg = args[-1] if args else None
                    raw_path = (_arg_text(body, path_arg) or "").strip()
                    if not raw_path:
                        continue
                    caption = label = None
                    anchor_start, anchor_end = node.pos, node.pos + node.len
                    if in_figure_env is not None:
                        anchor_start = in_figure_env.pos
                        anchor_end = in_figure_env.pos + in_figure_env.len
                        for sib in _walk_recursive(in_figure_env.nodelist):
                            if isinstance(sib, LatexMacroNode) and sib.macroname == "caption":
                                sargs = sib.nodeargd.argnlist if sib.nodeargd else []
                                caption = _arg_text(body, sargs[-1]) if sargs else None
                            elif isinstance(sib, LatexMacroNode) and sib.macroname == "label":
                                sargs = sib.nodeargd.argnlist if sib.nodeargd else []
                                label = _arg_text(body, sargs[-1]) if sargs else None
                    anchor = build_anchor(body, anchor_start, anchor_end)
                    figures.append(
                        {
                            "image_path": raw_path,
                            "caption": caption,
                            "label": label,
                            "anchor": anchor,
                            "page_number": None,
                            "missing": True,  # default — resolved by caller
                        }
                    )

    _scan(nodelist, None)
    return figures
