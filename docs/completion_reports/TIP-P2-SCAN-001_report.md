# P2-SCAN REPORT — TIP-P2-SCAN-001
**Date:** 2026-06-20 | **Branch:** `feat/gap-cold-start-mvp` (pre-merge) | **Builder:** Thợ (READ-ONLY)

---

## NHÓM 1 — EMBEDDING

### 1.1 EMBEDDING_BASE_URL
```
EMBEDDING_BASE_URL: SET ✅  →  https://integrate.api.nvidia.com/v1
model: nv-embed-v1
```
**Nhưng:** endpoint trả **404 Not Found** khi gọi thật → account/key không có quyền truy cập model này.

```
WARNING: embed_text failed: Client error '404 Not Found'
  for url 'https://integrate.api.nvidia.com/v1/embeddings'
embed_text: None
```

### 1.2 embed_text probe — **None (endpoint 404)**
- `embed_text("test query")` → `None`
- Nguyên nhân: NVIDIA NIM endpoint `nv-embed-v1` trả 404 → key SET nhưng model chưa được cấp quyền / URL sai
- dim: **N/A** (không lấy được vector)

**Code path khi None:** `embedding.py:20` — `if not settings.embedding_base_url: return None` chỉ guard khi UNSET. Khi SET nhưng 404 → `except Exception → logging.warning → return None` (graceful)

### 1.3 ChromaDB count — **0 records**
```python
_get_collection().count() → 0
```
Collection "papers" trống hoàn toàn. Chưa có lần nào `upsert_papers` thành công với vector thật.

### 1.4 OQ-01 dim mismatch
- SPECTER2 (S2 batch API) = **768d**
- `nv-embed-v1` local = **không xác định được** (embed_text = None vì 404)
- `nv-embed-v1` documented = 4096d → **MIS-MATCH nghiêm trọng nếu kích hoạt**
- Collection ChromaDB count=0 → chưa có vector nào → mismatch chưa xảy ra trên production, nhưng nếu khắc phục 404 sẽ crash ChromaDB ngay lần đầu upsert (dim conflict)

**OQ-01 STATUS: UNRESOLVED — mismatch 768d vs 4096d tiềm ẩn. Cần fix trước Phase 2-A.**

### 1.5 hybrid_search semantic arm
- `embed_text` → None → `query_by_vector` KHÔNG được gọi
- `hybrid_search` graceful degrade → BM25-only (`logging.info: embedding unavailable — BM25 only`)
- Semantic arm: **NOT ACTIVE** (BM25-only hiện tại)

```python
# hybrid_search.py:45-53
query_vec = await embed_text(query)
if query_vec:   # False → skip semantic
    ...
else:
    logging.info("hybrid_search: embedding unavailable — BM25 only")
```

---

## NHÓM 2 — STREAMING

### 2.1 `/research/stream` pattern
**File:** `backend/api/research.py`

```python
# Pattern: StreamingResponse + async generator (KHÔNG dùng EventSourceResponse)
@router.get("/research/stream")
async def research_stream(query: str):
    async def generator():
        async for chunk in _pipeline(query):
            yield chunk
            await asyncio.sleep(0)  # yield event loop

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Event format:**
```
data: {"type": "step", "step_type": "thought|action|observation", "stepNum": "①", "content": "..."}
data: {"type": "outline_draft", "themes": [...]}
data: {"type": "done", "content": "## Literature Review ..."}
data: {"type": "error", "message": "..."}
```

`_pipeline()` là async generator yield từng SSE string. Full pipeline ①→⑩ (10 steps) streaming từng node.

### 2.2 FE SSE consumer
**File:** `frontend/src/shared/store/useChatStore.js` (lines 115–160)

**Pattern:** `fetch()` + `ReadableStream` + `TextDecoder` (KHÔNG dùng `EventSource` API):

```javascript
// useChatStore.js:116-158
const res = await fetch(`/api/research/stream?query=${encodeURIComponent(trimmed)}`);
const reader = res.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop();  // keep incomplete tail
    for (const part of parts) {
        const dataLine = part.split('\n').find(l => l.startsWith('data: '));
        event = JSON.parse(dataLine.slice(6));
        if (event.type === 'step') _addStep(event);
        else if (event.type === 'done') _setContent(event.content);
        else if (event.type === 'error') _setError(event.message);
    }
}
```

**Đánh giá reuse cho gap streaming:**
- Pattern `fetch + ReadableStream reader` này **có thể reuse hoàn toàn** cho `/api/gap/stream`
- Cần thêm event types mới: `gap_extracting`, `gap_detecting`, `gap_done`
- Không cần EventSource polyfill; không cần refactor — chỉ thêm store action mới

### 2.3 LangGraph streaming API
**Version installed:** `langgraph==1.2.4`

**Probed on `CompiledStateGraph`:**
```
astream available:        True  ✅
astream_events available: True  ✅
ainvoke available:        True  ✅
```

**Hiện tại `graph.py` dùng:** `ainvoke` only:
```python
# graph.py:80
final_state = await graph.ainvoke(initial_state)
```

**astream_events output per node** (example):
```python
async for event in graph.astream_events(initial_state, version="v2"):
    if event["event"] == "on_chain_end":
        node = event["metadata"]["langgraph_node"]
        # → "extractor", "topical_detector", "method_detector", ...
        output = event["data"]["output"]
        yield sse({"type": "node_done", "node": node, ...})
