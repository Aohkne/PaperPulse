# Tổng quan (Overview)

**Version:** 2.0
**Changelog từ v1.0.1:** Xem mục [CHANGELOG](#changelog) cuối file

---

## Tóm tắt (Executive Summary)

> Nhà nghiên cứu mất hàng tuần để tổng quan tài liệu cho một chủ đề, đọc hàng trăm bài báo, và vẫn có nguy cơ bỏ sót công trình quan trọng hoặc không nhận ra khoảng trống nghiên cứu thực sự.

**v1.0.1** giải quyết được hallucination và citation drift thông qua RAG grounding + 3-tier verification. Tuy nhiên còn 3 điểm yếu cốt lõi chưa giải quyết:

1. **Không có intent routing** — mọi input kể cả "hello" đều bị đưa thẳng vào pipeline search.
2. **Single-query, single-source** — 1 query trên Semantic Scholar cho 100 bài, bỏ sót toàn bộ papers nhìn từ góc độ khác hoặc nằm ở database khác.
3. **1 LLM sequential** — các bước có thể chạy song song (content generation per theme, verification per claim) đang chạy tuần tự, tốn 5-10 phút không cần thiết.

**v2.0** giải quyết 3 vấn đề trên bằng:
- **Conversational pre-flight** (Step 0): LLM tự suy luận intent → hỏi lại hoặc tạo research plan trước khi search.
- **Multi-agent parallel search** (Step ①): N agents × M sources chạy đồng thời, mỗi agent nhìn từ 1 góc (foundational / optimization / evaluation / application / recent).
- **Specialized parallel agents** (Step ⑥⑧): Writer agents và Verifier agents chạy song song, dùng model phù hợp với từng task.

---

## Mục tiêu (Goals)

### Mục tiêu giữ nguyên từ v1.0.1
- Tiết kiệm thời gian đọc bài
- Tìm được bài → hiểu bài → đưa ra quyết định đúng đắn
- Hallucination cứng (bịa DOI): giải quyết ~99% bằng RAG grounding
- Citation drift: giải quyết ~65-70% bằng 3-tier verification

### Mục tiêu mới của v2.0

| Mục tiêu | Metric | Baseline (v1.0.1) |
|---|---|---|
| Corpus coverage | Papers tìm được trước snowball | 100 (1 query) → **400-600** (multi-agent) |
| Source diversity | Số database được check | 1 (S2) → **3** (S2 + OpenAlex + arXiv) |
| Wall-clock time | Tổng thời gian Step ⑥+⑧ | ~5-10 phút → **~1-2 phút** (parallel agents) |
| Query intent accuracy | Không gửi "hello" vào search | 0% → **~100%** (intent router) |
| User alignment | User confirm research scope trước khi search | Không có → **Có** (research plan approval) |

### Nằm ngoài phạm vi (Non-goals) — giữ nguyên từ v1.0.1
> Gợi ý khoảng trống nghiên cứu (Research Gap) quá chung chung, thiếu sự đánh giá so sánh đối chiếu và chỉ ra mâu thuẫn giữa các nghiên cứu cũ.

---

## Flow chính v2.0

```
[Step 0] User input → LLM Intent Router
            ↓
[Step ①] Multi-agent Parallel Search (N agents × M sources)
            ↓
[Step ①bis] Cross-source Dedup (DOI → arXiv ID → title fuzzy)
            ↓
[Step ②bis] Citation Snowballing (từ corpus lớn hơn)
            ↓
[Step ③] SPECTER v2 Batch Embed → ChromaDB
            ↓
[Step ④] MMR-20 → LLM Outline → User Approval
            ↓
[Step ⑤] Per-theme Hybrid Search (parallel, asyncio.gather)
            ↓
[Step ⑥] Parallel Writer Agents (1 agent/theme, đồng thời)
            ↓
[Step ⑦] Claim Extraction + Intent Metadata
            ↓
[Step ⑧] Parallel Verifier Agents (batch, small model)
            ↓
[Step ⑨] Routing + Human Review
            ↓
[Step ⑩] Merge → Literature Review + PDF Links → Export
```

---

## Chú thích từng bước

---

### Step 0 — Query Intent Router + Research Plan *(MỚI hoàn toàn)*

**Làm gì:**
LLM tự suy luận intent của user input trước khi bất kỳ API call nào được thực hiện. Không dùng classification schema cứng — để LLM thinking tự nhiên và ra quyết định.

```
Input: "hello"
LLM think: đây là greeting → trả lời bình thường → STOP (không search)

Input: "RAG"
LLM think: "RAG" có nhiều sub-domain, không đủ thông tin để search hiệu quả
→ Hỏi: "Bạn muốn nghiên cứu về khía cạnh nào của RAG?
         (a) Kiến trúc và hiệu năng  (b) Đánh giá và benchmark
         (c) Ứng dụng theo domain   (d) RAG vs Fine-tuning"

Input: "RAG optimization techniques"
LLM think: đủ rõ, topic scope medium → generate research plan:
  Sub-queries:
    1. "retrieval augmented generation efficiency latency"       ← Lens: Engineering
    2. "RAG chunking indexing strategies performance"           ← Lens: Implementation
    3. "RAG evaluation benchmark hallucination metrics"         ← Lens: Evaluation
    4. "corrective self-reflective RAG 2024 2025"               ← Lens: Recent advances
    5. "RAG domain-specific medical legal finance"              ← Lens: Application
  Sources: Semantic Scholar + arXiv (CS topic → không cần PubMed)
  Expected scope: ~400-600 papers

→ Hiển thị plan cho user: "Đây là những gì tôi sẽ research. Bạn có muốn thêm/bỏ hướng nào không?"
→ User confirm/edit → proceed to Step ①
```

**Lợi ích so với v1.0.1:**
- v1.0.1: mọi input đều vào search ngay → sai với greeting/concept questions
- v2.0: user thấy "bản đồ" research trước khi pipeline chạy → align expectations sớm

**Lợi ích so với các công cụ khác:**
- **Elicit**: có dialog trước search nhưng không generate research plan
- **Gemini Deep Research**: làm tương tự (generate plan → user confirm) — đây là pattern đúng
- **Perplexity**: không có step này, search thẳng → user không biết tool đang "nghĩ gì"

**Backing research:**
- **ReAct framework** (Yao et al., 2022) — arXiv:2210.03629: LLMs that "reason before acting" outperform rigid pipelines. Step 0 là implementation của Reason step trước Act (search).
- **STORM** (Shao et al., Stanford, 2024) — arXiv:2402.14207: Generate perspectives/questions trước khi search → diverse coverage. Step 0 adapt pattern này cho academic research.

**System prompt cho Step 0:**
```
You are an academic research assistant.

Rules:
- If the user greets you (hello, hi, thanks, etc.): respond naturally, do NOT search.
- If the user asks a conceptual question (what is X, explain Y): answer from knowledge, do NOT search.
- If the research query is too short or ambiguous (< 3 words, broad buzzword): 
  ask for clarification with 3-5 specific interpretations.
- If the research query is clear enough: generate a research plan with:
  * 4-6 sub-queries covering different angles (foundational, recent, evaluation, application, etc.)
  * Recommended sources based on topic domain
  * Estimated scope
  Then ask user to confirm or edit before proceeding.

Output format when generating plan:
{
  "action": "search",
  "sub_queries": ["...", "...", "..."],
  "sources": ["semantic_scholar", "arxiv"],  // or add "openalex", "pubmed"
  "message": "Here is my research plan: ..."
}
```

**API call — NVIDIA NIM (`stream=true` cho SSE):**
```http
POST https://integrate.api.nvidia.com/v1/chat/completions
Authorization: Bearer {LLM_API_KEY}
Content-Type: application/json

{
  "model": "openai/gpt-oss-120b",
  "temperature": 0,
  "stream": true,
  "messages": [
    {"role": "system", "content": "You are an academic research assistant..."},
    {"role": "user", "content": "RAG optimization techniques"}
  ]
}
```

Response SSE (LangGraph `astream_events()` bắt từng token qua `on_chat_model_stream`):
```
data: {"choices":[{"delta":{"content":"Query"},"index":0}]}
data: {"choices":[{"delta":{"content":" đủ"},"index":0}]}
data: [DONE]
```

Response non-stream (`stream=false`, dùng ở steps cần structured JSON output):
```json
{
  "choices": [{"message": {"content": "{\"action\":\"search\",\"sub_queries\":[]}"}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 487, "completion_tokens": 312}
}
```

**Guardrail:** Sub-queries tối đa 6 → tối đa 6 × max_per_source papers initial. User có thể remove sub-queries nếu thấy không liên quan.

**Chi phí Step 0 — `openai/gpt-oss-120b` via NVIDIA NIM:**
```
~500 tokens input + ~500 tokens output
Input:  0.5K × $0.039/1M = $0.00002
Output: 0.5K × $0.180/1M = $0.00009
Tổng:   ~$0.0001/session  ← không đáng kể
```

---

### Step ① — Multi-agent Parallel Search *(CẬP NHẬT LỚN)*

**Làm gì:**
Thay vì 1 query → 1 API call, mỗi sub-query từ Step 0 được gửi đồng thời đến các nguồn phù hợp bởi các search agents chạy song song.

```
Sub-queries từ Step 0:
  Query 1: "retrieval augmented generation efficiency"
  Query 2: "RAG chunking indexing performance"
  Query 3: "RAG evaluation hallucination benchmark"
  Query 4: "corrective self-reflective RAG 2024"
  Query 5: "RAG domain medical legal"

Chạy song song (asyncio.gather):
  Agent 1: S2.search(query_1, n=100) → 100 bài
  Agent 2: S2.search(query_2, n=100) → 98 bài
  Agent 3: S2.search(query_3, n=100) → 100 bài
  Agent 4: arXiv.search(query_4, n=100) → 95 bài  ← recent papers, S2 lag 3-6 tháng
  Agent 5: S2.search(query_5, n=100) + OA.search(query_5, n=50) → 140 bài

Total: ~533 bài trước dedup
Sau dedup: ~400-450 unique bài
```

**Nguồn được hỗ trợ:**

| Source | API | Papers | Specialty | Khi nào dùng |
|---|---|---|---|---|
| **Semantic Scholar** | Có key | 220M | CS/AI, all fields | Luôn luôn |
| **OpenAlex** | Không cần key | 250M | ALL fields, mạnh humanities/social | Topic cross-disciplinary |
| **arXiv** | Free, no key | 2.4M | CS/AI/Physics/Math preprints | Topic CS/AI, cần recency |
| **PubMed** | Free | 35M | Biomedical | Topic medical/health |

**LLM tự chọn nguồn** dựa trên topic domain (từ Step 0 research plan), không hardcode. Ví dụ:
- "RAG optimization" → S2 + arXiv (CS topic)
- "AI in drug discovery" → S2 + PubMed + arXiv
- "AI ethics in hiring" → S2 + OpenAlex (social science angle quan trọng)

**Semantic Scholar — Paper Search:**
```http
GET https://api.semanticscholar.org/graph/v1/paper/search
x-api-key: {SEMANTIC_SCHOLAR_API_KEY}

Query params:
  query=retrieval+augmented+generation+efficiency
  limit=100
  fields=paperId,title,abstract,year,citationCount,externalIds,openAccessPdf
```

Response mẫu:
```json
{
  "total": 4821, "offset": 0,
  "data": [{
    "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
    "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
    "year": 2020, "citationCount": 4821,
    "externalIds": {"ArXiv": "2005.11401", "DOI": "10.18653/v1/2020.findings-emnlp.50"},
    "openAccessPdf": {"url": "https://arxiv.org/pdf/2005.11401", "status": "GREEN"}
  }]
}
```
*`openAccessPdf.status`: `GREEN`/`GOLD` (free) · `BRONZE`/`HYBRID`/`CLOSED` (skip)*

**OpenAlex — không cần API key:**
```http
GET https://api.openalex.org/works
User-Agent: AcademicResearchAgent/2.0 (mailto:user@email.com)

Query params:
  search=retrieval+augmented+generation
  per-page=100
  filter=publication_year:2018-2026
  select=id,doi,title,abstract_inverted_index,publication_year,cited_by_count,primary_location,ids
```

Response mẫu:
```json
{
  "meta": {"count": 12483, "per_page": 100},
  "results": [{
    "doi": "https://doi.org/10.18653/v1/2020.findings-emnlp.50",
    "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
    "publication_year": 2020, "cited_by_count": 4821,
    "ids": {"arxiv": "https://arxiv.org/abs/2005.11401"},
    "primary_location": {"is_oa": true, "pdf_url": "https://arxiv.org/pdf/2005.11401"}
  }]
}
```
*`abstract_inverted_index` cần reconstruct — OpenAlex không trả abstract text trực tiếp:*
```python
def reconstruct_abstract(inv: dict) -> str:
    words = [""] * (max(max(p) for p in inv.values()) + 1)
    for word, positions in inv.items():
        for pos in positions: words[pos] = word
    return " ".join(words)
```

**arXiv — không cần key:**
```http
GET http://export.arxiv.org/api/query
  ?search_query=ti:retrieval+augmented+generation+AND+cat:cs.IR
  &max_results=100&sortBy=relevance&sortOrder=descending
```
*Category codes: `cs.IR` · `cs.CL` · `cs.AI` · `cs.LG`*

Response: Atom XML — parse bằng `arxiv` PyPI client:
```python
import arxiv
client = arxiv.Client()
results = list(client.results(arxiv.Search(
    query="retrieval augmented generation",
    max_results=100, sort_by=arxiv.SortCriterion.Relevance
)))
# result.arxiv_id → "2005.11401"
```

**Rate limits & retry:**

| API | Limit | Strategy |
|---|---|---|
| Semantic Scholar (có key) | 100 req/s | `tenacity` 3 retries, exp backoff 1s→2s→4s |
| OpenAlex | 10 req/s (polite pool) | `asyncio.sleep(0.1)` |
| arXiv | ~3 req/s | `asyncio.sleep(0.35)` |
| NVIDIA NIM | theo plan | retry 2 lần, backoff 2s |

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def s2_search(query: str, **kwargs): ...
```

**System guardrails (LLM không tự vượt qua):**
```python
MAX_PAPERS_TOTAL = 1500       # hard ceiling
MAX_SEARCH_CALLS = 15         # tối đa 15 API calls
MAX_TIME_SECONDS = 300        # 5 phút cho toàn bộ search phase
MIN_SOURCES = 2               # bắt buộc check ít nhất 2 database
```

**Lợi ích so với v1.0.1:**
- v1.0.1: 1 query → 100 bài từ 1 góc nhìn
- v2.0: 5 queries × 2 sources → 400-600 bài từ 5 góc nhìn

**Lợi ích so với công cụ khác:**
- **Elicit**: 1 database (S2), không multi-query
- **Consensus**: 1 database, không multi-source
- **OpenAI Deep Research**: web crawl nhiều nguồn nhưng không có academic-specific databases
- **v2.0**: academic databases + multi-angle queries → tốt hơn cho academic use case

**Backing research:**
- **Query2Doc** (Wang et al., 2023) — arXiv:2303.07678: query expansion bằng LLM generates pseudo-documents → better retrieval. Sub-query generation của Step 0 là variant của technique này.
- **HyDE** (Gao et al., 2022) — arXiv:2212.10496: Hypothetical Document Embeddings — generate hypothetical answer → encode → search. Multi-angle sub-queries là spirit tương tự.
- **LSE Study** (arXiv:2603.20235, 2026): Chỉ 20% overlap giữa bài AI chọn và bài expert chọn với single-query search. Multi-angle search tăng overlap này.
- **OpenAlex** (Priem et al., 2022): "OpenAlex: A fully-open index of the world's research" — 250M works, free API.

---

### Step ①bis — Cross-source Deduplication *(MỚI)*

**Làm gì:**
Merge kết quả từ nhiều sources + nhiều queries → loại bỏ duplicate theo priority key.

```python
def dedup_cross_source(all_papers: list[dict]) -> list[dict]:
    seen = {}
    for paper in all_papers:
        # Priority 1: DOI (universal key, ~70% papers có DOI)
        if doi := paper.get("doi") or paper.get("externalIds", {}).get("DOI"):
            key = f"doi:{doi.lower()}"
        # Priority 2: arXiv ID
        elif arxiv := paper.get("externalIds", {}).get("ArXiv"):
            key = f"arxiv:{arxiv}"
        # Priority 3: Semantic Scholar paperId
        elif pid := paper.get("paperId"):
            key = f"s2:{pid}"
        # Priority 4: Title fuzzy (last resort)
        else:
            key = f"title:{normalize(paper['title'])}"
        
        if key not in seen:
            seen[key] = paper  # giữ paper đầu tiên (S2 có metadata tốt nhất)
    
    return list(seen.values())
```

Kết quả: 400-600 bài raw → ~350-500 unique bài sau dedup.

---

### Step ②bis — Citation Snowballing *(giữ nguyên logic từ v1.0.1, input lớn hơn)*

**Thay đổi so với v1.0.1:**
- Input: từ 100 bài (v1.0.1) → từ **350-500 bài** (v2.0, sau cross-source dedup)
- Seed pool lớn hơn → snowball đa dạng hơn
- Logic dual-pool (Pool A: raw citations + Pool B: citations/year) giữ nguyên

**Kết quả ước tính:** 350-500 bài initial → sau snowball: **600-900 bài**

*(Chi tiết logic snowball: xem SPEC v1.0.1 — unchanged)*

**API calls — Citation Snowballing:**

*Backward (papers citing our seed):*
```http
GET https://api.semanticscholar.org/graph/v1/paper/{paperId}/citations
x-api-key: {SEMANTIC_SCHOLAR_API_KEY}

Query params:
  fields=contexts,intents,isInfluential,citationCount,year,externalIds,openAccessPdf
  limit=100
```

*Forward (papers our seed cites):*
```http
GET https://api.semanticscholar.org/graph/v1/paper/{paperId}/references
x-api-key: {SEMANTIC_SCHOLAR_API_KEY}

Query params:
  fields=contexts,intents,isInfluential,citationCount,year,externalIds,openAccessPdf
  limit=100
```

Response mẫu (citations):
```json
{
  "data": [{
    "contexts": ["As shown in [RAG]..."], "intents": ["methodology"], "isInfluential": true,
    "citingPaper": {
      "paperId": "xyz789...", "title": "Self-RAG: Learning to Retrieve...",
      "year": 2023, "citationCount": 312,
      "externalIds": {"ArXiv": "2310.11511"},
      "openAccessPdf": {"url": "...", "status": "GREEN"}
    }
  }]
}
```
*`isInfluential: true` → Pool A (tier 1 seed). `intents`: `methodology` / `background` / `result`.*

---

### Step ③ — SPECTER v2 Batch Embed → ChromaDB *(không đổi)*

*(Giữ nguyên từ v1.0.1: SPECTER v2 qua Batch API, fallback SPECTER2 adapter proximity local)*

Input giờ lớn hơn: 600-900 bài → cần 2 batch calls (max 500/call).

**API call — S2 Batch Embed:**
```http
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
    "embedding": {"model": "specter_v2@v0.1.1", "vector": [0.2341, -0.1823, 0.7621, ...]},
    "openAccessPdf": {"url": "https://arxiv.org/pdf/2005.11401", "status": "GREEN"}
  },
  {
    "paperId": "abc123...",
    "embedding": null
  }
]
```
*`embedding: null` ~10-15% papers (mới publish, chưa indexed). Fallback: encode abstract bằng `specter_local.py` (SPECTER2 adapter proximity, ~500MB local model).*

---

### Step ④ — MMR Outline + User Approval *(không đổi)*

*(Giữ nguyên từ v1.0.1: MMR-20 từ toàn bộ corpus → LLM → 5-8 themes → user edit + approve)*

Corpus lớn hơn (600-900 bài) → outline đa dạng hơn, bắt được nhiều sub-topics hơn.

**Chi phí Step ④ — `openai/gpt-oss-120b` via NVIDIA NIM:**
```
~100K tokens input (600 abstracts + MMR context + prompt) + ~2K tokens output (outline)
Input:  100K × $0.039/1M = $0.0039
Output:   2K × $0.180/1M = $0.0004
Tổng:   ~$0.004/session
```
*Note: 131K context window của gpt-oss-120b đủ để chứa toàn bộ 600 abstracts ngắn trong 1 call.*

---

### Step ⑤ — Per-theme Hybrid Search *(không đổi)*

*(Giữ nguyên từ v1.0.1: Semantic MMR + BM25 + RRF, chạy song song asyncio.gather)*

---

### Step ⑥ — Parallel Writer Agents *(CẬP NHẬT LỚN)*

**Làm gì:**
Thay vì 1 LLM chạy tuần tự qua từng theme (8 themes × 10s = 80s), mỗi theme được giao cho 1 Writer Agent chạy **đồng thời**.

```
v1.0.1 (sequential):
Theme 1 → LLM call → 10s
Theme 2 → LLM call → 10s  (phải chờ theme 1 xong)
...
Theme 8 → LLM call → 10s
Total: 80s

