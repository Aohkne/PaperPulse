"""PDF structure extraction for Step P1 — `.pdf` branch.

PLAN_2.0 §1 chọn MinerU (self-host layout+OCR) cho nhánh này. MinerU chưa
cài trong môi trường triển khai hiện tại (cần tải model weight vài GB,
không có GPU) nên branch này dùng **PyMuPDF** (đã là dependency của repo,
dùng chung pattern với `backend/agent/gap_detection/nodes/pdf_utils.py`)
làm fallback thực dụng — kém chính xác hơn MinerU ở việc ghép caption↔figure
và phát hiện heading (xem PLAN §9 Rủi ro: "MinerU accuracy limit"), nhưng
chạy được ngay, không cần hạ tầng thêm.

Để swap sang MinerU thật sau này: giữ nguyên contract của
`extract_structure_from_pdf()` (trả về sections/figures/raw_reference_lines),
chỉ đổi implementation bên trong.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.config import get_llm, get_settings
from backend.module.pdf_agent.graph.state import Figure, RawCitation, Section
from backend.module.pdf_agent.services.llm_timeout import ainvoke_with_timeout
from backend.module.pdf_agent.services.text_quote_selector import build_anchor
from backend.shared.services.latex_utils import escape_latex

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=get_settings().pdf_parser_max_workers,
            thread_name_prefix="pdf_parser",
        )
    return _executor

_HEADING_RE = re.compile(
    r"^(?:\d{1,2}[\.\)]?\s+)?"
    r"(Abstract|Introduction|Related Work|Background|Motivation|"
    r"Method(?:ology|s)?|Approach|Model|System|Architecture|"
    r"Experiments?|Evaluation|Results?|Analysis|Discussion|"
    r"Limitations?|Future Work|Conclusions?|Acknowledge?ments?|"
    r"References?|Bibliography|Appendix)"
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_FIGURE_CAPTION_RE = re.compile(r"\b(?:Figure|Fig\.?)\s*(\d+)\s*[:.]?\s*(.{0,200}?)(?:\n\n|\.\s|$)", re.IGNORECASE | re.DOTALL)
_REF_HEADING_RE = re.compile(r"^(References?|Bibliography)\s*$", re.IGNORECASE | re.MULTILINE)
_MIN_IMAGE_DIM = 50  # px — skip tiny logos/icons


def get_pdf_page_count(pdf_path: str) -> int:
    import fitz
    doc = fitz.open(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


async def extract_structure_from_pdf(pdf_path: str, figures_dir: str) -> dict:
    """Returns {"sections": list[Section], "figures": list[Figure], "raw_reference_lines": list[str]}."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_get_executor(), _extract_sync, pdf_path, figures_dir)


def _extract_sync(pdf_path: str, figures_dir: str) -> dict:
    import fitz

    doc = fitz.open(pdf_path)
    page_texts: list[str] = []
    page_offsets: list[int] = []
    full_text = ""
    for page in doc:
        # Escape LaTeX-special chars *before* computing offsets — sections, figure
        # anchors and the rendered main.tex must all agree on one coordinate system
        # (the escaped text), otherwise refind_anchor() would never match in the editor.
        text = escape_latex(page.get_text())
        page_offsets.append(len(full_text))
        page_texts.append(text)
        full_text += text + "\n\n"

    sections = _extract_sections(full_text)
    figures = _extract_figures(doc, page_texts, page_offsets, full_text, figures_dir)
    raw_reference_lines = _extract_reference_lines(full_text)
    doc.close()
    return {"sections": sections, "figures": figures, "raw_reference_lines": raw_reference_lines}


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)[:60] or "section"


def _extract_sections(full_text: str) -> list[Section]:
    matches = list(_HEADING_RE.finditer(full_text))
    if not matches:
        return [{"title": "Document", "raw_latex": full_text.strip(), "paragraph_ids": ["document-p0"]}]

    sections: list[Section] = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        raw_latex = full_text[body_start:body_end].strip()
        if not raw_latex:
            continue
        slug = _slug(title)
        paragraphs = [p for p in re.split(r"\n\s*\n", raw_latex) if p.strip()]
        paragraph_ids = [f"{slug}-p{j}" for j in range(len(paragraphs))] or [f"{slug}-p0"]
        sections.append({"title": title, "raw_latex": raw_latex, "paragraph_ids": paragraph_ids})
    return sections or [{"title": "Document", "raw_latex": full_text.strip(), "paragraph_ids": ["document-p0"]}]