```

### 2.4 Effort SSE cho gap — **MEDIUM**

**Lý do MEDIUM (không EASY, không HARD):**

| Việc phải làm | Effort |
|---|---|
| Đổi `router.py`: thêm `GET /gap/stream?topic=...` mới, giữ `POST /gap` | Low |
| Đổi `graph.py::run_gap_detection` → yield events qua `astream_events` | Medium |
| Thêm event types: `extracting N/M`, `detecting`, `verifying`, `done` | Low |
| FE: thêm `useGapStore.streamGaps(topic)` tương tự useChatStore pattern | Low |
| Xử lý `GapReport` partial yield (chỉ có sau synthesizer) | Medium |
| Không phá vỡ `POST /gap` hiện tại (backward compat) | Low |

**Blockers:** Không có blocker kỹ thuật. `astream_events` sẵn có, FE pattern sẵn có. Khó nhất là map `GapDetectionState` fields → meaningful progress events cho UX.

---

## NHÓM 3 — TECH DEBT

### 3.1 `_to_paper` bug — xác nhận

**File:** `backend/services/semantic_scholar.py` line 112

```python
# HIỆN TẠI (bug):
paperId=raw.get("paperId", ""),
# Khi S2 trả {'paperId': null}: raw.get('paperId', '') = None (fallback không trigger khi key tồn tại!)
# → Paper(paperId=None) → ValidationError

# FIX 1 dòng:
paperId=raw.get("paperId") or "",
# Khi paperId=null: raw.get('paperId')=None → None or '' = '' → Paper(paperId='') → valid string
```

**Tác động sau fix:** ValidationError warnings sẽ biến mất. Paper `paperId=''` vẫn bị lọc bởi G10.1 defensive filter trong `retrieval.py::_valid_papers`.

**Priority:** LOW (cosmetic — errors đã caught ở snowball.py:79, không ảnh hưởng yield sau G10).

### 3.2 `choices=None` path — `llm_client.py`

**Line 33:**
```python
return response.choices[0].message.content or ""
# Nếu response.choices = None → TypeError: 'NoneType' object is not subscriptable
```

**Callers trong gap module** (files import `from backend.services.llm_client import chat_completion`):

| File | Dùng chat_completion cho |
|---|---|
| `nodes/contradiction_detector.py` | Detect contradiction |
| `nodes/counter_search.py` | Query generation + fill assessment |
| `nodes/extractor.py` | LLM extraction (với retry) |
| `nodes/method_detector.py` | Detect method gap |
| `nodes/synthesizer.py` | Generate narrative |
| `nodes/topical_detector.py` | Detect topical gap |
| `nodes/_detector_common.py` | Base detector (dùng bởi topical/method/contradiction) |
| `nodes/intent_classifier.py` | Classify intent |
| `query_cleaner.py` | Clean/translate topic |

**Tổng: 9 callers** trong gap module.

**Tác động thực tế:** G10.4 log ghi nhận counter_search fail với `TypeError: 'NoneType' not subscriptable` khi LLM trả response không chuẩn (OpenAI-compat endpoint). Pipeline gracefully degrade (counter_search dùng fallback) — không crash.

**Fix đơn giản:**
```python
# llm_client.py:33
choices = response.choices  # có thể None nếu API lỗi
if not choices:
    return ""