v2.0 (parallel):
Theme 1 → Writer Agent 1 → 10s ─┐
Theme 2 → Writer Agent 2 → 10s  │
Theme 3 → Writer Agent 3 → 10s  ├─ tất cả hoàn thành lúc ~12s
...                              │
Theme 8 → Writer Agent 8 → 10s ─┘
Total: ~12-15s
```

**Specialization — Writer Agent khác Verifier Agent:**

| | Writer Agent | Verifier Agent |
|---|---|---|
| **Model** | `openai/gpt-oss-120b` (NVIDIA NIM) | `openai/gpt-oss-120b` (NVIDIA NIM) |
| **Temperature** | 0.6-0.7 | 0 (deterministic) |
| **Role** | Synthesize, connect ideas, write fluently | Conservative, skeptical, verify claims |
| **System prompt** | `LITERATURE_REVIEW_SYSTEM_PROMPT` (từ v1.0.1) | Verification prompt (conservative) |
| **Context** | 10 abstracts cho theme của nó ONLY | 1 claim + source text |

**Tại sao cần tách thành 2 loại agent:**
Cùng 1 LLM với cùng 1 system prompt khó làm tốt cả hai vai trò. Writer cần sáng tạo và liên kết ideas; Verifier cần cực kỳ conservative và không được "suy diễn". Conflict về behavior nếu dùng 1 agent.

**Context isolation:**
Mỗi Writer Agent chỉ thấy 10 abstracts của theme nó phụ trách → không bị "ô nhiễm" bởi content của theme khác → mỗi theme độc lập về writing style và focus.

**Implementation (asyncio.gather):**
```python
async def generate_all_themes(themes, papers_per_theme):
    tasks = [
        writer_agent(theme=t, papers=p, model="openai/gpt-oss-120b", temperature=0.7)
        for t, p in zip(themes, papers_per_theme)
    ]
    results = await asyncio.gather(*tasks)  # tất cả chạy đồng thời
    return results
