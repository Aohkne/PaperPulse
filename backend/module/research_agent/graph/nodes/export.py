"""Step ⑩ — LaTeX + BibTeX export.

Assembles the final literature review document:
  1. LLM writes an INTRODUCTION + CONCLUSION from the theme summaries (temperature=0.7)
  2. Builds a cite_key → Paper map for BibTeX generation
  3. Replaces (Source: PAPER_ID) tags with \\cite{cite_key} in each section
  4. Wraps sections in LaTeX preamble + \\maketitle
  5. Generates a .bib file with @article entries for all cited papers
"""

from __future__ import annotations

import logging
import re
import unicodedata

from backend.config import get_llm, get_settings
from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.services.llm_timeout import ainvoke_with_timeout
from backend.shared.models.paper import Paper
from backend.shared.services.latex_utils import escape_latex

log = logging.getLogger(__name__)

_INTRO_CONCLUSION_SYSTEM = (
    "You are an academic writer finishing a literature review. Given the review's "
    "topic and its theme sections (title + short excerpt), write:\n"
    "1. An INTRODUCTION (2-4 paragraphs) framing the topic, its scope, and why it "
    "matters, previewing the themes covered.\n"
    "2. A CONCLUSION (1-3 paragraphs) synthesizing the key findings across themes "
    "and noting open questions.\n\n"
    "Output PLAIN TEXT ONLY — no LaTeX commands, no markdown headers, no citations. "
    "Separate the two parts with a line containing exactly: ===CONCLUSION==="
)


async def _generate_intro_conclusion(query: str, theme_contents: list[dict]) -> tuple[str, str]:
    """LLM call producing the Introduction + Conclusion text (SPEC 2.0 §Step ⑩)."""
    settings = get_settings()
    summaries = []
    for tc in theme_contents:
        title = tc.get("theme", "")
        snippet = " ".join(tc.get("content", "").split()[:60])
        summaries.append(f"- {title}: {snippet}")
    themes_block = "\n".join(summaries) or "(no themes available)"

    llm = get_llm(temperature=settings.export_temperature)
    try:
        response = await ainvoke_with_timeout(llm, [
            ("system", _INTRO_CONCLUSION_SYSTEM),
            ("human", f"Topic: {query}\n\nThemes:\n{themes_block}"),
        ])
        text = (response.content or "").strip()
    except Exception as exc:
        log.warning("Intro/conclusion generation failed: %s", exc)
        return "", ""

    if "===CONCLUSION===" in text:
        intro, _, conclusion = text.partition("===CONCLUSION===")
    else:
        intro, conclusion = text, ""
    return intro.strip(), conclusion.strip()

_LATEX_PREAMBLE = (
    "\\documentclass[11pt]{{article}}\n"
    "\\usepackage[utf8]{{inputenc}}\n"
    "\\usepackage{{amsmath,amssymb}}\n"
    "\\usepackage{{hyperref}}\n"
    "\\usepackage[margin=1in]{{geometry}}\n\n"
    "\\title{{{title}}}\n"
    "\\date{{}}\n\n"
    "\\begin{{document}}\n"
    "\\maketitle\n\n"
)

_LATEX_CLOSING = "\n\\end{document}\n"

_SOURCE_TAG_RE = re.compile(r"\(Source:\s*([A-Za-z0-9_\-\.]+)\)")

_LLM_ARTIFACT_RE = re.compile(
    r"^\s*(#{1,6}\s+.*|\\documentclass\b.*|\\usepackage\b.*|"
    r"\\begin\{document\}|\\end\{document\}|\\maketitle|\\title\{.*\}|\\author\{.*\})\s*$"
)


def _clean(text: str) -> str:
    return "\n".join(ln for ln in text.split("\n") if not _LLM_ARTIFACT_RE.match(ln)).strip()


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())[:20]


def _cite_key(paper: Paper) -> str:
    last_name = _slugify((paper.authors[0] if paper.authors else "unknown").split()[-1])
    year = str(paper.year or "")
    first_word = _slugify((paper.title or "").split()[0]) if paper.title else ""
    raw = f"{last_name}{year}{first_word}"
    return raw[:30] or f"paper_{paper.paper_id[:8]}"


