"""Best-effort LaTeX -> PDF/Markdown rendering, shared by Reviews export and PDF Agent
export so both features stay on one renderer instead of duplicating ~300 lines of
LaTeX parsing (not a full TeX engine - good enough for our generated/edited content)."""

from __future__ import annotations

import re
from pathlib import Path

from backend.shared.services.latex_utils import unescape_latex

# DejaVu Sans is a Unicode TTF (bundled under backend/shared/assets/fonts, see
# LICENSE_DEJAVU.txt there) so the PDF export can render any Unicode text -
# curly quotes, em-dashes, math symbols, Vietnamese diacritics, etc. - instead
# of being limited to fpdf2's built-in Latin-1-only core fonts (Helvetica/Courier).
_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_SANS_REGULAR = _FONTS_DIR / "DejaVuSans.ttf"
_SANS_BOLD = _FONTS_DIR / "DejaVuSans-Bold.ttf"
_SANS_ITALIC = _FONTS_DIR / "DejaVuSans-Oblique.ttf"
_MONO_REGULAR = _FONTS_DIR / "DejaVuSansMono.ttf"

# fpdf2's multi_cell raises FPDFException ("Not enough horizontal space to render
# a single character") when one unbroken run of non-space characters is wider than
# the page - common with bare DOI/arXiv URLs in citations. fpdf2 honors the
# soft-hyphen character (U+00AD) as a word-break hint, so sprinkle one into any
# long unbroken token to give it somewhere to wrap instead of crashing the export.
_LONG_TOKEN_RE = re.compile(r"\S{61,}")


def _break_long_token(match: re.Match) -> str:
    token = match.group(0)
    return "\u00ad".join(token[i : i + 60] for i in range(0, len(token), 60))


def _sanitize(text: str) -> str:
    """Break up unbroken long tokens (e.g. DOI/arXiv URLs) so fpdf2 can wrap them.

    No longer transliterates/drops Unicode characters - the PDF renders with a
    Unicode TTF font (DejaVu Sans), so curly quotes, em-dashes, math symbols,
    and non-Latin scripts render natively instead of being replaced with '?'.
    """
    return _LONG_TOKEN_RE.sub(_break_long_token, text)


# -- LaTeX parsing (best-effort - not a full TeX engine) ----------------------

_Inext_lineINE_RE = re.compile(
    r"\\href\{(?P<href_url>[^{}]*)\}\{(?P<href_text>[^{}]*)\}"
    r"|\\url\{(?P<url>[^{}]*)\}"
    r"|\\cite[tp]?\{(?P<cite>[^{}]*)\}"
    r"|\\textbf\{(?P<bf>[^{}]*)\}"
    r"|\\textit\{(?P<it>[^{}]*)\}"
    r"|\\emph\{(?P<emph>[^{}]*)\}"
    r"|\$(?P<math1>[^$]+)\$"
    r"|\\\((?P<math2>.+?)\\\)"
    r"|\\\\"
    # Markdown fallback (legacy content saved before the LaTeX migration)
    r"|\*\*(?P<mdbf>[^*]+)\*\*"
    r"|\*(?P<mdit>[^*]+)\*"
    r"|__(?P<mdbf2>[^_]+)__"
    r"|`(?P<mdcode>[^`]+)`"
    r"|\[(?P<mdlinktext>[^\]]+)\]\((?P<mdlinkurl>[^)]+)\)"
)


def _build_bib_key_map(content: str) -> dict[str, str]:
    """Map each \\bibitem{key} to its 1-based reference number, in document order,
    so in-text \\cite{key} and the reference list both show the same [n]."""
    bib_map: dict[str, str] = {}
    for key in re.findall(r"\\bibitem\{([^{}]*)\}", content):
        if key not in bib_map:
            bib_map[key] = str(len(bib_map) + 1)
    return bib_map


def _inline_to_plain(text: str, bib_map: dict[str, str] | None = None) -> str:
    """Render inline LaTeX markup as plain text (for the fpdf2 PDF renderer)."""

    def repl(m: re.Match) -> str:
        if m.lastgroup == "href_text":
            return f"{m.group('href_text')} ({m.group('href_url')})"
        if m.lastgroup == "mdlinktext":
            return f"{m.group('mdlinktext')} ({m.group('mdlinkurl')})"
        if m.lastgroup == "url":
            return m.group("url")
        if m.lastgroup == "cite":
            key = m.group("cite")
            num = (bib_map or {}).get(key)
            return f"[{num}]" if num else f"({key})"
        if m.lastgroup in ("bf", "it", "emph", "math1", "math2", "mdbf", "mdbf2", "mdit", "mdcode"):
            return m.group(m.lastgroup)
        return " "  # \\ line break

    return unescape_latex(_Inext_lineINE_RE.sub(repl, text))


