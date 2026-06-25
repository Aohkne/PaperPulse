# COMPLETION REPORT — TIP-P2-02

**TIP-ID:** TIP-P2-02  
**Branch:** `feat/gap-cold-start-mvp`  
**Date:** 2026-06-21  
**Status:** ✅ DONE

---

## graph.py findings: [initial_state schema, synthesizer output key]

| Item | Value |
|------|-------|
| **Compile function** | `build_gap_detection_graph()` (không phải `build_graph`) |
| **initial_state schema** | `{"session_papers": list[PaperRef]}` — đơn giản, chỉ cần 1 key |
| **synthesizer output key** | `"final_report"` → `GapReport` object |
| **astream_events node key** | `event["metadata"]["langgraph_node"]` — đúng như TIP mô tả |

**Schema khác giả định ban đầu:** TIP viết `output.get("gap_report") or output` nhưng thực tế key là `"final_report"` (từ synthesizer_node return `{"final_report": report}`). Đã implement đúng theo code thực.

---

## streaming.py: [node events emitted, done event format]

**File:** [`backend/agent/gap_detection/streaming.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/streaming.py) **[MỚI]**

### Node events emitted (7 nodes):
```
extractor              → "Đang trích xuất nội dung bài báo"
topical_detector       → "Đang phát hiện gap chủ đề"
method_detector        → "Đang phát hiện gap phương pháp"
contradiction_detector → "Đang kiểm tra mâu thuẫn"
verifier               → "Đang xác minh gap"
counter_search         → "Đang tìm kiếm bằng chứng phản bác"
synthesizer            → "Đang tổng hợp kết quả"
```

### Event formats:
```json
// node_start (khi node bắt đầu)
{"type": "node_start", "node": "extractor", "label": "Đang trích xuất nội dung bài báo"}

// done (khi synthesizer kết thúc)
{"type": "done", "report": {<GapReport.model_dump()>}}

// error (exception trong astream_events — không raise, không crash FE)
{"type": "error", "message": "Lỗi nội bộ..."}
```

### Import boundary enforced:
- `astream_events` chỉ được gọi trong `streaming.py`
- `router.py` chỉ import `stream_gap_detection` (generator function)

---

## router.py: [GET /gap/stream added, POST /gap untouched]

**File:** [`backend/agent/gap_detection/router.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/router.py)

### GET /gap/stream:
- **Path:** `GET /api/gap/stream?topic=<string>`
- **Validation:** `min_length=3` (FastAPI Query) → 422 nếu ngắn hơn
- **Orchestration:** giống cold_start — clean → search → fallback → snowball → rank
- **Insufficient gate:** emit SSE `type=insufficient` (không crash)
- **Happy path:** `StreamingResponse(stream_gap_detection(...), media_type="text/event-stream")`
- **Headers:** `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- **POST /gap:** KHÔNG bị thay đổi — giữ nguyên 100%

### Imports mới trong router.py:
```python
import json
from fastapi import ..., Query
from fastapi.responses import StreamingResponse
from backend.agent.gap_detection import retrieval
from backend.agent.gap_detection.orchestrator import _papers_to_refs, cold_start
from backend.agent.gap_detection.query_cleaner import clean_query
from backend.agent.gap_detection.settings import get_max_papers_for_gap, get_min_papers_cold_start
from backend.agent.gap_detection.streaming import stream_gap_detection
```

---

## AC: [pass/fail từng scenario]

| Scenario | Status |
|----------|--------|
| `GET /gap/stream?topic=transformer+attention` → `text/event-stream` | ✅ PASS |
| Stream emit `type="node_start"` cho ≥1 node | ✅ PASS |
| Stream emit `type="done"` với report cuối | ✅ PASS |
| `GET /gap/stream?topic=ab` → 422 | ✅ PASS |
| Insufficient papers → SSE `type=insufficient` + narrative VN | ✅ PASS |
| Không crash khi insufficient | ✅ PASS |
| `POST /gap {"topic":"..."}` → 200 + GapReport (no regression) | ✅ PASS |

---

## REGRESSION: [53/53 PASS ✅]

```
tests/test_gap_streaming.py          8 passed  ← MỚI
tests/test_gap_chat_integration.py  18 passed
tests/test_gap_detection_schemas.py 10 passed
tests/test_gap_e2e.py               11 passed
tests/test_gap_endpoint.py           6 passed
─────────────────────────────────────────────
TOTAL                               53 passed, 0 failed
```

---

## DIFF: [file list]

| File | Type | Mô tả |
|------|------|-------|
| `backend/agent/gap_detection/streaming.py` | **[MỚI]** | SSE async generator, `_sse()` helper, `_NODE_LABELS` dict |
| `backend/agent/gap_detection/router.py` | MODIFY | Thêm GET /gap/stream + imports mới; POST /gap giữ nguyên |
| `tests/test_gap_streaming.py` | **[MỚI]** | 8 tests: stream unit tests + endpoint integration tests |
