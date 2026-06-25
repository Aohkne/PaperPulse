# ESCALATION REPORT — Class A Bug chặn MVP Demo
**Phát hiện bởi:** Thợ | **Date:** 2026-06-20 | **Branch:** `feat/gap-cold-start-mvp`
**Ưu tiên:** P0 🔥 — chặn hoàn toàn chức năng gap detection trên mọi topic

---

## Vấn đề

MVP `/gap` **không tìm được khoảng trống** cho bất kỳ topic nào, dù UI render bình thường và API trả 200 OK.

**Kết quả thực tế khi test** (topic: "transformer long-context"):
```
UI hiển thị: "Không đủ tài liệu cho chủ đề này..."
Log backend:  cold_start: only 0 papers (< MIN=5) — returning early with empty gaps
```

---

## Root Cause — Class A Bug (đã escalate từ G10.0, chưa fix)

**File:** `backend/services/semantic_scholar.py` — hàm `_to_paper()`

```python
# HIỆN TẠI (bug) — line ~112:
paperId = raw.get('paperId', '')
# Khi S2 API trả {"paperId": null}:
#   raw.get('paperId', '')  → None  (fallback '' không trigger vì key TỒN TẠI)
#   → Paper(paperId=None)  → Pydantic ValidationError!

# FIX — 1 dòng:
paperId = raw.get('paperId') or ''
# Khi S2 API trả {"paperId": null}:
#   raw.get('paperId')  → None  → None or '' = ''
#   → Paper(paperId='')  → valid, sau đó _valid_papers lọc ra
```

---

## Cascade Failure

```
S2 search("transformer long-context")
  → trả papers, nhiều bài có paperId=null
  → _to_paper() raise ValidationError cho mỗi bài đó
  → search_papers() bỏ qua các bài lỗi → returns [] hoặc rất ít bài
  → G11.2 fallback retry với topic gốc → cùng kết quả
  → _valid_papers filter → 0 papers hợp lệ
  → gate MIN=5: 0 < 5 → "Không đủ tài liệu"
  → GapReport(gaps=[], narrative="Không đủ...")
```

**Log xác nhận:**
```
WARNING: Snowball expand error for 2b8a...:
  1 validation error for Paper
  paperId — Input should be a valid string [input_value=None, input_type=NoneType]

WARNING: cold_start: only 0 papers (< MIN=5) — returning early with empty gaps
INFO:  POST /api/gap HTTP/1.1 200 OK  ← trả về đúng contract nhưng gaps=[]
```

---

## Tại sao Thợ không tự fix

File `backend/services/semantic_scholar.py` **nằm ngoài zone** `backend/agent/gap_detection/**`.

Theo ABSOLUTE RULES của mọi TIP trong sprint này:
> "KHÔNG đụng `services/**`; phát hiện vấn đề ngoài zone → REPORT, KHÔNG tự sửa"

---

## Fix đề xuất (Chủ thầu duyệt)

**File:** `backend/services/semantic_scholar.py` — 1 dòng duy nhất

```diff
- paperId = raw.get('paperId', '')
+ paperId = raw.get('paperId') or ''
```

**Effort:** ~2 phút. **Risk:** Rất thấp — chỉ đổi behavior khi `paperId=null`, không ảnh hưởng case bình thường.

**Sau fix:** Papers với `paperId=null` sẽ có `paper_id=''` → bị `_valid_papers` filter sạch → yield thật sự từ S2 tăng lên → gap detection hoạt động đúng.

---

## Hiện trạng tổng thể MVP

| Thành phần | Status |
|---|---|
| Route `/gap` độc lập | ✅ Hoạt động |
| UI `ColdStartInput` render | ✅ Hoạt động |
| API `/api/gap` contract | ✅ 200 OK |
| Backend pipeline (LLM + LangGraph) | ✅ Hoạt động |
| **S2 paper retrieval yield** | ❌ **0 papers** vì Class A bug |
| **Gap detection thật** | ❌ **Blocked** bởi Class A bug |

---

## Yêu cầu từ Chủ thầu

> **Duyệt fix 1 dòng trong `services/semantic_scholar.py`** để MVP gap detection hoạt động thật sự.
>
> Nếu duyệt → Thợ implement ngay trong TIP riêng (~5 phút) hoặc Chủ thầu tự patch.
