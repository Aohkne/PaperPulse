# COMPLETION REPORT — TIP-P2-06

**TIP-ID:** TIP-P2-06  
**Branch:** `feat/gap-cold-start-mvp`  
**Date:** 2026-06-21  
**Status:** ✅ DONE

---

## hyde.py: [abstract length, embed via embed_text, fallback]

**File:** [`backend/agent/gap_detection/hyde.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/hyde.py) **[MỚI]**

### ⚠️ Deviation từ TIP spec — QUAN TRỌNG:

> TIP-P2-06.A giả định `get_embeddings_batch([fake_paper])` có thể embed abstract giả.  
> **Thực tế:** `get_embeddings_batch(paper_ids: list[str])` chỉ nhận **real paper IDs** và gọi S2 API — không thể embed arbitrary text.

**Adaptation:** Dùng `embed_text(abstract, input_type="query")` từ `services/embedding.py` — function này gọi configured `EMBEDDING_BASE_URL` và đã có defensive fallback (trả `None` nếu không configured).

### Pipeline:
```
clean_query
  → LLM prompt (HYDE_ABSTRACT_WORDS words abstract)
  → abstract text
  → embed_text(abstract, input_type="query")
  → list[float] | None
```

### Fallback hierarchy (tất cả trả None, không raise):
1. `len(clean_query) < HYDE_ABSTRACT_WORDS` — không check, LLM tự handle
2. LLM exception → None
3. LLM trả empty string → None
4. `embed_text` raise exception → None
5. `embed_text` trả None (EMBEDDING_BASE_URL unset) → None

**Default abstract length:** 80 words (`HYDE_ABSTRACT_WORDS` env var, min=10)

---

## gap_specter_store.py: [collection name, dim=768, upsert/query]

**File:** [`backend/agent/gap_detection/gap_specter_store.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/gap_specter_store.py) **[MỚI]**

| Setting | Value |
|---------|-------|
| Collection name | `gap_papers_specter` |
| Dim | 768 |
| Distance metric | cosine (`hnsw:space: cosine`) |
| Client type | `chromadb.EphemeralClient()` (in-memory, per-process) |

**Isolation:** KHÔNG import `services/vector_store.py`. Collection riêng, client riêng.

### Functions:
| Function | Signature | Mô tả |
|----------|-----------|-------|
| `get_specter_collection()` | `→ Collection` | Lazy-create ChromaDB collection |
| `upsert_papers(papers_with_vectors)` | `list[dict] → int` | Upsert {paper_id, vector, title, year} |
| `query_by_vector(vector, top_k)` | `→ list[str]` | Nearest-neighbour by cosine |
| `clear_collection()` | `→ None` | Delete + reset (tests + session refresh) |

**Test isolation note:** `clear_collection()` (delete trên current client) là cách đúng để reset giữa tests — `_client = None` không đảm bảo fresh state trong ChromaDB 1.5.9 vì EphemeralClient có thể share internal state trong cùng process.

---

## retrieval.rank(): [hybrid score formula, SPECTER2_WEIGHT, fallback]

**File:** [`backend/agent/gap_detection/retrieval.py`](file:///d:/vinuni/Project/Build_project/C2-App-069/backend/agent/gap_detection/retrieval.py) **[MODIFY]**

### Hybrid score formula:

```
w_sem  = get_specter2_weight()          # default 0.4 (env SPECTER2_WEIGHT)
w_bm25 = 1 - w_sem                      # default 0.6

bm25  = term_overlap + 0.1*log(cit+1) + 0.001*year
sem   = 1 - rank_position / N           # inverted rank [0,1]

combined = w_sem * sem + w_bm25 * bm25

sort_key = (-combined, -log(cit+1), -year, paper_id)   # deterministic
```

### Flow trong rank():
1. `clear_collection()` — reset store mỗi call
2. `get_embeddings_batch(paper_ids)` → fetch SPECTER2 vectors via S2
3. `upsert_papers(papers_with_vectors)` → populate gap store
4. `generate_hyde_vector(clean_query)` → HyDE query vector
5. `query_by_vector(hyde_vec, top_k=N)` → semantic ranking
6. Hybrid scoring → sort

### Fallback:
- SPECTER2 fetch fail → `specter_map = {}` (no upsert), `w_sem = 0` via `hyde_vec = None`
- HyDE fail → `hyde_vec = None` → `w_sem = 0.0` → pure BM25
- Semantic query fail → `semantic_order = {}` → `sem = 0.0` for all papers
- **Không crash, không mất output** ở bất kỳ failure point

---

## AC: [pass/fail]

| AC Scenario | Test | Status |
|-------------|------|--------|
| clean_query → list[float] | `test_generate_hyde_vector_success` | ✅ PASS |
| LLM fail → None no raise | `test_generate_hyde_vector_llm_fail_returns_none` | ✅ PASS |
| embed_text fail → None | `test_generate_hyde_vector_embed_fail_returns_none` | ✅ PASS |
| embed_text=None → None | `test_generate_hyde_vector_embed_returns_none` | ✅ PASS |
| 5 papers upsert → query ≤3 IDs | `test_specter_store_upsert_and_query` | ✅ PASS |
| Collection empty → [] | `test_specter_store_empty_query_returns_empty` | ✅ PASS |
| Missing vector skipped | `test_specter_store_upsert_skips_missing_vector` | ✅ PASS |
| hyde_vec=None → BM25 fallback | `test_rank_hyde_none_fallback_bm25` | ✅ PASS |
| Deterministic output | `test_rank_deterministic` | ✅ PASS |
| Semantic arm changes order | `test_rank_semantic_arm_changes_order` | ✅ PASS |
| Regression all pass | Full suite 101/101 | ✅ PASS |

---

## REGRESSION: [101/101 PASS ✅]

```
tests/test_gap_hyde_specter.py       16 passed  ← MỚI
tests/test_gap_verifier_atomic.py    16 passed
tests/test_gap_co_occurrence.py      16 passed
tests/test_gap_chat_integration.py   18 passed
tests/test_gap_detection_schemas.py  10 passed
tests/test_gap_e2e.py                11 passed
tests/test_gap_endpoint.py            6 passed
tests/test_gap_streaming.py           8 passed
──────────────────────────────────────────────
TOTAL                               101 passed, 0 failed
```

---

## DIFF: [file list]

| File | Type | Mô tả |
|------|------|-------|
| `backend/agent/gap_detection/hyde.py` | **[MỚI]** | HyDE abstract generation + `embed_text` (không dùng `get_embeddings_batch`) |
| `backend/agent/gap_detection/gap_specter_store.py` | **[MỚI]** | ChromaDB EphemeralClient 768d cosine, isolated từ `services/vector_store.py` |
| `backend/agent/gap_detection/settings.py` | MODIFY | Thêm `_DEFAULT_HYDE_ABSTRACT_WORDS=80`, `_DEFAULT_SPECTER2_WEIGHT=0.4`, getters |
| `backend/agent/gap_detection/retrieval.py` | MODIFY | Hybrid rank: SPECTER2 fetch + HyDE query + inverted-rank semantic score |
| `tests/test_gap_hyde_specter.py` | **[MỚI]** | 16 tests: hyde (5), store (3), rank (4), settings (4) |
