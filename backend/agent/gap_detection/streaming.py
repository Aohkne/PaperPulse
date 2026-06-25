"""streaming.py — SSE async generator for gap-detection pipeline (TIP-P2-02).

Wraps the compiled LangGraph graph in an ``astream_events`` (v2) loop and
yields Server-Sent Event strings.  Two event types are emitted:

* ``node_start`` — fires when a pipeline node begins processing.
* ``done``       — fires when the synthesizer finishes; carries the full
                   ``GapReport`` (serialised to JSON-safe dict).

The caller (``router.py``) wraps this generator in a ``StreamingResponse``
with ``media_type="text/event-stream"``.

Import boundary: this module is the ONLY place in gap_detection that calls
``astream_events``.  The router MUST NOT import or call it directly.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from backend.agent.gap_detection.graph import build_gap_detection_graph
from backend.agent.gap_detection.schemas import GapReport, PaperRef

logger = logging.getLogger(__name__)

# Human-readable labels for each pipeline node (Vietnamese UI).
_NODE_LABELS: dict[str, str] = {
    "extractor":              "Đang trích xuất nội dung bài báo",
    "topical_detector":       "Đang phát hiện gap chủ đề",
    "method_detector":        "Đang phát hiện gap phương pháp",
    "contradiction_detector": "Đang kiểm tra mâu thuẫn",
    "verifier":               "Đang xác minh gap",
    "counter_search":         "Đang tìm kiếm bằng chứng phản bác",
    "synthesizer":            "Đang tổng hợp kết quả",
}


async def stream_gap_detection(
    session_papers: list[PaperRef],
    topic: str,
) -> AsyncGenerator[str, None]:
    """Async generator: yields SSE strings from the gap-detection graph.

    Args:
        session_papers: Pre-ranked list of :class:`PaperRef` objects to feed
            into the pipeline (produced by the orchestration in router.py).
        topic: Original topic string — included in the ``done`` event for FE
            logging / analytics.

    Yields:
        ``data: {JSON}\\n\\n`` strings (SSE format):

        * ``{"type": "node_start", "node": "<name>", "label": "<VN label>"}``
        * ``{"type": "done", "report": {<GapReport as dict>}}``

    The generator never raises: any uncaught exception is converted to a
    ``{"type": "error", "message": "..."}`` event so the FE SSE handler
    receives a clean close instead of a broken stream.
    """
    graph = build_gap_detection_graph()
    initial_state = {"session_papers": session_papers}

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")
            node = event.get("metadata", {}).get("langgraph_node", "")

            if kind == "on_chain_start" and node in _NODE_LABELS:
                logger.debug("stream_gap_detection: node_start → %s", node)
                yield _sse({"type": "node_start", "node": node, "label": _NODE_LABELS[node]})

            elif kind == "on_chain_end" and node == "synthesizer":
                # synthesizer_node returns {"final_report": GapReport}
                output = event.get("data", {}).get("output", {})
                report: GapReport | None = output.get("final_report")

                if report is None:
                    # Defensive: should not happen, but avoid silent failure.
                    logger.warning(
                        "stream_gap_detection: synthesizer on_chain_end has no final_report"
                    )
                    yield _sse({
                        "type": "done",
                        "report": GapReport(
                            papers_analyzed=len(session_papers),
                            gaps=[],
                            narrative="Không thể tổng hợp kết quả. Vui lòng thử lại.",
                        ).model_dump(),
                    })
                else:
                    yield _sse({"type": "done", "report": report.model_dump()})

    except Exception:
        logger.warning(
            "stream_gap_detection: unhandled exception in astream_events loop",
            exc_info=True,
        )
        yield _sse({
            "type": "error",
            "message": "Lỗi nội bộ trong quá trình streaming. Vui lòng thử lại.",
        })


def _sse(data: dict) -> str:
    """Encode *data* as a single SSE message string."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
