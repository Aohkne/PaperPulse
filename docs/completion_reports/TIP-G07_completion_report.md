# COMPLETION REPORT — TIP-G07: FE ColdStartInput + useGapStore {topic}

## HEADER
- **TIP-ID:** TIP-G07
- **Module:** `frontend/src/features/gap/` (3 files: `useGapStore.js` + `ColdStartInput.jsx` [NEW] + `GapSection.jsx`)
- **Branch:** `feat/gap-cold-start-mvp`
- **Commit:** `75b9a2e`
- **Date:** 2026-06-20
- **Status:** ✅ DONE

---

## 1. `useGapStore.js` — cold-start action + decouple

### Thay đổi

```js
// warm-start disabled (Lưu ý 2) — re-enable later
// import useResearchStore from '@/shared/store/useResearchStore';

const useGapStore = create((set) => ({
  gapReport: null,       // full GapReport object
  gapNarrative: null,    // backward-compat (GapResultPanel reads this)
  gapLoading: false,
  gapError: null,

  findGapsFromTopic: async (topic) => {
    // validate trim, length >= 3
    set({ gapLoading: true, gapError: null, gapReport: null, gapNarrative: null });
    const res = await fetch('/api/gap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: trimmed }),  // ← cold-start body
    });
    if (!res.ok) { detail = (await res.json()).detail; throw new Error(detail); }
    const data = await res.json();
    set({ gapReport: data, gapNarrative: data.narrative ?? null, gapLoading: false });
  },
  // findResearchGaps: ... (commented warm path)
  reset: () => set({ gapReport: null, gapNarrative: null, gapLoading: false, gapError: null }),
}));
```

**Decoupled:** `useResearchStore` import chỉ còn trong comment (không active).

### Error handling

- Topic < 3 chars → `set({ gapError: '...' })` local, không gọi API
- HTTP error → parse `res.json().detail` → `gapError`
- Network/exception → `e.message ?? 'Lỗi không xác định.'` → `gapError`
- 500 → detail từ server ("Gap detection thất bại…") → hiện qua GapResultPanel

---

## 2. `ColdStartInput.jsx` — NEW component

### Layout
```
┌─────────────────────────────────────────┐
│ Label: "Chủ đề nghiên cứu"              │
│ ┌─────────────────────────────────────┐ │
│ │ textarea (rows=3, id=gap-topic-input│ │
│ │ placeholder, Ctrl+Enter shortcut)   │ │
│ └─────────────────────────────────────┘ │
│ [🔍 Tìm khoảng trống]  [loading spinner]│
│ hint: "Ctrl+Enter để gửi"               │
└─────────────────────────────────────────┘
```

### Behavior
- `disabled` khi `topic.trim().length < 3 || gapLoading`
- `onClick` → `findGapsFromTopic(trimmed)`
- `onKeyDown`: Ctrl/Cmd+Enter → submit
- `gapLoading=true` → nút đổi sang spinner "Đang phân tích…"
- Unique IDs: `gap-topic-input`, `gap-find-btn` (browser-testable)

---

## 3. `GapSection.jsx` — mount ColdStartInput, comment GapButton

```jsx
const GapSection = () => {
  const { gapNarrative, gapLoading, gapError } = useGapStore();
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* ① Topic input — always visible, no paper-count gate */}
      <ColdStartInput />
      {/* ② Results panel — fills remaining height */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <GapResultPanel narrative={gapNarrative} loading={gapLoading} error={gapError} />
      </div>
    </div>
  );
};
```

**`GapButton` (warm-start) là fully commented** — còn trong file cho re-enable later.

---

## UX FLOW

| Trạng thái | UI |
|---|---|
| Empty / < 3 chars | Nút disabled (màu mờ), tooltip "Nhập ít nhất 3 ký tự" |
| Gõ topic ≥ 3 chars | Nút active (brand-600) |
| Click / Ctrl+Enter | Spinner "Đang phân tích…", nút disabled |
| GapReport thành công | GapResultPanel render narrative + gaps |
| insufficient (gaps=[]) | narrative "Không đủ tài liệu…" render bình thường |
| Error 422/500/network | GapResultPanel hiện error message |

---

## SELF-TEST KẾT QUẢ

```
ColdStartInput.jsx exists: PASS
useGapStore: useResearchStore decoupled (no active import): PASS
useGapStore: findGapsFromTopic defined: PASS
useGapStore: POST payload {topic}: PASS
useGapStore: parses error detail: PASS
GapSection: mounts ColdStartInput: PASS
GapSection: GapButton commented: PASS
ColdStartInput: all checks: PASS
ALL CHECKS PASSED
```

---

## ACCEPTANCE CRITERIA

| AC | Kết quả |
|---|---|
| Session trống, gõ topic + bấm → POST /api/gap {topic} + loading | ✅ `findGapsFromTopic` gọi fetch với `{topic}`, `gapLoading=true` |
| GapReport thành công → GapResultPanel render | ✅ `gapNarrative = data.narrative` → GapResultPanel nhận prop |
| gaps=[] + narrative → hiện narrative, không crash | ✅ GapResultPanel render narrative bình thường (ReactMarkdown) |
| cold-start action không đọc useResearchStore | ✅ import commented, findGapsFromTopic không gọi useResearchStore |

---

## KHÔNG CHẠM
- `GapResultPanel.jsx` — không sửa ✅
- `research/**` — không sửa ✅
- `chat/**` — không sửa ✅
- Backend — không sửa ✅

---

## NEXT
TIP-G07 DONE. Chuỗi phụ thuộc: **G08** (e2e verify — chờ G04✅ G05✅ G06-R✅ G07✅ G09-R✅).