```

**API call — Writer Agent (NVIDIA NIM, `stream=true`):**
```http
POST https://integrate.api.nvidia.com/v1/chat/completions
Authorization: Bearer {LLM_API_KEY}
Content-Type: application/json

{
  "model": "openai/gpt-oss-120b",
  "temperature": 0.7,
  "stream": true,
  "messages": [
    {"role": "system", "content": "{LITERATURE_REVIEW_SYSTEM_PROMPT}"},
    {"role": "user", "content": "Theme: RAG Efficiency\nPapers: [{abstract_1}, {abstract_2}, ...]"}
  ]
}
```

**Lợi ích so với công cụ khác:**
- **Elicit, Consensus**: không có generation step, chỉ summarize per paper
- **AutoSurvey**: 1 LLM sequential, không parallel
- **v2.0**: parallel + specialized writer → nhanh hơn 5-8x, quality tốt hơn vì context isolation

**Chi phí Step ⑥ — `openai/gpt-oss-120b` via NVIDIA NIM:**
```
8 Writer Agents chạy song song, mỗi agent: ~5K input + ~1.5K output
Tổng: 40K input + 12K output
Input:  40K × $0.039/1M = $0.0016
Output: 12K × $0.180/1M = $0.0022
Tổng:   ~$0.004/session
```

---

### Step ⑦ — Claim Extraction + Intent *(không đổi)*

*(Giữ nguyên từ v1.0.1)*

**API call — Claim Extraction (NVIDIA NIM, `stream=false`):**
```http
POST https://integrate.api.nvidia.com/v1/chat/completions
Authorization: Bearer {LLM_API_KEY}
Content-Type: application/json

