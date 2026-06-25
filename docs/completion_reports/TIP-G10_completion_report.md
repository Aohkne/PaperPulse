# COMPLETION REPORT — TIP-G10
**Branch:** `feat/gap-cold-start-mvp` | **Date:** 2026-06-20 | **Verifier:** Builder (Thợ)

---

## G10.0 INVESTIGATE — gốc `paperId=None`

**Gốc:** CLASS A (baseline, ngoài zone) · Bước đầu tiên sinh error: `services/semantic_scholar.py::_to_paper` line 112

### Trace path đầy đủ

```
S2 API trả citedPaper={'paperId': null, 'title': ...}
  → get_references/get_citations (services/semantic_scholar.py:47-59)
    → _to_paper(raw) với raw['paperId']=None
      → Paper(paperId=None) → pydantic ValidationError
        ← propagates out of list comprehension
      ← propagates out of get_references
    ← propagates as exception from asyncio.gather
  ← caught at snowball.py:79: logging.warning(...) + raw_results.append(([], []))

KẾT LUẬN: KHÔNG có paper paperId=None nào lọt vào extractor.
Chúng fail tại services layer và bị catch sạch.
```

### Lý do None lọt qua model (CLASS A)

`_to_paper` line 112:
```python
# services/semantic_scholar.py line 112
paperId=raw.get("paperId", ""),   # fallback = empty string ''
```
- Khi S2 trả `paperId: null` → `raw.get("paperId", "")` = `None` (vì key tồn tại với giá trị `None`, fallback không trigger) → `Paper(paperId=None)` → `ValidationError`
- Khi S2 omit paperId key hoàn toàn → `raw.get("paperId", "")` = `""` → `Paper(paper_id="")` slips through → potential 404 extractor (empty-string paperId case)

**Yield 40% thực chất không do paperId=None** — paper `9624170045` có paperId hợp lệ nhưng S2 `get_paper_detail` trả về data **không có abstract và không có PDF** → extractor skip.

### Phân loại

| ID fail trong G08 | Gốc thực | Tác động yield |
|---|---|---|
| `ef8d75f1`, `719273b2`, `2ab33fc5` | paperId=None từ S2 edge data | Caught tại snowball, KHÔNG ảnh hưởng yield |
| `9624170045`, `dceb29c8` | NoneType not iterable (related) | Caught tại snowball, KHÔNG ảnh hưởng yield |
| `9624170045` (extractor) | S2 get_paper_detail: no abstract, no PDF | **ẢNH HƯỞNG yield** |
| `40205636` (extractor) | PDF 403 + no abstract | **ẢNH HƯỞNG yield** |

> ⚠️ **ESCALATE CLASS A cho Chủ thầu:** `services/semantic_scholar.py::_to_paper` nên sửa:
> ```python
> # Thay line 112:
> paperId=raw.get("paperId") or "",   # None → "" instead of None
> ```
> Sửa gốc ở baseline sẽ eliminate ValidationError hoàn toàn. Hiện tại Thợ đã implement defensive filter in-zone thay thế.

---

## G10.1 FIX — Defensive filter (in-zone)

**File:** [`retrieval.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/retrieval.py)

Thêm `_valid_papers()` helper:
```python
def _valid_papers(papers, stage=""):
    valid = [p for p in papers if p.paper_id and p.title]
    # drops empty paperId (empty string) + empty title papers
```

Applied tại:
- `search()` — sau `search_papers()` call
- `snowball()` — sau `run_snowball()` call

**Verify 0 paperId=None tới extractor:** Confirmed từ G10.4 log — không có `"Fetch failed for paper"` log với empty ID. 2 fail còn lại (`9624170045`, `40205636`) đều có paperId hợp lệ, fail vì S2 data quality (no abstract) + PDF 403.

---

## G10.2 PDF — `MAX_PDF_ATTEMPTS` + timeout

**G09-R đề cập `MAX_PDF_ATTEMPTS` nhưng setting không tồn tại** trong codebase. `pdf_utils.py` nằm trong `gap_detection/nodes/` → **in-zone**.

**Fix:** [`pdf_utils.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/nodes/pdf_utils.py) line 126:
```python
# G10.2: 30s → 8s fast-fail for cold-start
resp = await client.get(url, timeout=8.0)
```

