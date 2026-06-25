# COMPLETION REPORT — TIP-P2-05

**TIP-ID:** TIP-P2-05  
**Branch:** `feat/gap-cold-start-mvp`  
**Date:** 2026-06-21  
**Status:** ✅ DONE

---

## Claim schema (từ schemas.py): [fields]

### `Claim` model (`backend/models/claim.py`):
| Field | Type | Ghi chú |
|-------|------|---------|
| `id` | `str` (uuid) | auto-generated |
| `text` | `str` | claim text |
| `paper_id` | `str` (alias: `paperId`) | **dùng `paper_id=` khi construct** |
| `status` | Literal enum | `"pending"/"supported"/"partial"/"unsupported"/"uncertain"` |

### Schema khác giả định TIP — QUAN TRỌNG:

> ⚠️ TIP giả định `gap.supporting_claims` với `claim.text` và `claim.paper_id`.  
> **Thực tế:** `GapItem` KHÔNG có `supporting_claims`. Chỉ có:
> - `statement: str` — single gap statement string
> - `supporting_papers: list[PaperRef]` — list of paper references

**Adaptation:** `_verify_limitation()` decompose `gap.statement` (không phải từng claim riêng), rồi với mỗi sub-claim text × mỗi supporting paper → tạo `Claim(text=sc_text, paper_id=ref.paper_id)`.

---

## _decompose_claim: [prompt, fallback]

**Location:** [`verifier.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/nodes/verifier.py) (cuối file, ~line 220+)

### Prompt:
```
Break the following research claim into atomic sub-claims
(each expressing exactly ONE assertion).
Output ONLY a JSON array of strings, no preamble, no trailing text.

Claim: {claim_text}
```

### Fallback hierarchy:
1. **Length check** — `len(claim_text) < 50` → skip LLM, trả `[claim_text]` ngay
2. **LLM exception** → `logger.debug(...)` + trả `[claim_text]`
3. **JSON parse error** → trả `[claim_text]`
4. **Empty response / empty list** → trả `[claim_text]`
5. **Markdown fence stripping** — `re.sub(r"```(?:json)?\s*|```", "", raw)` trước khi parse

---

## _most_restrictive_status: [order]

```python
_STATUS_ORDER = {
    "unsupported": 0,   # most restrictive
    "partial":     1,
    "uncertain":   2,
    "supported":   3,   # least restrictive
}

def _most_restrictive_status(statuses: list[str]) -> str:
    if not statuses:
        return "uncertain"
    return min(statuses, key=lambda s: _STATUS_ORDER.get(s, 2))
```

Ví dụ: `["supported", "partial", "unsupported"]` → `"unsupported"`

---

## wire point trong _verify_limitation: [line]

**Diff logic tại `_verify_limitation()`** (từ ~line 154):

```python
# BEFORE (single claim verify):
claims = [Claim(text=gap.statement, paper_id=ref.paper_id) for ref in gap.supporting_papers]
results = await verify_claims(claims, paper_abstracts=gap_abstracts or None)
if any(c.status in _CONFIRMING_STATUSES for c in results): return _CONFIRMED
...

# AFTER (atomic sub-claim decomposition):
sub_claim_texts = await _decompose_claim(gap.statement)         # NEW: decompose
all_statuses: list[str] = []
for sc_text in sub_claim_texts:                                  # NEW: per sub-claim
    claims = [Claim(text=sc_text, paper_id=ref.paper_id) for ref in gap.supporting_papers]
    results = await verify_claims(claims, paper_abstracts=gap_abstracts or None)
    all_statuses.extend(c.status for c in results)              # collect all statuses
worst = _most_restrictive_status([s for s in all_statuses if s != "pending"])
if worst in _CONFIRMING_STATUSES: return _CONFIRMED             # map to outcome
```

---

## AC: [pass/fail]

| AC Scenario | Test | Status |
|-------------|------|--------|
| Complex claim → ≥2 sub-claims | `test_decompose_claim_splits_complex_claim` | ✅ PASS |
| LLM fail → fallback [claim_text], no raise | `test_decompose_claim_fallback_on_llm_exception` | ✅ PASS |
| Invalid JSON → fallback | `test_decompose_claim_fallback_on_invalid_json` | ✅ PASS |
| Short claim < 50 → skip LLM | `test_decompose_claim_skips_llm_for_short_claim` | ✅ PASS |
| Markdown fence stripped | `test_decompose_claim_strips_markdown_fences` | ✅ PASS |
| `["supported","partial","unsupported"]` → `"unsupported"` | `test_most_restrictive_status_mixed` | ✅ PASS |
| Empty statuses → `"uncertain"` | `test_most_restrictive_status_empty` | ✅ PASS |
| Sub-claim "unsupported" → gap NOT_CONFIRMED | `test_verify_limitation_unsupported_subclaim_downgrades_gap` | ✅ PASS |
| All "supported" → CONFIRMED | `test_verify_limitation_all_supported_confirms_gap` | ✅ PASS |
| verify_claims exception → ERROR | `test_verify_limitation_verify_exception_returns_error` | ✅ PASS |
| Regression all pass | Full suite 85/85 | ✅ PASS |

---

## REGRESSION: [85/85 PASS ✅]

```
tests/test_gap_verifier_atomic.py    16 passed  ← MỚI
tests/test_gap_co_occurrence.py      16 passed
tests/test_gap_chat_integration.py   18 passed
tests/test_gap_detection_schemas.py  10 passed
tests/test_gap_e2e.py                11 passed
tests/test_gap_endpoint.py            6 passed
tests/test_gap_streaming.py           8 passed
──────────────────────────────────────────────
TOTAL                                85 passed, 0 failed (1 expected Pydantic warning)
```

---

## DIFF: [file list]

| File | Type | Mô tả |
|------|------|-------|
| `backend/agent/gap_detection/nodes/verifier.py` | MODIFY | Thêm `_decompose_claim()`, `_most_restrictive_status()`, `_STATUS_ORDER`, `_MIN_CLAIM_LEN_FOR_DECOMPOSE`; wire vào `_verify_limitation()`; thêm imports `json`, `re`, `chat_completion` |
| `tests/test_gap_verifier_atomic.py` | **[MỚI]** | 16 tests: decompose (6), most_restrictive (6), wire (4) |
