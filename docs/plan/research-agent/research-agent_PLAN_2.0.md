# PLAN_2.0.md — Academic Research Assistant

> Derived from SPEC_2.0.md | MVP: Full Flow Step 0→⑩ | Env: Local Development
> Changelog từ PLAN v1.0.1: Xem mục [CHANGELOG](#changelog) cuối file

---

## 1. Tech Stack

| Layer | Technology | Thay đổi so với v1.0.1 |
|---|---|---|
| **Backend** | FastAPI (Python 3.11+) | Không đổi |
| **Pipeline Orchestration** | **LangGraph** | **MỚI** — thay thế frontend-driven multi-endpoint |
| **Streaming** | SSE via FastAPI `StreamingResponse` + LangGraph `astream_events()` | **MỚI** — real-time LLM thinking visible to user |
| **LLM** | `openai/gpt-oss-120b` via NVIDIA NIM (`https://integrate.api.nvidia.com/v1`) | **CẬP NHẬT** — 1 model, nhiều system prompt + temperature |
| **LLM Client** | `langchain-openai` `ChatOpenAI` (OpenAI-compatible base_url) | **CẬP NHẬT** — từ custom `llm_client.py` |
| **Vector DB** | ChromaDB (local persistent) | Không đổi |
| **Embedding — Document** | SPECTER v2 qua Semantic Scholar Batch API | Không đổi |
| **Embedding — Query** | `allenai/specter2` adapter `proximity` (local ~500MB) | Không đổi |
| **BM25** | `rank_bm25` | Không đổi |
| **MMR** | Custom `mmr.py` | Không đổi |
| **Academic Search** | `semanticscholar` (PyPI) + `arxiv` (PyPI) + `httpx` (OpenAlex REST) | **MỚI** — thêm OpenAlex + arXiv search |
| **arXiv full text** | `ar5iv.labs.arxiv.org` HTML + BeautifulSoup | Không đổi |
| **Dedup** | `rapidfuzz` (title fuzzy matching) | **MỚI** |
| **Retry** | `tenacity` (exponential backoff) | **MỚI** |
| **LaTeX export** | `jinja2` template → `literature_review.tex` + `references.bib` | **MỚI** — thay Markdown output |
| **Package manager** | `pyproject.toml` (uv) | **CẬP NHẬT** — thay `requirements.txt` |
| **Frontend** | React.js + TailwindCSS + Iconify | Không đổi |
| **LaTeX viewer** | `LaTeXViewer.tsx` — syntax highlight + Download .tex/.bib buttons | **MỚI** — thay `ReviewEditor.tsx` (react-markdown) |
| **Deployment (MVP)** | Local only | Không đổi |

---

## 2. Environment Variables

```env
# LLM — NVIDIA NIM (OpenAI-compatible)
LLM_MODEL="openai/gpt-oss-120b"
LLM_BASE_URL="https://integrate.api.nvidia.com/v1"
LLM_API_KEY=""                         # NVIDIA NIM API key

# Temperature per role (1 model, 4 behaviors — sync với SPEC model routing table)
INTENT_TEMPERATURE=0                   # Step 0: reproducible JSON output
OUTLINE_TEMPERATURE=0.7                # Step ④: diverse theme suggestions
WRITER_TEMPERATURE=0.7                 # Step ⑥: fluent synthesis
CLAIM_TEMPERATURE=0                    # Step ⑦: structured JSON parsing
VERIFIER_TEMPERATURE=0                 # Step ⑧: deterministic classification
EXPORT_TEMPERATURE=0.7                 # Step ⑩: cohesive intro/conclusion

# Semantic Scholar
SEMANTIC_SCHOLAR_API_KEY=""            # Key đã có

# SPECTER2 Adapter (local, cho query encoding)
SPECTER2_MODEL_PATH="allenai/specter2_base"
SPECTER2_ADAPTER="allenai/specter2"

# ChromaDB
CHROMA_PERSIST_PATH="./data/chroma"

# LangGraph Checkpointer (local SQLite)
LANGGRAPH_CHECKPOINT_DB="./data/checkpoints.db"

# App
CORS_ORIGINS="http://localhost:3000"

# Snowballing config (giữ từ v1.0.1)
SNOWBALL_POOL_SIZE=5
SNOWBALL_FORWARD_YEAR_WINDOW=4
SNOWBALL_BACKWARD_RECENT=2
SNOWBALL_BACKWARD_MID=5

# MMR config (giữ từ v1.0.1)
MMR_LAMBDA=0.5
MMR_PREFETCH_OUTLINE=150
MMR_PREFETCH_THEME=50

# Search guardrails (từ SPEC 2.0)
MAX_SUB_QUERIES=6
MAX_PAPERS_PER_SOURCE=200
MAX_PAPERS_TOTAL=1500
MAX_SEARCH_CALLS=15

# OpenAlex (không cần key, chỉ cần User-Agent)
OPENALEX_EMAIL="user@email.com"        # dùng trong User-Agent header

# LaTeX export
LATEX_OUTPUT_DIR="./data/output"       # {LATEX_OUTPUT_DIR}/{thread_id}/literature_review.tex
```

---

## 3. LangGraph State & Graph

### ResearchState

```python
# graph/state.py
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages

class ResearchState(TypedDict):
    # ── Input ──
    query: str
    thread_id: str

    # ── Step 0: Intent Router ──
    intent: Literal["greeting", "clarify", "search"]
    clarify_questions: list[str] | None       # nếu intent == "clarify"
    sub_queries: list[str] | None             # nếu intent == "search"
    sources: list[str] | None                 # ["semantic_scholar", "arxiv", ...]
    research_plan_approved: bool

    # ── Step ①: Search ──
    raw_papers: list[dict]                    # ~400-600 bài trước dedup

    # ── Step ①bis: Dedup ──
    unique_papers: list[dict]                 # ~350-500 bài sau dedup

    # ── Step ②bis: Snowball ──
    snowballed_papers: list[dict]             # ~600-900 bài

    # ── Step ③: Embed ──
    embedded_paper_ids: list[str]

    # ── Step ④: Outline ──
    draft_outline: list[dict]                 # [{name, description}] — LLM generated
    approved_outline: list[dict]              # user edited + approved

    # ── Step ⑤: Hybrid Search ──
    papers_per_theme: dict[str, list[dict]]   # {theme_name: [top-10 papers]}

    # ── Step ⑥: Writing ──
    theme_contents: dict[str, str]            # {theme_name: markdown content}

    # ── Step ⑦: Claims ──
    claims: list[dict]

    # ── Step ⑧: Verification ──
    verified_claims: list[dict]

    # ── Step ⑨: Routing ──
    routed_claims: dict                       # {include, remove, human_review, ...}
    human_reviewed_claims: list[dict]         # sau khi user approve/reject

    # ── Step ⑩: Export ──
    literature_review: str                    # final markdown
    cited_papers: list[dict]

    # ── Metadata ──
    messages: Annotated[list, add_messages]   # conversation history (Step 0)
    error: str | None
```

### Graph Definition

```python
# graph/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt
from graph.state import ResearchState
from graph.nodes import *

def build_graph():
    g = StateGraph(ResearchState)

    # ── Nodes ──
    g.add_node("intent_router",   intent_router_node)    # Step 0
    g.add_node("parallel_search", parallel_search_node)  # Step ①
    g.add_node("dedup",           dedup_node)             # Step ①bis
    g.add_node("snowball",        snowball_node)          # Step ②bis
    g.add_node("embed",           embed_node)             # Step ③
    g.add_node("outline_gen",     outline_gen_node)       # Step ④ (có interrupt)
    g.add_node("hybrid_search",   hybrid_search_node)    # Step ⑤
    g.add_node("write_themes",    write_themes_node)      # Step ⑥
    g.add_node("extract_claims",  extract_claims_node)   # Step ⑦
    g.add_node("verify_claims",   verify_claims_node)    # Step ⑧
    g.add_node("route_claims",    route_claims_node)      # Step ⑨ (có interrupt)
    g.add_node("export",          export_node)            # Step ⑩

    # ── Edges ──
    g.set_entry_point("intent_router")

    # Conditional: intent router output
    g.add_conditional_edges("intent_router", route_after_intent, {
        "clarify": END,            # graph dừng, trả câu hỏi cho user
        "greeting": END,           # graph dừng, đã trả lời tự nhiên
        "search": "parallel_search",
    })

    # Linear pipeline
    g.add_edge("parallel_search", "dedup")
    g.add_edge("dedup",           "snowball")
    g.add_edge("snowball",        "embed")
    g.add_edge("embed",           "outline_gen")
    # outline_gen có interrupt() → sau resume tiếp tục hybrid_search
    g.add_edge("outline_gen",     "hybrid_search")
    g.add_edge("hybrid_search",   "write_themes")
    g.add_edge("write_themes",    "extract_claims")
    g.add_edge("extract_claims",  "verify_claims")
    g.add_edge("verify_claims",   "route_claims")
    # route_claims có interrupt() → sau resume tiếp tục export
    g.add_edge("route_claims",    "export")
    g.add_edge("export",          END)

    # Checkpointer (SQLite local)
    memory = SqliteSaver.from_conn_string(LANGGRAPH_CHECKPOINT_DB)
    return g.compile(checkpointer=memory, interrupt_before=["outline_gen", "route_claims"])
```

---

## 4. SSE Event Protocol

Frontend nhận events qua `text/event-stream`. Schema chuẩn:

```typescript
// frontend/src/types/events.ts
type SSEEvent =
  | { type: "step_start";  node: string; label: string }
  | { type: "step_done";   node: string; stats?: Record<string, unknown> }
  | { type: "llm_token";   content: string }                    // token streaming
  | { type: "search_start"; source: string; query: string }
  | { type: "search_done";  source: string; count: number }
  | { type: "interrupt";    interrupt_type: "outline_approval" | "claim_review"; data: unknown }
  | { type: "error";        message: string }
  | { type: "done" }
```

**Ví dụ stream khi user gõ "RAG":**

```
data: {"type":"step_start","node":"intent_router","label":"Phân tích query..."}

data: {"type":"llm_token","content":"Query "}
data: {"type":"llm_token","content":"'RAG' "}
data: {"type":"llm_token","content":"quá ngắn, "}
data: {"type":"llm_token","content":"cần làm rõ hướng..."}

data: {"type":"step_done","node":"intent_router"}
data: {"type":"done"}
```

**Ví dụ stream khi user gõ "RAG optimization techniques":**

```
data: {"type":"step_start","node":"intent_router","label":"Phân tích query..."}
data: {"type":"llm_token","content":"Query đủ rõ, tạo research plan..."}
data: {"type":"step_done","node":"intent_router","stats":{"sub_queries":5,"sources":["s2","arxiv"]}}

data: {"type":"step_start","node":"parallel_search","label":"Tìm kiếm papers..."}
data: {"type":"search_start","source":"semantic_scholar","query":"RAG efficiency latency"}
data: {"type":"search_start","source":"arxiv","query":"corrective self-reflective RAG 2025"}
data: {"type":"search_done","source":"semantic_scholar","count":100}
data: {"type":"search_done","source":"arxiv","count":95}
data: {"type":"step_done","node":"parallel_search","stats":{"total_raw":533}}

data: {"type":"step_start","node":"dedup","label":"Loại bỏ trùng lặp..."}
data: {"type":"step_done","node":"dedup","stats":{"unique":421}}

...

data: {"type":"interrupt","interrupt_type":"outline_approval","data":{"outline":[...]}}
```

---

## 5. Project Structure

```
academic_research/
├── backend/
│   ├── main.py                              # FastAPI entry + router mount
│   ├── config.py                            # Load .env, constants, ChatOpenAI init
│   │
│   └── module/
│       ├── __init__.py
│       │
│       ├── research_agent/                  # ── Core module ──
│       │   ├── __init__.py
│       │   │
│       │   ├── graph/                       # LangGraph pipeline [MỚI]
│       │   │   ├── __init__.py
│       │   │   ├── state.py                 # ResearchState TypedDict
│       │   │   ├── graph.py                 # build_graph() → compiled StateGraph
│       │   │   └── nodes/
│       │   │       ├── __init__.py
│       │   │       ├── intent_router.py     # Step 0  [MỚI]
│       │   │       ├── parallel_search.py   # Step ①  [MỚI]
│       │   │       ├── dedup.py             # Step ①bis [MỚI]
│       │   │       ├── snowball.py          # Step ②bis [wrap service]
│       │   │       ├── embed.py             # Step ③  [wrap service]
│       │   │       ├── outline_gen.py       # Step ④  + interrupt() [MỚI]
│       │   │       ├── hybrid_search.py     # Step ⑤  [wrap service]
│       │   │       ├── write_themes.py      # Step ⑥  parallel [MỚI]
│       │   │       ├── extract_claims.py    # Step ⑦  [wrap service]
│       │   │       ├── verify_claims.py     # Step ⑧  parallel [MỚI]
│       │   │       ├── route_claims.py      # Step ⑨  + interrupt() [MỚI]
│       │   │       └── export.py            # Step ⑩  → .tex + .bib [MỚI]
│       │   │
│       │   ├── services/                    # Business logic
│       │   │   ├── __init__.py
│       │   │   ├── semantic_scholar.py      # [giữ] S2 search + batch embed
│       │   │   ├── openalex.py              # [MỚI] OpenAlex REST search
│       │   │   ├── arxiv_search.py          # [MỚI] arXiv keyword search
│       │   │   ├── specter_batch.py         # [giữ] SPECTER v2 Batch API
│       │   │   ├── specter_local.py         # [giữ] SPECTER2 adapter proximity
│       │   │   ├── arxiv_fetcher.py         # [giữ] ar5iv HTML full text
│       │   │   ├── vector_store.py          # [giữ] ChromaDB operations
│       │   │   ├── mmr.py                   # [giữ] Maximal Marginal Relevance
│       │   │   ├── bm25_search.py           # [giữ] rank_bm25 wrapper
│       │   │   ├── rrf_merge.py             # [giữ] Reciprocal Rank Fusion
│       │   │   ├── snowball_logic.py        # [giữ] Dual-pool seed selection
│       │   │   ├── citation_verifier.py     # [giữ] 3-tier verify pipeline
│       │   │   ├── latex_exporter.py        # [MỚI] Jinja2 → .tex + .bib
│       │   │   └── dedup_utils.py           # [MỚI] rapidfuzz title fuzzy
│       │   │
│       │   ├── api/
│       │   │   ├── __init__.py
│       │   │   ├── research.py              # POST /api/research/stream → SSE
│       │   │   ├── resume.py                # POST /api/research/resume
│       │   │   └── export.py                # GET  /api/review/export → .tex/.bib
│       │   │
│       │   └── models/
│       │       ├── __init__.py
│       │       ├── paper.py                 # [giữ + source: s2|openalex|arxiv]
│       │       ├── claim.py                 # [giữ]
│       │       ├── outline.py               # [giữ]
│       │       └── review.py                # [giữ]
│       │
│       └── gap_detection/                   # placeholder — phát triển sau
│           └── __init__.py
│
├── frontend/
│   └── app/
│       ├── src/
│       │   ├── components/
│       │   │   ├── SearchBar.tsx            # [giữ]
│       │   │   ├── StreamingPanel.tsx       # [MỚI] SSE event timeline
│       │   │   ├── LLMThinking.tsx          # [MỚI] token stream
│       │   │   ├── ResearchPlan.tsx         # [MỚI] sub-queries edit + confirm
│       │   │   ├── ThemeOutline.tsx         # [giữ] editable + approvable
│       │   │   ├── LaTeXViewer.tsx          # [MỚI] .tex syntax highlight + Download
│       │   │   ├── ClaimVerifier.tsx        # [giữ] priority queue + approve/reject
│       │   │   └── PDFLinksSection.tsx      # [giữ]
│       │   ├── hooks/
│       │   │   └── useSSEStream.ts          # [MỚI] EventSource hook
│       │   ├── pages/
│       │   │   ├── Home.tsx
│       │   │   └── Review.tsx
│       │   └── App.tsx
│       ├── tailwind.config.js
│       └── package.json
│
├── data/
│   ├── chroma/                              # ChromaDB persistent storage
│   ├── checkpoints.db                       # LangGraph SQLite checkpointer
│   └── output/                             # .tex + .bib files per session
│       └── {thread_id}/
│           ├── literature_review.tex
│           └── references.bib
│
├── templates/
│   └── literature_review.tex.j2            # Jinja2 LaTeX template
│
├── .env.example                             # template env — không commit .env thật
└── pyproject.toml                           # uv package manager
```

**Import path với structure mới:**
```python
# backend/main.py
from module.research_agent.api.research import router as research_router
from module.research_agent.graph.graph import build_graph
```

**`module/research_agent/` là Python package** → dùng underscore (không dùng hyphen).
`gap_detection/` chỉ có `__init__.py` placeholder, không implement ở v2.0 MVP.

---

## 6. API Endpoints

| Method | Path | Mô tả | So với v1.0.1 |
|---|---|---|---|
| `POST` | `/api/research/stream` | Start session → SSE stream Step 0→⑩ | **MỚI** — thay thế toàn bộ 8 endpoints cũ |
| `POST` | `/api/research/resume` | Resume sau interrupt (outline / claims) | **MỚI** |
| `GET`  | `/api/review/export` | Export literature review hoàn chỉnh | Giữ nguyên |

### POST /api/research/stream

```python
# api/research.py
@app.post("/api/research/stream")
async def research_stream(body: ResearchRequest):
    """
    Body: {query: str, thread_id: str}
    Response: text/event-stream
    """
    async def event_gen():
        config = {"configurable": {"thread_id": body.thread_id}}
        async for event in graph.astream_events(
            {"query": body.query, "thread_id": body.thread_id},
            config=config,
            version="v2",
        ):
            match event["event"]:
                case "on_chain_start" if event["name"] in NODE_LABELS:
                    payload = {"type": "step_start", "node": event["name"],
                               "label": NODE_LABELS[event["name"]]}
                    yield f"data: {json.dumps(payload)}\n\n"

                case "on_chat_model_stream":
                    token = event["data"]["chunk"].content
                    if token:
                        yield f"data: {json.dumps({'type':'llm_token','content':token})}\n\n"

                case "on_chain_end" if event["name"] in NODE_LABELS:
                    payload = {"type": "step_done", "node": event["name"],
                               "stats": event["data"].get("output", {}).get("_stats")}
                    yield f"data: {json.dumps(payload)}\n\n"

                case "on_tool_start":
                    payload = {"type": "search_start", "source": event["name"],
                               "query": event["data"].get("input", {}).get("query", "")}
                    yield f"data: {json.dumps(payload)}\n\n"

                case "on_tool_end":
                    payload = {"type": "search_done", "source": event["name"],
                               "count": len(event["data"].get("output", []))}
                    yield f"data: {json.dumps(payload)}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

### POST /api/research/resume

```python
# api/resume.py
@app.post("/api/research/resume")
async def research_resume(body: ResumeRequest):
    """
    Body: {thread_id: str, resume_data: dict}
    resume_data cho outline: {approved_outline: [...]}
    resume_data cho claims:  {human_reviewed_claims: [...]}
    Response: text/event-stream (tiếp tục stream)
    """
    config = {"configurable": {"thread_id": body.thread_id}}
    # Inject user input và resume graph
    async def event_gen():
        async for event in graph.astream_events(
            Command(resume=body.resume_data), config=config, version="v2"
        ):
            # emit events tương tự research_stream
            ...
    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

---

## 7. Implementation Phases

---

### Phase 1 — LangGraph Foundation + Intent Router (Step 0)

**Mục tiêu:** LangGraph graph chạy được, SSE streaming hoạt động, Step 0 intent routing đúng

**Tasks:**

- [ ] Setup LangGraph: `pip install langgraph langchain-openai`
- [ ] `graph/state.py`: Define `ResearchState` TypedDict
- [ ] `config.py`: Load env vars, setup `ChatOpenAI` với NVIDIA NIM base_url:
  ```python
  from langchain_openai import ChatOpenAI
  llm = ChatOpenAI(
      model="openai/gpt-oss-120b",
      base_url="https://integrate.api.nvidia.com/v1",
      api_key=LLM_API_KEY,
      temperature=0,            # override per node
      streaming=True,           # bắt buộc cho astream_events
  )
  ```
- [ ] `graph/nodes/intent_router.py`: Step 0 node
  - Input: `state["query"]`
  - LLM call với `INTENT_SYSTEM_PROMPT` (từ SPEC 2.0), `temperature=0`, `streaming=True`
  - Parse output JSON: `{action, sub_queries, sources, message}`
  - Return: cập nhật `intent`, `sub_queries`, `sources`, `messages`
- [ ] `graph/graph.py`: Build graph với chỉ `intent_router` + conditional edge
- [ ] `api/research.py`: SSE endpoint, `astream_events()` emit `llm_token` events
- [ ] `frontend/hooks/useSSEStream.ts`: EventSource hook
- [ ] `frontend/components/LLMThinking.tsx`: render token stream
- [ ] `frontend/components/ResearchPlan.tsx`: hiển thị sub-queries + edit + confirm button

**Kiểm tra Phase 1:**
- Gõ "hello" → stream LLM thinking → intent=greeting → graph END
- Gõ "RAG" → stream thinking → clarify questions hiện ra → graph END
- Gõ "RAG optimization" → stream thinking → research plan hiện → user confirm

---

### Phase 2 — Multi-source Search + Dedup (Step ①, ①bis)

**Mục tiêu:** 400-600 unique bài sau dedup từ S2 + OpenAlex + arXiv

**Tasks:**

- [ ] `services/openalex.py`: OpenAlex REST search
  ```python
  async def search(query: str, n: int = 100) -> list[dict]:
      url = "https://api.openalex.org/works"
      params = {"search": query, "per-page": n,
                "filter": "publication_year:2018-2026"}
      headers = {"User-Agent": f"AcademicResearchAgent/2.0 (mailto:{OPENALEX_EMAIL})"}
      resp = await httpx_client.get(url, params=params, headers=headers)
      return normalize_openalex(resp.json()["results"])
  ```
- [ ] `services/arxiv_search.py`: arXiv API search (khác `arxiv_fetcher.py`)
  ```python
  async def search(query: str, cat: str = "cs.IR", n: int = 100) -> list[dict]:
      import arxiv
      client = arxiv.Client()
      search = arxiv.Search(query=query, max_results=n,
                            sort_by=arxiv.SortCriterion.Relevance)
      return [normalize_arxiv(r) for r in client.results(search)]
  ```
- [ ] `services/dedup_utils.py`: Cross-source dedup với rapidfuzz
  - Priority: DOI → arXiv ID → S2 paperId → title fuzzy (threshold 90%)
- [ ] `graph/nodes/parallel_search.py`: asyncio.gather tất cả queries × sources
  - Emit `_stats: {total_raw}` để SSE `step_done` hiển thị
- [ ] `graph/nodes/dedup.py`: gọi `dedup_utils.dedup_cross_source()`
- [ ] `models/paper.py`: thêm field `source: Literal["s2", "openalex", "arxiv"]`

**Kiểm tra Phase 2:**
- 5 sub-queries × 2 sources → ~500 raw papers
- Sau dedup → ~400 unique, không còn bài trùng DOI/arXiv ID

---

### Phase 3 — Data Layer: Snowball + Embed (Step ②bis, ③)

**Mục tiêu:** ~600-900 bài trong ChromaDB với SPECTER v2 embeddings

**Tasks:**

- [ ] `graph/nodes/snowball.py`: wrap `services/snowball_logic.py` (logic từ v1.0.1, unchanged)
  - Input: `state["unique_papers"]` (~400 bài)
  - Output: `state["snowballed_papers"]` (~600-900 bài)
- [ ] `graph/nodes/embed.py`: wrap `services/specter_batch.py`
  - 600-900 bài → cần 2 batch calls (max 500/call)
  - Fallback: `specter_local.py` cho papers thiếu embedding
  - Insert vào ChromaDB qua `vector_store.py`
- [ ] SSE events cho Phase 3:
  - `{type:"step_start", node:"snowball", label:"Mở rộng corpus qua citations..."}`
  - `{type:"step_done", node:"embed", stats:{embedded:847}}`

**Kiểm tra Phase 3:**
- ChromaDB có ~600-900 documents với SPECTER v2 vectors
- Không duplicate trong ChromaDB

---

### Phase 4 — Outline + Human-in-Loop Interrupt (Step ④)

**Mục tiêu:** LLM tạo outline từ corpus, user edit + approve, graph resume

**Tasks:**

- [ ] `graph/nodes/outline_gen.py`:
  ```python
  async def outline_gen_node(state: ResearchState):
      # 1. MMR-20 từ toàn bộ ChromaDB
      mmr_papers = mmr.mmr_select(
          query_vec=encode_query(state["query"]),
          fetch_k=MMR_PREFETCH_OUTLINE, k=20
      )
      # 2. LLM generate outline (temperature=0.7 per SPEC model routing table)
      outline_llm = llm.with_config({"temperature": OUTLINE_TEMPERATURE})
      draft = await outline_llm.ainvoke(OUTLINE_PROMPT + abstracts(mmr_papers))
      # 3. interrupt() → graph pause, emit interrupt event
      approved = interrupt({"type": "outline_approval", "outline": draft})
      return {"draft_outline": draft, "approved_outline": approved}
  ```
- [ ] `api/resume.py`: nhận `{thread_id, approved_outline}` → `graph.astream_events(Command(resume=...))`
- [ ] `frontend/components/ThemeOutline.tsx`: giữ nguyên từ v1.0.1 (editable, drag-to-reorder)
- [ ] Frontend: khi nhận `{type:"interrupt", interrupt_type:"outline_approval"}`:
  - Render `ThemeOutline.tsx` với data từ interrupt
  - User edit → click "Approve" → POST `/api/research/resume`

**Kiểm tra Phase 4:**
- Graph pause tại outline_gen
- User thêm/xóa theme → resume → graph tiếp tục với `approved_outline`

---

### Phase 5 — RAG + Writing (Step ⑤, ⑥, ⑦)

**Mục tiêu:** Per-theme hybrid search + parallel writing + claim extraction

**Tasks:**

- [ ] `graph/nodes/hybrid_search.py`: wrap `services/bm25_search.py` + `mmr.py` + `rrf_merge.py`
  - asyncio.gather cho tất cả themes song song
  - Return `papers_per_theme: {theme_name: [top-10 papers]}`
- [ ] `graph/nodes/write_themes.py`: 8 Writer agents song song
  ```python
  async def write_themes_node(state: ResearchState):
      tasks = [
          llm.with_config({"temperature": WRITER_TEMPERATURE}).ainvoke(
              [SystemMessage(LITERATURE_REVIEW_SYSTEM_PROMPT),
               HumanMessage(theme_prompt(theme, papers))]
          )
          for theme, papers in state["papers_per_theme"].items()
      ]
      results = await asyncio.gather(*tasks)
      return {"theme_contents": dict(zip(state["approved_outline"], results))}
  ```
- [ ] `graph/nodes/extract_claims.py`: wrap `services/claim_extractor.py` (từ v1.0.1, unchanged)
- [ ] SSE progress:
  - `{type:"step_start", node:"write_themes", label:"Viết 8 themes song song..."}`
  - `{type:"step_done", node:"write_themes", stats:{themes_written:8}}`

**Kiểm tra Phase 5:**
- 8 theme sections được viết parallel (~12-15s thực tế)
- Mỗi claim có `(Source: PAPER_ID)` để extractor parse được

---

### Phase 6 — Verification + Routing (Step ⑧, ⑨)

**Mục tiêu:** 200 claims verified parallel, human review via interrupt

**Tasks:**

- [ ] `graph/nodes/verify_claims.py`: 200 Verifier agents song song
  ```python
  async def verify_claims_node(state: ResearchState):
      tasks = [
          citation_verifier.verify(claim, temperature=VERIFIER_TEMPERATURE)
          for claim in state["claims"]
      ]
      verified = await asyncio.gather(*tasks)  # parallel, ~20s
      return {"verified_claims": list(verified)}
  ```
- [ ] `graph/nodes/route_claims.py`: routing logic (từ v1.0.1) + interrupt
  ```python
  async def route_claims_node(state: ResearchState):
      routed = route_all(state["verified_claims"])
      # interrupt() cho human review
      reviewed = interrupt({"type": "claim_review", "claims": routed["human_review"]})
      return {"routed_claims": routed, "human_reviewed_claims": reviewed}
  ```
- [ ] Frontend: khi nhận `{type:"interrupt", interrupt_type:"claim_review"}`:
  - Render `ClaimVerifier.tsx` với priority queue (Contrasting first)
  - User approve/reject → POST `/api/research/resume`

**Kiểm tra Phase 6:**
- 200 claims verify xong trong ~20s (parallel)
- Claims chia đúng route: include / remove / human_review

---

### Phase 7 — Export LaTeX + Frontend SSE (Step ⑩ + StreamingPanel)

**Mục tiêu:** Literature review xuất `.tex` + `.bib` compile được, UI streaming real-time

**Tasks:**

- [ ] `templates/literature_review.tex.j2`: Jinja2 template
  ```latex
  \documentclass[12pt,a4paper]{article}
  \usepackage[utf8]{inputenc}
  \usepackage{natbib}
  \usepackage{hyperref}
  \usepackage{amsmath}
  \title{ {{- query -}} }
  \author{Academic Research Assistant v2.0}
  \date{\today}
  \begin{document}
  \maketitle
  \begin{abstract}{{ introduction }}\end{abstract}
  \section{Introduction}{{ introduction }}
  {% for theme in themes %}
  \section{ {{- theme.name -}} }
  {{ theme.content }}
  {% endfor %}
  \section{Conclusion}{{ conclusion }}
  \bibliographystyle{apalike}
  \bibliography{references}
  \end{document}
  ```

- [ ] `services/latex_exporter.py`: Jinja2 render + BibTeX generation
  ```python
  from jinja2 import Environment, FileSystemLoader
  import re

  def export_latex(state: dict, output_dir: str) -> tuple[str, str]:
      env = Environment(loader=FileSystemLoader("templates/"))
      template = env.get_template("literature_review.tex.j2")
      tex = template.render(
          query=state["query"],
          introduction=state["introduction"],
          themes=state["themes"],
          conclusion=state["conclusion"],
      )
      bib = _build_bib(state["cited_papers"])
      return tex, bib

  def _build_bib(papers: list[dict]) -> str:
      entries = []
      for p in papers:
          key = _bib_key(p)  # e.g. "lewis2020rag"
          entries.append(
              f"@article{{{key},\n"
              f"  title = {{{p['title']}}},\n"
              f"  author = {{{p.get('authors','')}}},\n"
              f"  year = {{{p.get('year','')}}},\n"
              f"  url = {{{p.get('pdf_url','')}}}\n}}"
          )
      return "\n\n".join(entries)
  ```

- [ ] `graph/nodes/export.py`: LLM intro/conclusion + `latex_exporter.export_latex()`
  ```python
  async def export_node(state: ResearchState):
      export_llm = llm.with_config({"temperature": EXPORT_TEMPERATURE})
      intro_conclusion = await export_llm.ainvoke(EXPORT_PROMPT + theme_summaries(state))
      tex, bib = latex_exporter.export_latex(state, LATEX_OUTPUT_DIR)
      # write to data/output/{thread_id}/
      path = Path(LATEX_OUTPUT_DIR) / state["thread_id"]
      path.mkdir(parents=True, exist_ok=True)
      (path / "literature_review.tex").write_text(tex)
      (path / "references.bib").write_text(bib)
      return {"literature_review": tex, "cited_papers": state["cited_papers"]}
  ```

- [ ] `api/export.py`: trả về file download
  ```python
  @app.get("/api/review/export")
  async def export_review(thread_id: str, fmt: Literal["tex", "bib"] = "tex"):
      path = Path(LATEX_OUTPUT_DIR) / thread_id / f"literature_review.{fmt}"
      return FileResponse(path, filename=f"literature_review.{fmt}",
                          media_type="application/octet-stream")
  ```

- [ ] `frontend/components/LaTeXViewer.tsx`:
  - Hiển thị `.tex` source trong code block (syntax highlight bằng `react-syntax-highlighter`)
  - Nút **Download .tex** → GET `/api/review/export?thread_id=…&fmt=tex`
  - Nút **Download .bib** → GET `/api/review/export?thread_id=…&fmt=bib`
  - Copy to clipboard button

- [ ] `frontend/components/StreamingPanel.tsx`: render timeline của events
  ```
  ✅ Phân tích query                 [0.5s]
  ✅ Tìm kiếm: S2(100) ArXiv(95)    [8.2s]
  ✅ Loại bỏ trùng lặp → 421 bài   [0.1s]
  ✅ Mở rộng citations → 847 bài    [45s]
  ✅ Embedding → ChromaDB           [30s]
  ⏸  Chờ bạn duyệt outline...
  ✅ Hybrid search 8 themes         [2s]
  ✅ Viết 8 themes song song        [14s]
  ✅ Trích xuất 200 claims          [5s]
  ✅ Verify 200 claims              [22s]
  ⏸  Chờ bạn review claims...
  ✅ Export → literature_review.tex [8s]
  ```

---

### Phase 8 — Integration Testing

**Tasks:**

- [ ] E2E test: "RAG optimization techniques" → full flow
- [ ] Kiểm tra interrupt/resume: outline approval + claim review
- [ ] Đo wall-clock: Step ⑥+⑧ mục tiêu < 2 phút
- [ ] Đo corpus: mục tiêu 400-600 bài sau dedup, 600-900 sau snowball
- [ ] Đo hallucination rate: mục tiêu ~0% bịa paperId
- [ ] Đo citation drift: mục tiêu giảm 65-70% sau verification
- [ ] Test SSE: stream không bị block, token hiện đúng thứ tự
- [ ] Test checkpointer: tắt server giữa chừng → restart → resume đúng thread_id

---

## 8. Key Dependencies

### pyproject.toml (uv)

```toml
[project]
name = "academic-research-backend"
version = "2.0.0"
description = "Academic Research Assistant v2.0"
requires-python = ">=3.11"
dependencies = [
    # Web framework
    "fastapi",
    "uvicorn[standard]",

    # LangGraph + LangChain
    "langgraph>=0.2.0",
    "langchain-openai>=0.1.0",
    "langchain-core>=0.2.0",

    # HTTP client
    "httpx",                    # async: OpenAlex + ar5iv + S2

    # Vector DB
    "chromadb",

    # Keyword search
    "rank-bm25",

    # Embedding — SPECTER2 adapter proximity (query encoding)
    "transformers>=4.35.0",
    "adapters>=0.1.1",
    "torch",
    "numpy",

    # HTML parsing (ar5iv full text)
    "beautifulsoup4",
    "lxml",

    # Academic search
    "semanticscholar",          # official S2 Python client
    "arxiv",                    # arXiv Python client

    # Cross-source dedup
    "rapidfuzz",                # title fuzzy matching

    # Retry / backoff
    "tenacity",

    # LaTeX export
    "jinja2",                   # template → .tex file

    # Utils
    "python-dotenv",
    "pydantic",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",                    # test client
]

[tool.uv]
# uv run uvicorn backend.main:app --reload
```

*Setup:*
```bash
uv sync                    # install deps từ pyproject.toml
uv run uvicorn main:app --reload --app-dir backend
```

### Frontend (npm)

```bash
npm install react-syntax-highlighter   # LaTeXViewer syntax highlight
npm install @types/react-syntax-highlighter
# react-markdown có thể giữ nếu cần text preview song song
```

---

## 9. Rủi ro & Giải pháp

| Rủi ro | Giải pháp v2.0 |
|---|---|
| LangGraph `astream_events()` miss events từ subgraph | Dùng `version="v2"` + test từng node riêng trước khi ghép graph |
| SSE connection timeout (pipeline 3-5 phút) | Set `keepalive_timeout=600` trong uvicorn; emit `{type:"heartbeat"}` mỗi 30s |
| `interrupt()` trong async node | Dùng `interrupt_before` khi compile graph, không call `interrupt()` trực tiếp trong async context |
| OpenAlex rate limit (10 req/s polite) | `tenacity` retry + `asyncio.sleep(0.1)` giữa requests |
| arXiv API unavailable | Fallback: skip arXiv source, tiếp tục với S2 + OpenAlex |
| SPECTER v2 `null` cho paper mới | Fallback `specter_local.py` (giữ nguyên từ v1.0.1) |
| `/snippet/search` S2 không trả kết quả | 3-tier verification (giữ nguyên từ v1.0.1) |
| `rapidfuzz` false positive title match | Threshold 90% + require year match nếu title ngắn (< 5 words) |
| LangGraph SQLite lock khi concurrent sessions | Mỗi session có `thread_id` riêng, SQLite per-thread safe |
| gpt-oss-120b context overflow Step ④ | 131K context window đủ cho 600 abstracts ~150 tokens/abstract |

---

## 10. Milestones

| Milestone | Nội dung | Target |
|---|---|---|
| **M1** | LangGraph setup + SSE endpoint + Intent Router (Step 0) streaming | Week 1 |
| **M2** | Multi-source search (S2 + OpenAlex + arXiv) + Cross-source dedup | Week 2 |
| **M3** | Snowball + SPECTER v2 embed → ChromaDB (wrap từ v1.0.1) | Week 2-3 |
| **M4** | Outline gen + LangGraph interrupt() + user approve + resume | Week 3 |
| **M5** | Hybrid search + Parallel writer agents + Claim extraction | Week 4 |
| **M6** | Parallel verifier agents + Routing + interrupt() claim review | Week 5 |
| **M7** | Export + Frontend SSE StreamingPanel + E2E connected | Week 5-6 |
| **M8** | Integration test + measure metrics + bug fix | Week 6-7 |

---

## CHANGELOG

### PLAN_2.0 — so với PLAN_1.0.1

| Thay đổi | Chi tiết |
|---|---|
| **Pipeline orchestration** | LangGraph `StateGraph` thay thế frontend-driven multi-endpoint approach |
| **Streaming** | `astream_events()` → SSE → frontend nhận real-time LLM tokens + step events |
| **Endpoints** | 8 endpoints → 3 endpoints: `/stream`, `/resume`, `/export` |
| **Human-in-loop** | LangGraph `interrupt()` tại Step ④ và ⑨, resume qua `/api/research/resume` |
| **LLM Client** | `llm_client.py` tự viết → `langchain-openai` `ChatOpenAI` với NVIDIA NIM base_url |
| **Model** | Multi-provider → 1 model: `openai/gpt-oss-120b`, nhiều system prompt + temperature |
| **Academic search** | Semantic Scholar only → S2 + OpenAlex + arXiv parallel |
| **Dedup** | Không có → DOI → arXiv ID → S2 paperId → title fuzzy (rapidfuzz) |
| **Corpus size** | 100 bài initial → 400-600 bài initial → 600-900 sau snowball |
| **Writer agents** | Sequential → asyncio.gather parallel (8 agents cùng lúc) |
| **Verifier agents** | Sequential → asyncio.gather parallel (200 claims ~20s) |
| **State management** | Frontend session → LangGraph checkpointer (SQLite) |
| **Frontend** | `ProgressStepper.tsx` (manual WebSocket) → `StreamingPanel.tsx` (SSE EventSource) |
| **Dependencies** | Thêm: `langgraph`, `langchain-openai`, `langchain-core`, `semanticscholar`, `arxiv`, `rapidfuzz`, `tenacity` |
| **Milestones** | 6 tuần → 7 tuần (thêm LangGraph migration + streaming frontend) |

### PLAN_2.0 — updates so với PLAN_2.0 draft đầu

| Thay đổi | Chi tiết |
|---|---|
| **Directory structure** | Flat `backend/{graph,services,api,models}` → `backend/module/research_agent/{graph,services,api,models}` + `gap_detection/` placeholder |
| **Package manager** | `requirements.txt` → `pyproject.toml` (uv) |
| **LaTeX export** | `export_node` → `latex_exporter.py` (Jinja2) → `.tex` + `.bib` thay cho Markdown |
| **Frontend** | `ReviewEditor.tsx` (react-markdown) → `LaTeXViewer.tsx` (syntax highlight + Download) |
| **Temperature sync** | Thêm `OUTLINE_TEMPERATURE=0.7`, `CLAIM_TEMPERATURE=0`, `EXPORT_TEMPERATURE=0.7` — sync với SPEC model routing table |
| **Phase 4 code** | `outline_gen_node` giờ dùng `llm.with_config({"temperature": OUTLINE_TEMPERATURE})` |
| **`.env.example`** | Dùng `.env.example` commit được thay cho `.env` |

### Service files GIỮ NGUYÊN từ v1.0.1

Các file sau không cần viết lại, LangGraph nodes chỉ wrap gọi vào:
`specter_batch.py`, `specter_local.py`, `arxiv_fetcher.py`, `vector_store.py`,
`mmr.py`, `bm25_search.py`, `rrf_merge.py`, `snowball_logic.py`,
`citation_verifier.py`, `paper.py`, `claim.py`, `outline.py`, `review.py`,
`ThemeOutline.tsx`, `ClaimVerifier.tsx`, `PDFLinksSection.tsx`