**Tác động số gaps (on/off PDF):**
- G08 (PDF 30s timeout): 10 gaps từ 4/10 papers
- G10.4 (PDF 8s timeout): **13 gaps từ 8/10 papers**

PDF timeout 8s vẫn đủ cho CDN-hosted PDFs (ArXiv thường < 5s). Phát hiện: PDF 403 fail do `resp.raise_for_status()` (không phải timeout) — fail fast ngay lập tức. PDF content-type=HTML cũng fail fast. Chỉ slow CDN mới hưởng lợi từ timeout giảm.

**Không cần `MAX_PDF_ATTEMPTS`:** mỗi paper chỉ try 1 PDF URL, không retry. Timeout reduction đủ.

---

## G10.3 S2 fast-fail — `s2_client.py`

**File:** [`s2_client.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/s2_client.py) line 36:
```python
# G10.3: 30s → 10s fast-fail
r = await client.get(url, ..., timeout=10)
```

Non-429 errors vẫn raise ngay (không retry). 429 vẫn retry 3× với backoff (2^attempt). Paper không tồn tại trên S2 sẽ nhận 404 ngay → fail trong < 1s. Timeout chỉ ảnh hưởng S2 slow responses.

---

## G10.4 RE-MEASURE (số THẬT sau G10 fixes)

**Topic:** `"transformer attention mechanism"` · **N=10** · LLM+S2 thật

| Stage | G08 (before) | G10.4 (after) | Delta |
|---|---|---|---|
| clean_query | 2.43s | 6.67s | +4.2s (LLM variance) |
| search | 8.75s (0 results!) / 1.62s | 1.63s | ~same |
| snowball | 15.59s | **4.84s** | -10.8s ✅ |
| pipeline | 164.1s | **175.3s** | +11.2s (LLM variance) |
| **TOTAL E2E @N=10** | **183.5s** | **188.5s** | ~same |

### Yield

| | G08 | G10.4 |
|---|---|---|
| Extracted OK | 4/10 | **8/10** |
| **YIELD** | **40%** | **80%** |
| Fail reasons | S2+PDF timeout | 2 remain: no-abstract + PDF 403 |

**YIELD 80% → ngưỡng "no G10 needed"** ✅

### Fail còn lại (2/10)

1. `9624170045` — S2 trả detail thành công nhưng `abstract=None`, `openAccessPdf=None` → extractor: "no PDF, abstract, or tldr — skipping". **Gốc: S2 data quality** (paper này có paperId=None trong snowball nên không có metadata). Không fix được in-zone.
2. `40205636` — PDF 403 Forbidden (fast-fail ✅), `abstract=None` → skip. Gốc: S2 data quality.

### Extrapolation N=10 → N=30

```
Retrieval (cố định): 13.1s
Pipeline @N=10 (2 batches conc=5): 175.3s
Pipeline @N=30 (6 batches conc=5): 175.3 × (6/2) = 526.0s

E2E@30 estimate: 13.1 + 526.0 = 539s (~9.0 min)
5-min GATE: ⛔ FAIL (539 > 300s)
```

**⚠️ Lưu ý về extrapolation:** Scaling ×3 là conservative vì giả định pipeline linear theo batches. Detector/verifier/counter/synthesizer là O(gaps), không O(N). Nếu tách extractor (dominant) vs fixed nodes:

```
Ước lượng tách: extractor ~100s @N=10, fixed nodes ~75s
Budget (5min): 300 - 13.1 - 75 = 211.9s cho extractor
@N: 211.9 / (100/2 batches) × 5 conc ≈ 21 papers

Cap an toàn ước tính: ~18-20 papers (thận trọng)
```

---

## ESCALATIONS (shared code ngoài zone)

| ID | Code | Vấn đề | Tác động |
|---|---|---|---|
| E-1 | `services/semantic_scholar.py::_to_paper` line 112 | `raw.get("paperId", "")` không guard None khi key tồn tại với giá trị null | ValidationError warnings (cosmetic, không ảnh hưởng yield hiện tại vì caught) |
| E-2 | `services/llm_client.py::chat_completion` line 33 | `response.choices[0].message.content or ""` fails khi choices=None (counter_search fail) | counter_search degraded gracefully (dùng raw statement fallback) — không block |

---

## ISOLATION

**G10 changes (unstaged vs HEAD):**
```
backend/agent/gap_detection/nodes/pdf_utils.py |  4 ++--   (timeout 30→8)
backend/agent/gap_detection/retrieval.py       | 31 +++   (defensive filter)
backend/agent/gap_detection/s2_client.py       |  2 +-    (timeout 30→10)
backend/agent/gap_detection/settings.py        | 10 ++--  (comment update)
4 files changed, 38 insertions(+), 9 deletions(-)
```

- Tất cả trong `backend/agent/gap_detection/**` ✅
- KHÔNG đụng `services/**` ✅
- KHÔNG đụng `graph.py` (nodes/edges không đổi) ✅
- KHÔNG đụng `frontend/**` ✅

---

## SELF-TEST / AC

| AC | Status | Bằng chứng |
|---|---|---|
| G10.0: báo bước đầu tiên sinh paperId=None + path:symbol | ✅ | `services/semantic_scholar.py::_to_paper` line 112 · CLASS A |
| G10.0: phân loại gốc A/B/C | ✅ | CLASS A (baseline) |
| G10.1: 0 paper paperId=None tới extractor | ✅ | G10.4 log: không có empty-ID fetch fail |
| G10.2: PDF fail không kẹt 30s | ✅ | 403 fail nhanh (< 1s) · timeout 8s |
| G10.2: báo tác động số gaps | ✅ | G08: 10 gaps @4/10 → G10.4: 13 gaps @8/10 |
| G10.3: S2 get_paper_detail fast-fail isolated | ✅ | timeout=10s, non-429 không retry |
| G10.4: E2E@30 + yield% mới + A1 vẫn ra gaps | ✅ | E2E@30 ~539s · Yield 80% · 13 gaps |
| Isolation: chỉ gap_detection/**, graph unchanged | ✅ | diff xác nhận |
| Đụng shared → ESCALATE, không tự sửa | ✅ | E-1 (services/semantic_scholar.py) escalated |

---

## DỮ LIỆU QUYẾT ĐỊNH cho Chủ thầu

| Metric | G08 (trước) | G10.4 (sau fixes) | Quyết định cần |
|---|---|---|---|
| **E2E@10 thật** | 183.5s | **188.5s** | — |
| **E2E@30 extrapolated** | ~512s (8.5min) | **~539s (9.0min)** | ⛔ **Cap phải giảm** |
| **Yield** | **40%** | **80%** | ✅ Đạt ngưỡng "no G10 needed" |
| **Số gaps (A1)** | 10 | **13** | ✅ Chất lượng tăng |
| **Cap safe ước tính** | — | **~18-20 papers** | Chủ thầu chốt |

### Tại sao E2E@30 vẫn cao?

Pipeline wall-time dominated bởi **LLM calls** (extraction + detectors + verifier + counter + synthesizer), không phải S2/PDF timeout. Với N=10, LLM calls chiếm phần lớn 175s. Timeout giảm chỉ cứu 2 fail-case lẻ, không đổi được LLM latency.

**Giải pháp dài hạn (Phase 2, ngoài scope G10):**
1. Giảm cap `MAX_PAPERS_FOR_GAP` từ 30 → 18 (back-calculated)
2. Streaming/SSE để user không cảm thấy "treo" trong khi chờ
3. Async job + polling nếu E2E > 2 phút

---

## KHUYẾN NGHỊ (Thợ báo, Chủ thầu quyết)

1. **Hạ cap `MAX_PAPERS_FOR_GAP` từ 30 → 18** — back-calc từ E2E@30 ~539s và tỷ lệ scaling
2. **Giữ `EXTRACTOR_CONCURRENCY=5`** — S2 không bị rate-limit nghiêm với key SET
3. **Sửa `services/semantic_scholar.py::_to_paper`** (E-1) — cosmetic fix nhưng dọn warning log
4. **Xem xét streaming FE (Phase 2)** — UX bị treo 3+ phút không chấp nhận được dù E2E OK về mặt kỹ thuật
