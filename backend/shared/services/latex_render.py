"""Best-effort LaTeX → PDF/Markdown rendering, shared by Reviews export and PDF Agent
export so both features stay on one renderer instead of duplicating ~300 lines of
LaTeX parsing (not a full TeX engine — good enough for our generated/edited content)."""

from __future__ import annotations

import re

from backend.shared.services.latex_utils import unescape_latex

# fpdf2's multi_cell raises FPDFException ("Not enough horizontal space to render
# a single character") when one unbroken run of non-space characters is wider than
# the page — common with bare DOI/arXiv URLs in citations. fpdf2 honors the
# soft-hyphen character (U+00AD) as a word-break hint, so sprinkle one into any
# long unbroken token to give it somewhere to wrap instead of crashing the export.
_LONG_TOKEN_RE = re.compile(r"\S{61,}")


def _break_long_token(match: re.Match) -> str:
    token = match.group(0)
    return "\u00ad".join(token[i : i + 60] for i in range(0, len(token), 60))


def _sanitize(text: str) -> str:
    """Replace common Unicode chars that Latin-1 fonts can't render, and break up
    unbroken long tokens (e.g. DOI/arXiv URLs) so fpdf2 can wrap them."""
    _MAP = {
        "–": "-", "—": "--", "‘": "'", "’": "'",
        "“": '"', "”": '"', "…": "...", "•": "-",
        "·": "*", "→": "->", "←": "<-", "≤": "<=",
        "≥": ">=", "×": "x", "÷": "/", "α": "alpha",
        "β": "beta", "γ": "gamma", "δ": "delta",
    }
    for src, dst in _MAP.items():
        text = text.replace(src, dst)
    text = _LONG_TOKEN_RE.sub(_break_long_token, text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ── LaTeX parsing (best-effort — not a full TeX engine) ──────────────────────

_INLINE_RE = re.compile(
    r"\\href\{(?P<href_url>[^{}]*)\}\{(?P<href_text>[^{}]*)\}"
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


def _inline_to_plain(text: str) -> str:
    """Render inline LaTeX markup as plain text (for the fpdf2 PDF renderer)."""
    def repl(m: re.Match) -> str:
        if m.lastgroup == "href_text":
            return f"{m.group('href_text')} ({m.group('href_url')})"
        if m.lastgroup == "mdlinktext":
            return f"{m.group('mdlinktext')} ({m.group('mdlinkurl')})"
        if m.lastgroup == "cite":
            return f"({m.group('cite')})"
        if m.lastgroup in ("bf", "it", "emph", "math1", "math2", "mdbf", "mdbf2", "mdit", "mdcode"):
            return m.group(m.lastgroup)
        return " "  # \\ line break

    return unescape_latex(_INLINE_RE.sub(repl, text))


def _inline_to_markdown(text: str) -> str:
    """Render inline LaTeX markup as Markdown."""
    def repl(m: re.Match) -> str:
        if m.lastgroup == "href_text":
            return f"[{m.group('href_text')}]({m.group('href_url')})"
        if m.lastgroup == "mdlinktext":
            return f"[{m.group('mdlinktext')}]({m.group('mdlinkurl')})"
        if m.lastgroup == "cite":
            return f"({m.group('cite')})"
        if m.lastgroup in ("bf", "mdbf", "mdbf2"):
            return f"**{m.group(m.lastgroup)}**"
        if m.lastgroup in ("it", "emph", "mdit"):
            return f"*{m.group(m.lastgroup)}*"
        if m.lastgroup == "mdcode":
            return f"`{m.group('mdcode')}`"
        if m.lastgroup in ("math1", "math2"):
            return f"${m.group(m.lastgroup)}$"
        return "  \n"  # \\ line break

    return unescape_latex(_INLINE_RE.sub(repl, text))


def _parse_latex_body(content: str) -> list[tuple[str, object]]:
    """Split .tex source into a sequence of (kind, data) blocks for rendering.

    kind is one of: h1, h2, h3, item, item_num, quote_start, quote_end,
    verbatim, hr, blank, para.
    """
    body_match = re.search(r"\\begin\{document\}(.*)\\end\{document\}", content, re.S)
    body = body_match.group(1) if body_match else content

    blocks: list[tuple[str, object]] = []
    list_stack: list[str] = []
    enum_counters: list[int] = []
    in_verbatim = False

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

    NL = {"new_x": "LMARGIN", "new_y": "NEXT"}  # reset cursor to left margin after each cell

    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 10, _sanitize(title), align="L", **NL)
    pdf.ln(4)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    for kind, data in _parse_latex_body(content):
        if kind == "h1":
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(0, 9, _sanitize(_inline_to_plain(data)), align="L", **NL)
            pdf.ln(1)
        elif kind == "h2":
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 8, _sanitize(_inline_to_plain(data)), align="L", **NL)
            pdf.ln(1)
        elif kind == "h3":
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 7, _sanitize(_inline_to_plain(data)), align="L", **NL)
        elif kind == "hr":
            pdf.ln(2)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)
        elif kind in ("quote_start", "quote_end"):
            continue
        elif kind == "mdquote":
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, "  " + _sanitize(_inline_to_plain(data)), align="L", **NL)
            pdf.set_text_color(0, 0, 0)
        elif kind == "item":
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _sanitize("  * " + _inline_to_plain(data)), align="L", **NL)
        elif kind == "item_num":
            num, text = data
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _sanitize(f"  {num}. " + _inline_to_plain(text)), align="L", **NL)
        elif kind == "verbatim":
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 5, _sanitize(data) or " ", align="L", **NL)
            pdf.set_text_color(0, 0, 0)
        elif kind == "blank":
            pdf.ln(3)
        else:  # para
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _sanitize(_inline_to_plain(data)), align="L", **NL)

    return bytes(pdf.output())


def latex_to_markdown(content: str) -> str:
    """Convert LaTeX content to Markdown (best-effort)."""
    lines: list[str] = []
    for kind, data in _parse_latex_body(content):
        if kind == "h1":
            lines.append(f"## {_inline_to_markdown(data)}")
        elif kind == "h2":
            lines.append(f"### {_inline_to_markdown(data)}")
        elif kind == "h3":
            lines.append(f"#### {_inline_to_markdown(data)}")
        elif kind == "hr":
            lines.append("---")
        elif kind == "quote_start":
            lines.append("> ")
        elif kind == "quote_end":
            continue
        elif kind == "mdquote":
            lines.append(f"> {_inline_to_markdown(data)}")
        elif kind == "item":
            lines.append(f"- {_inline_to_markdown(data)}")
        elif kind == "item_num":
            num, text = data
            lines.append(f"{num}. {_inline_to_markdown(text)}")
        elif kind == "verbatim":
            lines.append(f"    {data}")
        elif kind == "blank":
            lines.append("")
        else:  # para
            lines.append(_inline_to_markdown(data))

    return "\n".join(lines)
