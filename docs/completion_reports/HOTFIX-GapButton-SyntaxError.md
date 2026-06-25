# BÁO CÁO HOTFIX — Web trắng trang sau merge MVP
**Phát hiện bởi:** Thợ | **Date:** 2026-06-20 | **Branch:** `feat/gap-cold-start-mvp`

---

## Vấn đề
App hoàn toàn **trắng trang** sau khi tất cả TIP G01–G12 được implement. Không có component nào render được — người dùng chỉ thấy trang trắng hoàn toàn.

## Root cause

**TIP-G07** comment out `export const GapButton` trong [`GapSection.jsx`](file:///d:/vinuni/Project/Build_project/C2-App-069/frontend/src/features/gap/GapSection.jsx) (warm-start disabled), nhưng **không cập nhật** [`ResearchPage.jsx`](file:///d:/vinuni/Project/Build_project/C2-App-069/frontend/src/pages/ResearchPage.jsx) — file này vẫn còn named import:

```js
// ResearchPage.jsx:9 — TRƯỚC khi fix
import GapSection, { GapButton } from '@/features/gap/GapSection';
// ...
<GapButton papers={papers} snowballedPapers={snowballedPapers} />
```

ES Module strict: named export không tồn tại → **`SyntaxError` ngay lúc load** → toàn bộ React app crash, không render gì cả.

```
Uncaught SyntaxError: The requested module '/src/features/gap/GapSection.jsx'
does not provide an export named 'GapButton' (at ResearchPage.jsx:9:22)
```

## Fix áp dụng

**File:** [`ResearchPage.jsx`](file:///d:/vinuni/Project/Build_project/C2-App-069/frontend/src/pages/ResearchPage.jsx)

```diff
- import GapSection, { GapButton } from '@/features/gap/GapSection';
+ import GapSection /*, { GapButton } */ from '@/features/gap/GapSection'; // warm-start disabled (TIP-G07)

- <GapButton papers={papers} snowballedPapers={snowballedPapers} />
+ {/* <GapButton papers={papers} snowballedPapers={snowballedPapers} /> */}{/* warm-start disabled (TIP-G07) */}
```

Vite HMR tự reload — không cần restart server. App hoạt động bình thường sau fix.

## Bài học cho Chủ thầu

> **Khi comment out một named export ở module nguồn, phải đồng thời cập nhật toàn bộ caller import named export đó.**
>
> TIP-G07 thiếu bước này — chỉ comment `GapButton` trong `GapSection.jsx` mà không scan caller.

**Khuyến nghị bổ sung vào checklist TIP FE:**
> *"Nếu xóa/comment export → tìm tất cả file import nó → comment tương ứng."*
>
> Lệnh scan nhanh (PowerShell):
> ```powershell
> Get-ChildItem -Recurse -Include "*.jsx","*.js" frontend/src | Select-String "GapButton"
> ```
