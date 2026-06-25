# PLAN.md — Academic Research Assistant

> Derived from SPEC.md v1.0 | MVP: Full Flow ①→⑩ | Env: Local Development

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI (Python 3.11+) |
| **Vector DB** | ChromaDB (local persistent) |
| **LLM / Embedding** | Multi-provider via env config |
| **BM25 (keyword search)** | `rank_bm25` |
| **Frontend** | React.js + TailwindCSS + Iconify |
| **API nguồn dữ liệu** | Semantic Scholar API (có key) |
| **Deployment (MVP)** | Local only |

---

## 2. Environment Variables

```env
# LLM Provider
PROVIDER="custom"                  # openai | anthropic | google | custom
LLM_API_KEY=""                     # API key của provider
LLM_MODEL="gpt-oss-120b"          # Model name
LLM_BASE_URL=""                    # Base URL nếu dùng custom endpoint

# Embedding
EMBEDDING_MODEL="nv-embed-v1"      # Model embedding
EMBEDDING_BASE_URL=""              # Base URL nếu custom

# Semantic Scholar
SEMANTIC_SCHOLAR_API_KEY=""        # Key đã có

# ChromaDB
CHROMA_PERSIST_PATH="./data/chroma"

# App
CORS_ORIGINS="http://localhost:3000"
```

---

## 3. Project Structure

```
academic_research/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Load env vars
│   ├── api/
│   │   ├── search.py              # POST /api/search
│   │   ├── snowball.py            # POST /api/snowball
│   │   ├── review.py              # POST /api/review/generate
│   │   └── verify.py             # POST /api/verify/claims
│   ├── services/
│   │   ├── semantic_scholar.py    # Wrapper Semantic Scholar API
│   │   ├── embedding.py           # SPECTER v2 + custom embed
│   │   ├── vector_store.py        # ChromaDB operations
│   │   ├── hybrid_search.py       # Semantic + BM25 + RRF merge
│   │   ├── llm_client.py          # Multi-provider LLM caller
│   │   ├── outline_generator.py   # Step ④: LLM → outline
│   │   ├── content_generator.py   # Step ⑥: LLM → themed content
│   │   ├── claim_extractor.py     # Step ⑦: tách claims + paperId
│   │   ├── citation_verifier.py   # Step ⑧: /snippet/search verify
│   │   └── snowball.py            # Step ②bis: citation snowballing
│   ├── models/
│   │   ├── paper.py               # Paper schema
│   │   ├── claim.py               # Claim schema
│   │   └── review.py              # LiteratureReview schema
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── PaperGraph.tsx     # Citation graph visualization
│   │   │   ├── ReviewEditor.tsx
│   │   │   ├── ClaimVerifier.tsx  # Human review panel (step ⑨)
│   │   │   └── ThemeOutline.tsx
│   │   ├── pages/
│   │   │   ├── Home.tsx
│   │   │   └── Review.tsx
│   │   └── App.tsx
│   ├── tailwind.config.js
│   └── package.json
├── data/
│   └── chroma/                    # ChromaDB persistent storage
└── docs/
    ├── SPEC.md
    └── PLAN.md
```

---

