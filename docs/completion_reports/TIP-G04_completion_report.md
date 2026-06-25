# COMPLETION REPORT — TIP-G04: orchestrator.py cold_start ①→⑥

## HEADER
- **TIP-ID:** TIP-G04
- **Module:** `backend/agent/gap_detection/orchestrator.py` (mới tạo)
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `32d36bd`
- **Date:** 2026-06-20
- **Status:** ✅ DONE

---

## FILE TẠO: `orchestrator.py`

### Signature

```python
async def cold_start(topic: str) -> GapReport
```

### Luồng ①→⑥

```
① clean  = await clean_query(topic)               # VN→EN, strip meta-words
② pool   = await retrieval.search(clean, 100)     # S2 keyword search
③ merged = await retrieval.snowball(pool)          # citation graph expansion
④ top    = await retrieval.rank(clean, merged, top_k=get_max_papers_for_gap())
⑤ gate   → len(top) < MIN_PAPERS_COLD_START(5):
           return GapReport(gaps=[], narrative=<VN>, papers_analyzed=len(top))
⑥ session_papers = _papers_to_refs(top)
   return await run_gap_detection(session_papers)
```

### Insufficient-paper response (bước ⑤)

```python
GapReport(
    papers_analyzed=len(top),   # số thật, không phải 0
    gaps=[],
    narrative="Không đủ tài liệu cho chủ đề này. ...",  # tiếng Việt, FE render được
    baseline_triggered=False,
)
```

**`run_gap_detection` KHÔNG được gọi ở nhánh này.**

### Map `Paper → PaperRef` (`_papers_to_refs`)

```python
PaperRef(
    paper_id = paper.paper_id,   # Paper.paper_id (alias paperId)
    title    = paper.title,
    year     = paper.year,       # optional
    url      = paper.url,        # optional
)
```

**Không map `abstract` vào `PaperRef`** (field không có trong `PaperRef`). `abstract` được persist sau bởi `extractor_node` từ S2 detail API (TIP-G06-R). KHÔNG thêm field mới vào schema.

### Cô lập imports

```python
from backend.agent.gap_detection import retrieval
from backend.agent.gap_detection.graph import run_gap_detection
from backend.agent.gap_detection.query_cleaner import clean_query
from backend.agent.gap_detection.schemas import GapReport, PaperRef
from backend.agent.gap_detection.settings import get_max_papers_for_gap, get_min_papers_cold_start
```

**Không import `services.**` trực tiếp.** ✅

---

## SELF-TEST KẾT QUẢ

```
import cold_start, _papers_to_refs: PASS
_papers_to_refs: PASS
_papers_to_refs skip no paper_id: PASS
cold_start happy path: PASS
cold_start insufficient path: PASS (narrative non-empty, len=177)
cold_start call order (1->6): PASS
ALL SELF-TESTS PASSED
```

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| Topic đủ tài liệu → trả GapReport từ run_gap_detection | ✅ run_gap_detection được gọi với list[PaperRef] |
| Topic ngách < MIN_PAPERS → GapReport hợp lệ: gaps=[] + narrative VN | ✅ gaps=[], papers_analyzed=len(top), baseline_triggered=False |
| run_gap_detection KHÔNG gọi ở nhánh insufficient | ✅ assert_not_awaited() PASS |
| Thứ tự clean→search→snowball→rank→run | ✅ call_log == ['clean','search','snowball','rank','run'] |
| Cô lập: chỉ import nội bộ gap | ✅ không import services trực tiếp |
| Không sửa graph structure | ✅ |
| Không thêm field mới vào schema | ✅ PaperRef/GapReport không thay đổi |

---

## KHÔNG CHẠM
- `graph.py` — không sửa gì ✅
- `schemas.py` — không sửa gì ✅
- `services/**` — không import trực tiếp ✅
- Frontend — không sửa gì ✅

---

## NEXT
TIP-G04 DONE. Chuỗi phụ thuộc: **G05** (router expose cold_start endpoint → depends G04 ✅).
