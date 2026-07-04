"""Research-gap detection endpoint - gap-detection module router.

Moved from backend/api/gap.py into the self-contained gap_detection folder.
The baseline wires this in via api/__init__.py (2-line residual).

TIP-G05: POST /gap now accepts {topic: str} and routes to cold_start().
TIP-P2-02: GET /gap/stream added for SSE streaming (topic query param).
The warm-start path ({papers: [...]}) is COMMENTED OUT - see below.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent.gap_detection import retrieval
from backend.agent.gap_detection.nodes.query_analyzer import analyze_query
from backend.agent.gap_detection.orchestrator import _papers_to_refs, cold_start
from backend.agent.gap_detection.query_cleaner import clean_query
from backend.agent.gap_detection.schemas import GapReport, QueryRejectedError
from backend.agent.gap_detection.settings import (
    get_max_papers_for_gap,
    get_min_papers_cold_start,
    is_query_analyzer_enabled,
)
from backend.agent.gap_detection.streaming import stream_gap_detection
from backend.auth.dependencies import get_current_user
from backend.module.payment.services import billing_db, token_meter
from backend.module.payment.services.billing_db import QuotaExceededError

logger = logging.getLogger(__name__)

router = APIRouter()


# -- Cold-start request model -----------------------------------------------


class GapColdStartRequest(BaseModel):
    """Request body for POST /gap (cold-start flow, TIP-G05).

    The client sends a research topic (in any language; Vietnamese supported).
    The orchestrator translates, searches, snowballs, ranks, and runs the full
    gap-detection pipeline internally.
    """

    topic: str = Field(
        ...,
        min_length=3,
        description="Research topic to detect gaps for (VN or EN).",
    )


# -- Cold-start endpoint ----------------------------------------------------


@router.post("/gap", response_model=GapReport)
async def detect_gaps_cold_start(
    request: GapColdStartRequest,
    user: Any = Depends(get_current_user),
) -> GapReport:
    """Run cold-start gap detection from a topic string.

    1. Translates/cleans *topic* (VN->EN).
    2. Searches Semantic Scholar, snowballs, ranks top-N papers.
    3. Runs the full LangGraph gap-detection pipeline.
    4. Returns a :class:`~backend.agent.gap_detection.schemas.GapReport`.

    If fewer than MIN_PAPERS_COLD_START papers are found, returns a valid
    ``GapReport`` with ``gaps=[]`` and a Vietnamese narrative - never 500.
    Deducts 1 Research Gap unit per call (same convention as Literature
    Review's "lr" feature) - refunded only on a true pipeline failure.
    """
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic must not be empty.")

    session_id = str(uuid.uuid4())
    try:
        await billing_db.start_session(str(user.id), "gap", session_id)
    except QuotaExceededError as exc:
        raise HTTPException(402, "Research Gap quota exhausted - please upgrade your plan.") from exc

    token_meter.start()  # per-request token accounting (token-weighted billing)
    logger.info("detect_gaps_cold_start: topic=%r", topic[:80])
    try:
        report = await cold_start(topic)
    except QueryRejectedError as exc:
        raise HTTPException(status_code=400, detail=f"query_rejected:{exc.reason}") from exc
    except Exception:
        logger.warning("detect_gaps_cold_start: pipeline failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Gap detection failed. Please try again later.",
        )

    # Charge the actual token credits on success (a failure above never charges).
    try:
        credits = token_meter.credits_used()
        if credits > 0:
            await billing_db.settle_session(str(user.id), "gap", session_id, credits)
    except Exception as exc:
        logger.warning("settle gap credits failed for session=%s: %s", session_id, exc)
    return report


# -- SSE streaming endpoint (TIP-P2-02) ------------------------------------


async def _meter_gap_stream(stream, user_id: str, session_id: str):
    """Wrap the gap SSE generator: charge the ACTUAL token credits it consumed
    when it finishes successfully, and skip the charge if it emitted an
    ``{"type": "error"}`` event (``stream_gap_detection`` converts internal
    failures into that event rather than raising) \u2014 token-weighted billing."""
    errored = False
    try:
        async for chunk in stream:
            if chunk.startswith("data: "):
                try:
                    payload = json.loads(chunk[6:].strip())
                except json.JSONDecodeError:
                    payload = {}
                if payload.get("type") == "error":
                    errored = True
            yield chunk
    finally:
        if not errored:
            try:
                credits = token_meter.credits_used()
                if credits > 0:
                    await billing_db.settle_session(user_id, "gap", session_id, credits)
            except Exception as exc:
                logger.warning("settle gap stream credits failed for session=%s: %s", session_id, exc)


@router.get("/gap/stream")
async def gap_stream(
    topic: str = Query(..., min_length=3, description="Research topic (VN or EN)."),
    user: Any = Depends(get_current_user),
) -> StreamingResponse:
    """Stream gap-detection pipeline progress as Server-Sent Events.

    Runs the same 6-step cold-start orchestration as ``POST /gap`` but instead
    of waiting for the full result, streams intermediate node-start events and
    the final ``done`` event carrying the ``GapReport``.

    SSE event shapes:
    - ``{"type": "node_start", "node": "<name>", "label": "<VN label>"}``
    - ``{"type": "done",       "report": {...GapReport...}}``
    - ``{"type": "insufficient", "narrative": "..."}``  (thin corpus)
    - ``{"type": "error",     "message": "..."}``  (internal failure)

    Deducts 1 Research Gap unit up front (same convention as ``POST /gap``),
    refunded if the pipeline fails before or during streaming.
    """
    topic = topic.strip()
    if not topic:
        raise HTTPException(
            status_code=422, detail="Ch\u1ee7 \u0111\u1ec1 kh\u00f4ng \u0111\u01b0\u1ee3c \u0111\u1ec3 tr\u1ed1ng."
        )

    session_id = str(uuid.uuid4())
    try:
        await billing_db.start_session(str(user.id), "gap", session_id)
    except QuotaExceededError as exc:
        raise HTTPException(
            402, "H\u1ebft quota Research Gap \u2014 vui l\u00f2ng n\u00e2ng c\u1ea5p g\u00f3i."
        ) from exc

    token_meter.start()  # per-request token accounting \u2014 shared with the stream generator below
    logger.info("gap_stream: topic=%r", topic[:80])

    # Stage A guardrail - validate before any expensive search/LLM work
    if is_query_analyzer_enabled():
        try:
            _gq = await analyze_query(topic)
        except Exception:
            _gq = None  # fail-open: network/parse error -> let pipeline proceed
        if _gq is not None and not _gq.is_research_topic:
            _reason = _gq.reject_reason or "off_topic"
            logger.info("gap_stream: Stage A guardrail rejected — reason=%s", _reason)
            await billing_db.refund_session(str(user.id), "gap", session_id)
            _msg = (
                "This query cannot be processed. Please enter a research topic."
                if _reason == "injection"
                else (
                    "This doesn't look like a research topic. "
                    "Please describe an academic field or area, "
                    "for example: 'RAG in healthcare' or 'long-context transformers'."
                )
            )

            async def _rejected_stream():
                yield f"data: {json.dumps({'type': 'rejected', 'reason': _reason, 'message': _msg}, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                _rejected_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

    try:
        # Step 1: Clean query
        clean = await clean_query(topic)

        # Step 2: Search + fallback
        pool = await retrieval.search(clean, limit=100)
        fallback_threshold = 3
        if len(pool) < fallback_threshold and clean.lower() != topic.lower():
            pool = await retrieval.search(topic, limit=100)

        # Step 3: Snowball
        merged = await retrieval.snowball(pool)

        # Step 4: Rank
        top = await retrieval.rank(clean or topic, merged, top_k=get_max_papers_for_gap())

        # Step 5: Insufficient gate - return an SSE stream with a single event
        if len(top) < get_min_papers_cold_start():

            async def _insufficient():
                payload = {
                    "type": "insufficient",
                    "narrative": "Not enough literature was found for this topic. "
                    "Please try again with a broader topic.",
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                _insufficient(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        # Step 6: Build PaperRefs and stream
        session_papers = _papers_to_refs(top)

        return StreamingResponse(
            _meter_gap_stream(stream_gap_detection(session_papers, topic), str(user.id), session_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except HTTPException:
        raise
    except Exception:
        logger.warning("gap_stream: orchestration failed", exc_info=True)
        await billing_db.refund_session(str(user.id), "gap", session_id)
        raise HTTPException(
            status_code=500,
            detail="Gap stream th\u1ea5t b\u1ea1i. Vui l\u00f2ng th\u1eed l\u1ea1i sau.",
        )


# -- warm-start disabled (Lưu ý 2) - re-enable later -------------------
#
# from backend.agent.gap_detection.graph import run_gap_detection
# from backend.agent.gap_detection.nodes.paper_check import MIN_SESSION_PAPERS
# from backend.agent.gap_detection.schemas import PaperRef
# from backend.agent.gap_detection.settings import get_max_papers_for_gap
#
# _TOO_FEW_PAPERS_MESSAGE = (
#     "Cần ít nhất 5 papers để phân tích khoảng trống. "
#     "Hãy tìm/snowball thêm tài liệu trước."
# )
#
#
# class GapPaperInput(BaseModel):
#     """One session paper supplied by the Research page."""
#
#     paper_id: str
#     title: str
#     year: int | None = None
#     url: str | None = None
#
#
# class GapDetectionRequest(BaseModel):
#     papers: list[GapPaperInput] = []
#
#
# @router.post("/gap", response_model=GapReport)
# async def detect_gaps(request: GapDetectionRequest) -> GapReport:
#     """Run gap detection over the supplied session papers.
#
#     Papers are deduplicated by ``paper_id``.  With fewer than
#     ``MIN_SESSION_PAPERS`` papers, returns an early report (no baseline
#     search).  Otherwise runs the full pipeline.
#     """
#     # Map -> PaperRef, dedup by paper_id (preserve first-seen order).
#     refs: list[PaperRef] = []
#     seen: set[str] = set()
#     for item in request.papers:
#         if item.paper_id and item.paper_id not in seen:
#             seen.add(item.paper_id)
#             refs.append(
#                 PaperRef(paper_id=item.paper_id, title=item.title or item.paper_id, year=item.year, url=item.url)
#             )
#
#     if len(refs) < MIN_SESSION_PAPERS:
#         logger.info("detect_gaps: %d paper(s) < %d - returning early", len(refs), MIN_SESSION_PAPERS)
#         return GapReport(
#             papers_analyzed=len(refs),
#             gaps=[],
#             narrative=_TOO_FEW_PAPERS_MESSAGE,
#             baseline_triggered=True,
#         )
#
#     # Cap the number of papers fed to the pipeline to keep latency bounded.
#     total = len(refs)
#     max_papers = get_max_papers_for_gap()
#     cap_note: str | None = None
#     if total > max_papers:
#         refs = refs[:max_papers]
#         cap_note = (
#             f"Đã phân tích {len(refs)}/{total} papers (giới hạn để đảm bảo tốc độ). "
#             "Thu hẹp tập tài liệu để kết quả tập trung hơn."
#         )
#         logger.info("detect_gaps: capped %d -> %d papers", total, len(refs))
#
#     try:
#         report = await run_gap_detection(refs)
#     except Exception as e:
#         logger.warning("detect_gaps: pipeline failed", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Gap detection failed: {e}")
#
#     if cap_note:
#         report.narrative = f"{cap_note}\n\n{report.narrative}"
#     return report
