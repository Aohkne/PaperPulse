# Tổng quan (Overview)

**Version:** 1.0.1

# Tính năng: Save to My Review

## Tổng quan

Sau khi LLM generate xong Literature Review (Step ⑩), user có thể lưu lại kết quả vào "My Review" để đọc lại và chỉnh sửa sau. Không lưu trung gian — chỉ lưu output cuối cùng (markdown).

## UX Flow

```
Step ⑩ xong → ReviewEditor.tsx hiển thị markdown
     ↓
User click "..." (3 chấm) ở góc đoạn chat
     ↓
Popup hiện ra:
  - Input: "Tên review" (default = query gốc, user có thể đổi)
  - Nút "Lưu vào My Review"
     ↓
POST /api/reviews → lưu vào Supabase
     ↓
Toast "Đã lưu thành công" → user tiếp tục dùng bình thường

My Review page:
  - List reviews đã lưu (5 items, infinite scroll khi vuốt)
  - Search theo tên
  - Click vào review → mở đọc + edit markdown
```

## Database Schema (Supabase)

Chỉ cần **1 bảng**:

```sql
CREATE TABLE reviews (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,       -- user đặt tên, default = query
  query            TEXT NOT NULL,       -- query gốc ở Step ①
  markdown_content TEXT NOT NULL,       -- output markdown từ Step ⑩
  created_at       TIMESTAMPTZ DEFAULT now(),
  updated_at       TIMESTAMPTZ DEFAULT now()
);
```

**Row Level Security — mỗi user chỉ thấy review của mình:**

```sql
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users own reviews"
  ON reviews FOR ALL
  USING (user_id = auth.uid());
```

**Auto-update `updated_at` khi edit:**

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reviews_updated_at
  BEFORE UPDATE ON reviews
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

**Index cho My Review page:**

```sql
-- List reviews của user, mới nhất trước
CREATE INDEX idx_reviews_user_created ON reviews(user_id, created_at DESC);

-- Search theo title
CREATE INDEX idx_reviews_title ON reviews USING GIN (to_tsvector('english', title));
```

## API Endpoints

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/reviews` | Lưu review mới (từ popup) |
| `GET` | `/api/reviews` | List reviews của user (có pagination + search) |
| `GET` | `/api/reviews/:id` | Lấy 1 review đầy đủ để đọc/edit |
| `PATCH` | `/api/reviews/:id` | Edit title hoặc markdown content |
| `DELETE` | `/api/reviews/:id` | Xóa review |
| `GET` | `/api/reviews/:id/export` | Export review ra file Markdown hoặc PDF |
| `POST` | `/api/reviews/:id/duplicate` | Nhân đôi review thành bản copy mới |

---

### POST `/api/reviews`

Request body:
```json
{
  "title": "RAG optimization",
  "query": "RAG optimization",
  "markdown_content": "# Introduction\n..."
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "title": "RAG optimization",
  "created_at": "2026-06-17T..."
}
```

---

### GET `/api/reviews`

Query params:

| Param | Mô tả | Default |
|---|---|---|
| `page` | Trang số mấy (bắt đầu từ 1) | `1` |
| `limit` | Số items mỗi trang | `5` |
| `search` | Tìm theo title (optional) | — |

Ví dụ: `GET /api/reviews?page=1&limit=5&search=RAG`

Response — **không trả `markdown_content`** (content lớn, chỉ trả khi mở cụ thể):
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "RAG optimization",
      "query": "RAG optimization",
      "created_at": "2026-06-17T...",
      "updated_at": "2026-06-17T..."
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 5,
    "total": 23,
    "has_more": true
  }
}
```

`has_more: true` → frontend gọi `page=2` khi user vuốt tới cuối danh sách.

---

### GET `/api/reviews/:id`

Response — trả full content:
```json
{
  "id": "uuid",
  "title": "RAG optimization",
  "query": "RAG optimization",
  "markdown_content": "# Introduction\n...",
  "created_at": "...",
  "updated_at": "..."
}
```

---

### PATCH `/api/reviews/:id`

Cho phép edit title hoặc nội dung markdown:
```json
{
  "title": "RAG optimization v2",
  "markdown_content": "# Introduction\n... (đã chỉnh sửa)"
}
```

Response `200 OK` — trả lại review đã update.

---

### DELETE `/api/reviews/:id`

Response `204 No Content`.

---

### GET `/api/reviews/:id/export`

Export review ra file. Query param `format` chọn định dạng:

| Param | Giá trị | Default |
|---|---|---|
| `format` | `markdown` \| `pdf` | `markdown` |

**Export Markdown** (`format=markdown`):
```
GET /api/reviews/:id/export?format=markdown

Response 200 OK:
  Content-Type: text/markdown
  Content-Disposition: attachment; filename="RAG-optimization.md"
  Body: <markdown_content raw>
```

**Export PDF** (`format=pdf`):
```
GET /api/reviews/:id/export?format=pdf

Response 200 OK:
  Content-Type: application/pdf
  Content-Disposition: attachment; filename="RAG-optimization.pdf"
  Body: <PDF binary>
```

Backend convert markdown → PDF bằng thư viện (ví dụ `weasyprint` hoặc `playwright`). Tên file được slug hóa từ `title`.

---

### POST `/api/reviews/:id/duplicate`

Tạo bản copy của review với title mới.

Request body (optional):
```json
{
  "title": "RAG optimization (Copy)"
}
```

Nếu không truyền `title`, backend tự đặt `"<title gốc> (Copy)"`.

Response `201 Created`:
```json
{
  "id": "uuid-mới",
  "title": "RAG optimization (Copy)",
  "query": "RAG optimization",
  "created_at": "2026-06-17T..."
}
```

Backend thực hiện: đọc review gốc → insert row mới với `markdown_content` giống hệt, `title` mới, `created_at` = now().

## Quyết định thiết kế

**Tại sao chỉ lưu markdown, không lưu papers/themes/claims?**

Use case hiện tại là "lưu kết quả cuối để đọc lại và edit text" — không cần resume mid-flow hay structured editing từng theme. Lưu thêm papers/themes/claims sẽ tốn công implement mà không thêm giá trị cho flow này.

Nếu sau này cần:
- Resume mid-flow → thêm `current_step` + bảng `review_themes`
- Re-run từng theme → thêm bảng `review_themes` với `content_markdown` per theme
- Xem audit trail claims → thêm bảng `review_claims`