def _inline_to_markdown(text: str, bib_map: dict[str, str] | None = None) -> str:
    """Render inline LaTeX markup as Markdown."""

    def repl(m: re.Match) -> str:
        if m.lastgroup == "href_text":
            return f"[{m.group('href_text')}]({m.group('href_url')})"
        if m.lastgroup == "mdlinktext":
            return f"[{m.group('mdlinktext')}]({m.group('mdlinkurl')})"
        if m.lastgroup == "url":
            return f"<{m.group('url')}>"
        if m.lastgroup == "cite":
            key = m.group("cite")
            num = (bib_map or {}).get(key)
            return f"[{num}]" if num else f"({key})"
        if m.lastgroup in ("bf", "mdbf", "mdbf2"):
            return f"**{m.group(m.lastgroup)}**"
        if m.lastgroup in ("it", "emph", "mdit"):
            return f"*{m.group(m.lastgroup)}*"
        if m.lastgroup == "mdcode":
            return f"`{m.group('mdcode')}`"
        if m.lastgroup in ("math1", "math2"):
            return f"${m.group(m.lastgroup)}$"
        return "  \n"  # \\ line break

    return unescape_latex(_Inext_lineINE_RE.sub(repl, text))


def _parse_latex_body(content: str, bib_map: dict[str, str] | None = None) -> list[tuple[str, object]]:
    """Split .tex source into a sequence of (kind, data) blocks for rendering.

    kind is one of: h1, h2, h3, item, item_num, bibitem, quote_start, quote_end,
    verbatim, hr, blank, para.
    """
    body_match = re.search(r"\\begin\{document\}(.*)\\end\{document\}", content, re.S)
    body = body_match.group(1) if body_match else content

    blocks: list[tuple[str, object]] = []
    list_stack: list[str] = []
    enum_counters: list[int] = []
    in_verbatim = False
    in_bibliography = False
    pending_bib_num: str | None = None

    for raw_line in body.split("\n"):
        line = raw_line.strip()

        if in_verbatim:
            if line == r"\end{verbatim}":
                in_verbatim = False
            else:
                blocks.append(("verbatim", raw_line))
            continue

        if not line:
            blocks.append(("blank", ""))
            continue
        if line.startswith("%"):
            continue
        if line in (r"\maketitle",) or re.match(r"^\\(title|author|date)\{", line):
            continue
        if re.match(r"^\\(documentclass|usepackage)\b", line) or line in (r"\begin{document}", r"\end{document}"):
            continue
        if line == r"\begin{verbatim}":
            in_verbatim = True
            continue

        if re.match(r"^\\begin\{thebibliography\}", line):
            in_bibliography = True
            blocks.append(("h2", "References"))
            continue
        if line == r"\end{thebibliography}":
            in_bibliography = False
            pending_bib_num = None
            continue
        if in_bibliography:
            m = re.match(r"^\\bibitem\{([^{}]*)\}\s*$", line)
            if m:
                pending_bib_num = (bib_map or {}).get(m.group(1), m.group(1))
                continue
            if pending_bib_num is not None:
                blocks.append(("bibitem", (pending_bib_num, line)))
                pending_bib_num = None
                continue

        m = re.match(r"\\section\*?\{(.*)\}\s*$", line)
        if m:
            blocks.append(("h1", m.group(1)))
            continue
        m = re.match(r"\\subsection\*?\{(.*)\}\s*$", line)
        if m:
            blocks.append(("h2", m.group(1)))
            continue
        m = re.match(r"\\subsubsection\*?\{(.*)\}\s*$", line)
        if m:
            blocks.append(("h3", m.group(1)))
            continue

        # Markdown fallback (legacy content saved before the LaTeX migration)
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            kind = {1: "h1", 2: "h2"}.get(len(m.group(1)), "h3")
            blocks.append((kind, m.group(2)))
            continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            blocks.append(("mdquote", m.group(1)))
            continue

        if line == r"\begin{itemize}":
            list_stack.append("itemize")
            continue
        if line == r"\begin{enumerate}":
            list_stack.append("enumerate")
            enum_counters.append(0)
            continue
        if line == r"\end{itemize}":
            if list_stack and list_stack[-1] == "itemize":
                list_stack.pop()
            continue
        if line == r"\end{enumerate}":
            if list_stack and list_stack[-1] == "enumerate":
                list_stack.pop()
                enum_counters.pop()
            continue
        if line == r"\begin{quote}":
            blocks.append(("quote_start", ""))
            continue
        if line == r"\end{quote}":
            blocks.append(("quote_end", ""))
            continue

        m = re.match(r"\\item\s*(.*)$", line)
        if m:
            text = m.group(1)
            if list_stack and list_stack[-1] == "enumerate":
                enum_counters[-1] += 1
                blocks.append(("item_num", (enum_counters[-1], text)))
            else:
                blocks.append(("item", text))
            continue

        if re.match(r"^[-=]{3,}$", line) or line == r"\hrulefill":
            blocks.append(("hr", ""))
            continue

        m = re.match(r"^[-*+]\s+(.*)$", line)
        if m:
            blocks.append(("item", m.group(1)))
            continue
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m:
            blocks.append(("item_num", (int(m.group(1)), m.group(2))))
            continue

        blocks.append(("para", line))

    return blocks