def _extract_figures(doc, page_texts: list[str], page_offsets: list[int], full_text: str, figures_dir: str) -> list[Figure]:
    Path(figures_dir).mkdir(parents=True, exist_ok=True)
    figures: list[Figure] = []
    seen_xrefs: set[int] = set()

    for page_index, page in enumerate(doc):
        page_text = page_texts[page_index]
        captions = [(m.group(1), m.group(2).strip()) for m in _FIGURE_CAPTION_RE.finditer(page_text)]
        images = [img for img in page.get_images(full=True) if img[2] >= _MIN_IMAGE_DIM and img[3] >= _MIN_IMAGE_DIM]

        for i, img in enumerate(images):
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                extracted = doc.extract_image(xref)
            except Exception:
                logger.warning("Failed to extract image xref=%s on page %d", xref, page_index + 1, exc_info=True)
                continue
            ext = extracted.get("ext", "png")
            filename = f"page{page_index + 1}_img{i}.{ext}"
            out_path = Path(figures_dir) / filename
            out_path.write_bytes(extracted["image"])

            fig_num, caption = captions[i] if i < len(captions) else (None, None)
            anchor = None
            if caption:
                local_pos = page_text.find(caption)
                if local_pos != -1:
                    global_start = page_offsets[page_index] + local_pos
                    anchor = build_anchor(full_text, global_start, global_start + len(caption))

            figures.append({
                "image_path": str(out_path),
                "caption": caption,
                "label": None,  # PDF gốc không có \label — xem SPEC Step P1 "Giới hạn cần biết"
                "anchor": anchor,
                "page_number": page_index + 1,
                "missing": False,
            })

    return figures


def _extract_reference_lines(full_text: str) -> list[str]:
    matches = list(_REF_HEADING_RE.finditer(full_text))
    if not matches:
        return []
    block = full_text[matches[-1].end():]
    # Numbered markers like "[12]" or "12." at line start — split before each.
    splits = list(re.finditer(r"(?:^|\n)\s*(?:\[\d+\]|\d{1,3}\.)\s+", block))
    if len(splits) >= 2:
        lines = []
        for i, sm in enumerate(splits):
            start = sm.end()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(block)
            line = re.sub(r"\s+", " ", block[start:end]).strip()
            if line:
                lines.append(line)
        return lines
    # Fallback: blank-line-separated chunks.
    return [re.sub(r"\s+", " ", chunk).strip() for chunk in re.split(r"\n\s*\n", block) if chunk.strip()]


_REFERENCE_CLEANUP_PROMPT = """You are a bibliography parser. You will be given raw, possibly OCR-noisy \
reference list entries from an academic paper, one per line. For EACH entry, extract structured fields.

Output a JSON array, one object per input entry, in the same order, with fields:
  "raw_text": the original entry text (verbatim, unchanged)
  "guessed_title": the paper title, or null if unclear
  "guessed_authors": list of author last names, or null if unclear
  "guessed_year": 4-digit publication year as integer, or null if unclear
  "guessed_doi_or_url": a DOI or URL if present in the text, or null

Do not invent information not present in the text. If a field is unclear, use null rather than guessing.
Output ONLY the JSON array, no other text."""


async def parse_references_with_llm(raw_lines: list[str]) -> list[RawCitation]:
    """1 LLM call (temperature=0) → structured RawCitation[] từ raw reference text (PLAN §7 Phase 2).

    raw_text gốc luôn được giữ nguyên (PLAN §9 Rủi ro: nếu LLM parse sai field,
    Phase 4 fallback dùng raw_text full-text search).
    """
    if not raw_lines:
        return []

    llm = get_llm(temperature=get_settings().pdf_judge_temperature, streaming=False)
    numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(raw_lines))
    try:
        response = await ainvoke_with_timeout(llm, [
            {"role": "system", "content": _REFERENCE_CLEANUP_PROMPT},
            {"role": "user", "content": numbered},
        ])
        content = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\[.*\]", content, re.DOTALL)
        parsed = json.loads(match.group(0) if match else content)
    except Exception:
        logger.warning("parse_references_with_llm failed — falling back to raw_text-only citations", exc_info=True)
        return [
            {"key": None, "raw_text": line, "guessed_title": None, "guessed_authors": None,
             "guessed_year": None, "guessed_doi_or_url": None}
            for line in raw_lines
        ]

    citations: list[RawCitation] = []
    for i, line in enumerate(raw_lines):
        item = parsed[i] if i < len(parsed) and isinstance(parsed[i], dict) else {}
        citations.append({
            "key": None,
            "raw_text": item.get("raw_text") or line,
            "guessed_title": item.get("guessed_title"),
            "guessed_authors": item.get("guessed_authors"),
            "guessed_year": item.get("guessed_year"),
            "guessed_doi_or_url": item.get("guessed_doi_or_url"),
        })
    return citations