{
  "model": "openai/gpt-oss-120b",
  "temperature": 0,
  "stream": false,
  "messages": [
    {"role": "system", "content": "Extract verifiable claims. Output JSON array with fields: claim, source_paperId, intent (Supports|Contradicts|Extends)."},
    {"role": "user", "content": "[theme section text — all 8 themes concatenated]"}
  ]
}
```

Response:
```json
{
  "choices": [{"message": {"content": "[{\"claim\":\"RAG reduces hallucination by grounding responses\",\"source_paperId\":\"649def...\",\"intent\":\"Supports\"}]"}}],
  "usage": {"prompt_tokens": 15000, "completion_tokens": 20000}
}
```

**Chi phí Step ⑦ — `openai/gpt-oss-120b` via NVIDIA NIM:**
```
Extract claims từ 8 theme sections + classify intent (Supports / Contradicts / Extends):
~15K tokens input + ~20K tokens output (200 claims với metadata)
Input:  15K × $0.039/1M = $0.0006
Output: 20K × $0.180/1M = $0.0036
Tổng:   ~$0.004/session
```

---

### Step ⑧ — Parallel Verifier Agents *(CẬP NHẬT LỚN)*

**Làm gì:**
Verification là step tốn thời gian nhất: mỗi claim cần 1 LLM call để verify. Với 200 claims × 2s = 400s nếu sequential. V2.0 batch verification song song.

```
v1.0.1 (sequential):
Claim 1 → verify → 2s
Claim 2 → verify → 2s
...
Claim 200 → verify → 2s
Total: 400s ≈ 6.7 phút

