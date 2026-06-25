# Tổng quan (Overview)

**Version:** 1.0

**Tóm tắt (Executive Summary):**
> Nhà nghiên cứu mất hàng tuần để tổng quan tài liệu cho một chủ đề, đọc hàng trăm bài báo, và vẫn có nguy cơ bỏ sót công trình quan trọng hoặc không nhận ra khoảng trống nghiên cứu thực sự

**Mục tiêu (Goals):**
- Tiết kiệm thời gian đọc bài
- Tìm được bài -> hiểu bài -> đưa ra quyết định đúng đăng

**Nằm ngoài phạm vi (Non-goals/Out of scope):** không xử lý trong đợt phát triển này.
> Hạn chế về phân tích chuyên sâu: Gợi ý khoảng trống nghiên cứu (Research Gap) quá chung chung, thiếu sự đánh giá, so sánh đối chiếu và chỉ ra mâu thuẫn giữa các nghiên cứu cũ.

---

# Phân tích Pain Points

## 1. Thiếu độ tin cậy nghiêm trọng (Hallucination)

AI tự bịa đặt trích dẫn hoặc cung cấp các nguồn tài liệu không có thật.

**Nguyên nhân:** tự bịa khi không đủ thông tin
> ref: Microsoft Research (arXiv:2305.18248): LLMs "notoriously susceptible to generating hallucinated information" — ChatGPT: 0.62 hallucinations/tóm tắt, Claude 2: 1.55

### 1.1 Hallucination cứng (bịa DOI)

Bịa tên bài, tác giả, DOI không tồn tại. `dễ Evaluate`

### 1.2 Citation drift

Bài thật, nhưng AI dùng sai ý — SemanticCite (arXiv:2511.16198)

Phân loại:
- **Supported:** Bài gốc nói đúng điều AI claim
- **Partially Supported:** Bài gốc có liên quan nhưng AI lấy một phần, bỏ điều kiện quan trọng
- **Unsupported:** Bài gốc không nói điều đó, hoặc nói ngược
- **Uncertain:** Bài gốc mơ hồ, không thể kết luận rõ -> human in the loop

> Elicit, Consensus

### Giải pháp

**Hallucination cứng (bịa DOI)** — mức độ giải quyết 99%:
- RAG (Elicit, Consensus)
- Factored Verification

**Citation drift** — mức độ giải quyết ~65-70%:

- **Citation Intent Classification** — phân loại thành 3 phần:
  - `Supporting`: Paper A cite B vì B ủng hộ claim của A
  - `Contrasting`: Paper A cite B vì B phản bác claim của A
  - `Mentioning`: Paper A chỉ nhắc đến B như background

  kiểm tra xem trong đó có contrasting và mentioning không để đúng ý không nếu đúng thì tôi có ý kiến sau: sao không cần chỉ cần thấy Contrasting và Mentioning là kết luận là Citation drift lun sao phải chạy hết

- **SemanticCite:** từ là tải full text, so sanh claim và đoạn text gốc, so sánh clam với đoạn text để phân loại supported và partially supported -> quote cụ thể từ bài gốc

**Evaluate:** giải pháp của nhóm: sau khi triển khai và test

---

## Đề xuất: RAG kết hợp với API (Semantic Scholar)

### Hallucination cứng (bịa DOI)

```bash
# Tìm kiếm theo relevance (semantic search)
GET /paper/search?query=RAG+literature+review&fields=title,abstract,year,citationCount
# → dùng khi tìm chủ đề liên quan topic để cho LLM phân tích
```

### Citation drift

```bash
# Tìm snippets trong full text ← CỰC KỲ có ích
GET /snippet/search?query=AI hallucination reduction
# → trả về 500 word trong fulltext và dùng LLM check xem bài đó có thực sự về chủ đề đó không
```

### Embedding — SPECTER v2 *(chốt phương án này)*

embedding bài cũ đã embedding trước đó: có 2 giải phảp

```bash
# Lấy pre-computed SPECTER v2 embedding ← quan trọng
GET /paper/{id}?fields=embedding.specter_v2
```

Response mẫu:

```json
{
  "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
  "embedding": {
    "model": "specter_v2@v0.1.1",
    "vector": [
      0.2341, -0.1823, 0.7621, 0.0412, -0.5534,
      0.1209, 0.8821, -0.3301, 0.4412, 0.2198,
      // ... tổng cộng 768 số
    ]
  }
}
```

### Persistent Vector DB + deduplication bằng paperId

```python
def process_papers(papers):
    to_embed = []

    for paper in papers:
        # Kiểm tra paperId đã có trong DB chưa
        if not vector_db.exists(paper["paperId"]):
            to_embed.append(paper)   # chỉ embed bài mới
        # Bài cũ → bỏ qua, dùng vector đã lưu

    if to_embed:
        vectors = embedding_model.encode([p["abstract"] for p in to_embed])
        vector_db.insert(to_embed, vectors)
```

---

## Flow chính

