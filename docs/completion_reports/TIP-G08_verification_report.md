# VERIFICATION EVIDENCE REPORT — TIP-G08
**Branch:** `feat/gap-cold-start-mvp` | **HEAD:** `75b9a2e` | **Date:** 2026-06-20  
**Verifier:** Builder (Thợ) | **Status:** ⚠️ PARTIAL — see escalations below

---

## A. FUNCTIONAL E2E

### A1 — Topic thường: `"transformer attention mechanism"` (EN proxy)

| Step | Kết quả |
|---|---|
| clean_query | `"transformer attention mechanism"` (2.16s) |
| search | **10 papers** (1.62s) |
| snowball | 49 papers total (15.59s) |
| rank → top 10 | 10 papers |
| gate (≥ MIN=5) | **PASS** (10 ≥ 5) |
| pipeline | **RAN** — pipeline wall **164.1s** |
| GapReport | **10 gaps** detected |

**→ A1: ✅ PASS** — GapReport có gaps, không crash.

> ⚠️ **Issue A1-1:** Query gốc `"transformer efficiency long-context NLP research gap"` → clean ra `"transformer efficiency long-context NLP"` → S2 trả **0 papers**. Phải dùng query ngắn hơn `"transformer attention mechanism"`. `clean_query` đang rút ngắn quá nhiều — ghi nhận cho G10.

### A2 — Topic ngách: `"zygomorphic petals evolutionary biology micro-habitats obscure 1940"`

| Step | Kết quả |
|---|---|
| clean_query | `"zygomorphic petals evolutionary biology microhabitats 1940"` (1.57s) |
| search | **2 papers** (3.06s) |
| snowball | 2 papers (10.14s) |
| rank → top 2 | 2 papers |
| gate | **FAIL** (2 < MIN=5) → early return |
| GapReport | `gaps=[]` + narrative VN |
| UI | Không crash, GapResultPanel render narrative |

**→ A2: ✅ PASS** — insufficient path hoạt động đúng.

---

## B. MEASUREMENTS

### B1 — E2E@N=10 wall-time THẬT (LLM + S2 thật)

> **Lưu ý:** Node monkey-patching không capture được timing từng node vì LangGraph compile graph và capture ref tại compile-time (không phải invocation-time). Pipeline wall-time được đo bao gồm toàn bộ nodes.

| Stage | Wall-time ĐO | Ghi chú |
|---|---|---|
| clean_query | **2.16s** | LLM call |
| search (S2) | **1.62s** | 10 papers |
| snowball | **15.59s** | Seeds → 49 papers; 4 snowball errors |
| rank | **~0.01s** | Local, no I/O |
| **Pipeline (extractor→synthesizer)** | **164.10s** | N=10 @conc=5 |
| **Total E2E @N=10** | **~183.5s** | |

**Node breakdown bị BLOCKED** vì LangGraph capture node refs tại compile-time — monkey-patch không intercept được. Chỉ có tổng pipeline wall.

**📊 EXTRAPOLATION N=10 → N=30:**

```
Batch scaling: N=10 @conc=5 = 2 batches; N=30 @conc=5 = 6 batches
Pipeline time @N=10 = 164.1s (2 batches)
Pipeline time @N=30 ≈ 164.1 × (6/2) = 492.3s (~8.2 min)

Retrieval overhead: ~19.4s (fixed, does not scale with N)
E2E @N=30 ≈ 19.4 + 492.3 = ~512s (~8.5 min)
```

**→ E2E@N=30 ≈ 8.5 phút > 5 phút gate → ⛔ FAIL**

> **Cơ sở extrapolation:** Pipeline wall dominated bởi extractor (S2 retry timeout × 6 papers fail + PDF download) và LLM calls. Scaling linear với số batches là conservative (detector/verifier/counter là O(gaps) không O(N), nhưng extractor chiếm phần lớn 164.1s).

> **Correction từ G09-R:** G09-R đo 25.48s/5 papers (1 batch) → extrapolate 6 batches = 153s. Task-510 đo 164.1s cho 2 batches → extrapolate 6 batches = 492s. **Sự chênh lệch:** G09-R benchmark dùng N=5 với 3 papers fail sớm (timeout nhanh), task-510 có thêm PDF download (403 Forbidden, 30s timeout) và các retry dài hơn. **164.1s/2 batches là số thật đáng tin hơn.**

### B2 — YIELD THẬT

| Metric | Giá trị |
|---|---|
| Papers requested | 10 |
| Extracted OK | **4** |
| **YIELD** | **40%** |
| Failed | **6** |

