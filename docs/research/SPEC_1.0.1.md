# Tổng quan (Overview)

**Version:** 1.0.1
**Changelog từ v1.0:** Xem mục [CHANGELOG](#changelog) cuối file

**Tóm tắt (Executive Summary):**
> Nhà nghiên cứu mất hàng tuần để tổng quan tài liệu cho một chủ đề, đọc hàng trăm bài báo, và vẫn có nguy cơ bỏ sót công trình quan trọng hoặc không nhận ra khoảng trống nghiên cứu thực sự

**Mục tiêu (Goals):**
- Tiết kiệm thời gian đọc bài
- Tìm được bài → hiểu bài → đưa ra quyết định đúng đắn

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
- **Uncertain:** Bài gốc mơ hồ, không thể kết luận rõ → human in the loop

### Giải pháp

**Hallucination cứng (bịa DOI)** — mức độ giải quyết 99%:
- RAG: LLM chỉ được cite từ papers đã retrieve (Grounded Generation)
- Factored Verification

**Citation drift** — mức độ giải quyết ~65-70%:

- **Citation Intent Classification** — phân loại thành 3 phần:
  - `Supporting`: Paper A cite B vì B ủng hộ claim của A
  - `Contrasting`: Paper A cite B vì B phản bác claim của A
  - `Mentioning`: Paper A chỉ nhắc đến B như background

  > **[v1.0.1 — Clarification quan trọng]** Citation Intent KHÔNG phải shortcut để skip verification.
  > Intent nói lên *tại sao* A cite B, không nói lên *liệu B có support đúng claim C không*.
  > Citation drift phổ biến nhất trong `Supporting` citations — AI muốn dùng B để ủng hộ claim và oversimplify.
  >
  > **Vai trò đúng của Intent trong pipeline:**
  > - Intent = `Contrasting` → đẩy lên đầu human review queue để ưu tiên xem xét
  > - Intent = `Mentioning` → warning nhẹ (bài chỉ được nhắc tên)
  > - **Tất cả claims vẫn phải chạy full snippet verification ở Step ⑧**

- **SemanticCite approach:** tải full text, so sánh claim với đoạn text gốc → phân loại Supported/Partially/Unsupported/Uncertain → quote cụ thể từ bài gốc

---

## Đề xuất: RAG kết hợp với API (Semantic Scholar)

### Hallucination cứng (bịa DOI)

```bash
# Tìm kiếm theo relevance (semantic search)
GET /paper/search?query=RAG+literature+review&fields=title,abstract,year,citationCount,externalIds,openAccessPdf
# → dùng khi tìm chủ đề liên quan topic để cho LLM phân tích
```

### Citation drift — Verification Pipeline

```bash
# Case A: Tìm snippets trong full text (~30% papers có full text)
GET /snippet/search?query={claim_text}&paperId={paperId}
# → trả về 500 word trong fulltext → verify chính xác nhất

# Case B: arXiv full text (~80%+ CS/AI papers)
# Lấy arXiv ID từ externalIds.ArXiv trong Step ②
GET https://ar5iv.labs.arxiv.org/html/{arxiv_id}
# → HTML full text, free, no API key, stable

# Case C fallback: abstract (đã có từ Step ②)
# Chỉ dùng để detect rõ ràng sai, KHÔNG return "Supported"
```

### Embedding — SPECTER v2

```bash
# Lấy pre-computed SPECTER v2 embedding qua Batch API
POST https://api.semanticscholar.org/graph/v1/paper/batch?fields=embedding.specter_v2,openAccessPdf
Content-Type: application/json
x-api-key: {SEMANTIC_SCHOLAR_API_KEY}

Body: {"ids": ["paperId1", "paperId2", ...]}  # tối đa 500 ids/call
```

Response mẫu:

```json
[
  {
    "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
    "embedding": {
      "model": "specter_v2@v0.1.1",
      "vector": [0.2341, -0.1823, 0.7621, ...]
    }
  },
  {
    "paperId": "abc123...",
    "embedding": null
  }
]
```

> `embedding: null` → paper quá mới hoặc không có abstract → fallback encode abstract bằng SPECTER2 adapter proximity locally

### Persistent Vector DB + deduplication bằng paperId

```python
def process_papers(papers):
    to_embed = []
    for paper in papers:
        if not vector_db.exists(paper["paperId"]):
            to_embed.append(paper)
    if to_embed:
        vector_db.insert(to_embed, vectors_from_batch_api)
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

**Giải pháp:**
- Hybrid search (SPECTER v2 semantic + BM25 keyword + RRF merge)
- Citation Graph Snowballing → visualize thành graph (bài nằm ở rìa graph = ít được biết đến nhưng liên quan)
- MMR selection cho outline → cover nhiều góc nhìn của topic

**API endpoints Snowballing:**

```bash
# Forward snowballing: Bài nào cite seed paper (bài MỚI hơn)
GET /paper/{paper_id}/citations?fields=contexts,intents,isInfluential,citationCount,year,externalIds,openAccessPdf

# Backward snowballing: Seed paper cite bài nào (bài CŨ hơn — nền tảng)
GET /paper/{paper_id}/references?fields=contexts,intents,isInfluential,citationCount,year,externalIds,openAccessPdf
```

---

## Flow hoàn thiện cuối cùng (v1.0.1)

```
① User nhập query: "RAG optimization"
   → Embed query bằng SPECTER2 adapter proximity → lưu query_vector
              ↓
② Semantic Scholar /paper/search
   → 100 bài (title + abstract + paperId + citationCount + year + externalIds + openAccessPdf)
              ↓
②bis Citation Snowballing

   [Seed Selection — v1.0.1]
   Pool A: top-5 by RAW citationCount           (foundational papers)
   Pool B: top-5 by citationCount/(current_year - year)  (recent impactful)
   Seeds = Pool A ∪ Pool B → deduplicate → ~7-9 seeds

   [Backward — /references — tìm bài nền tảng CŨ hơn seed]
   isInfluential = true                → KEEP (bypass filter)
   isInfluential = false/null:
     year ≥ current_year - 2           → min_citations = 0
     year ≥ current_year - 5           → min_citations = 3
     year < current_year - 5           → min_citations = 5

   [Forward — /citations — tìm bài follow-up MỚI hơn seed]
   isInfluential = true  AND citations ≥ 1              → KEEP (mọi năm)
   isInfluential = false AND year ≥ current_year-4
                         AND citations ≥ 1               → KEEP
   else                                                  → DISCARD

   Deduplicate bằng paperId → corpus ~300-400 bài
              ↓
③ SPECTER v2 Batch API
   POST /paper/batch?fields=embedding.specter_v2,openAccessPdf (max 500 ids/call)
   embedding = null → fallback: encode abstract bằng SPECTER2 adapter proximity locally
   → Lưu vào ChromaDB với metadata {paperId, title, year, citationCount, externalIds, openAccessPdf}
              ↓
④ Outline Generation — v1.0.1 (từ toàn bộ 300-400 bài, có user approval)

   Pre-filter: top-150 by cosine(query_vector, SPECTER_v2_vector)
   MMR (λ=0.5, fetch_k=150, k=20):
     Vòng 1: Chọn bài Sim(bài, query) cao nhất → Paper_1
     Vòng N: Chọn bài max[0.5×Sim(bài,query) - 0.5×max(Sim(bài, đã_chọn))]
     → 20 bài diverse + relevant → cover nhiều góc nhìn của topic

   LLM đọc 20 abstracts → generate OUTLINE (5-8 themes)
   Mỗi theme: tên ngắn gọn + mô tả 1-2 câu

   → Hiển thị cho user (ThemeOutline component)
   → User có thể: edit tên, thêm theme, xóa theme, reorder
   → User APPROVE → tiếp tục Step ⑤
              ↓
⑤ Per theme: Hybrid Search (chạy song song cho tất cả themes)

   [Semantic] Embed theme description bằng SPECTER2 adapter proximity
              Pre-filter top-50 by cosine → MMR (k=10) → diverse top-10
              (Document vectors = SPECTER v2 từ API, Query vector = SPECTER2 local)
   [Keyword]  BM25 trên title + abstract → top-10
   [Merge]    RRF → top-10 per theme
              ↓
⑥ Per theme: LLM đọc top-10 abstracts
   → Generate content với format bắt buộc: (Source: PAPER_ID)
   → Mỗi claim ghi rõ paper nó cite
              ↓
⑦ Parse output
   → List {claim_text, paperId}
   → Gắn thêm Citation Intent metadata nếu có (Supporting/Contrasting/Mentioning)
     (từ intents field trong Semantic Scholar /references hoặc /citations)
              ↓
⑧ Verify mỗi claim — 3-tier pipeline

   Case A (~30% papers) — Semantic Scholar snippet:
     GET /snippet/search?query={claim_text}&paperId={paperId}
     → 500-word snippet → LLM classify:
       Supported | Partially Supported | Unsupported | Uncertain

   Case B (~80% CS/AI papers) — arXiv full text:
     Check externalIds.ArXiv từ metadata
     GET https://ar5iv.labs.arxiv.org/html/{arxiv_id}
     → HTML full text → LLM classify (nếu Case A không có snippet)

   Case C (còn lại) — Abstract conservative verify:
     Dùng abstract từ Step ② (đã có sẵn, không cần API call thêm)
     → LLM classify CONSERVATIVE:
       - Unsupported: nếu abstract rõ ràng mâu thuẫn với claim
       - Unsupported: nếu topic của paper không liên quan claim (topic mismatch)
       - Uncertain: MỌI trường hợp còn lại
     [KHÔNG BAO GIỜ return "Supported" từ abstract-only]
     → Gắn flag low_confidence = true
              ↓
⑨ Routing kết quả verify

   Supported + snippet/arXiv              → include trong review, hiển thị quote nguồn
   Supported + abstract/low_confidence    → hold → mandatory human confirm
   Partially Supported                    → hold + flag → human review
   Unsupported                            → xóa khỏi review, log lại
   Uncertain                              → mandatory human review
   [Intent = Contrasting, bất kể status] → ưu tiên đầu human review queue

   User review ClaimVerifier (approve/reject)
              ↓
⑩ Merge tất cả themes đã verified
   → Render Literature Review theo cấu trúc bắt buộc (xem Literature Review Format):
     INTRODUCTION (10%) → BODY thematic (80%) → CONCLUSION (10%)
     APA 7 in-text: (Author, Year) | reference list alphabetical
   → Cuối review: PDF Links Section
     Mỗi paper được cite: APA 7 reference entry + [PDF] link clickable
     PDF URL priority:
       1. openAccessPdf.url (status GREEN/GOLD) — verified open access
       2. https://arxiv.org/pdf/{externalIds.ArXiv} — guaranteed direct PDF (best UX)
       3. openAccessPdf.url (status BRONZE/HYBRID) — có thể là HTML landing page
       4. https://doi.org/{externalIds.DOI} — thường paywalled
       5. https://www.semanticscholar.org/paper/{paperId} — last resort
   → Export Markdown / PDF
```

---

## Literature Review Format — System Prompt (Step ⑥ + ⑩)

Dùng làm **system message** trong `content_generator.py` (Step ⑥ per-theme) và khi LLM generate Introduction + Conclusion lúc merge final (Step ⑩):

```
You are an AI assistant specialized in academic literature review. Your task is to 
synthesize research papers retrieved from a verified corpus. Fabrication is strictly 
prohibited — only cite papers explicitly provided to you.

---

## LITERATURE REVIEW STRUCTURE
### INTRODUCTION (~10% of total length)
- State the research question clearly
- Justify its significance within the field
- Define scope: what sources are included/excluded and why
- Map the themes to be covered in the body
- Note known limitations of this review (e.g., language bias, date range, database coverage)
---
### BODY (~80% of total length) — Thematic Organization
For each theme identified from the literature, follow this sequence:
**1. Topic Sentence**
Introduce the theme and list the papers to be discussed in this section.
**2. Description**
Summarize each paper's key claims and findings as they relate to the research question.
**3. Analysis**
Compare and contrast across papers: trends, methods, theoretical frameworks, points 
of consensus, and ongoing debates.
**4. Evaluation**
Identify strengths, limitations, and research gaps within this specific theme.
**5. Transition**
Logically connect the current theme to the next one.
---
### CONCLUSION (~10% of total length)
- Restate the research question and confirm it has been addressed
- Synthesize cross-theme gaps and contradictions
- Identify specific directions for future research
- State which gap(s) the next study could address
---
## CITATION AND REFERENCES
**In-text citations:**
- Follow APA 7th edition: (Author, Year) or Author (Year)
- Example: (Nguyen & Tran, 2023) or Nguyen and Tran (2023) demonstrated that...
- For direct quotes, include page number: (Nguyen & Tran, 2023, p. 45)
**Reference list:**
- Place at the end of the review, sorted alphabetically by first author's last name
- Only list papers that are actually cited in the body text
- APA 7 format for journal articles:
  Last, F. M., & Last, F. M. (Year). Title of article. Journal Name, volume(issue), 
  pages. https://doi.org/xxxxx
---
## HARD RULES
**On citations:**
- Never cite any paper outside the provided corpus
- Every claim must be traceable to a specific paper (author, year)
- Every in-text citation must have a corresponding full entry in the reference list
- Every reference list entry must be cited at least once in the body text
**On honesty:**
- If papers report conflicting findings, explicitly flag the contradiction — do not artificially resolve it
- If evidence is insufficient to support a claim, state "evidence is insufficient" 
  rather than speculate
- If a paper's metadata is incomplete (missing DOI, page numbers, etc.), include 
  what is available — never fabricate missing fields
**On transparency:**
- Clearly distinguish between what the paper states (description) and your own 
  synthesis or interpretation (analysis)
- Never use vague language to mask a lack of information.
```

**Lưu ý triển khai:**
- **Step ⑥ (per-theme):** system prompt này + user prompt = `theme description` + `top-10 abstracts` → generate phần BODY cho 1 theme
- **Step ⑩ (merge final):** system prompt này + tất cả BODY đã generate → LLM viết INTRODUCTION + CONCLUSION bao trùm toàn bộ
- LLM chỉ được cite papers trong provided abstracts — HARD RULE, không bịa paperId

---

## PDF Links Section (Step ⑩)

Hiển thị cuối Literature Review — danh sách tất cả papers được cite với clickable PDF link:

**Priority logic để chọn URL:**

| Priority | Nguồn | Lý do |
|---|---|---|
| 1 | `openAccessPdf.url` — status GREEN/GOLD | Verified open access từ S2; GREEN thường là direct PDF |
| 2 | `https://arxiv.org/pdf/{externalIds.ArXiv}` | **Luôn là direct PDF** — UX tốt nhất cho CS/AI papers |
| 3 | `openAccessPdf.url` — status BRONZE/HYBRID | Có thể là HTML landing page, không guaranteed |
| 4 | `https://doi.org/{externalIds.DOI}` | Thường paywalled, nhưng đúng bài |
| 5 | `https://www.semanticscholar.org/paper/{paperId}` | Last resort |

**Tại sao ArXiv PDF (Priority 2) trước openAccessPdf GOLD (Priority 1 chỉ cho GREEN)?**
- `openAccessPdf.url` status GOLD thường trỏ đến HTML journal landing page, không phải file PDF
- `arxiv.org/pdf/{id}` luôn là direct PDF — browser mở ngay, không cần click thêm
- Với status GREEN (institutional repo, preprint server): thường cũng direct PDF → để Priority 1 hợp lý
- BRONZE/HYBRID: link có thể bị paywall sau thời gian hoặc là landing page → Priority 3

**Data đã có sẵn:** `openAccessPdf` và `externalIds` được collect từ Step ② và ②bis — không cần API call thêm.

---

## Ghi chú kỹ thuật: SPECTER2 adapter proximity [v1.0.1]

**Vấn đề gốc:** SPECTER v2 default được train bằng citation triplet loss (paper-to-paper similarity). Dùng để encode "theme description" (text query) là asymmetric retrieval — task không được train cho.

**Giải pháp được chọn:** Dùng `allenai/specter2` với **adapter `proximity`** — task-specific adapter được train cho retrieval (query→paper), khác với default adapter.

```python
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
model.load_adapter("allenai/specter2", source="hf", load_as="proximity", set_active=True)
tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")

def encode_query(text: str) -> list[float]:
    inputs = tokenizer(text, return_tensors="pt", max_length=512, truncation=True)
    outputs = model(**inputs)
    return outputs.last_hidden_state[:, 0, :].squeeze().tolist()
```

- **Document embedding (papers trong ChromaDB):** SPECTER v2 từ Semantic Scholar Batch API (pre-computed, không cần local model, ~400 papers/call)
- **Query embedding (theme description):** SPECTER2 adapter proximity local (~500MB)
- **Ưu điểm:** Cùng model family → embedding space gần nhau hơn so với dùng BGE/E5 khác model hoàn toàn

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

## CHANGELOG

### v1.0.1 — so với v1.0

---

#### [Fix 1] Step ②bis — Seed selection: citations/year đơn → Dual-pool

| | v1.0 | v1.0.1 |
|---|---|---|
| **Seed metric** | top-10 by citations/year | Dual-pool: top-5 raw ∪ top-5 citations/year |
| **Số seeds** | 10 | ~7-9 (sau deduplicate) |

**Lý do:** citations/year thuần túy ưu tiên bài mới → bỏ sót foundational papers. Ví dụ: bài 2020 có 30 citations = 5/year bị rank thấp hơn bài 2024 có 20 citations = 10/year dù ít important hơn. Dual-pool đảm bảo cả 2 loại đều có đại diện làm seed.

**Ưu điểm:** Cover cả foundational (raw count) lẫn recent impactful (per-year).
**Tradeoff:** Thêm 1-2 API calls, số seeds có thể thấp hơn 10 nếu overlap nhiều.

---

#### [Fix 2] Step ②bis — Backward filter: flat → time-decayed + isInfluential

| | v1.0 | v1.0.1 |
|---|---|---|
| **Backward filter** | `min_citations ≥ 5` (flat, hardcode) | Time-decayed relative + isInfluential bypass |
| **Year threshold** | Hardcode 2022 | `current_year - N` (relative, không stale) |

**Lý do:** Flat `≥ 5` loại systematically bài breakthrough mới publish chưa kịp tích lũy citations. Ke et al. (2015) chứng minh papers trong 1-2 năm đầu thường có impact cao nhưng citations thấp.

**isInfluential** (Semantic Scholar ML classifier, ~65% precision): bài được label influential dù citations thấp → bypass threshold. Guard `citations ≥ 1` cho forward để tránh false positive của classifier với bài 0 citation.

**Ưu điểm:** Giảm temporal bias, bắt được breakthrough papers mới.
**Tradeoff:** Corpus có thể thêm noise (preprints chưa peer-review). Mitigation: MMR + RRF ranking tự nhiên lọc bài ít liên quan xuống rank thấp.

---

#### [Fix 3] Step ④ — Outline: từ 100 bài → 400 bài + MMR + user approval

| | v1.0 | v1.0.1 |
|---|---|---|
| **Input** | Top-20 cosine từ 100 bài gốc | MMR-20 từ toàn bộ 300-400 bài |
| **Selection** | Cosine similarity thuần | Pre-filter top-150 → MMR (λ=0.5, k=20) |
| **User control** | Không có | User edit & approve trước khi tiếp tục |

**Lý do:** Outline từ 100 bài gốc = structural bias theo keyword search ban đầu. Snowballed papers (foundational, cross-disciplinary) không ảnh hưởng themes → review thiếu góc nhìn quan trọng. MMR đảm bảo 20 bài đại diện cover nhiều sub-topics khác nhau thay vì 20 bài cùng nói một chuyện.

**Tại sao cần user approval:** Outline là "bản đồ" của review. Sửa outline ở đây = 1 lần, ảnh hưởng tất cả. Sửa ở Step ⑨ (claim level) = tốn công hơn nhiều. User có domain knowledge để biết granularity đúng.

**Ưu điểm:** Fix Phản biện 6 (structural bias); themes phong phú hơn; early error catching.
**Tradeoff:** User phải đợi Steps ①②②bis③ xong (~3-5 phút) mới thấy outline. Giải pháp UX: streaming progress indicator.

---

#### [Fix 4] Step ⑤ — Query encoder: SPECTER v2 default → SPECTER2 adapter proximity

| | v1.0 | v1.0.1 |
|---|---|---|
| **Document embedding** | SPECTER v2 (API) | SPECTER v2 (API) — giữ nguyên |
| **Query embedding** | SPECTER v2 local (default adapter) | SPECTER2 adapter `proximity` |
| **Retrieval mode** | Symmetric (paper↔paper) — SAI | Asymmetric (query→paper) — ĐÚNG |

**Lý do:** SPECTER v2 default train cho paper-to-paper similarity (citation triplets). Dùng encode theme description là asymmetric retrieval — task không được train cho. SciRepEval (Singh 2022) confirm SPECTER2 default kém hơn retrieval models trên search tasks.

**Adapter proximity** = task-specific adapter của cùng model SPECTER2, được fine-tune cho retrieval. Cùng model family → embedding space gần nhau hơn so với dùng BGE/E5 khác model.

**Ưu điểm:** Query embedding đúng task; cùng model → cross-space compatibility tốt hơn.
**Tradeoff:** Cần load adapter (~500MB). Với local MVP chấp nhận được.

---

#### [Fix 5] Step ⑧ — Verification: 1-tier → 3-tier fallback

| | v1.0 | v1.0.1 |
|---|---|---|
| **Coverage** | /snippet/search only (~30% papers) | snippet → arXiv HTML → abstract |
| **Khi no snippet** | Flag uncertain chung | 3 cases với confidence levels khác nhau |
| **Abstract role** | Fallback verify (có thể return Supported) | Conservative only (không return Supported) |

**Lý do:** /snippet/search chỉ có full text cho ~30% papers. 70% còn lại cần fallback. Abstract không đủ verify citation drift (drift xảy ra ở paragraph level). Nếu abstract fallback return "Supported" → false positive bypass human review → nguy hiểm hơn human review ngay.

**arXiv fallback:** Free, no API key, coverage ~80%+ cho CS/AI/ML papers. Lấy arXiv ID từ `externalIds.ArXiv` đã có trong metadata từ Step ②.

**Abstract conservative rule:** KHÔNG bao giờ return "Supported" từ abstract-only. Chỉ detect topic mismatch và rõ ràng mâu thuẫn → Unsupported. Mọi thứ còn lại → Uncertain + low_confidence flag → mandatory human review.

**Ưu điểm:** Phân biệt rõ loại uncertainty; giảm false positive; coverage tốt hơn.
**Tradeoff:** Thêm ar5iv call (có thể slow); low_confidence claims vẫn cần human review.

---

#### [Fix 6] Citation Intent — Làm rõ vai trò, bỏ early-exit

| | v1.0 | v1.0.1 |
|---|---|---|
| **Vai trò** | Chưa rõ; có đề xuất dùng làm shortcut | Metadata bổ sung, không phải shortcut |
| **Logic** | Contrasting/Mentioning → kết luận drift ngay | Contrasting → ưu tiên human review queue |
| **Verification** | Có thể skip nếu intent ≠ Supporting | Luôn chạy full snippet verification |

**Lý do:** Intent = *tại sao* A cite B. Citation drift phổ biến nhất trong `Supporting` citations — AI oversimplify bài nó dùng để ủng hộ claim. Skip verification khi intent = Supporting → miss phần lớn citation drift.

**Ưu điểm:** Verification coverage đầy đủ; Intent vẫn có ích để prioritize human review.
**Tradeoff:** Không tiết kiệm compute bằng early-exit. Correctness > speed cho academic tool.

---

#### [Addendum] Literature Review Display + PDF Links

| | Trước | Sau |
|---|---|---|
| **S2 API fields** | `title,abstract,paperId,citationCount,year,externalIds` | Thêm `openAccessPdf` vào tất cả calls (search, batch, citations, references) |
| **Step ⑥ generation** | User prompt only, không có structure constraint | System prompt `LITERATURE_REVIEW_SYSTEM_PROMPT`: enforce Intro/Body/Conclusion + APA 7 |
| **Step ⑩ output** | Raw markdown, không có PDF links | Structured review + PDF Links Section với priority logic |
| **PDF URL source** | Không có | `openAccessPdf` (GREEN/GOLD) → ArXiv PDF → `openAccessPdf` (BRONZE) → DOI → S2 page |
| **ChromaDB metadata** | Không có `openAccessPdf` | Lưu kèm `openAccessPdf` để dùng ở Step ⑩ |

**Lý do:** `openAccessPdf` từ S2 là nguồn chính xác nhất (đã resolve source), nhưng không phải lúc nào cũng là direct PDF link (GOLD có thể là HTML landing page). ArXiv PDF (`arxiv.org/pdf/{id}`) luôn là direct PDF — UX tốt hơn cho CS/AI papers. Kết hợp cả hai theo priority cho coverage rộng nhất.

---

#### [Identified Gap — Ghi nhận, defer post-MVP]

1. **Co-citation + bibliographic coupling chưa implement:** SPEC đề cập nhưng không có trong flow. Tìm bài cross-disciplinary mà backward/forward snowballing miss. Có thể implement qua cross-join của `/references` lists. → defer v1.1

2. **Single-hop snowballing:** Chỉ 1 hop từ seed. 2-hop tăng recall nhưng tăng corpus size và latency. → cần data thực tế từ MVP để quyết định.

3. **Theme cross-disciplinary gap:** Paper touches nhiều themes nhưng không dominate theme nào → có thể miss ở top-10 của mọi theme. Partial mitigation: MMR trong Step ⑤ giúp chọn diverse papers per theme.
