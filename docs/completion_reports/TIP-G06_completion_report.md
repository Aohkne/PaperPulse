# COMPLETION REPORT — TIP-G06: Fix verify_claims nhận paper_abstracts (OQ-05)

## HEADER
- **TIP-ID:** TIP-G06
- **Module:** `backend/agent/gap_detection/nodes/verifier.py` (sửa file có sẵn)
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `1ccb8a3`
- **Date:** 2026-06-20
- **Status:** ✅ DONE

---

## BUG GỐC (OQ-05)

`_verify_limitation()` gọi `verify_claims(claims)` **không truyền `paper_abstracts`**.
Hậu quả: khi S2 snippet (Case A) miss và arXiv (Case B) miss,
`verify_claims` Case C không có abstract để so sánh
→ tất cả LIMITATION gaps bị ép status `"uncertain"` → bị drop.

---

## PHÂN TÍCH TRƯỚC KHI SỬA

**Vấn đề nguồn:** `ExtractedPaperData` schema **không có field `abstract` raw**.
Extractor node dùng `get_paper_detail()` lấy abstract tạm để gửi LLM,
nhưng không persist vào `GapDetectionState.extracted_data`.

**Giải pháp:** Synthesise proxy abstract từ các fields semantic đã có
trong `ExtractedPaperData`:
- `key_claims` — main findings
- `limitation_statements` — limitation text
- `methodology` — method description

Proxy này đủ cho Case C (LLM so sánh claim với context text).

---

## VIỆC ĐÃ LÀM

### Thay đổi trong `nodes/verifier.py`

**1. Thêm hàm `_build_abstracts_map(state)` (private)**

```python
def _build_abstracts_map(state: GapDetectionState) -> dict[str, str]:
    """Build {paper_id → abstract_proxy} from state["extracted_data"]."""
    extracted = state.get("extracted_data", []) or []
    result: dict[str, str] = {}
    for item in extracted:
        pid = item.paper_ref.paper_id if item.paper_ref else None
        if not pid:
            continue
        parts = []
        if item.key_claims:       parts.append(" ".join(item.key_claims))
        if item.limitation_statements: parts.append(" ".join(item.limitation_statements))
        if item.methodology:      parts.append(item.methodology)
        proxy = " ".join(parts).strip()
        if proxy:
            result[pid] = proxy
    return result
```

**2. `verifier_node` build map và truyền vào `_verify_limitation`**

```diff
+    extracted_data_map = _build_abstracts_map(state)
     for gap in candidates:
         ...
-        outcome = await _verify_limitation(gap)
+        outcome = await _verify_limitation(gap, extracted_data_map)
```

**3. `_verify_limitation` refactor: nhận `paper_abstracts` + truyền xuống `verify_claims`**

```diff
-async def _verify_limitation(gap: GapItem) -> str:
+async def _verify_limitation(gap: GapItem, paper_abstracts: dict[str, str]) -> str:
     ...
+    gap_abstracts = {
+        ref.paper_id: paper_abstracts[ref.paper_id]
+        for ref in gap.supporting_papers
+        if ref.paper_id in paper_abstracts
+    }
-    results = await verify_claims(claims)
+    results = await verify_claims(claims, paper_abstracts=gap_abstracts or None)
```

**Guard:** `gap_abstracts or None` — nếu không có paper nào trong map → truyền `None`
(giữ nguyên behavior cũ, không crash).

---

## CALL SITE CHECK

Chỉ có **1 call site** của `verify_claims` trong `verifier.py` (line 123).
Đã sửa. Không có call site nào khác trong node.

Không sửa `services/citation_verifier.py`.

---

## SELF-TEST KẾT QUẢ

```
_build_abstracts_map: PASS -> ['P1']
_build_abstracts_map(empty state): PASS
_verify_limitation: paper_abstracts passed correctly PASS
_verify_limitation(no abstracts -> None): PASS
ALL SELF-TESTS PASSED
```

**Test chi tiết:**
- `_build_abstracts_map`: P1 có content → trong map; P2 empty → không có trong map ✅
- `_verify_limitation`: khi có abstract, `verify_claims` nhận đúng `paper_abstracts={'P1': '...'}` ✅
- `_verify_limitation`: khi không có abstract (paper_id không trong map), `paper_abstracts=None` → fallback an toàn ✅

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| LIMITATION gap có supporting paper kèm extracted_data → `verify_claims` nhận `paper_abstracts` không rỗng | ✅ Test mocked xác nhận |
| snippet + arXiv miss nhưng có abstract → Case C dùng được | ✅ `paper_abstracts` được truyền → `verify_claims` có text để so sánh |
| Gap không có paper trong extracted_data → `paper_abstracts=None` (behavior cũ) | ✅ `gap_abstracts or None` guard |
| Không sửa `services/citation_verifier.py` | ✅ |
| Chỉ sửa `verifier.py` | ✅ 1 file, trong `gap_detection/` |

---

## PHÁT HIỆN / GHI CHÚ

**Giải pháp proxy thay vì raw abstract:** Do `ExtractedPaperData` không lưu raw abstract, proxy từ `key_claims + limitation_statements + methodology` là approximation tốt — thực tế các field này thường chứa nội dung cốt lõi mà Case C cần so sánh với claim.

**Hướng cải thiện dài hạn (không thuộc TIP này):** Thêm field `abstract: str | None` vào `ExtractedPaperData` và persist từ extractor node — khi đó `_build_abstracts_map` dùng raw abstract thay proxy.

---

## KHÔNG CHẠM

- `services/citation_verifier.py` — không sửa gì
- `services/**` (khác) — không sửa gì
- `frontend/**` — không sửa gì
- Các node gap khác — không sửa gì

---

## NEXT

TIP-G06 là prerequisite của **TIP-G08** (verify end-to-end).
Chuỗi phụ thuộc tiếp theo: **G04 → G05 → G07 → G08**.