## 4. API Endpoints (Backend)

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/search` | ① Search Semantic Scholar → 100 bài |
| `POST` | `/api/snowball` | ②bis Citation snowballing → mở rộng corpus |
| `POST` | `/api/embed` | ③ Lấy SPECTER v2 + lưu vào ChromaDB |
| `POST` | `/api/outline` | ④ Top-20 → LLM → outline themes |
| `POST` | `/api/review/theme` | ⑤⑥ Hybrid search + generate content per theme |
| `POST` | `/api/claims/extract` | ⑦ Tách claims từ generated content |
| `POST` | `/api/claims/verify` | ⑧ /snippet/search → verify từng claim |
| `GET`  | `/api/review/export` | ⑩ Export literature review hoàn chỉnh |

---

## 5. Implementation Phases

### Phase 1 — Data Layer (Steps ①②③)

**Mục tiêu:** Có corpus 300–400 bài đã embed trong ChromaDB

**Tasks:**
- [ ] Setup FastAPI project, config env, CORS
- [ ] `semantic_scholar.py`: wrap `/paper/search` (title + abstract + paperId + citationCount + year)
- [ ] `snowball.py`: top-10 by citations/year → `/references` + `/citations` → deduplicate
- [ ] `embedding.py`: lấy SPECTER v2 qua batch API `GET /paper/{id}?fields=embedding.specter_v2` (400 papers/call)
- [ ] `vector_store.py`: ChromaDB insert với metadata `{paperId, title, year, citationCount}`
- [ ] Deduplication bằng `paperId` trước khi insert

**Key constraint:** SPECTER v2 từ Semantic Scholar API (pre-computed, không cần chạy local model)

---

### Phase 2 — Retrieval Layer (Steps ④⑤)

**Mục tiêu:** Hybrid search hoạt động, LLM ra outline có themes

**Tasks:**
- [ ] `hybrid_search.py`:
  - Semantic: embed theme description bằng `EMBEDDING_MODEL` → query ChromaDB
  - Keyword: BM25 trên title + abstract
  - Merge: Reciprocal Rank Fusion (RRF) → top-10
- [ ] `llm_client.py`: multi-provider caller (đọc `PROVIDER` env → route đúng SDK)
- [ ] `outline_generator.py`: top-20 by cosine similarity → prompt → outline với danh sách themes

---

### Phase 3 — Generation Layer (Steps ⑥⑦)

**Mục tiêu:** LLM sinh content có citation rõ ràng theo format `[PAPER_ID: xxx]`

**Tasks:**
- [ ] `content_generator.py`: per theme, đọc abstracts → prompt structured → output với `(Source: PAPER_ID)`
- [ ] `claim_extractor.py`: parse output → list `{claim_text, paper_id}` dùng regex hoặc LLM extraction
- [ ] Schema `Claim`: `{id, text, paperId, status: pending|supported|partial|unsupported|uncertain}`

---

### Phase 4 — Verification Layer (Steps ⑧⑨)

**Mục tiêu:** Mỗi claim được verify bằng full text snippet

**Tasks:**
- [ ] `citation_verifier.py`:
  - `/snippet/search?query={claim_text}` → 500-word snippet từ full text
  - LLM classify: `Supported | Partially Supported | Unsupported | Uncertain`
  - Map về `Claim.status`
- [ ] Unsupported → flag, không đưa vào review cuối
- [ ] Uncertain → `human_review: true` → hiển thị trên UI để user quyết định

---

### Phase 5 — Frontend (Parallel với Phase 3–4)

**Mục tiêu:** UI cho phép user chạy toàn bộ flow, review claims

**Tasks:**
- [ ] Setup Vite + React + TailwindCSS + Iconify
- [ ] `SearchBar`: nhập topic → gọi `/api/search`
- [ ] Progress indicator cho từng step (①→⑩)
- [ ] `ThemeOutline`: hiển thị outline từ Phase 2
- [ ] `ReviewEditor`: markdown view của literature review
- [ ] `ClaimVerifier`: list claims `uncertain/unsupported` → user approve/reject
- [ ] `PaperGraph`: visualize citation graph (snowballed papers) — dùng `react-force-graph` hoặc `d3`
- [ ] Export button → Markdown / PDF

---

### Phase 6 — Integration & Testing

**Tasks:**
- [ ] End-to-end test với 1 topic thực (ví dụ: "RAG for systematic literature review")
- [ ] Đo: số bài hallucination cứng (DOI không tồn tại) → mục tiêu ~0%
- [ ] Đo: citation drift rate trước/sau verify → mục tiêu giảm 65–70%
- [ ] Đo: thời gian chạy full flow (mục tiêu < 3 phút cho 100 bài)
- [ ] Evaluate theo SPEC: ghi lại kết quả thực tế

---

## 6. Key Dependencies (requirements.txt)

```txt
fastapi
uvicorn[standard]
httpx                  # async HTTP calls to Semantic Scholar
chromadb
rank_bm25
openai                 # dùng cho custom endpoint (PROVIDER=custom)
anthropic              # optional
python-dotenv
pydantic
```

---

## 7. Rủi ro & Giới hạn (từ SPEC)

| Rủi ro | Giải pháp |
|---|---|
| SPECTER v2 không có cho paper mới | Fallback: embed abstract bằng `EMBEDDING_MODEL` |
| `/snippet/search` không trả kết quả | Flag claim là `uncertain` → human review |
| Rate limit Semantic Scholar | Exponential backoff + cache theo `paperId` |
| Citation drift chỉ giải quyết ~65–70% | Scope đã được ghi nhận trong SPEC Non-goals |
| LLM provider thay đổi | Tất cả route qua `llm_client.py`, chỉ đổi env |

---

## 8. Milestones

| Milestone | Nội dung | Target |
|---|---|---|
| M1 | Phase 1 done: search + snowball + embed + ChromaDB | Week 1 |
| M2 | Phase 2 done: hybrid search + outline | Week 2 |
| M3 | Phase 3–4 done: generation + verification | Week 3–4 |
| M4 | Phase 5 done: Frontend connected | Week 5 |
| M5 | Phase 6: E2E test + evaluate | Week 6 |
