"""POST /api/pdf-agent/upload — Step P0→P4, SSE stream (PLAN §4, §6).

Mirrors the SSE pattern in `research_agent/api/research.py` (background
producer task draining `astream_events()` into a queue, consumer only ever
times out on `queue.get()` — never on the event iterator itself, which
would cancel a node mid-execution). No interrupts here, so the generator is
much simpler: just map `on_chain_start`/`on_chain_end` per node to step events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Security, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.module.payment.services import billing_db
from backend.module.payment.services.billing_db import QuotaExceededError
from backend.module.pdf_agent.api._common import pdf_agent_config
from backend.module.pdf_agent.graph.graph import get_pdf_agent_graph

router = APIRouter(prefix="/pdf-agent", tags=["pdf-agent"])
log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=True)

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
_HEARTBEAT_SECONDS = 15

PDF_AGENT_NODE_LABELS = {
    "format_detect": "Nhận diện định dạng file...",
    "parse_document": "Phân tích cấu trúc văn bản...",
    "render_bundle": "Dựng file .tex editable...",
    "batch_analysis": "Kiểm tra văn phong + citation song song...",
    "build_annotations": "Tổng hợp gợi ý + cảnh báo...",
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stats_for_node(name: str, output: dict) -> dict:
    if name == "format_detect":
        return {"input_format": output.get("input_format")}
    if name == "parse_document":
        return {
            "sections": len(output.get("sections") or []),
            "citations": len(output.get("raw_citations") or []),
            "figures": len(output.get("figures") or []),
        }
    if name == "batch_analysis":
        counts = Counter(v.get("verdict") for v in (output.get("citation_verdicts") or []))
        broken = sum(1 for link in (output.get("link_results") or []) if not link.get("alive"))
        return {
            "verified": counts.get("Verified", 0),
            "mismatch": counts.get("Metadata Mismatch", 0),
            "not_found": counts.get("Not Found", 0),
            "broken_links": broken,
        }
    if name == "build_annotations":
        return {"total_annotations": len(output.get("annotations") or [])}
    return {}


async def _stream_pdf_graph(graph, initial_state: dict, config: dict):
    queue: asyncio.Queue = asyncio.Queue()
    _DONE = object()

    async def _produce() -> None:
        try:
            async for event in graph.astream_events(initial_state, config, version="v2"):
                await queue.put(event)
        except Exception as exc:  # noqa: BLE001 — forwarded to the consumer below
            await queue.put(exc)
        finally:
            await queue.put(_DONE)

    producer_task = asyncio.create_task(_produce())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
            except TimeoutError:
                yield _sse({"type": "heartbeat"})
                continue

            if item is _DONE:
                break
            if isinstance(item, Exception):
                raise item

            event = item
            name = event.get("name", "")
            if name not in PDF_AGENT_NODE_LABELS:
                continue

            kind = event["event"]
            if kind == "on_chain_start":
                yield _sse({"type": "step_start", "node": name, "label": PDF_AGENT_NODE_LABELS[name]})
            elif kind == "on_chain_end":
                output = event["data"].get("output")
                if isinstance(output, dict):
                    yield _sse({"type": "step_done", "node": name, "stats": _stats_for_node(name, output)})
    except Exception as exc:
        log.exception("pdf-agent pipeline error: %s", exc)
        yield _sse({"type": "error", "message": str(exc)})
        return
    finally:
        if not producer_task.done():
            producer_task.cancel()


# Per-instance in-flight counter (optimize_Plan.html §2.2) — each PDF upload
# holds a PyMuPDF ThreadPoolExecutor slot + LLM calls for the whole SSE
# stream lifetime, so unbounded concurrent uploads can starve the pool/OOM
# the Cloud Run instance. Returns 429 fast instead of queuing silently.
_inflight_uploads = 0


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user=Depends(get_current_user),
):
    global _inflight_uploads
    settings = get_settings()

    if _inflight_uploads >= settings.pdf_agent_upload_concurrency:
        raise HTTPException(429, "Server đang xử lý quá nhiều PDF cùng lúc — vui lòng thử lại sau vài giây.")
    _inflight_uploads += 1

    try:
        raw_bytes = await file.read()
        max_bytes = settings.pdf_agent_max_file_size_mb * 1024 * 1024
        if len(raw_bytes) > max_bytes:
            raise HTTPException(413, f"File quá lớn — tối đa {settings.pdf_agent_max_file_size_mb}MB")

        doc_id = str(uuid4())

        # Deduct 1 PDF Agent unit at session start, before any file I/O/graph work
        # (payment_SPEC_2.0.md §Logic deduction — "trừ ngay khi session bắt đầu").
        try:
            await billing_db.start_session(str(user.id), "pdf", doc_id)
        except QuotaExceededError as exc:
            raise HTTPException(402, "Hết quota PDF Agent — vui lòng nâng cấp gói hoặc mua thêm.") from exc

        doc_dir = Path(settings.pdf_agent_output_dir) / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        raw_path = doc_dir / f"raw_{file.filename or 'upload'}"
        raw_path.write_bytes(raw_bytes)

        graph = await get_pdf_agent_graph()
        config = pdf_agent_config(doc_id)
        initial_state = {"doc_id": doc_id, "user_id": str(user.id), "raw_file_path": str(raw_path)}
    except Exception:
        _inflight_uploads -= 1
        raise

    async def generator():
        global _inflight_uploads
        try:
            yield _sse({"type": "doc_id", "doc_id": doc_id})
            error_occurred = False
            async for raw in _stream_pdf_graph(graph, initial_state, config):
                if '"type": "error"' in raw:  # cheap check — avoids re-parsing every event's JSON
                    error_occurred = True
                yield raw
            # Only signal completion if the pipeline actually reached build_annotations —
            # an error mid-pipeline (e.g. parse_document fails on a malformed PDF) means
            # main_tex_path/annotations were never set, so a "done" here would make the
            # frontend call GET /content on a state that doesn't have it yet (KeyError 500).
            if not error_occurred:
                yield _sse({"type": "done", "doc_id": doc_id})
            else:
                # System pipeline error (no interrupts in PDF Agent, so this is the
                # only refund path needed — payment_SPEC_2.0.md §refund table).
                await billing_db.refund_session(str(user.id), "pdf", doc_id)
        finally:
            _inflight_uploads -= 1

    return StreamingResponse(generator(), media_type="text/event-stream", headers=_SSE_HEADERS)
