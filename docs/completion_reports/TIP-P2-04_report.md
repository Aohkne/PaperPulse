# COMPLETION REPORT — TIP-P2-04

**TIP-ID:** TIP-P2-04  
**Branch:** `feat/gap-cold-start-mvp`  
**Date:** 2026-06-21  
**Status:** ✅ DONE

---

## ExtractedPaperData fields tìm được: [method field, domain field]

> ⚠️ **Schema khác giả định TIP:** `methodology_tags` và `domain_tags` KHÔNG tồn tại trong `ExtractedPaperData`.

| Field TIP giả định | Field thực tế trong schemas.py | Type | Ghi chú |
|--------------------|-------------------------------|------|---------|
| `methodology_tags` | `methodology` | `str \| None` | Single string, không phải list. Cần split trên `,`/`/` |
| `domain_tags` | `topics` | `list[str]` | Multi-valued, đúng như domain list |

**Adaptation thực hiện:** `co_occurrence.py` implements `_normalise_method()` để split compound methodology strings (e.g. `"BERT, fine-tuning"` → `["bert", "fine-tuning"]`). `topics` được dùng trực tiếp làm domain tokens (lowercased).

---

## co_occurrence.py: [build_co_occurrence, find_underexplored_pairs]

**File:** [`backend/agent/gap_detection/co_occurrence.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/co_occurrence.py) **[MỚI]**

### Functions:

| Function | Signature | Mô tả |
|----------|-----------|-------|
| `_normalise_method(methodology)` | `str \| None → list[str]` | Split compound methodology trên `,`/`/`, lowercase |
| `build_co_occurrence(extracted_data)` | `list → dict[tuple, int]` | Đếm số papers cover mỗi (method, domain) pair |
| `find_underexplored_pairs(matrix, methods, domains, threshold)` | `→ list[tuple]` | Trả pairs có count < threshold |
| `collect_corpus_vocab(extracted_data)` | `→ (list[str], list[str])` | Thu thập all unique methods + domains (sorted, deduped) |

### Pure module constraints:
- Không có I/O, không có LLM calls, không có side effects
- `defaultdict` → converted to `dict` trước khi return
- Tất cả string comparisons lowercase-normalised

---

## method_detector.py: [wire point, line changed]

**File:** [`backend/agent/gap_detection/nodes/method_detector.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/nodes/method_detector.py)

### Wire point — `method_detector_node()` (line ~105–120):
```python
# Thêm sau: paper_index = {...}
co_matrix = build_co_occurrence(extracted)
all_methods, all_domains = collect_corpus_vocab(extracted)
underexplored = set(find_underexplored_pairs(co_matrix, all_methods, all_domains))

matrix = _build_method_matrix(extracted, underexplored)   # ← param mới
```

### `_build_method_matrix()` — annotation logic (line ~150–180):
- Signature: `_build_method_matrix(extracted, underexplored: set | None = None)`
- Với mỗi paper có method + topics: kiểm tra primary method token có pair nào UNDEREXPLORED không
- Annotate `[UNDEREXPLORED domains exist]` hoặc `[COVERED]` vào dòng `method:` của prompt
- LLM nhận tín hiệu rõ ràng để tránh sinh gap cho well-covered pairs

### Import thêm:
```python
from backend.agent.gap_detection.co_occurrence import (
    build_co_occurrence,
    collect_corpus_vocab,
    find_underexplored_pairs,
)
```

---

## CO_OCCURRENCE_THRESHOLD default=2 trong settings

**File:** [`backend/agent/gap_detection/settings.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/settings.py)

```python
_DEFAULT_CO_OCCURRENCE_THRESHOLD = 2  # gap if < 2 papers cover (method, domain) pair

def get_co_occurrence_threshold() -> int:
    """Configurable via CO_OCCURRENCE_THRESHOLD env var (default 2)."""
    val = os.environ.get("CO_OCCURRENCE_THRESHOLD")
    ...
```

- Default = 2 (pair cần ≥2 papers mới "covered")
- Min bound = 1 (để tránh threshold=0 vô nghĩa)
- Invalid env → fallback về default 2

---

## REGRESSION: test_gap_* [69/69 PASS ✅]

```
tests/test_gap_co_occurrence.py      16 passed  ← MỚI
tests/test_gap_chat_integration.py   18 passed
tests/test_gap_detection_schemas.py  10 passed
tests/test_gap_e2e.py                11 passed
tests/test_gap_endpoint.py            6 passed
tests/test_gap_streaming.py           8 passed
──────────────────────────────────────────────
TOTAL                                69 passed, 0 failed
```

### AC verification:
| AC Scenario | Status |
|-------------|--------|
| 3 papers (transformer, NLP) → count=3 | ✅ `test_build_co_occurrence_counts_pairs` |
| (transformer, vision)=0 → in underexplored | ✅ `test_find_underexplored_pairs_below_threshold` |
| (transformer, NLP)=3 → NOT in underexplored | ✅ `test_find_underexplored_pairs_below_threshold` |
| method_detector không sinh gap cho covered pairs | ✅ `test_method_detector_no_gap_for_covered_pairs` |
| method_detector prompt có `[COVERED]` annotation | ✅ `test_method_detector_prompt_contains_covered_annotation` |
| method_detector prompt có `[UNDEREXPLORED]` annotation | ✅ `test_method_detector_prompt_contains_underexplored_annotation` |
| Regression tests all pass | ✅ 69/69 |

---

## DIFF: [file list]

| File | Type | Mô tả |
|------|------|-------|
| `backend/agent/gap_detection/co_occurrence.py` | **[MỚI]** | Pure co-occurrence matrix functions |
| `backend/agent/gap_detection/settings.py` | MODIFY | Thêm `_DEFAULT_CO_OCCURRENCE_THRESHOLD` + `get_co_occurrence_threshold()` |
| `backend/agent/gap_detection/nodes/method_detector.py` | MODIFY | Import co_occurrence, wire filtering, update `_build_method_matrix()` signature |
| `tests/test_gap_co_occurrence.py` | **[MỚI]** | 16 tests: co_occurrence unit + settings + method_detector wiring |
