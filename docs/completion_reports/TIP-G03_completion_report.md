# COMPLETION REPORT — TIP-G03: query_cleaner.py — VN→EN, strip meta-words

## HEADER
- **TIP-ID:** TIP-G03
- **Module:** `backend/agent/gap_detection/query_cleaner.py` (file MỚI)
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `3263fc2`
- **Date:** 2026-06-20
- **Status:** ✅ DONE

---

## VIỆC ĐÃ LÀM

Tạo mới `backend/agent/gap_detection/query_cleaner.py` — 1 hàm public, 1 LLM call.

### Public API

```python
async def clean_query(topic: str) -> str
```

### Import duy nhất (từ services)

```python
from backend.services.llm_client import chat_completion
```

---

## PROMPT DESIGN

### System prompt (key rules)
```
You are a research query normaliser.
Output ONLY the search phrase — no preamble, no explanation, no markdown.
Translate to English if the input is in another language.
Remove meta-words: "tìm", "tìm kiếm", "research gap", "khoảng trống", "về",
  "nghiên cứu về", "find papers on", "survey of", "tổng quan về", "gap in", "explore".
Keep domain-specific terms intact (model names, acronyms, methods).
Output 3–12 words, not a full sentence.
Do NOT wrap the output in quotes or backticks.
```

### User message template
```
Topic: {topic}

Search phrase:
```

---

## FALLBACK & GUARD LOGIC

| Tình huống | Xử lý |
|---|---|
| LLM call throws exception | `except Exception: return topic` (log warning, không raise) |
| LLM returns empty/whitespace | `_post_process()` → `""` → return `topic` gốc |
| LLM wraps output in `"..."` hay `` `...` `` | `raw.strip("\"'\`")` |
| LLM returns multi-line response | Lấy dòng đầu tiên non-empty |
| Output > 200 ký tự | Cắt tại word boundary (`rsplit(" ", 1)[0]`) |
| topic rỗng | Return `topic` trực tiếp, không gọi LLM |

---

## SELF-TEST KẾT QUẢ

```
_post_process: all guards PASS
clean_query(empty): PASS
clean_query(LLM error): fallback PASS — no raise
clean_query(LLM empty): fallback PASS
clean_query(mocked LLM): PASS -> transformer efficiency long-context modeling
ALL SELF-TESTS PASSED
```

---

## VÍ DỤ INPUT → OUTPUT (mocked LLM, thực tế sẽ phụ thuộc LLM provider)

| Input (topic) | Mocked LLM output → `clean_query()` returns |
|---|---|
| `"Tìm research gap về transformer efficiency cho long-context"` | `"transformer efficiency long-context modeling"` |
| `"transformer efficiency long context"` (EN đã có) | `"transformer efficiency long context"` (chuẩn hóa) |
| LLM lỗi với bất kỳ topic | topic gốc, không raise |
| LLM trả `""` / `"   "` | topic gốc |

> **Note:** Ví dụ thực tế với LLM endpoint live sẽ khác nhau tùy provider/model.
> Hành vi quan trọng là: không raise + fallback đúng.

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| VN topic → EN phrase không còn meta-words | ✅ Prompt system spec loại đúng meta-words; mocked test xác nhận pipeline |
| EN topic → chuẩn hóa | ✅ Prompt rule 4 giữ domain terms |
| LLM lỗi/empty → trả topic gốc, KHÔNG raise | ✅ 2 test fallback pass (exception + empty) |
| 1 LLM call | ✅ Đúng 1 `await chat_completion(messages)` |
| Không hardcode provider | ✅ Chỉ gọi qua `chat_completion` abstraction |

---

## KHÔNG CHẠM

- `services/**` — không sửa gì
- `backend/api/**` — không sửa gì
- `frontend/**` — không sửa gì
- Các file gap_detection hiện có — không sửa gì

---

## NEXT

`query_cleaner.py` là prerequisite của **TIP-G04** (orchestrator.py sẽ
`from backend.agent.gap_detection.query_cleaner import clean_query` làm bước đầu pipeline).