**Lý do fail (6 papers):**
1. `9624170045b3c659a524f3a2461c49399c53a6ea` → S2 `get_paper_detail` fail (snowball error: `'NoneType' object is not iterable`)
2. `dceb29c843053cb850e5cf9b12bea30e4594f112` → S2 snowball error: same
3. `ef8d75f1de8d16411fef405c34c77639a2d266b1` → Pydantic validation: `paperId = None`
4. `719273b24e82cefab64b51e7f4488127d9b0d221` → Pydantic validation: `paperId = None`
5. `40205636069c955aadd1688a43ef86cf2bd160fb` → `Fetch failed` (sau PDF 403 Forbidden)
6. `7e109394990a54e7cb915f7ec891045bdeeab4c5` → `Fetch failed`

**Phân loại:**
- **S2 `get_paper_detail` HTTP fail / field mismatch:** 4/6 (67%)
- **PDF download 403 Forbidden:** 1/6 (17%)
- **Unknown fetch fail:** 1/6 (17%)

> **Đếm get_paper_detail fail:** 4 papers fail do S2 issues (paperId=None từ snowball = S2 returning malformed data, NoneType iteration = missing references field).

**→ Yield 40% → ⚠️ G10 BẮT BUỘC** (threshold: < 50%)

### B3 — Sufficiency gate

- Topic A1 (transformer): 10 papers xin → 10 qua gate → **gate PASS** (40% yield là sau gate, không phải trước)
- Extracted 4/10 — pipeline vẫn chạy vì gate check số papers trước extraction, không sau
- 10 gaps được synthesized từ 4 papers extract thành công → pipeline hoạt động đúng

**→ B3: ✅ Gate PASS** — với topic đủ rộng, corpus ≥ MIN=5 trước extraction.

---

## C. FE INTEGRATION

### C1 — Timeout

**Vite proxy config** (`frontend/vite.config.js:19-24`):
```js
proxy: {
  '/api': { target: 'http://localhost:8000', changeOrigin: true }
}
```

**Không có `timeout` setting** → Vite proxy dùng Node.js `http-proxy` default = **no timeout** (connection không bị cắt phía proxy). Tuy nhiên:
- Browser mặc định không có timeout với `fetch()` — request sẽ chờ đến khi server respond
- E2E @N=10 = 183s, @N=30 ≈ 512s → **browser sẽ không timeout phía Vite/proxy**
- Risk thực tế: user UX bị treo 3–8 phút mà không có progress indicator ngoài spinner

**→ C1: Vite proxy KHÔNG cắt request. Nhưng UX spin ~8 phút là vấn đề Phase 2 (streaming).**

### C2 — Render states

Đánh giá qua code review (`GapResultPanel.jsx`, `useGapStore.js`, `ColdStartInput.jsx`):

| State | Render | Bằng chứng |
|---|---|---|
| `gapLoading=true` | `<Centered icon="mdi:loading">Đang phân tích…</Centered>` | `GapResultPanel.jsx:28` |
| `gapError` (network/500) | `<Centered icon="mdi:alert-circle-outline">{error}</Centered>` | `GapResultPanel.jsx:29` |
| `gaps=[] + narrative` (insufficient) | Render narrative bình thường qua ReactMarkdown | `GapResultPanel.jsx:38-40` |
| `gapLoading=true` trên nút | Spinner + "Đang phân tích…" trong `ColdStartInput.jsx` | `ColdStartInput.jsx:74-76` |

> **⚠️ Issue C2-1:** `GapResultPanel` hiện render **chỉ `narrative`** (string) nhưng không render **individual `gaps` list** (gap type/statement/citations). `gapNarrative` được set = `data.narrative` — synthesizer tổng hợp gaps vào narrative. Nếu narrative rỗng mà gaps không rỗng → UI blank. Cần kiểm tra synthesizer luôn populate narrative. **Ghi nhận là in-zone fix cho TIP tiếp theo.**

> **⚠️ Issue C2-2:** `useGapStore.gapReport` store toàn bộ GapReport nhưng GapSection chỉ forward `gapNarrative` (narrative string) → `gaps[]` list không được render riêng lẻ. Nếu muốn render per-gap UI → cần pass `gapReport.gaps` qua. **Ghi nhận cho G10 / Phase 2.**

**→ C2: Loading ✅, Error ✅, Insufficient narrative ✅. Gap list riêng lẻ: KHÔNG render (chỉ narrative tổng hợp). In-zone fix cần thiết.**

---

## D. ISOLATION AUDIT

