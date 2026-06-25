"""Real MinerU integration — Step P1 `.pdf` branch (PLAN §1/§7 Phase 2).

Two ways to reach MinerU, picked via `settings.mineru_mode`:
  - "cli" (default): subprocess to a local `mineru` binary in THIS process's
    Python env. Install: `pip install -e ".[mineru]"` (→ `mineru[pipeline]`,
    requires Python >=3.10,<3.14 — see pyproject.toml). CLI:
    `mineru -p <input> -o <output> -m auto [-b pipeline]` (`-b pipeline` forces
    the CPU-only backend). Output: a `*_content_list.json` somewhere under the
    output dir — exact nesting differs by version/backend, so we glob for it.
  - "http": POST to a `mineru-api` server's `/file_parse` (e.g. running in
    Docker via `mineru-api --host 0.0.0.0`) — lets the backend run natively
    without installing MinerU's heavy ML deps (torch/paddle/onnxruntime) into
    its own env. Verified against the actual installed `mineru==3.4.0` source
    (`mineru/cli/fast_api.py`/`api_request.py`/`output_paths.py`), not guessed.

Both verified against the current (v3.x) MinerU release, NOT the older
`magic-pdf` CLI the original PLAN pseudocode was modeled on. Model weights are
a separate explicit step either way — `mineru-models-download` (baked into the
Docker image at build time, see Dockerfile / Dockerfile.mineru).

In "cli" mode this module shells out to the `mineru` binary — it does NOT
`import mineru` as a Python package, so it stays importable even in
environments (like this project's Python 3.14 dev sandbox) where the `mineru`
package itself can't be installed. `is_available()` lets `parse_document.py`
fall back to `pdf_parser.py` (PyMuPDF) when neither mode is reachable.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import shutil
import tempfile
from glob import glob
from pathlib import Path

import httpx

from backend.config import get_settings
from backend.module.pdf_agent.graph.state import Figure, Section
from backend.module.pdf_agent.services.text_quote_selector import build_anchor
from backend.shared.services.latex_utils import escape_latex

logger = logging.getLogger(__name__)

_HEADING_TEXT_LEVEL = 1  # MinerU's own text_level signal — 1 == top-level heading
_FIGURE_TYPES = ("image", "table", "chart")
_HTTP_BACKEND = "pipeline"  # matches `-b pipeline` in cli mode — CPU-only backend
_HTTP_PARSE_METHOD = "auto"


class MinerUTimeoutError(Exception):
    pass


class MinerUExecutionError(Exception):
    pass


def is_available() -> bool:
    """True if MinerU can plausibly be reached in the configured mode.

    "cli": the `mineru` binary is on PATH. "http": an API URL is configured —
    actual reachability is verified by the real call in `run_mineru_http()`
    (a ConnectError there is translated to MinerUExecutionError, so the
    fallback-to-PyMuPDF path in parse_document.py works the same either way).
    """
    settings = get_settings()
    if settings.mineru_mode == "http":
        return bool(settings.mineru_api_url)
    return shutil.which(settings.mineru_bin) is not None


async def run_mineru(pdf_path: str, output_dir: str) -> str:
    """Runs the `mineru` CLI, returns the path to the produced `*_content_list.json`.

    Raises MinerUTimeoutError if the subprocess exceeds MINERU_TIMEOUT_S (killed,
    not left to hang) and MinerUExecutionError on a non-zero exit or missing output.
    """
    settings = get_settings()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cmd = [settings.mineru_bin, "-p", pdf_path, "-o", output_dir, "-m", "auto"]
    if settings.mineru_device_mode == "cpu":
        cmd += ["-b", "pipeline"]  # CPU-only backend — see module docstring

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.mineru_timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise MinerUTimeoutError(f"MinerU vượt {settings.mineru_timeout_s}s — PDF có thể quá phức tạp/dài")

    if proc.returncode != 0:
        raise MinerUExecutionError(f"mineru exited {proc.returncode}: {stderr.decode(errors='ignore')[-2000:]}")

    matches = glob(f"{output_dir}/**/*_content_list.json", recursive=True)
    if not matches:
        raise MinerUExecutionError("MinerU không sinh ra content_list.json — kiểm tra log subprocess")
    return matches[0]


async def run_mineru_http(pdf_path: str) -> tuple[list[dict], str]:
    """Calls a running `mineru-api` server's `POST /file_parse` (verified against
    the actual installed mineru==3.4.0 source, `mineru/cli/fast_api.py` — this is
    a *synchronous* endpoint: it waits for the task to finish and returns the
    final result in the same response, no polling needed).

    Returns (content_list, content_dir). The HTTP server has no shared
    filesystem with this (natively-running) process, so figure images are
    requested as base64 (`return_images=True`, verified against a real run —
    response key is `images: {basename: "data:<mime>;base64,<...>"}`, where
    `basename` matches `os.path.basename(block["img_path"])` for every
    image/table/chart block in content_list) and materialized into a local
    temp dir at the same `images/<basename>` layout `parse_content_list()`
    already expects, so that function stays identical across both modes.
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.mineru_timeout_s) as client:
            with open(pdf_path, "rb") as f:
                resp = await client.post(
                    f"{settings.mineru_api_url}/file_parse",
                    files={"files": (Path(pdf_path).name, f, "application/pdf")},
                    data={
                        "backend": _HTTP_BACKEND,
                        "parse_method": _HTTP_PARSE_METHOD,
                        "return_content_list": "true",
                        "return_images": "true",
                        "response_format_zip": "false",
                    },
                )
    except httpx.TimeoutException as exc:
        raise MinerUTimeoutError(f"mineru-api vượt {settings.mineru_timeout_s}s") from exc
    except httpx.ConnectError as exc:
        raise MinerUExecutionError(f"Không kết nối được mineru-api tại {settings.mineru_api_url}") from exc

    if resp.status_code != 200:
        raise MinerUExecutionError(f"mineru-api trả {resp.status_code}: {resp.text[:2000]}")

    results = resp.json().get("results") or {}
    if not results:
        raise MinerUExecutionError("mineru-api trả results rỗng")
    pdf_name, result = next(iter(results.items()))
    content_list_raw = result.get("content_list")
    if not content_list_raw:
        raise MinerUExecutionError("mineru-api không trả content_list")
    content_list = json.loads(content_list_raw)

    content_dir = tempfile.mkdtemp(prefix=f"mineru_http_{pdf_name}_")
    images_b64: dict = result.get("images") or {}
    if images_b64:
        images_subdir = Path(content_dir) / "images"
        images_subdir.mkdir(parents=True, exist_ok=True)
        for name, data_uri in images_b64.items():
            _, _, b64_data = data_uri.partition(",")
            (images_subdir / name).write_bytes(base64.b64decode(b64_data))

    return content_list, content_dir