v2.0 (parallel batches):
Batch 1 (claim 1-20)  → Verifier Agent 1 → 5s ─┐
Batch 2 (claim 21-40) → Verifier Agent 2 → 5s   │
...                                               ├─ xong trong ~15-20s
Batch 10 (181-200)    → Verifier Agent 10 → 5s ─┘
Total: ~20s (20x faster)
```

**Verifier Agent đặc điểm:**
- **Model**: `openai/gpt-oss-120b` — MoE architecture (5.1B active params) → cost tương đương small model, không cần đổi model riêng cho verification.
- **Temperature = 0**: deterministic, không random. Conservative "Uncertain" tốt hơn creative "Supported" sai.
- **Prompt**: y hệt v1.0.1 (3-tier: snippet → arXiv → abstract conservative)

**API calls — 3-tier Verification:**

**Case A — S2 Snippet Search (coverage ~30% papers):**
```http
GET https://api.semanticscholar.org/graph/v1/snippet/search
x-api-key: {SEMANTIC_SCHOLAR_API_KEY}

Query params:
  query=RAG+reduces+hallucination+by+grounding+in+retrieved+documents
  paperId=649def34f8be52c8b66281af98ae884c09aef38b
```

Response:
```json
{"snippets": [{"text": "...RAG significantly reduces hallucination...", "section": "Abstract", "score": 0.92}]}
```
*Rỗng → Case B*

**Case B — ar5iv Full Text (~70% arXiv papers có HTML):**
```http
GET https://ar5iv.labs.arxiv.org/html/{arxiv_id}
# Timeout 15s. Parse BeautifulSoup, strip nav/header/footer, lấy 10k chars.
```

```python
soup = BeautifulSoup(resp.text, "html.parser")
for tag in soup(["nav", "header", "footer", "script", "style"]): tag.decompose()
text = soup.get_text(separator=" ", strip=True)[:10000]
```
*Lỗi hoặc không có arxiv_id → Case C (abstract conservative)*

**NVIDIA NIM Verifier call (`stream=false`, `temperature=0`):**
```http
POST https://integrate.api.nvidia.com/v1/chat/completions
Authorization: Bearer {LLM_API_KEY}
Content-Type: application/json