```
git diff --stat develop..HEAD

 backend/agent/gap_detection/nodes/extractor.py |  36 ++++-
 backend/agent/gap_detection/nodes/verifier.py  |  67 ++++++++-
 backend/agent/gap_detection/orchestrator.py    | 122 ++++++++++++++++
 backend/agent/gap_detection/query_cleaner.py   | 119 +++++++++++++++
 backend/agent/gap_detection/retrieval.py       | 191 +++++++++++++++++++++++++
 backend/agent/gap_detection/router.py          | 172 ++++++++++++++--------
 backend/agent/gap_detection/schemas.py         |   5 +
 backend/agent/gap_detection/settings.py        |  32 ++++-
 backend/api/__init__.py                        |   3 +-
 frontend/src/features/gap/ColdStartInput.jsx   | 106 ++++++++++++++
 frontend/src/features/gap/GapSection.jsx       |  85 ++++++-----
 frontend/src/features/gap/useGapStore.js       |  79 +++++++---
 12 files changed, 891 insertions(+), 126 deletions(-)
```

**Phân tích:**
- `backend/agent/gap_detection/**` — ✅ tất cả trong scope
- `frontend/src/features/gap/**` — ✅ tất cả trong scope
- `backend/api/__init__.py` — ✅ trong scope (mount gap_router)
- Không có `services/**` ✅
- Không có `research/**` ✅
- Không có `chat/**` ✅
- Không có `useResearchStore`/`useChatStore` active ✅
- Không có SSE ✅
- `graph.py` — **KHÔNG THAY ĐỔI** ✅ (graph nodes/edges nguyên vẹn)

> **⚠️ Issue D-1:** `backend/api/__init__.py` thay đổi **2 dòng thực chất** (1 import line + 1 include_router uncommenting), không phải "đúng 1 dòng" theo TIP spec (G01 spec nói "1 dòng mount"). Về logic: mount gap_router cần cả import lẫn include_router. Diff stat hiển thị `3 +-` vì 1 line thêm + 1 line đổi. **Tác động: không ảnh hưởng chức năng, nhưng vi phạm spec "1 dòng".** Báo cáo cho Chủ thầu.

**→ D: ✅ Trong scope** — không có breach. Issue D-1 là spec wording (2 dòng vs 1 dòng).

---

## E. REGRESSION — `tests/test_gap_*`

```
tests/test_gap_detection_schemas.py  — 19/19 PASSED ✅
tests/test_gap_e2e.py               — 19/19 PASSED ✅
tests/test_gap_endpoint.py          —  0/7  FAILED ❌
                                        38 passed, 7 failed total
```

### test_gap_endpoint.py — 7 FAIL (expected regression)

**Root cause:** `test_gap_endpoint.py` test **warm-start API** — patch `router.run_gap_detection` và `router.get_max_papers_for_gap`. Sau G05, `router.py` chuyển sang cold-start và **comment out** `run_gap_detection`/`get_max_papers_for_gap` import → attributes không còn tồn tại trên module → `AttributeError`.

**Đây là EXPECTED regression do G05 chuyển contract từ `{papers:[]}` sang `{topic:str}`.** Tests cần được cập nhật để test cold-start contract.

> ⚠️ **Escalate:** `test_gap_endpoint.py` cần rewrite để test `GapColdStartRequest{topic}` flow. Chủ thầu cần quyết có làm TIP-G10-tests không.

**→ E: ⚠️ 38 PASS, 7 FAIL (all expected regression từ G05 contract change)**

---

## F. REQ TRACEABILITY

> REQ-CS definitions không tìm thấy trong `/docs` — mapping dựa trên FOCUSED SCAN REPORT và TIP specs.

| REQ-CS | Yêu cầu | Implemented | Bằng chứng |
|---|---|---|---|
| **CS-01** | cold_start(topic) entry point | ✅ | `orchestrator.py::cold_start` |
| **CS-02** | clean_query VN→EN | ✅ | `query_cleaner.py::clean_query` |
| **CS-03** | S2 keyword search | ✅ | `retrieval.py::search` |
| **CS-04** | Snowball expansion | ✅ | `retrieval.py::snowball` |
| **CS-05** | Embedding-free deterministic rank | ✅ | `retrieval.py::rank` (term+citation+recency) |
| **CS-06** | MIN_PAPERS gate → insufficient GapReport | ✅ | `orchestrator.py:70-79` |
| **CS-07** | MAX_PAPERS_FOR_GAP cap (30) | ✅ | `settings.py::get_max_papers_for_gap` |
| **CS-08** | EXTRACTOR_CONCURRENCY=5 | ✅ | `settings.py` + `extractor.py` asyncio.Semaphore |
| **CS-09** | Raw abstract persist (fix circular proxy) | ✅ | `schemas.py::abstract` + `extractor.py` + `verifier.py` |
| **CS-10** | POST /api/gap {topic} → GapReport | ✅ | `router.py::detect_gaps_cold_start` |
| **CS-11** | FE ColdStartInput + cold-start store | ✅ | `ColdStartInput.jsx`, `useGapStore.js::findGapsFromTopic` |
| **CS-13** | decouple useResearchStore | ✅ | `useGapStore.js` — active import commented |

