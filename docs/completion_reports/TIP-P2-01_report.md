# COMPLETION REPORT — TIP-P2-01

**TIP-ID:** TIP-P2-01  
**Branch:** `feat/gap-cold-start-mvp`  
**Date:** 2026-06-21  
**Status:** ✅ DONE

---

## A — `choices=None` guard: [FIXED]

**File:** [`backend/services/llm_client.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/services/llm_client.py)

- Added `import logging` + `logger = logging.getLogger(__name__)`
- Replaced line 33 (`return response.choices[0].message.content or ""`) with safe guard:
  ```python
  choices = response.choices
  if not choices:
      logger.warning("llm_client: response.choices is None/empty — returning empty string")
      return ""
  return choices[0].message.content or ""
  ```
- **AC verified:** returns `""` (không raise `TypeError`) khi `choices=None`; logs WARNING "response.choices is None/empty"

---

## B1 — Log retry exhaustion: [FIXED]

**File:** [`backend/services/semantic_scholar.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/services/semantic_scholar.py)

- Added `logger.warning("S2 _get: all retries exhausted for %s — returning empty (rate-limit or API down)", url)` TRƯỚC `return {}`
- **AC verified:** log xuất hiện sau khi hết 3 retry, không raise exception

---

## B2 — Rate-limit delay: [default=1.0, env-configurable]

**File:** [`backend/services/semantic_scholar.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/services/semantic_scholar.py)

- Added `import os as _os` (underscore prefix, tránh pollute namespace)
- Added module-level constant:
  ```python
  _S2_REQUEST_DELAY = float(_os.getenv("S2_REQUEST_DELAY", "1.0"))
  # default 1.0 = ~1 req/s (unauthenticated)
  # override: S2_REQUEST_DELAY=0.0 nếu có key tier cao hơn
  ```
- Added delay TRƯỚC HTTP call trong `_get()`:
  ```python
  if _S2_REQUEST_DELAY > 0:
      await asyncio.sleep(_S2_REQUEST_DELAY)
  ```
- **AC verified:**
  - Default `S2_REQUEST_DELAY=1.0` → `asyncio.sleep(1.0)` được gọi
  - `S2_REQUEST_DELAY=0.0` → không có delay (condition `> 0` fails)

---

## C — Migration `retrieval.search()`: [counter_search ✅ | chat_integration ✅ | circular import check ✅]

### `counter_search.py`

**File:** [`backend/agent/gap_detection/nodes/counter_search.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/nodes/counter_search.py)

- Replaced: `from backend.services.semantic_scholar import search_papers`
- With: `from backend.agent.gap_detection import retrieval`
- Call site (~line 91): `await search_papers(...)` → `await retrieval.search(query, limit=DEFAULT_SEARCH_LIMIT)`
- Docstring updated

### `chat_integration.py`

**File:** [`backend/agent/gap_detection/chat_integration.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/chat_integration.py)

- Replaced: `from backend.services.semantic_scholar import search_papers`
- With: `from backend.agent.gap_detection import retrieval`
- Call site (~line 68): `await search_papers(...)` → `await retrieval.search(query, limit=BASELINE_SEARCH_LIMIT)`
- Docstring updated

### Circular import check ✅

```
retrieval.py → services.semantic_scholar  (OK)
counter_search.py → retrieval            (OK, không ngược)
chat_integration.py → retrieval          (OK, không ngược)
retrieval.py ↛ counter_search.py        (verified)
retrieval.py ↛ chat_integration.py      (verified)
```

---

## Test mock migration (FE export rule applied)

Vì `search_papers` không còn là symbol trong `chat_integration` và `counter_search`, các tests mock cũ bị broken. Đã update:

- **`tests/test_gap_chat_integration.py`**: 4 patch targets `{_CI}.search_papers` → `{_CI}.retrieval.search`
- **`tests/test_gap_e2e.py`**: `_patch_pipeline()` refactored — patch tại source `backend.agent.gap_detection.retrieval.search` với `side_effect` phân biệt baseline calls (`limit=10`) và counter calls (`limit=5`). Assertions updated dùng `await_args_list` filter.

---

## REGRESSION: test_gap_* [45/45 PASS ✅]

```
tests/test_gap_chat_integration.py   18 passed
tests/test_gap_detection_schemas.py  10 passed
tests/test_gap_e2e.py                11 passed
tests/test_gap_endpoint.py            6 passed
─────────────────────────────────────────────
TOTAL                                45 passed, 0 failed
```

---

## DIFF: file list + line counts

| File | Type | Lines changed |
|------|------|--------------|
| `backend/services/llm_client.py` | MODIFY | +6 (logging import, logger, guard block) |
| `backend/services/semantic_scholar.py` | MODIFY | +9 (os import, _S2_REQUEST_DELAY, logger, delay, warning log) |
| `backend/agent/gap_detection/nodes/counter_search.py` | MODIFY | +3 (docstring, import swap, call site) |
| `backend/agent/gap_detection/chat_integration.py` | MODIFY | +3 (docstring, import swap, call site) |
| `tests/test_gap_chat_integration.py` | MODIFY | +4 (4 patch target updates) |
| `tests/test_gap_e2e.py` | MODIFY | +18 (_patch_pipeline refactor + assertion updates) |