def _block_text(block: dict) -> str:
    """Best-effort plain-text content of a content_list block (for anchors/sections)."""
    btype = block.get("type")
    if btype in ("text", "equation"):
        return block.get("text", "")
    if btype in _FIGURE_TYPES:
        caption = block.get("image_caption") or block.get("table_caption") or block.get("chart_caption") or []
        return " ".join(c for c in caption if c)
    return ""


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)[:60] or "section"


def parse_content_list(content_list: list[dict], content_dir: str, figures_dir: str) -> dict:
    """Returns {"sections": list[Section], "figures": list[Figure]}.

    `content_dir` is the directory containing content_list.json — every block's
    `img_path` is relative to it. Figures get copied into `figures_dir`.
    """
    Path(figures_dir).mkdir(parents=True, exist_ok=True)

    # One shared escaped full_text + per-block char offsets, so section boundaries
    # and figure anchors agree on a single coordinate system (same requirement as
    # the PyMuPDF fallback in pdf_parser.py — see its module docstring).
    full_text = ""
    offsets: list[tuple[int, int]] = []
    for block in content_list:
        text = escape_latex(_block_text(block))
        start = len(full_text)
        full_text += text + "\n\n"
        offsets.append((start, start + len(text)))

    # Sections — MinerU's own text_level is a more reliable heading signal than
    # the regex heuristics pdf_parser.py needs (it has no such structure to lean on).
    headings: list[tuple[str, int, int]] = []  # (title, heading_start, heading_end)
    for i, block in enumerate(content_list):
        if block.get("type") == "text" and block.get("text_level") == _HEADING_TEXT_LEVEL:
            h_start, h_end = offsets[i]
            title = block.get("text", "").strip() or "(untitled)"
            headings.append((title, h_start, h_end))

    sections: list[Section] = []
    if not headings:
        sections.append({"title": "Document", "raw_latex": full_text.strip(), "paragraph_ids": ["document-p0"]})
    else:
        for i, (title, _h_start, h_end) in enumerate(headings):
            body_start = h_end
            body_end = headings[i + 1][1] if i + 1 < len(headings) else len(full_text)
            raw_latex = full_text[body_start:body_end].strip()
            if not raw_latex:
                continue
            slug = _slug(title)
            paragraphs = [p for p in re.split(r"\n\s*\n", raw_latex) if p.strip()]
            paragraph_ids = [f"{slug}-p{j}" for j in range(len(paragraphs))] or [f"{slug}-p0"]
            sections.append({"title": title, "raw_latex": raw_latex, "paragraph_ids": paragraph_ids})
        if not sections:
            sections.append({"title": "Document", "raw_latex": full_text.strip(), "paragraph_ids": ["document-p0"]})

    # Figures — image/table/chart blocks, anchored against the same full_text so
    # bundle_exporter's splice-by-substring-match works identically to the other branches.
    figures: list[Figure] = []
    for i, block in enumerate(content_list):
        if block.get("type") not in _FIGURE_TYPES:
            continue
        img_path = block.get("img_path")
        if not img_path:
            continue
        src = Path(content_dir) / img_path
        if not src.is_file():
            logger.warning("MinerU referenced image not found on disk: %s", src)
            continue
        dest = Path(figures_dir) / src.name
        shutil.copy(src, dest)

        caption_list = block.get("image_caption") or block.get("table_caption") or block.get("chart_caption") or []
        caption = " ".join(c.strip() for c in caption_list if c.strip()) or None

        start, end = offsets[i]
        anchor = build_anchor(full_text, start, end) if end > start else None

        figures.append({
            "image_path": str(dest),
            "caption": caption,
            "label": None,  # PDF has no \label{} source — Identified Gap, same as pdf_parser.py
            "anchor": anchor,
            "page_number": block.get("page_idx", 0) + 1,
            "missing": False,
        })

    return {"sections": sections, "figures": figures}


