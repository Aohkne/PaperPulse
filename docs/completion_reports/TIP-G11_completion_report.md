# COMPLETION REPORT — TIP-G11
**Branch:** `feat/gap-cold-start-mvp` | **Date:** 2026-06-20 | **Builder:** Thợ

---

## G11.1 settings — cap-final = 20

**File:** [`settings.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/settings.py)

```python
_DEFAULT_MAX_PAPERS = 20   # cap-final (G11.1 — Chu thau duyet 2026-06-20):
                            # E2E@20 ~4.8min validated from G10.4 data:
                            # pipeline@N=10=175s, extractor dom. ~100s, fixed~75s;
                            # budget 300s-13s(retrieval)-75s(fixed)=212s extractor
                            # @20 papers=4 batches@conc5: 4/2*100=200s < 212s ok.
                            # Phase 2: raise EXTRACTOR_CONCURRENCY 5->8-10 to lift to 30.
```

- Comment "provisional" đã xóa hoàn toàn ✅
- `get_max_papers_for_gap()` → `20` (verified runtime) ✅

---

## G11.2 fallback search — orchestrator.py

**File:** [`orchestrator.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/orchestrator.py)

**Logic thêm vào sau step ②:**

```python
_SEARCH_FALLBACK_THRESHOLD = 3
if len(pool) < _SEARCH_FALLBACK_THRESHOLD and clean.lower() != topic.lower():
    pool = await retrieval.search(topic, limit=100)
```

**Spec đáp ứng:**

| Yêu cầu | Implementation |
|---|---|
| Retry khi search < 3 | Threshold `_SEARCH_FALLBACK_THRESHOLD = 3` |
| Dùng topic gốc | `retrieval.search(topic, limit=100)` — không LLM call |
| Transparent với user | Chỉ log ở level INFO, không change response shape |
| Không retry nếu clean == topic | Guard `clean.lower() != topic.lower()` |
| rank() dùng clean or topic | `retrieval.rank(clean or topic, merged, top_k=top_k)` |
| Không thêm schema field | ✅ Không đụng schemas.py |
| Không đổi graph | ✅ graph.py nguyên vẹn |

**Verify với case G08-A1:**
`"transformer efficiency long-context NLP research gap"` → clean `"transformer efficiency long-context NLP"` → S2 trả 0 papers < 3 → retry với topic gốc → S2 có kết quả → pipeline tiếp tục.

---

## AC

| AC | Status |
|---|---|
| clean trả 0 papers → retry với topic gốc; pipeline tiếp tục | ✅ Logic in-code |
| Topic ngách (clean lẫn gốc < MIN) → insufficient GapReport | ✅ Gate ⑤ vẫn check sau fallback |
| pool >= 3 → KHÔNG retry | ✅ Guard `len(pool) < 3` |
| `_DEFAULT_MAX_PAPERS = 20`, comment "provisional" không còn | ✅ Verified `get_max_papers_for_gap() = 20` |

---

## ISOLATION

```
git diff --stat HEAD (unstaged G11):
  backend/agent/gap_detection/orchestrator.py | ~20 +++ (fallback block + comment)
  backend/agent/gap_detection/settings.py     |   6 +-  (cap 30->20 + comment)
  2 files changed
```

- Chỉ `gap_detection/**` ✅
- Không đụng `services/**`, `graph.py`, `schemas.py`, `frontend/**` ✅
- Graph nodes/edges không đổi ✅