{
  "model": "openai/gpt-oss-120b",
  "temperature": 0,
  "stream": false,
  "messages": [
    {"role": "system", "content": "You are a conservative scientific claim verifier. Output JSON: {verdict, confidence, evidence}."},
    {"role": "user", "content": "Claim: RAG reduces hallucination by 65%\nSource text: [snippet or abstract text]"}
  ]
}
```

Response:
```json
{"choices": [{"message": {"content": "{\"verdict\":\"Supported\",\"confidence\":0.92,\"evidence\":\"...RAG significantly reduces hallucination...\"}"}}]}
```

**Chi phí Step ⑧ — `openai/gpt-oss-120b` via NVIDIA NIM:**
```
200 verifications: mỗi verification ~600 tokens input + ~50 tokens output
Tổng: ~120K input + ~10K output

Input:  120K × $0.039/1M = $0.0047
Output:  10K × $0.180/1M = $0.0018
Tổng:   ~$0.007/session

So sánh với mô hình cũ trong SPEC v1.0.1:
  200 claims × Claude Sonnet:  $0.60  (85x đắt hơn)
  200 claims × Claude Haiku:   $0.05  (7x đắt hơn)

→ gpt-oss-120b là MoE: chỉ activate 5.1B/116.8B params mỗi inference
  → inference cost tương đương small model nhưng knowledge của 120B model
```

**Backing research:**
- **LLM Cascade** (Dohan et al., 2022): route simple tasks to small models, complex tasks to big models. Verification = structured classification = simple task → small model sufficient.
- **RouteLLM** (Ong et al., 2024) — arXiv:2406.18665: routing framework shows 40-70% cost reduction without quality loss for classification tasks.

---

### Step ⑨ — Routing + Human Review *(không đổi)*

*(Giữ nguyên từ v1.0.1: 5 routing categories, Contrasting intent priority queue)*

---

### Step ⑩ — Merge + Export *(CẬP NHẬT: output → LaTeX .tex + .bib)*

**Làm gì:**
LLM tạo INTRODUCTION + CONCLUSION từ toàn bộ 8 theme sections. `latex_exporter.py` wrap nội dung vào Jinja2 template → xuất 2 files:
- `literature_review.tex` — full LaTeX document, compile trực tiếp bằng `pdflatex`
- `references.bib` — BibTeX entries cho tất cả cited papers

**Output format:**
```latex
\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{natbib}
\usepackage{hyperref}
\usepackage{amsmath}

\title{Literature Review: {query}}
\author{Academic Research Assistant v2.0}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
{introduction_text}
\end{abstract}

\section{Introduction}
{introduction_text}

\section{Theme 1: RAG Efficiency}
{theme_1_content}

% ... 7 more \section{} ...

\section{Conclusion}
{conclusion_text}

