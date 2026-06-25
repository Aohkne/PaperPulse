# COMPLETION REPORT — TIP-G06-R: Persist RAW abstract + fix circular proxy

## HEADER
- **TIP-ID:** TIP-G06-R (revise của G06 `1ccb8a3`)
- **Module:** `schemas.py` + `extractor.py` + `verifier.py`
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `371d895`
- **Date:** 2026-06-20
- **Status:** ✅ DONE — Bước 1 xác nhận Case C có giá trị; Bước 3 implemented

---

## BƯỚC 1 — KẾT LUẬN CASE C (read-only investigation)

**File:** `backend/services/citation_verifier.py`

### Logic Case C (line 118–130)

```python
# ── Case C: Abstract conservative (NEVER return Supported) ───────────
abstract = paper_abstracts.get(claim.paper_id)
if abstract:
    status, quote = await _llm_classify(abstract, claim.text, claim.paper_id, conservative=True)
    if status == "supported":
        status = "uncertain"      # ← chỉ cap "supported" → "uncertain"
    claim.status = status         # "partial", "unsupported", "uncertain" đều có thể
    ...
```

### `_STATUS_MAP` (line 51–57)
```python
_STATUS_MAP = {
    "supported":           "supported",
    "partially supported": "partial",       # ← có thể ra
    "partially":           "partial",       # ← có thể ra
    "unsupported":         "unsupported",   # ← có thể ra
    "uncertain":           "uncertain",
}
```

### Kết luận Bước 1: **Case C CÓ GIÁ TRỊ LỌC**

- **CHỈ cap** `"supported"` → `"uncertain"` (vì abstract không đủ để confirm).
- `"unsupported"` và `"partial"` **được giữ nguyên** — Case C có thể lọc gap sai.
- **Bằng chứng:** `citation_verifier.py:122–123` (`if status == "supported": status = "uncertain"`)
- **Nhánh chọn:** Bước 3 — IMPLEMENT ✅

### Vấn đề với proxy cũ (G06)
Proxy = `key_claims + limitation_statements + methodology`. LIMITATION gap được suy từ `limitation_statements`, rồi verify chống proxy **chứa chính** `limitation_statements` → LLM luôn thấy text khớp claim → gần như không bao giờ trả `unsupported` → mất khả năng lọc.

---

## BƯỚC 3 — IMPLEMENT

### 3 file thay đổi

#### 1. `schemas.py` — thêm `abstract: str | None = None`
```diff
 class ExtractedPaperData(BaseModel):
     ...
     extraction_source: str = "abstract"
+    # Raw abstract from Semantic Scholar (TIP-G06-R).
+    # Independent từ LLM-extracted fields — dùng cho verifier Case C.
+    abstract: str | None = None
```
Non-breaking: `default=None` → consumer cũ không vỡ.

#### 2. `extractor.py` — capture raw abstract, persist qua `extract_from_text`

```diff
 async def _process_one_paper(...):
     detail = await get_paper_detail(paper_ref.paper_id)
+    # 1b. Capture raw abstract TRƯỚC khi process (TIP-G06-R)
+    raw_abstract: str | None = detail.get("abstract") or None
     ...
-    return await extract_from_text(paper_ref, text, source=source, pdf_url=pdf_url)
+    return await extract_from_text(paper_ref, text, source=source, pdf_url=pdf_url,
+                                   raw_abstract=raw_abstract)

 async def extract_from_text(..., *, pdf_url=None, raw_abstract=None):
     return ExtractedPaperData(
         ...
+        abstract=raw_abstract or None,
     )
```

#### 3. `verifier.py::_build_abstracts_map` — raw first, proxy fallback

```diff
 def _build_abstracts_map(state):
     for item in extracted:
+        # 1. Raw abstract (non-circular)
+        if item.abstract and item.abstract.strip():
+            result[pid] = item.abstract.strip()
+            continue
+        # 2. Proxy fallback (chỉ khi raw None/empty)
         parts = [key_claims, limitation_statements, methodology]
         result[pid] = proxy
```

---

## VÍ DỤ RAW ABSTRACT VS PROXY

**Tình huống:** Paper "Transformer Efficiency Study", limitation_statement: "We only tested on translation tasks, not summarization."

Gap claim: "Transformer models have not been tested on summarization tasks."

| Nguồn | Nội dung |
|---|---|
| **Raw abstract (cũ G06 bị bỏ)** | "We present an efficient transformer architecture achieving 40% speedup on WMT translation benchmarks while maintaining BLEU scores." |
| **Proxy (vòng tròn G06)** | "Transformer models have high BLEU improvement. We only tested on translation tasks, not summarization. Attention mechanism." |

**Verify Case C:**
- Với **proxy** → LLM thấy "We only tested on translation tasks, not summarization" → khớp gần như exact với claim → gần như luôn `partial`/`supported` → gap **không bao giờ bị lọc**
- Với **raw abstract** → LLM thấy "efficient transformer, WMT, BLEU" → không nhắc đến summarization → trả `unsupported` hoặc `uncertain` → gap **có thể bị lọc nếu là hallucination**

---

## SELF-TEST KẾT QUẢ

```
schema: PASS
_build_abstracts_map RAW preferred: PASS
_build_abstracts_map proxy fallback: PASS
_build_abstracts_map empty-abstract proxy: PASS
extract_from_text raw_abstract persist: PASS → abstract: 'The REAL raw abstract.'
ALL PASS
```

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| Case C report: có trả unsupported/partial theo abstract không | ✅ Có — chỉ cap `supported`→`uncertain`; partial/unsupported giữ nguyên |
| `ExtractedPaperData.abstract` populate khi có S2 abstract | ✅ `extract_from_text` nhận `raw_abstract`, persist vào field |
| `_build_abstracts_map`: paper có raw → dùng raw | ✅ `if item.abstract: continue` |
| `_build_abstracts_map`: raw None → fallback proxy | ✅ Proxy path vẫn có |
| Regression: consumer không vỡ (field optional) | ✅ `abstract: str | None = None` default |

---

## KHÔNG CHẠM
- `services/citation_verifier.py` — không sửa gì ✅
- Graph structure/edges — không sửa gì ✅
- Frontend — không sửa gì ✅

---

## NEXT
TIP-G06-R unblock **TIP-G04** (orchestrator) và **TIP-G08** (e2e verify).