def _build_bibtex(papers: list[Paper], key_map: dict[str, str]) -> str:
    entries: list[str] = []
    seen_keys: dict[str, int] = {}

    for paper in papers:
        base_key = key_map.get(paper.paper_id, _cite_key(paper))
        # Disambiguate duplicate keys
        if base_key in seen_keys:
            seen_keys[base_key] += 1
            key = f"{base_key}{seen_keys[base_key]}"
        else:
            seen_keys[base_key] = 0
            key = base_key

        key_map[paper.paper_id] = key  # update in place for final pass

        ext = paper.external_ids or {}
        doi = ext.get("DOI") or ""
        arxiv_id = ext.get("ArXiv") or ""
        authors_bib = " and ".join(paper.authors) if paper.authors else "Unknown"

        fields = [
            f"  title = {{{escape_latex(paper.title or '')}}}",
            f"  author = {{{escape_latex(authors_bib)}}}",
        ]
        if paper.year:
            fields.append(f"  year = {{{paper.year}}}")
        if doi:
            fields.append(f"  doi = {{{doi}}}")
        if arxiv_id:
            fields.append(f"  eprint = {{{arxiv_id}}}")
            fields.append("  archivePrefix = {arXiv}")
        if paper.url:
            fields.append(f"  url = {{{paper.url}}}")

        entry_type = "article" if not arxiv_id else "misc"
        entries.append(f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}")

    return "\n\n".join(entries)


def _build_thebibliography(papers: list[Paper], key_map: dict[str, str]) -> str:
    """Generate a self-contained \\begin{thebibliography} block (no external .bib needed)."""
    if not papers:
        return ""
    lines = ["\\begin{thebibliography}{99}"]
    for paper in papers:
        key = key_map.get(paper.paper_id, _cite_key(paper))
        authors = ", ".join(paper.authors[:3]) if paper.authors else "Unknown"
        if len(paper.authors or []) > 3:
            authors += " et al."
        year = f" ({paper.year})" if paper.year else ""
        title = escape_latex(paper.title or "Untitled")
        url = f" \\url{{{paper.url}}}" if paper.url else ""
        lines.append(f"\n\\bibitem{{{key}}}")
        lines.append(f"{escape_latex(authors)}{year}. \\textit{{{title}}}.{url}")
    lines.append("\n\\end{thebibliography}")
    return "\n".join(lines)


def _replace_source_tags(content: str, paper_map: dict[str, Paper], key_map: dict[str, str]) -> str:
    def _repl(m: re.Match) -> str:
        pid = m.group(1)
        key = key_map.get(pid)
        return f"\\cite{{{key}}}" if key else m.group(0)

    return _SOURCE_TAG_RE.sub(_repl, content)


async def export_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state.get("query", "")
    await narrate_step(f"assembling the final LaTeX document and BibTeX references for {query}")
    theme_contents = state.get("theme_contents", [])
    papers = state.get("papers", [])
    included_claims = state.get("included_claims", [])
    review_claims = state.get("review_claims", [])

    paper_map = {p.paper_id: p for p in papers}

    # Collect cited paper IDs
    cited_ids = {c.paper_id for c in included_claims + review_claims}
    # Also include papers referenced in theme content sections
    for tc in theme_contents:
        for pid in tc.get("paper_ids", []):
            cited_ids.add(pid)

    cited_papers = [paper_map[pid] for pid in cited_ids if pid in paper_map]

    # Build cite key map (paper_id → cite_key)
    key_map: dict[str, str] = {p.paper_id: _cite_key(p) for p in cited_papers}

    # Generate BibTeX
    bib_content = _build_bibtex(cited_papers, key_map)

    # LLM-generated Introduction + Conclusion (SPEC 2.0 §Step ⑩)
    intro_text, conclusion_text = await _generate_intro_conclusion(query, theme_contents)

    # Assemble LaTeX sections
    sections: list[str] = []
    if intro_text:
        sections.append(f"\\section{{Introduction}}\n\n{escape_latex(intro_text)}\n")
    for tc in theme_contents:
        content = _replace_source_tags(_clean(tc.get("content", "")), paper_map, key_map)
        sections.append(f"\\section{{{escape_latex(tc.get('theme', ''))}}}\n\n{content}\n")
    if conclusion_text:
        sections.append(f"\\section{{Conclusion}}\n\n{escape_latex(conclusion_text)}\n")

    body = "\n".join(sections)
    title = escape_latex(f"Literature Review: {query}")
    thebib = _build_thebibliography(cited_papers, key_map)
    latex_doc = _LATEX_PREAMBLE.format(title=title) + body + "\n" + thebib + _LATEX_CLOSING

    return {
        "latex_doc": latex_doc,
        "bib_content": bib_content,
    }