return choices[0].message.content or ""
```

**Priority:** MEDIUM — nên fix trước Phase 2 để không che lấp LLM errors thật.

### 3.3 `counter_search.py` + `chat_integration.py` — direct S2 import

**Hiện trạng:**
```
counter_search.py:31    from backend.services.semantic_scholar import search_papers
chat_integration.py:26  from backend.services.semantic_scholar import search_papers
retrieval.py:37-38      from backend.services.semantic_scholar import search_papers  ← ĐÚNG (adapter)
                        from backend.services.snowball import run_snowball, select_seeds
```

**`retrieval.py` ĐÚNG** — nó là adapter layer. `counter_search.py` và `chat_integration.py` bypass adapter.

**Phương án migrate:**

| File | Hiện tại | Migrate sang | Phức tạp? |
|---|---|---|---|
| `counter_search.py` | `search_papers(query, limit=5)` → `Paper[]` | `retrieval.search(query, limit=5)` → `Paper[]` (API tương thích) | **LOW** — 1 line import + 1 call site, cùng signature |
| `chat_integration.py` | `search_papers(query, limit=10)` | `retrieval.search(query, limit=10)` | **LOW** — 2 call sites, cùng signature |

`retrieval.search()` wrap `search_papers()` + thêm `_valid_papers` filter → migrate còn tốt hơn (G10.1 filter tự động áp dụng).

**Effort: LOW** — nhưng cần thêm `retrieval` import + xác nhận không circular (retrieval không import counter_search/chat_integration → an toàn).

---

## VERDICT

| Nhóm | Metric | Trạng thái | Chi tiết |
|---|---|---|---|
| **Embedding** | EMBEDDING_BASE_URL | SET nhưng 404 | nv-embed-v1 không accessible |
| **Embedding** | embed_text | **NOT READY** | Returns None, endpoint 404 |
| **Embedding** | ChromaDB | 0 records | Chưa bao giờ upsert |
| **Embedding** | OQ-01 dim | **UNRESOLVED** | SPECTER2=768d vs nv-embed-v1=4096d (potential crash) |
| **Embedding** | hybrid_search | BM25-only | Graceful degraded, semantic arm inactive |
| **Streaming** | BE pattern | StreamingResponse + async generator | Reusable ✅ |
| **Streaming** | FE consumer | fetch+ReadableStream reader | Reusable ✅ |
| **Streaming** | LangGraph | astream + astream_events available | v1.2.4 ✅ |
| **Streaming** | Gap SSE effort | **MEDIUM** | ~1-2 TIPs, no blockers |
| **Tech debt** | _to_paper bug | Confirmed CLASS A | Fix 1 dòng, LOW priority |
| **Tech debt** | choices=None | 9 callers exposed | Fix 2-3 dòng, MEDIUM priority |
| **Tech debt** | S2 direct import | 2 files ngoài adapter | Migrate LOW effort |

### VERDICT TỔNG KẾT

- **Embedding: NOT READY** — NVIDIA endpoint 404. Cần: (1) fix endpoint URL/key, hoặc (2) chuyển sang provider khác (OpenAI `text-embedding-3-small` 1536d, hoặc local SPECTER2 768d). **Phải giải quyết trước Phase 2-A/B**.

- **Streaming: MEDIUM** — Không có blockers kỹ thuật. LangGraph `astream_events` sẵn có. FE pattern `fetch+ReadableStream` reusable. Effort ~1-2 TIPs để implement `/gap/stream`. Có thể bắt đầu Phase 2-D ngay.

- **Tech debt: OK (không URGENT)** — Ba items đã identified, không block MVP. Nên fix trước khi ship Phase 2 để cleaner logs và error handling.

---

## RECOMMENDATIONS CHO CHỦ THẦU

1. **Quyết định embedding provider** cho Phase 2-A:
   - Option A: Fix NVIDIA NIM (check API key scope, đổi URL sang `/v1/embeddings` đúng)
   - Option B: Dùng `text-embedding-3-small` (OpenAI, 1536d) — đã có LLM key
   - Option C: Self-host SPECTER2 (768d, match S2 batch API) — consistent với existing
   - **Chú ý:** bất kỳ option nào đều phải flush ChromaDB hoặc rebuild collection với dim mới

2. **Phase 2-D (streaming gap) có thể song song** với Phase 2-A/B — không phụ thuộc embedding

3. **Pre-Phase 2 tech debt TIP** (nhỏ, ~20'): fix `_to_paper` + `choices=None` + migrate 2 S2 direct imports