**→ F: ✅ REQ-CS 01–11, 13 đều implemented.**

---

## G. DECISION DATA (tóm tắt cho Chủ thầu)

| Metric | Giá trị ĐO | Ngưỡng | Quyết định |
|---|---|---|---|
| **E2E @N=10 thật** | **183.5s** | — | — |
| **E2E @N=30 extrapolated** | **~512s (~8.5 min)** | ≤ 300s (5 min) | ⛔ **FAIL → hạ cap** |
| **Yield thật** | **4/10 = 40%** | ≥80% no-G10 · 50–80% G10 nên · <50% G10 bắt buộc | ⛔ **<50% → G10 BẮT BUỘC** |
| **Sufficiency gate** | **PASS** (gate trước extraction) | ≥5 papers | ✅ |
| **Pipeline functional** | **✅ 10 gaps** | có gaps | ✅ |
| **Insufficient path** | **✅ gaps=[] + narrative** | không crash | ✅ |

### Cap-final recommendation (Thợ báo, Chủ thầu quyết):

```
E2E @N=30 ≈ 8.5 min > 5 min gate
→ Khuyến nghị hạ MAX_PAPERS_FOR_GAP từ 30 → N thoả ≤5 min

Back-calculate: 5 min / 8.5 min × 30 ≈ 17–18 papers (conservative)
→ Cap-safe ≈ 15–18 (cần validate bằng đo thật nếu có thể)
→ Hoặc: giữ 30 nhưng giảm PDF timeout (30s → 10s) + tăng concurrency (5 → 8–10, cần S2 key tier cao hơn)
```

---

## H. ISSUES / ESCALATIONS — KHÔNG TỰ FIX

| ID | Mức | Nội dung | Tác động |
|---|---|---|---|
| **H-1** | ⛔ CRITICAL | E2E@30 ~8.5 min > 5 min gate → cap 30 INVALID | Cần hạ cap hoặc tối ưu pipeline. Chủ thầu chốt cap-final |
| **H-2** | ⛔ CRITICAL | Yield 40% < 50% → G10 BẮT BUỘC | G10 phải fix S2 yield trước SHIP |
| **H-3** | ⚠️ HIGH | `test_gap_endpoint.py` 7/7 FAIL (warm-start tests cũ) | Cần rewrite tests cho cold-start contract |
| **H-4** | ⚠️ HIGH | S2 yield fail: 4/6 do `paperId=None` từ snowball | Snowball trả paper với paperId=None → extractor skip. Fix: filter paperId=None trong `retrieval.snowball` |
| **H-5** | ⚠️ MEDIUM | `clean_query` rút ngắn quá nhiều → "transformer efficiency long-context NLP research gap" → 0 S2 results | LLM over-distill topic. Cần guard: nếu search trả 0 → retry với topic gốc |
| **H-6** | ⚠️ MEDIUM | Node timing BLOCKED vì LangGraph capture refs tại compile-time | Monkey-patch không intercept được. Per-node breakdown cần approach khác (wrap tại node file level, không tại module level) |
| **H-7** | ⚠️ MEDIUM | `GapResultPanel` không render `gaps[]` list riêng lẻ | Chỉ render narrative tổng hợp. Nếu muốn per-gap UI → cần pass `gapReport.gaps` |
| **H-8** | ℹ️ LOW | `api/__init__.py` thay đổi 2 dòng thực chất (không phải 1 dòng) | Vi phạm spec wording nhỏ, không ảnh hưởng chức năng |
| **H-9** | ℹ️ LOW | Vite proxy không có timeout → user spin 8+ phút | Phase 2 fix: streaming/SSE |
| **H-10** | ℹ️ LOW | `synthesizer` log 4 fabricated citations bị strip | Citation guard hoạt động đúng — chỉ là warning |

---

## TỔNG KẾT

- **A (functional):** ✅ A1 GapReport 10 gaps · A2 insufficient correct
- **B (measurements):** ⛔ E2E@30 ~8.5min > 5min · Yield 40% < 50%
- **C (FE):** ✅ timeout OK · render states OK · gap list UI không render riêng (medium issue)
- **D (isolation):** ✅ trong scope, graph unchanged, 2 dòng api/__init__ (minor)
- **E (regression):** ⚠️ 38 PASS / 7 FAIL (test_gap_endpoint warm-start expected regression)
- **F (REQ):** ✅ CS-01..11, 13 implemented
- **G (decision):** ⛔ hạ cap từ 30 · ⛔ G10 bắt buộc
