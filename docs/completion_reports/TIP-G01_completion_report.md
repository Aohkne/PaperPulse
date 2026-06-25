# COMPLETION REPORT — TIP-G01: Mount gap router + smoke

## HEADER
- **TIP-ID:** TIP-G01
- **Module:** api wiring (ngoại lệ cô lập duy nhất)
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `98a395c`
- **Date:** 2026-06-20
- **Status:** ✅ DONE

---

## VIỆC ĐÃ LÀM

Sửa **đúng 1 file chung duy nhất** được phép: `backend/api/__init__.py`

### Diff

```diff
 from backend.api.snowball import router as snowball_router
+from backend.agent.gap_detection.router import router as gap_router
 from backend.api.verify import router as verify_router
 
-# api_router.include_router(gap_router)
+api_router.include_router(gap_router)
```

**2 thay đổi:**
1. Thêm import `gap_router` từ `backend.agent.gap_detection.router` — import này bị **thiếu hoàn toàn** (không phải comment), đây là lý do dòng include_router phải bị comment trước đó (import error crash app).
2. Uncomment `api_router.include_router(gap_router)`.

### File sau khi sửa

```python
from fastapi import APIRouter

from backend.api.admin import router as admin_router
from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.api.research import router as research_router
from backend.api.review import router as review_router
from backend.api.reviews import router as reviews_router
from backend.api.search import router as search_router
from backend.api.snowball import router as snowball_router
from backend.agent.gap_detection.router import router as gap_router   # ← thêm
from backend.api.verify import router as verify_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(chat_router)
api_router.include_router(research_router)
api_router.include_router(search_router)
api_router.include_router(snowball_router)
api_router.include_router(review_router)
api_router.include_router(reviews_router)
api_router.include_router(verify_router)
api_router.include_router(gap_router)                                  # ← uncomment
```

---

## SMOKE TEST

**Lệnh chạy:**
```bash
conda run -n vinuni_project python -c \
  "from backend.api import api_router; \
   routes = [r.path for r in api_router.routes]; \
   print('OK routes:', [r for r in routes if 'gap' in r.lower()])"
```

**Kết quả:**
```
WARNING:root:beautifulsoup4 not installed — arXiv fetcher will use plain-text fallback
OK routes: ['/gap']
```

> Warning `beautifulsoup4` là pre-existing, không liên quan TIP-G01.

Route `/gap` đã reachable. `POST /api/gap` sẽ trả status != 404.

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| `POST /api/gap` → status != 404 (route resolve được) | ✅ Route `/gap` confirmed qua import probe |
| Diff của `api/__init__.py` chỉ chứa dòng `include_router` + `import` | ✅ Đúng 2 dòng thay đổi, không gì khác |
| Không chạm file chung nào khác | ✅ |
| Không sửa shape/handler của gap router | ✅ |

---

## PHÁT HIỆN NGOÀI SPEC

| Phát hiện | Mức độ | Ghi chú |
|---|---|---|
| Import `gap_router` bị **thiếu hoàn toàn** (không phải bị comment) | Info | Đã fix đồng thời. Không ảnh hưởng Blueprint — đây là state pre-existing. |

---

## KHÔNG CHẠM

- `backend/agent/gap_detection/**` — không sửa gì
- `backend/services/**` — không sửa gì
- `frontend/**` — không sửa gì
- `backend/api/*.py` (các router khác) — không sửa gì

---

## NEXT

TIP-G01 unblock tất cả TIP tiếp theo cần `/api/gap` reachable.  
Các TIP độc lập có thể dispatch song song: **G03, G06, G09**.
