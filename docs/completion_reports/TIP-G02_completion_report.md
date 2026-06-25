# COMPLETION REPORT — TIP-G02: retrieval.py — adapter seam

## HEADER
- **TIP-ID:** TIP-G02
- **Module:** `backend/agent/gap_detection/retrieval.py` (file MỚI)
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `4ffdb68`
- **Date:** 2026-06-20
- **Status:** ✅ DONE

---

## VIỆC ĐÃ LÀM

Tạo mới `backend/agent/gap_detection/retrieval.py` — adapter seam duy nhất
wrapping toàn bộ retrieval services cho gap cold-start pipeline.

### 3 hàm public

```python
async def search(clean_query: str, limit: int = 100) -> list[Paper]
async def snowball(pool: list[Paper], depth: int = 1) -> list[Paper]
async def rank(clean_query: str, papers: list[Paper], top_k: int) -> list[Paper]
```

### Imports trong retrieval.py (theo spec)

```python
from backend.models.paper import Paper
from backend.services.semantic_scholar import search_papers
from backend.services.snowball import run_snowball, select_seeds
```

Không import `hybrid_search`, `embed_text`, `vector_store`, hay service nào khác.

---

## RANKING MECHANISM — Quyết định & Lý do

### Lý do KHÔNG dùng `hybrid_search`

`hybrid_search` gọi `await embed_text(query)` tại line 45 bất kể env.
BM25-only path chỉ kích hoạt khi `embed_text()` trả `None`
(runtime-conditional: phụ thuộc `EMBEDDING_BASE_URL` env var unset).
**Không đảm bảo embedding-free by construction** → loại theo spec.

### Cơ chế Composite đã chọn

Sort key: `(-term_score, -citation_score, -recency_score, paper_id)` ascending.

| Thành phần | Công thức | Vai trò |
|---|---|---|
| **term_score** | `len(query_tokens ∩ doc_tokens) / len(query_tokens)` | Primary — relevance từ vựng; range [0.0, 1.0] |
| **citation_score** | `log(citationCount + 1)` | Secondary — ảnh hưởng học thuật; log-scale giảm outlier |
| **recency_score** | `float(year)` nếu year != None, else `0.0` | Tertiary — ưu tiên bài gần đây |
| **paper_id** | lexicographic ascending | Tiebreaker — đảm bảo determinism tuyệt đối bất kể input order |

**Tất định:** `sorted()` Python stable + complete tiebreaker → same input → same output guaranteed.

**Không I/O:** Toàn bộ tính toán local (`re`, `math`, `frozenset`). `rank()` có thể await an toàn không tốn cost.

---

## SELF-TEST KẾT QUẢ

```bash
python -c "..." (từ repo root, sys.path insert)
```

```
rank() PASS: deterministic, top_k=3 correct, A first
  Order: ['A', 'C', 'D']
rank() top_k>len PASS: 4
rank() abstract=None/empty PASS
ALL SELF-TESTS PASSED
```

**Order giải thích:**
- A = "deep learning transformers NLP" + abstract — 3/3 query tokens `{deep, learning, transformers}` match → term_score 1.0
- C = "deep learning image recognition" + abstract=None — 2/3 match → term_score 0.67
- D beats B vì D có citationCount=1000 (log≈6.9) > B có 200 (log≈5.3), mặc dù B recent hơn

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| `search()` → `list[Paper]` (len ≤ limit), không lỗi | ✅ (gọi `search_papers` trực tiếp, không lỗi với empty result) |
| `snowball()` → pool+new dedup, không trùng paperId | ✅ (`seen: set[str]` merge pool + new_papers) |
| `rank(top_k=30)` → `min(top_k, len)` papers, tất định, không cần embed/ChromaDB | ✅ 3 lần assert pass |
| Gọi `rank()` 2 lần cùng input → thứ tự giống hệt | ✅ (`ids1 == ids2`) |
| `abstract=None`/`""` không crash | ✅ (`paper.abstract or ""`) |

---

## PHÁT HIỆN NGOÀI SPEC (ghi chú cho Chủ thầu)

**Isolation AC cuối chưa 100%:** Ngoài `retrieval.py`, có 2 file pre-existing trong
`gap_detection/` cũng import `services.semantic_scholar` trực tiếp:

| File | Import |
|---|---|
| `nodes/counter_search.py:31` | `from backend.services.semantic_scholar import search_papers` |
| `chat_integration.py:26` | `from backend.services.semantic_scholar import search_papers` |

Đây là code cũ, KHÔNG được TIP-G02 chạm. Đây là tech debt của gap module hiện tại.
TIP-G02 chỉ đảm bảo `retrieval.py` là seam DUY NHẤT **trong cold-start path mới** (orchestrator sẽ import từ retrieval, không import services trực tiếp).

**Quyết định cần Chủ thầu:** Có yêu cầu migrate `counter_search.py` / `chat_integration.py`
sang dùng `retrieval.py` không, hay để như cũ?

---

## KHÔNG CHẠM

- `services/**` — không sửa gì
- `backend/api/**` — không sửa gì
- `frontend/**` — không sửa gì
- Các node gap hiện có — không sửa gì

---

## NEXT

TIP-G02 là prerequisite của **TIP-G04** (orchestrator.py sẽ `from backend.agent.gap_detection.retrieval import search, snowball, rank`).
TIP độc lập có thể dispatch song song: **G03, G06, G09**.
