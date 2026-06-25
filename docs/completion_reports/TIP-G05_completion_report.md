# COMPLETION REPORT — TIP-G05: router.py → cold-start {topic}; comment warm {papers}

## HEADER
- **TIP-ID:** TIP-G05
- **Module:** `backend/agent/gap_detection/router.py`
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `0bef139`
- **Date:** 2026-06-20
- **Status:** ✅ DONE

---

## THAY ĐỔI

### Request model mới: `GapColdStartRequest`

```python
class GapColdStartRequest(BaseModel):
    topic: str = Field(..., min_length=3,
                       description="Research topic (VN or EN)")
```

Pydantic `min_length=3` → `topic` rỗng / < 3 ký tự tự động trả **422** với message chuẩn FastAPI — không cần code thêm.

### Endpoint mới: `POST /gap`

```python
@router.post("/gap", response_model=GapReport)
async def detect_gaps_cold_start(request: GapColdStartRequest) -> GapReport:
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(422, "Chủ đề không được để trống.")
    try:
        report = await cold_start(topic)
    except Exception:
        raise HTTPException(500, "Gap detection thất bại. Vui lòng thử lại sau.")
    return report
```

- **500** không lộ stack trace — chỉ message an toàn.
- Response model `GapReport` giữ nguyên → contract FE ổn định.

### Imports active (cold-start)

```python
from backend.agent.gap_detection.orchestrator import cold_start
from backend.agent.gap_detection.schemas import GapReport
```

### Warm path: COMMENTED OUT

```python
# ── warm-start disabled (Lưu ý 2) — re-enable later ────────────────────────
#
# from backend.agent.gap_detection.graph import run_gap_detection
# from backend.agent.gap_detection.nodes.paper_check import MIN_SESSION_PAPERS
# from backend.agent.gap_detection.schemas import PaperRef
# from backend.agent.gap_detection.settings import get_max_papers_for_gap
# ...
# class GapPaperInput(BaseModel): ...
# class GapDetectionRequest(BaseModel): papers: list[GapPaperInput] = []
# @router.post("/gap")
# async def detect_gaps(request: GapDetectionRequest) -> GapReport: ...
```

**Toàn bộ code warm còn trong file** (chỉ comment, không xóa). ✅

---

## SELF-TEST KẾT QUẢ

```
router import + /gap route: PASS
GapColdStartRequest min_length=3 validation: PASS
GapColdStartRequest valid topic: PASS
Warm path GapDetectionRequest commented out: PASS
Imports: cold_start active, run_gap_detection commented: PASS
Warm path still in file (commented): PASS
ALL SELF-TESTS PASSED
```

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| `POST /api/gap {topic:"transformer long-context"}` → 200 + GapReport | ✅ `/gap` route exists, cold_start called |
| `POST /api/gap {papers:[...]}` (shape cũ) → 422 thiếu `topic` | ✅ `GapDetectionRequest` commented, pydantic reject missing `topic` |
| `topic` rỗng → 422 | ✅ `min_length=3` + strip() guard |
| Warm path CÒN trong file nhưng đã comment | ✅ `GapDetectionRequest`, `GapPaperInput`, `detect_gaps` toàn bộ còn trong file |
| Lỗi nội bộ → 500 message an toàn | ✅ `except Exception` → HTTPException(500, safe message) |

---

## KHÔNG CHẠM
- `orchestrator.py` — không sửa ✅
- `schemas.py` — không sửa ✅
- `graph.py` — không sửa ✅
- `api/__init__.py` — không sửa (gap_router đã được mount ở G01) ✅
- Frontend — không sửa ✅

---

## NEXT
TIP-G05 DONE → chuỗi phụ thuộc: **G07** (paper_check.py) → **G08** (e2e verify).