\bibliographystyle{apalike}
\bibliography{references}
\end{document}
```

`references.bib` (generated từ `cited_papers`):
```bibtex
@article{lewis2020rag,
  title     = {Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks},
  author    = {Lewis, Patrick and others},
  year      = {2020},
  url       = {https://arxiv.org/abs/2005.11401}
}
```

**API call — Intro + Conclusion (NVIDIA NIM, `stream=true`):**
```http
POST https://integrate.api.nvidia.com/v1/chat/completions
Authorization: Bearer {LLM_API_KEY}
Content-Type: application/json

{
  "model": "openai/gpt-oss-120b",
  "temperature": 0.7,
  "stream": true,
  "messages": [
    {
      "role": "system",
      "content": "Write an INTRODUCTION and CONCLUSION for a literature review. Use \\cite{key} syntax for citations. Output plain text only — LaTeX wrapping is handled by the exporter."
    },
    {"role": "user", "content": "Themes:\n1. RAG Efficiency: ...\n[8 themes total]\nCited papers: [bibtex keys]"}
  ]
}
```

**Chi phí Step ⑩ — `openai/gpt-oss-120b` via NVIDIA NIM:**
```
INTRODUCTION + CONCLUSION từ toàn bộ 8 theme sections:
~15K tokens input + ~2K tokens output
Input:  15K × $0.039/1M = $0.0006
Output:  2K × $0.180/1M = $0.0004
Tổng:   ~$0.001/session
```

---

## Kiến trúc tổng thể v2.0

```
┌─────────────────────────────────────────────────────┐
│              ORCHESTRATOR (LLM)                     │
│  • Manages workflow Step 0 → ⑩                     │
│  • Enforces system guardrails                       │
│  • Routes to specialized agents                     │
└──────────────┬──────────────────────────────────────┘
               │
    ┌──────────┼──────────────────────────┐
    ▼          ▼                          ▼
┌────────┐ ┌──────────────────────┐ ┌───────────────────┐
│ Search │ │  Writer Agents (×N)  │ │  Verifier         │
│ Agents │ │  (per theme,         │ │  Agents (×M)      │
│ (×5)   │ │   parallel)          │ │  (per batch,      │
│        │ │  Model: gpt-oss-120b │ │   parallel)       │
│ S2     │ │  Temp: 0.7           │ │  Model: gpt-oss-120b
│ OA     │ │                      │ │  Temp: 0          │
│ arXiv  │ └──────────────────────┘ └───────────────────┘
└────────┘
```

**Model routing summary — v2.0 dùng `openai/gpt-oss-120b` (NVIDIA NIM):**

| Task | Model | Temperature | Lý do |
|---|---|---|---|
| Step 0: Intent + Plan | `openai/gpt-oss-120b` | 0 | Cần reasoning + structured JSON output |
| Step ④: Outline gen | `openai/gpt-oss-120b` | 0.7 | 131K context đủ chứa 600 abstracts |
| Step ⑥: Writing | `openai/gpt-oss-120b` | 0.7 | Fluency + synthesis, chain-of-thought |
| Step ⑦: Claim extract | `openai/gpt-oss-120b` | 0 | Structured parsing, JSON output |
| Step ⑧: Verification | `openai/gpt-oss-120b` | 0 | Classification task, deterministic |
| Step ⑩: Intro/Conclusion | `openai/gpt-oss-120b` | 0.7 | Coherence toàn bài |

**Tại sao 1 model cho tất cả tasks khả thi với gpt-oss-120b:**
- Behavioral conflict (Writer vs Verifier) được giải quyết bởi **system prompt khác nhau** + **temperature khác nhau**, không phụ thuộc vào model size
- MoE architecture: 5.1B active params/token → inference cost thấp, đủ dùng cho cả classification lẫn synthesis
- 131K context window: đủ cho Step ④ (600 abstracts) mà không cần chunking phức tạp

---

## System Guardrails (v2.0)

```python
SYSTEM_GUARDRAILS = {
    # Search guardrails
    "max_sub_queries": 6,            # tối đa 6 sub-queries từ Step 0
    "max_papers_per_source": 200,    # tối đa 200 bài/query/source
    "max_papers_total": 1500,        # hard ceiling toàn bộ
    "max_search_calls": 15,          # tối đa 15 API calls search
    "max_search_time_s": 300,        # 5 phút cho search phase
    "min_sources_required": 2,       # phải check ít nhất 2 database
    
    # Agent guardrails
    "max_writer_agents": 8,          # = số themes tối đa
    "max_verifier_agents": 20,       # 20 batch parallel verification
    "verifier_batch_size": 10,       # 10 claims/batch
    
    # Quality guardrails
    "writer_temperature": 0.7,       # không quá creative
    "verifier_temperature": 0,       # deterministic
    "query_gen_temperature": 0,      # reproducible sub-queries
}
```

---

## Chi phí ước tính toàn pipeline v2.0

**Model:** `openai/gpt-oss-120b` — NVIDIA NIM (`https://integrate.api.nvidia.com/v1`)
**Kiến trúc:** Mixture-of-Experts, 116.8B total / 5.1B active params, 128 experts, 131K context
**Pricing tham chiếu:** OpenRouter — $0.039/1M input · $0.180/1M output

> NVIDIA NIM pricing chưa có public pricing page. Dùng OpenRouter làm baseline tham chiếu.
> Nguồn pricing: [openrouter.ai/openai/gpt-oss-120b](https://openrouter.ai/openai/gpt-oss-120b)

### Breakdown per step — 1 research session (600 papers, 8 themes, 200 claims)

| Step | Task | Input tokens | Output tokens | Chi phí |
|---|---|---|---|---|
| **Step 0** | Intent Router + Research Plan | ~500 | ~500 | **~$0.0001** |
| **Step ④** | MMR Outline (600 abstracts → 8 themes) | ~100K | ~2K | **~$0.004** |
| **Step ⑥** | 8 Writer Agents (parallel) | ~40K | ~12K | **~$0.004** |
| **Step ⑦** | Claim Extraction (200 claims) | ~15K | ~20K | **~$0.004** |
| **Step ⑧** | 200 Verifier Agents (parallel) | ~120K | ~10K | **~$0.007** |
| **Step ⑩** | Intro + Conclusion | ~15K | ~2K | **~$0.001** |
| **TOTAL** | | **~290K** | **~47K** | **~$0.020/session** |

*Steps ①, ①bis, ②bis, ③, ⑤, ⑨: không dùng LLM (API calls miễn phí hoặc embedding)*

### So sánh chi phí với phương án gốc (SPEC v1.0.1 với Claude)

| | SPEC v1.0.1 (Claude) | v2.0 (gpt-oss-120b) |
|---|---|---|
| **Step ⑧ Verification** | ~$0.05–$0.60/session | ~$0.007/session |
| **Tổng/session** | ~$1–2/session (ước tính) | **~$0.020/session** |
| **100 sessions/tháng** | ~$100–200/tháng | **~$2/tháng** |

### Tại sao gpt-oss-120b rẻ hơn kỳ vọng

gpt-oss-120b là **Mixture-of-Experts (MoE)**: mỗi token chỉ activate 4/128 experts → chỉ 5.1B params chạy thực tế. Pricing theo số token processed, không theo model size → cost tương đương small model (8B dense) nhưng knowledge + quality của 120B model.

**Nguồn kỹ thuật:**
- NVIDIA Technical Blog: [Delivering 1.5M TPS on GB200 NVL72](https://developer.nvidia.com/blog/delivering-1-5-m-tps-inference-on-nvidia-gb200-nvl72-nvidia-accelerates-openai-gpt-oss-models-from-cloud-to-edge/)
- Model card: [build.nvidia.com/openai/gpt-oss-120b/deploy](https://build.nvidia.com/openai/gpt-oss-120b/deploy)
- NGC Catalog: [catalog.ngc.nvidia.com — gpt-oss-20b](https://catalog.ngc.nvidia.com/orgs/nim/teams/openai/containers/gpt-oss-20b)
- OpenRouter pricing: [openrouter.ai/openai/gpt-oss-120b](https://openrouter.ai/openai/gpt-oss-120b)
- PricePerToken: [pricepertoken.com — gpt-oss-120b](https://pricepertoken.com/pricing-page/model/openai-gpt-oss-120b)

---

## CHANGELOG

### v2.0 — so với v1.0.1

| Thay đổi | v1.0.1 | v2.0 | Lý do |
|---|---|---|---|
| **Step 0 (MỚI)** | Không có | Intent Router + Research Plan | Mọi input kể cả "hello" bị search; user không có cơ hội redirect sớm |
| **Multi-query search** | 1 query → 100 bài | N sub-queries (LLM-generated) → 400-600 bài | 1 angle bỏ sót papers nhìn từ góc khác |
| **Multi-source search** | Semantic Scholar only | S2 + OpenAlex + arXiv (+ PubMed nếu bio) | S2 mạnh CS/AI nhưng yếu cross-disciplinary và recency |
| **Cross-source dedup** | Không có (1 source) | DOI → arXiv ID → title fuzzy | Cần khi merge nhiều sources |
| **Corpus size (initial)** | 100 bài | 400-600 bài | 100 bài từ 1 query không đủ là "deep research" |
| **Corpus size (post-snowball)** | ~300-400 bài | **600-900 bài** | Input lớn hơn → snowball lớn hơn |
| **Writer agents** | 1 LLM sequential | N Writer Agents parallel | 8 themes × 10s = 80s sequential → 12s parallel |
| **Verifier agents** | 1 LLM sequential | M Verifier Agents parallel (gpt-oss-120b, temp=0) | 200 claims × 2s = 400s → 20s; MoE cost = small model |
| **Model routing** | 1 model cho tất cả | 1 model (`gpt-oss-120b`) + nhiều system prompt + temperature khác nhau | MoE architecture đủ cho mọi task; behavior tách bằng prompt |
| **Agent specialization** | 1 system prompt | Writer prompt (temp=0.7) ≠ Verifier prompt (temp=0) | Conflict behavior giải quyết bằng prompt, không cần 2 model |
| **Research plan approval** | Không có | User confirm sub-queries trước search | Early error catching trước khi tốn 3-5 phút |
| **Export format** | Markdown `.md` | **LaTeX `.tex` + BibTeX `.bib`** | Researcher cần file compile được luôn với `pdflatex` |

### Những gì KHÔNG thay đổi từ v1.0.1

- Dual-pool snowball (Pool A: raw citations + Pool B: citations/year)
- SPECTER v2 Batch API (document embedding) + SPECTER2 adapter proximity (query embedding)
- ChromaDB storage + metadata schema
- MMR-20 for outline generation (Step ④) + user approval
- Per-theme hybrid search: Semantic MMR + BM25 + RRF (Step ⑤)
- 3-tier verification: snippet → arXiv → abstract conservative (Step ⑧ logic)
- Citation intent routing: Contrasting → priority human review queue (Step ⑨)
- Literature Review format: INTRODUCTION + BODY + CONCLUSION (Step ⑩)
- PDF Links Section với priority URL logic (Step ⑩)
- `LITERATURE_REVIEW_SYSTEM_PROMPT` (unchanged)

### Identified Gaps — Defer post-v2.0

1. **2-hop snowballing**: Chỉ 1 hop từ seed. 2-hop tăng recall nhưng tăng corpus 3-5x và latency đáng kể → cần data từ v2.0 MVP để quyết định.
2. **Co-citation + bibliographic coupling**: OpenAlex `related_works` đã có sẵn từ v2.0 (multi-source), nhưng chưa được dùng. Implement cross-join references lists → defer v2.1.
3. **Saturation detection**: Hiện tại dùng hard ceiling. Embedding-based saturation detection (cosine similarity new papers vs corpus centroid) → defer v2.1.
4. **Adaptive follow-up search**: Sau khi xem initial results, LLM có thể request thêm 1-2 targeted searches cho sub-topics thiếu. Trong guardrails → defer v2.1.
5. **Research gap identification**: Structured gap analysis từ cross-theme comparison → listed as Non-goal, defer post-MVP.
