# PLAN_1.0.1.md — Academic Research Assistant

> Derived from SPEC_1.0.1.md | MVP: Full Flow ①→⑩ | Env: Local Development
> Changelog từ PLAN v1.0: Xem mục [CHANGELOG](#changelog) cuối file

---

## 1. Tech Stack

| Layer | Technology | Thay đổi so với v1.0 |
|---|---|---|
| **Backend** | FastAPI (Python 3.11+) | Không đổi |
| **Vector DB** | ChromaDB (local persistent) | Không đổi |
| **LLM** | Multi-provider via env config | Không đổi |
| **Embedding — Document** | SPECTER v2 qua Semantic Scholar Batch API | Không đổi |
| **Embedding — Query** | `allenai/specter2` adapter `proximity` (local ~500MB) | **MỚI** — thay EMBEDDING_MODEL generic |
| **BM25 (keyword search)** | `rank_bm25` | Không đổi |
| **MMR selection** | Custom implementation (hoặc LangChain MMR) | **MỚI** |
| **arXiv full text** | `ar5iv.labs.arxiv.org` HTML + BeautifulSoup | **MỚI** |
| **Markdown renderer** | `react-markdown` + `remark-gfm` | **MỚI** — render Literature Review |
| **Frontend** | React.js + TailwindCSS + Iconify | Không đổi |
| **API nguồn dữ liệu** | Semantic Scholar API (có key) | Không đổi |
| **Deployment (MVP)** | Local only | Không đổi |

---

## 2. Environment Variables

```env
# LLM Provider
PROVIDER="custom"                  # openai | anthropic | google | custom
LLM_API_KEY=""                     # API key của provider
LLM_MODEL="gpt-oss-120b"          # Model name
LLM_BASE_URL=""                    # Base URL nếu dùng custom endpoint

# Semantic Scholar
SEMANTIC_SCHOLAR_API_KEY=""        # Key đã có

# SPECTER2 Adapter (local model cho query encoding)
SPECTER2_MODEL_PATH="allenai/specter2_base"   # HuggingFace model id hoặc local path
SPECTER2_ADAPTER="allenai/specter2"           # Adapter proximity từ HuggingFace

# ChromaDB
CHROMA_PERSIST_PATH="./data/chroma"

# App
CORS_ORIGINS="http://localhost:3000"

# Snowballing config
SNOWBALL_POOL_SIZE=5               # top-N cho mỗi pool (raw + per-year)
SNOWBALL_FORWARD_YEAR_WINDOW=4     # current_year - N cho forward filter
SNOWBALL_BACKWARD_RECENT=2         # year >= current_year - N → min_citations=0
SNOWBALL_BACKWARD_MID=5            # year >= current_year - N → min_citations=3

# MMR config
MMR_LAMBDA=0.5                     # λ cho MMR (0=pure diversity, 1=pure relevance)
MMR_PREFETCH_OUTLINE=150           # fetch_k trước MMR cho Step ④
MMR_PREFETCH_THEME=50              # fetch_k trước MMR cho Step ⑤
```

---

## 3. Project Structure

```
academic_research/
├── backend/
│   ├── main.py                        # FastAPI entry point
│   ├── config.py                      # Load env vars + constants
│   ├── api/
│   │   ├── search.py                  # POST /api/search (Step ①②)
│   │   ├── snowball.py                # POST /api/snowball (Step ②bis)
│   │   ├── embed.py                   # POST /api/embed (Step ③)
│   │   ├── outline.py                 # POST /api/outline/generate (Step ④)
│   │   │                              # POST /api/outline/approve
│   │   ├── review.py                  # POST /api/review/theme (Step ⑤⑥)
│   │   ├── claims.py                  # POST /api/claims/extract (Step ⑦)
│   │   │                              # POST /api/claims/verify (Step ⑧⑨)
│   │   └── export.py                  # GET  /api/review/export (Step ⑩)
│   ├── services/
│   │   ├── semantic_scholar.py        # Wrapper Semantic Scholar API
│   │   ├── specter_batch.py           # SPECTER v2 qua Batch API (document embedding)
│   │   ├── specter_local.py           # SPECTER2 adapter proximity (query embedding) [MỚI]
│   │   ├── arxiv_fetcher.py           # ar5iv HTML full text fetcher [MỚI]
│   │   ├── vector_store.py            # ChromaDB operations
│   │   ├── mmr.py                     # Maximal Marginal Relevance selection [MỚI]
│   │   ├── hybrid_search.py           # Semantic(MMR) + BM25 + RRF merge
│   │   ├── llm_client.py              # Multi-provider LLM caller
│   │   ├── snowball.py                # Citation snowballing (dual-pool + isInfluential)
│   │   ├── outline_generator.py       # Step ④: MMR-20 → LLM → outline
│   │   ├── content_generator.py       # Step ⑥: LLM → themed content
│   │   ├── claim_extractor.py         # Step ⑦: tách claims + paperId + intent
│   │   └── citation_verifier.py       # Step ⑧: 3-tier verify pipeline
│   ├── models/
│   │   ├── paper.py                   # Paper schema (thêm externalIds, isInfluential)
│   │   ├── claim.py                   # Claim schema (thêm intent, low_confidence)
│   │   ├── outline.py                 # Theme + Outline schema [MỚI]
│   │   └── review.py                  # LiteratureReview schema
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── ProgressStepper.tsx    # Streaming progress ①→⑩ [MỚI]
│   │   │   ├── PaperGraph.tsx         # Citation graph visualization
│   │   │   ├── ThemeOutline.tsx       # Edit/approve outline (Step ④) [CẬP NHẬT]
│   │   │   ├── ReviewEditor.tsx
│   │   │   └── ClaimVerifier.tsx      # Human review panel (step ⑨) [CẬP NHẬT]
│   │   ├── pages/
│   │   │   ├── Home.tsx
│   │   │   └── Review.tsx
│   │   └── App.tsx
│   ├── tailwind.config.js
│   └── package.json
├── data/
│   └── chroma/                        # ChromaDB persistent storage
└── docs/
    ├── SPEC.md
    ├── SPEC_1.0.1.md
    ├── PLAN.md
    └── PLAN_1.0.1.md
```

---

## 4. API Endpoints (Backend)

| Method | Path | Mô tả | Thay đổi |
|---|---|---|---|
| `POST` | `/api/search` | ① Search Semantic Scholar → 100 bài (thêm `externalIds`) | Thêm field |
| `POST` | `/api/snowball` | ②bis Dual-pool seed selection + isInfluential filter | **Cập nhật logic** |
| `POST` | `/api/embed` | ③ SPECTER v2 Batch API → ChromaDB | Không đổi |
| `POST` | `/api/outline/generate` | ④ MMR-20 từ 400 bài → LLM → outline draft | **Cập nhật** |
| `POST` | `/api/outline/approve` | ④ User submit outline đã edit → lưu vào session | **MỚI** |
| `POST` | `/api/review/theme` | ⑤⑥ Hybrid search (MMR) + generate content per theme | Thêm MMR |
| `POST` | `/api/claims/extract` | ⑦ Tách claims + intent metadata | Thêm intent |
| `POST` | `/api/claims/verify` | ⑧ 3-tier verify (snippet→arXiv→abstract) | **Cập nhật lớn** |
| `GET`  | `/api/review/export` | ⑩ Export literature review hoàn chỉnh | Không đổi |

---

## 5. Implementation Phases

### Phase 1 — Data Layer (Steps ①②bis③)

**Mục tiêu:** Có corpus 300–400 bài đã embed trong ChromaDB với metadata đầy đủ

**Tasks:**

- [ ] Setup FastAPI project, config env, CORS
- [ ] `semantic_scholar.py`: wrap `/paper/search`
  - Fields: `title, abstract, paperId, citationCount, year, externalIds, openAccessPdf`
  - `externalIds` cần có để lấy `ArXiv` ID cho Step ⑧
  - `openAccessPdf` cần có để build PDF display link cho Step ⑩ (status GREEN/GOLD → priority 1)
- [ ] `snowball.py`: Dual-pool seed selection + isInfluential filter
  - Seed selection:
    - Pool A: top-5 by raw `citationCount`
    - Pool B: top-5 by `citationCount / (current_year - year)`
    - Seeds = Pool A ∪ Pool B → deduplicate paperId
  - Backward filter (isInfluential bypass + time-decayed):
    ```python
    current_year = datetime.now().year
    def backward_keep(paper):
        if paper["isInfluential"]:
            return True
        year = paper.get("year", 2000)
        citations = paper.get("citationCount", 0)
        if year >= current_year - 2:   return citations >= 0
        if year >= current_year - 5:   return citations >= 3
        return citations >= 5
    ```
  - Forward filter:
    ```python
    def forward_keep(paper):
        year = paper.get("year", 0)
        citations = paper.get("citationCount", 0)
        if paper["isInfluential"] and citations >= 1:
            return True
        return year >= current_year - 4 and citations >= 1
    ```
  - Deduplicate → corpus ~300-400 bài
  - API calls: include `openAccessPdf` trong fields cho cả `/citations` và `/references`
    `?fields=contexts,intents,isInfluential,citationCount,year,externalIds,openAccessPdf`
- [ ] `specter_batch.py`: SPECTER v2 qua Batch API
  ```
  POST /paper/batch?fields=embedding.specter_v2,openAccessPdf
  Body: {"ids": [paperIds]} — max 500/call
  ```
  - `embedding: null` → fallback encode abstract bằng `specter_local.py`
- [ ] `specter_local.py`: Load SPECTER2 adapter proximity
  ```python
  from adapters import AutoAdapterModel
  model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
  model.load_adapter("allenai/specter2", source="hf",
                     load_as="proximity", set_active=True)
  ```
  - Dùng cho: query encoding (Step ①④⑤) + fallback document encoding (Step ③)
- [ ] `vector_store.py`: ChromaDB insert
  - Metadata: `{paperId, title, year, citationCount, externalIds, openAccessPdf}`
  - Deduplication bằng `paperId` trước khi insert
- [ ] `paper.py`: cập nhật Paper schema thêm `openAccessPdf`
  ```python
  class Paper(BaseModel):
      paperId: str
      title: str
      abstract: str | None = None
      year: int | None = None
      citationCount: int = 0
      externalIds: dict | None = None
      openAccessPdf: dict | None = None  # {"url": str, "status": str} | null
  ```

---

### Phase 2 — Outline Layer (Step ④)

**Mục tiêu:** Outline đa góc nhìn từ toàn bộ corpus, có user approval

**Tasks:**

- [ ] `mmr.py`: MMR selection utility
  ```python
  def mmr_select(query_vec, doc_vecs, doc_ids, k=20, lambda_mult=0.5, fetch_k=150):
      # 1. Pre-filter top fetch_k by cosine similarity
      # 2. Greedy MMR từ fetch_k candidates
      # Returns: list of doc_ids (k items)
  ```
- [ ] `outline_generator.py`: MMR-20 → LLM → outline
  - Input: query_vector (từ Step ①), toàn bộ ChromaDB (300-400 bài)
  - MMR: `fetch_k=150, k=20, λ=0.5` → 20 bài diverse
  - Prompt LLM: "Từ 20 abstracts này, identify 5-8 themes chính của topic. Mỗi theme: tên ngắn + mô tả 1-2 câu."
  - Output: `Outline {themes: [{name, description}]}`
- [ ] API `/api/outline/generate`: gọi `outline_generator.py`, trả về draft outline
- [ ] API `/api/outline/approve`: nhận outline đã edit từ user → lưu vào session state
- [ ] Frontend `ThemeOutline.tsx`: editable outline component
  - Hiển thị themes dạng list
  - Mỗi theme: editable name + description
  - Nút "Add Theme", "Delete", drag-to-reorder
  - Nút "Approve & Continue" → POST `/api/outline/approve`

---

### Phase 3 — Retrieval & Generation Layer (Steps ⑤⑥⑦)

**Mục tiêu:** Per-theme hybrid search với MMR, LLM generate content có citation

**Tasks:**

- [ ] `hybrid_search.py`: Updated hybrid search per theme
  - Semantic: embed theme description bằng `specter_local.py` (adapter proximity) → pre-filter top-50 → MMR(k=10)
  - Keyword: BM25 trên `title + abstract` (rank_bm25)
  - Merge: RRF → top-10 per theme
  - Chạy song song cho tất cả themes (asyncio.gather)
- [ ] `content_generator.py`: LLM generate per theme
  - Input: top-10 abstracts + theme description
  - **System prompt:** `LITERATURE_REVIEW_SYSTEM_PROMPT` (xem SPEC — Literature Review Format)
    - Enforce per-theme structure: Topic Sentence → Description → Analysis → Evaluation → Transition
    - Enforce APA 7 in-text citations: `(Author, Year)` hoặc `Author (Year)`
    - Hard rule: chỉ cite papers trong provided abstracts — không bịa
  - User prompt format bắt buộc: `(Source: PAPER_ID)` sau mỗi claim (để `claim_extractor.py` parse)
  - Output: structured markdown content cho theme
- [ ] **Step ⑩ merge** — `export.py`:
  - LLM generate INTRODUCTION + CONCLUSION bao trùm toàn bộ themes (cùng system prompt)
  - `build_pdf_url(paper)` cho mỗi cited paper:
    ```python
    def build_pdf_url(paper: dict) -> str | None:
        oa = paper.get("openAccessPdf") or {}
        ext = paper.get("externalIds") or {}
        if oa.get("status") in ("GREEN", "GOLD") and oa.get("url"):
            return oa["url"]                              # Priority 1: S2 open access
        if ext.get("ArXiv"):
            return f"https://arxiv.org/pdf/{ext['ArXiv']}"  # Priority 2: direct PDF
        if oa.get("url"):
            return oa["url"]                              # Priority 3: BRONZE/HYBRID
        if ext.get("DOI"):
            return f"https://doi.org/{ext['DOI']}"        # Priority 4: DOI
        return f"https://www.semanticscholar.org/paper/{paper['paperId']}"  # Priority 5
    ```
  - `GET /api/review/export` response thêm: `citedPapers: [{paperId, title, authors, year, pdfUrl}]`
- [ ] `claim_extractor.py`: Parse output + gắn intent
  - Extract `{claim_text, paperId}` bằng regex hoặc LLM extraction
  - Lookup `intents` từ Semantic Scholar metadata (lưu khi snowball)
  - Schema `Claim`:
    ```python
    {
      "id": str,
      "text": str,
      "paperId": str,
      "intent": "Supporting" | "Contrasting" | "Mentioning" | None,
      "status": "pending" | "supported" | "partial" | "unsupported" | "uncertain",
      "low_confidence": bool,
      "source": "snippet" | "arxiv" | "abstract" | None,
      "quote": str | None
    }
    ```

---

### Phase 4 — Verification Layer (Steps ⑧⑨)

**Mục tiêu:** 3-tier verification, routing thông minh theo status + intent

**Tasks:**

- [ ] `arxiv_fetcher.py`: Fetch arXiv full text
  ```python
  async def fetch_arxiv_text(arxiv_id: str) -> str | None:
      url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
      resp = await httpx.get(url, timeout=15)
      if resp.status_code != 200: return None
      soup = BeautifulSoup(resp.text, "html.parser")
      # Extract main content, remove nav/header/footer
      return soup.get_text(separator=" ", strip=True)[:10000]  # 10k chars
  ```
- [ ] `citation_verifier.py`: 3-tier pipeline
  ```
  Case A: /snippet/search?query={claim}&paperId={id}
    → Có kết quả → verify → classify 4 categories
    → Lưu snippet làm quote
  
  Case B: externalIds.ArXiv exists → ar5iv HTML
    → Parse text → extract đoạn relevant → verify
  
  Case C: Abstract conservative
    → Chỉ return Unsupported (topic mismatch / rõ mâu thuẫn)
    → Mọi thứ còn lại → Uncertain + low_confidence=True
    → KHÔNG return Supported
  ```
- [ ] LLM verify prompt template (dùng cho cả 3 cases):
  ```
  "Given the following source text from paper {paperId}:
  ---
  {source_text}
  ---
  Does this source text support the following claim?
  Claim: {claim_text}
  
  Classify as one of:
  - Supported: source explicitly and directly confirms the claim
  - Partially Supported: source is related but claim oversimplifies or omits conditions
  - Unsupported: source contradicts or does not mention the claim
  - Uncertain: source is ambiguous or insufficient to determine
  
  [For abstract-only: if not explicitly confirmed → classify as Uncertain, never Supported]
  
  Return JSON: {status, quote (relevant excerpt or null)}"
  ```
- [ ] Routing logic (Step ⑨):
  ```python
  def route_claim(claim):
      if claim.status == "unsupported":
          return "remove"
      if claim.status == "supported" and not claim.low_confidence:
          return "include"  # với quote
      if claim.intent == "Contrasting":
          return "human_review_priority"
      return "human_review"  # partial, uncertain, low_confidence
  ```
- [ ] API `/api/claims/verify`: batch verify all claims, return với routing decision
- [ ] Frontend `ClaimVerifier.tsx`: Updated
  - Priority queue: Contrasting intent → đầu danh sách
  - Hiển thị: status badge, source type (snippet/arxiv/abstract), quote nếu có
  - Nút Approve / Reject per claim
  - Low confidence claims được highlight rõ

---

### Phase 5 — Frontend (Parallel với Phase 3–4)

**Mục tiêu:** UI cho phép user chạy toàn bộ flow với progress tracking

**Tasks:**

- [ ] Setup Vite + React + TailwindCSS + Iconify
- [ ] `SearchBar`: nhập topic → POST `/api/search`
- [ ] `ProgressStepper.tsx`: **MỚI** — streaming progress indicator
  - Hiển thị từng step ①→⑩ với status (pending/running/done/error)
  - WebSocket hoặc SSE để update realtime trong khi Steps ①②②bis③ chạy
  - User không thấy màn hình trắng trong 3-5 phút chờ
- [ ] `ThemeOutline.tsx`: **Cập nhật** — editable, approvable
- [ ] `ReviewEditor.tsx`: render literature review bằng `react-markdown` + `remark-gfm`
  - Tailwind `prose` classes cho typography (headings, paragraphs, bold)
  - Custom renderer: H2 = theme title, H3 = sub-section (Description/Analysis/Evaluation)
  - In-text citations `(Author, Year)` render as-is — không cần thêm xử lý
- [ ] `PDFLinksSection.tsx` — **MỚI**: section cuối review hiển thị cited papers
  - Mỗi paper: APA 7 reference entry + `[PDF]` link (`target="_blank"`, `rel="noopener noreferrer"`)
  - PDF URL từ `pdfUrl` trong `citedPapers` response (đã resolved bởi `build_pdf_url` ở backend)
  - Badge hiển thị nguồn: `OA` (GREEN/GOLD) / `ArXiv` / `DOI` / `S2` — user biết expect gì khi click
- [ ] `ClaimVerifier.tsx`: **Cập nhật** — priority queue, source badges, low_confidence highlight
- [ ] `PaperGraph.tsx`: visualize citation graph — dùng `react-force-graph` hoặc `d3`
- [ ] Export button → Markdown / PDF
  - Trigger `GET /api/review/export` → nhận `{markdownContent, citedPapers}`
  - Mount `<PDFLinksSection papers={citedPapers} />` bên dưới `<ReviewEditor />`

---

### Phase 6 — Integration & Testing

**Tasks:**

- [ ] End-to-end test với 1 topic thực (ví dụ: "RAG for systematic literature review")
- [ ] Đo: số bài hallucination cứng (paperId không tồn tại) → mục tiêu ~0%
- [ ] Đo: citation drift rate trước/sau verify → mục tiêu giảm 65–70%
- [ ] Đo: snippet coverage (Case A %) / arXiv coverage (Case B %) / abstract fallback (Case C %)
- [ ] Đo: thời gian chạy full flow (mục tiêu < 5 phút cho full corpus 400 bài)
- [ ] Đo: outline quality — số themes, có cover các góc nhìn quan trọng không (manual eval)
- [ ] Evaluate theo SPEC_1.0.1: ghi lại kết quả thực tế

---

## 6. Key Dependencies (requirements.txt)

```txt
# Web framework
fastapi
uvicorn[standard]

# HTTP client
httpx                      # async calls to Semantic Scholar + arXiv

# Vector DB
chromadb

# Keyword search
rank_bm25

# Embedding — SPECTER2 adapter proximity
transformers>=4.35.0
adapters>=0.1.1            # HuggingFace adapters library (allenai/specter2 adapter)
torch                      # CPU ok cho inference ~500MB model
numpy

# HTML parsing (arXiv fallback)
beautifulsoup4
lxml

# LLM providers
openai                     # dùng cho custom endpoint (PROVIDER=custom)
anthropic                  # optional

# Utils
python-dotenv
pydantic
```

**Frontend (npm):**

```bash
npm install react-markdown remark-gfm
```

| Package | Version | Mục đích |
|---|---|---|
| `react-markdown` | ^9.x | Render markdown Literature Review |
| `remark-gfm` | ^4.x | GitHub Flavored Markdown: tables, strikethrough, task lists |

---

## 7. Rủi ro & Giới hạn

| Rủi ro | Giải pháp v1.0.1 |
|---|---|
| SPECTER v2 `null` cho paper mới | Fallback: encode abstract bằng SPECTER2 adapter proximity locally |
| `/snippet/search` không trả kết quả (~70%) | 3-tier: arXiv → abstract conservative |
| ar5iv.labs.arxiv.org không có paper | Fallback về Case C (abstract) |
| arXiv HTML quá dài → LLM overwhelmed | Truncate tại 10,000 chars, lấy đoạn relevant bằng keyword search |
| Rate limit Semantic Scholar | Exponential backoff + cache theo `paperId` |
| SPECTER2 adapter load time (~500MB) | Load 1 lần khi server start, cache in memory |
| User approval Step ④ blocking | Progress indicator + streaming; user thấy outline sau ~3-5 phút |
| Citation drift chỉ giải quyết ~65–70% | Known limitation, ghi nhận trong SPEC Non-goals |
| LLM provider thay đổi | Tất cả route qua `llm_client.py`, chỉ đổi env |
| isInfluential classifier ~65% precision | Guard `citations ≥ 1` cho forward; chỉ dùng như soft signal |

---

## 8. Milestones

| Milestone | Nội dung | Target |
|---|---|---|
| M1 | Phase 1 done: search + snowball (dual-pool + isInfluential) + SPECTER2 local + ChromaDB | Week 1 |
| M2 | Phase 2 done: MMR outline + user approval UI | Week 2 |
| M3 | Phase 3 done: hybrid search (MMR) + generation + claim extraction | Week 3 |
| M4 | Phase 4 done: 3-tier verification + routing | Week 4 |
| M5 | Phase 5 done: Frontend connected với progress streaming | Week 5 |
| M6 | Phase 6: E2E test + evaluate + điều chỉnh thresholds | Week 6 |

---

## CHANGELOG

### PLAN_1.0.1 — so với PLAN v1.0

| Thay đổi | Chi tiết |
|---|---|
| **Embedding model** | Tách thành 2: `specter_batch.py` (document, API) + `specter_local.py` (query, adapter proximity) |
| **Env vars** | Thay `EMBEDDING_MODEL/EMBEDDING_BASE_URL` bằng `SPECTER2_MODEL_PATH/SPECTER2_ADAPTER` + snowball/MMR config |
| **Snowball logic** | Dual-pool seed selection; time-decayed backward filter; isInfluential bypass; relative year thresholds |
| **Outline** | Input từ 400 bài (không phải 100); MMR selection; user edit & approve; mới có `/api/outline/approve` |
| **Hybrid search** | Thêm MMR(fetch_k=50, k=10) sau cosine filter trước RRF |
| **Claim schema** | Thêm `intent`, `low_confidence`, `source`, `quote` fields |
| **Verification** | 3-tier pipeline: snippet → arXiv (ar5iv) → abstract conservative; mới có `arxiv_fetcher.py` |
| **Routing** | 5 categories + Contrasting intent priority; `low_confidence` flag riêng |
| **Frontend** | Thêm `ProgressStepper.tsx`; cập nhật `ThemeOutline.tsx` + `ClaimVerifier.tsx` |
| **Dependencies** | Thêm `adapters`, `beautifulsoup4`, `lxml`; giữ các dep cũ |
| **Milestones** | 5 tuần → 6 tuần (thêm Phase 2 riêng cho outline) |

---

### PLAN_1.0.1 — Addendum: Literature Review Display + PDF Links

| Thay đổi | Chi tiết |
|---|---|
| **`openAccessPdf` field** | Thêm vào tất cả S2 API calls: `/paper/search`, `/paper/batch`, `/citations`, `/references` |
| **`paper.py` schema** | Thêm `openAccessPdf: dict \| None` field |
| **`content_generator.py`** | Dùng `LITERATURE_REVIEW_SYSTEM_PROMPT` làm system message: enforce Intro/Body/Conclusion + APA 7 |
| **`export.py`** | `build_pdf_url()` — priority: openAccessPdf GREEN/GOLD → ArXiv PDF → openAccessPdf BRONZE → DOI → S2; response thêm `citedPapers` |
| **`ReviewEditor.tsx`** | Migrate sang `react-markdown` + `remark-gfm` + Tailwind prose |
| **`PDFLinksSection.tsx`** | Component mới — cited papers với `[PDF]` links + source badge cuối review |
| **Tech Stack (frontend)** | Thêm `react-markdown` + `remark-gfm` |