def latex_to_pdf(title: str, content: str) -> bytes:
    """Convert LaTeX content to PDF bytes using fpdf2 (best-effort, not a TeX engine)."""
    from fpdf import FPDF  # type: ignore[import]

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.add_font("DejaVu", "", str(_SANS_REGULAR))
    pdf.add_font("DejaVu", "B", str(_SANS_BOLD))
    pdf.add_font("DejaVu", "I", str(_SANS_ITALIC))
    pdf.add_font("DejaVuMono", "", str(_MONO_REGULAR))

    next_line = {"new_x": "LMARGIN", "new_y": "NEXT"}  # reset cursor to left margin after each cell

    pdf.set_font("DejaVu", "B", 18)
    pdf.multi_cell(0, 10, _sanitize(title), align="L", **next_line)
    pdf.ln(4)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    bib_map = _build_bib_key_map(content)

    for kind, data in _parse_latex_body(content, bib_map):
        if kind == "h1":
            pdf.ln(3)
            pdf.set_font("DejaVu", "B", 16)
            pdf.multi_cell(0, 9, _sanitize(_inline_to_plain(data, bib_map)), align="L", **next_line)
            pdf.ln(1)
        elif kind == "h2":
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", 14)
            pdf.multi_cell(0, 8, _sanitize(_inline_to_plain(data, bib_map)), align="L", **next_line)
            pdf.ln(1)
        elif kind == "h3":
            pdf.ln(1)
            pdf.set_font("DejaVu", "B", 12)
            pdf.multi_cell(0, 7, _sanitize(_inline_to_plain(data, bib_map)), align="L", **next_line)
        elif kind == "hr":
            pdf.ln(2)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)
        elif kind in ("quote_start", "quote_end"):
            continue
        elif kind == "mdquote":
            pdf.set_font("DejaVu", "I", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, "  " + _sanitize(_inline_to_plain(data, bib_map)), align="L", **next_line)
            pdf.set_text_color(0, 0, 0)
        elif kind == "item":
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(0, 6, _sanitize("  * " + _inline_to_plain(data, bib_map)), align="L", **next_line)
        elif kind == "item_num":
            num, text = data
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(0, 6, _sanitize(f"  {num}. " + _inline_to_plain(text, bib_map)), align="L", **next_line)
        elif kind == "bibitem":
            num, text = data
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, _sanitize(f"[{num}] " + _inline_to_plain(text, bib_map)), align="L", **next_line)
        elif kind == "verbatim":
            pdf.set_font("DejaVuMono", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 5, _sanitize(data) or " ", align="L", **next_line)
            pdf.set_text_color(0, 0, 0)
        elif kind == "blank":
            pdf.ln(3)
        else:  # para
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(0, 6, _sanitize(_inline_to_plain(data, bib_map)), align="L", **next_line)

    return bytes(pdf.output())


def latex_to_markdown(content: str) -> str:
    """Convert LaTeX content to Markdown (best-effort)."""
    bib_map = _build_bib_key_map(content)
    lines: list[str] = []
    for kind, data in _parse_latex_body(content, bib_map):
        if kind == "h1":
            lines.append(f"## {_inline_to_markdown(data, bib_map)}")
        elif kind == "h2":
            lines.append(f"### {_inline_to_markdown(data, bib_map)}")
        elif kind == "h3":
            lines.append(f"#### {_inline_to_markdown(data, bib_map)}")
        elif kind == "hr":
            lines.append("---")
        elif kind == "quote_start":
            lines.append("> ")
        elif kind == "quote_end":
            continue
        elif kind == "mdquote":
            lines.append(f"> {_inline_to_markdown(data, bib_map)}")
        elif kind == "item":
            lines.append(f"- {_inline_to_markdown(data, bib_map)}")
        elif kind == "item_num":
            num, text = data
            lines.append(f"{num}. {_inline_to_markdown(text, bib_map)}")
        elif kind == "bibitem":
            num, text = data
            lines.append(f"[{num}] {_inline_to_markdown(text, bib_map)}")
        elif kind == "verbatim":
            lines.append(f"    {data}")
        elif kind == "blank":
            lines.append("")
        else:  # para
            lines.append(_inline_to_markdown(data, bib_map))

    return "\n".join(lines)