```mermaid
① User nhập: "AI trong systematic literature review"
              ↓
② /paper/search → 100 bài (title + abstract + paperId)
              ↓
③ Lấy SPECTER v2 qua BATCH API (1 call cho 400 papers)
   → Vector DB
              ↓
④ Top-20 by relevance (100 bài gốc) → LLM → OUTLINE
   [Limitation: snowballed papers không ảnh hưởng outline — MVP]
              ↓
⑤ Per theme: Hybrid search
   [Semantic] embed THEME DESCRIPTION (30-50 words) bằng SPECTER v2 locally
   [Keyword]  BM25
   [Merge]    RRF → top-10
              ↓
⑥ LLM đọc abstracts với structured format [PAPER_ID: xxx]
   → generate content, mỗi claim ghi rõ (Source: PAPER_ID)
              ↓
⑦ Tách claims có citation → từng claim gắn paperId
              ↓
⑧ /snippet/search → verify claim trong full text
              ↓
⑨ Unsupported → xóa hoặc flag → human review
              ↓
⑩ Ghép các themes → Literature Review hoàn chỉnh
```

---

## OpenAlex API *(phase sẽ nghiên cứu)*

```bash
# Search với filter phức tạp
GET /works?search=literature+review+AI&filter=publication_year:2023-2026,open_access.is_oa:true

# Filter theo concept (không cần đúng từ khóa)
GET /works?filter=concepts.id:C154945302  # ← "Artificial Intelligence" concept

# Related works (bibliographic coupling tự động)
# → Mỗi work object đã có sẵn "related_works": [...]
```

---

## 2. Rủi ro bỏ sót tài liệu

Công cụ thường xuyên bỏ qua các bài báo/công trình nghiên cứu bản lề (key papers), đặc biệt là các bài báo có giá trị khoa học cao nhưng ít lượt trích dẫn hoặc các nghiên cứu cũ.

**Nguyên nhân:**
- Bài ít citation → AI training data ít nhắc đến → AI không "biết" bài đó quan trọng
- Bài cũ (trước 2010) → ít xuất hiện trong web data → bị underrepresent
- Bài non-English → gần như invisible với general LLMs
- Bài cross-disciplinary → không fit vào keyword nào của domain

> ref:
> - LSE (arXiv:2603.20235, 2026): Chỉ 20% overlap giữa bài AI chọn và bài expert chọn
> - Elicit (1 trong những công cụ tốt nhất hiện tại): Vẫn miss ~5% bài — tưởng nhỏ nhưng với corpus 10,000 bài = 500 bài bị bỏ
> - Nguy hiểm hơn vì là "bias of ignorance" — bạn không biết mình đang thiếu gì

> STORM/Stanford (2024)

**Giải pháp:**
- Hybrid search
- Citation Graph Snowballing -> visualize thành graph ( bài nằm ở rìa graph = ít được biết đến nhưng liên quan.)

```
Bạn cung cấp 1 "seed paper" (bài bạn đã biết là quan trọng)
              ↓
Backward:               Tìm tất cả bài mà seed paper cite
Forward:                Tìm tất cả bài sau này cite seed paper
Co-citation:            Tìm bài được cite cùng với seed paper
Bibliographic coupling: Tìm bài cite cùng sources với seed paper
              ↓
Kết quả: Bài ít citation nhưng nằm trong mạng lưới
         của bài quan trọng sẽ được tìm thấy
```

**Evaluate:** giải pháp của nhóm: sau khi triển khai và test

**API endpoints:**

```bash
# Lấy citations của 1 bài (Forward snowballing)
GET /paper/{paper_id}/citations?fields=contexts,intents,isInfluential
# → check bỏ sót tài liệu

# Lấy references của 1 bài (Backward snowballing)
GET /paper/{paper_id}/references?fields=contexts,intents,isInfluential
# → check bỏ sót tài liệu
```

**Flow đề xuất bổ sung để giải quyết:**

```
②bis  ← THÊM MỚI: Citation Snowballing
   → Lọc top-10 bài có citationCount CAO NHẤT từ 100 bài
   → Với mỗi seed paper:
       /paper/{id}/references  → backward (tìm bài nền tảng)
       /paper/{id}/citations   → forward  (tìm bài follow-up)
   → Deduplicate + filter (year range, min citations ≥ 5)
   → Corpus mở rộng: 100 → ~300-400 bài
```

---

**Flow hoàn thiện cuối cùng**

```bash
① User nhập: "AI trong systematic literature review"
              ↓
② /paper/search → 100 bài (title + abstract + paperId)
                ↓
②bis Citation Snowballing
   → top-10 by CITATIONS/YEAR (không phải raw citationCount)
   → Backward (/references): filter min citations ≥ 5
   → Forward  (/citations):  filter year ≥ 2022, min citations ≥ 0
   → corpus: ~300-400 bài
              ↓
③ Lấy SPECTER v2 qua BATCH API (1 call cho 400 papers)
   → Vector DB
              ↓
④ Top-20 by relevance (100 bài gốc) → LLM → OUTLINE
   [Limitation: snowballed papers không ảnh hưởng outline — MVP]
              ↓
⑤ Per theme: Hybrid search
   [Semantic] embed THEME DESCRIPTION (30-50 words) bằng SPECTER v2 locally
   [Keyword]  BM25
   [Merge]    RRF → top-10
              ↓
⑥ LLM đọc abstracts với structured format [PAPER_ID: xxx]
   → generate content, mỗi claim ghi rõ (Source: PAPER_ID)
              ↓
⑦ Tách claims có citation → từng claim gắn paperId
              ↓
⑧ /snippet/search → verify claim trong full text
              ↓
⑨ Unsupported → xóa hoặc flag → human review
              ↓
⑩ Ghép các themes → Literature Review hoàn chỉnh
```