async def extract_structure_from_pdf(pdf_path: str, figures_dir: str) -> dict:
    """Same contract as `pdf_parser.extract_structure_from_pdf()` — drop-in MinerU
    implementation. Raises MinerUTimeoutError/MinerUExecutionError on failure;
    `parse_document.py` catches these and falls back to the PyMuPDF path.
    """
    settings = get_settings()
    if settings.mineru_mode == "http":
        content_list, content_dir = await run_mineru_http(pdf_path)
    else:
        work_dir = Path(settings.mineru_tmp_dir) / Path(pdf_path).stem
        content_list_path = await run_mineru(pdf_path, str(work_dir))
        content_list = json.loads(Path(content_list_path).read_text(encoding="utf-8"))
        content_dir = str(Path(content_list_path).parent)

    result = parse_content_list(content_list, content_dir, figures_dir)

    # Reference list raw text — same downstream contract as pdf_parser.py: split
    # a literal "References"/"Bibliography" section's body into entries for
    # pdf_parser.parse_references_with_llm() (reused as-is, no need to duplicate
    # the LLM cleanup step here).
    raw_reference_lines: list[str] = []
    for s in result["sections"]:
        if re.match(r"(?i)^(references?|bibliography)$", s["title"].strip()):
            raw_reference_lines = [line.strip() for line in re.split(r"\n\s*\n", s["raw_latex"]) if line.strip()]
            break

    return {"sections": result["sections"], "figures": result["figures"], "raw_reference_lines": raw_reference_lines}
