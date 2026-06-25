# ESCALATION REPORT — GapSection bị gate sau Research pipeline
**Phát hiện bởi:** Thợ | **Date:** 2026-06-20 | **Branch:** `feat/gap-cold-start-mvp`
**Ưu tiên:** P1 — ảnh hưởng trực tiếp khả năng demo MVP

---

## Vấn đề

`GapSection` (cold-start flow, TIP-G07) **không thể truy cập trực tiếp** được. Người dùng phải thực hiện toàn bộ Research pipeline trước mới thấy tab "Gaps".

### Flow hiện tại (sai với mục tiêu cold-start)

```
localhost:5173/research
    → Welcome screen (search bar)
    → [User phải search một topic]
    → [Đợi Research pipeline: Search → Snowball → Embed → Outline]
    → Layout 3-cột xuất hiện
    → Tab "Outline" | "Gaps" ← | "Review"
    → Mới vào được GapSection
```

### Flow đúng thiết kế cold-start (TIP-G05/G07)

```
GapSection hoàn toàn độc lập — KHÔNG phụ thuộc Research pipeline
    → Người dùng nhập topic → POST /api/gap → GapReport
    → KHÔNG cần papers từ Research pipeline
```

### Code xác nhận

```jsx
// ResearchPage.jsx:207–216 — GapSection bị gate trong tab của Research layout
{activePanel === 'gaps' ? (
    <GapSection />   // ← chỉ render khi đã có activePanel='gaps'
) : ...}

// activePanel chỉ xuất hiện sau khi Research search xong và layout 3-cột hiện
```

---

## Tác động

| | |
|---|---|
| **Demo MVP** | ❌ Không thể demo gap detection trực tiếp — phải chạy Research pipeline ~2-3 phút trước |
| **UX** | ❌ Người dùng không biết tab "Gaps" tồn tại nếu chưa search |
| **Mục tiêu cold-start** | ❌ Mất đi tính "độc lập hoàn toàn" mà TIP-G05/G07 đặt ra |
| **Backend** | ✅ Không ảnh hưởng — `/api/gap` hoạt động đúng |

---

## Phương án đề xuất (Thợ không tự quyết)

### Option A — Route độc lập `/gap` *(khuyến nghị, ~20')*
Thêm route mới `localhost:5173/gap` mount `GapSection` trực tiếp, không qua Research layout:
```jsx
// main.jsx — thêm route mới
<Route path="/gap" element={<GapPage />} />
```
- **Ưu:** Demo được ngay, đúng tinh thần cold-start
- **Nhược:** Cần tạo `GapPage.jsx` mới (đơn giản, ~30 dòng)

### Option B — GapSection luôn visible trong sidebar *(~10')*
Mount `ColdStartInput` trong sidebar/nav, không cần tab:
- **Ưu:** Nhanh hơn, không cần route mới
- **Nhược:** Thay đổi layout hiện tại

### Option C — Giữ nguyên, document workaround *(0')*
User search bất kỳ topic → đợi kết quả → click tab "Gaps":
- **Ưu:** Không cần code
- **Nhược:** UX kém, không demo được cold-start đúng nghĩa

---

## Yêu cầu quyết định từ Chủ thầu

> **Chọn Option A, B, hay C?**
> Nếu A hoặc B → Thợ implement ngay (~1 TIP nhỏ, không chạm backend).
> Nếu C → Thợ document workaround cho demo.
