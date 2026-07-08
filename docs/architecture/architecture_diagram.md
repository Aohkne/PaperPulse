# Architecture Diagram — PaperPulse

## System Overview

```mermaid
graph TB
    User([Researcher / User])
    FE["Frontend — React 19 + Vite + Zustand<br/>(ChatPage, ResearchPage, Admin pages)"]

    User --> FE

    subgraph Backend["FastAPI Backend (backend/main.py)"]
        AuthAPI["/api/auth/*"]
        ResearchAPI["/api/research/stream (SSE)<br/>/api/search · /api/snowball · /api/embed"]
        ReviewAPI["/api/outline · /api/review/theme<br/>/api/claims/* · /api/review/export"]
        ReviewsAPI["/api/reviews (CRUD)"]
        ChatAPI["/api/chat"]
        AdminAPI["/api/admin/*"]
    end

    FE -->|REST + SSE, Bearer JWT| AuthAPI
    FE --> ResearchAPI
    FE --> ReviewAPI
    FE --> ReviewsAPI
    FE --> ChatAPI
    FE --> AdminAPI

    subgraph Services["Services layer — orchestration (backend/services/)"]
        S2svc["semantic_scholar.py"]
        Snow["snowball.py"]
        Emb["embedding.py"]
        VS["vector_store.py"]
        Hybrid["hybrid_search.py"]
        CitVerify["citation_verifier.py"]
        ArxivFetch["arxiv_fetcher.py"]
        LLMClient["llm_client.py"]
        Latex["latex_utils.py"]
        SBClient["supabase_client.py"]
    end

    subgraph Agents["Agent layer — LLM prompts (backend/agent/)"]
        Outline["outline.py"]
        Content["content.py"]
        ClaimExt["claim_extractor.py"]
        Verifier["verifier.py"]
        ChatAgent["chat.py"]
        GapGraph["gap_detection/ — LangGraph StateGraph<br/>(built, router not mounted yet)"]
    end

    ResearchAPI --> S2svc
    ResearchAPI --> Snow
    ResearchAPI --> Emb
    ResearchAPI --> Hybrid
    ResearchAPI --> Outline
    ResearchAPI --> Content
    ResearchAPI --> ClaimExt
    ResearchAPI --> CitVerify
    ResearchAPI --> Latex

    ReviewAPI --> Outline
    ReviewAPI --> Content
    ReviewAPI --> VS

    Snow --> S2svc
    Hybrid --> VS
    Hybrid --> Emb
    CitVerify --> ArxivFetch
    CitVerify --> Verifier
    Outline --> LLMClient
    Content --> LLMClient
    ClaimExt --> LLMClient
    Verifier --> LLMClient
    ChatAgent --> LLMClient
    ChatAPI --> ChatAgent

    AuthAPI --> SBClient
    ReviewsAPI --> SBClient
    AdminAPI -->|service-role key, bypass RLS| SBClient

    GapGraph -.->|designed for chat_integration.py,<br/>not yet called from ChatAPI| ChatAPI

    SemanticScholarAPI[("Semantic Scholar API")]
    ArxivWeb[("arXiv HTML<br/>ar5iv.labs.arxiv.org")]
    LLMProvider[("LLM Provider<br/>OpenAI / Anthropic / custom")]
    ChromaDB[("ChromaDB<br/>local persistent vector store")]
    Supabase[("Supabase<br/>Postgres + Auth (GoTrue) + RLS")]

    S2svc --> SemanticScholarAPI
    ArxivFetch --> ArxivWeb
    LLMClient --> LLMProvider
    VS --> ChromaDB
    SBClient --> Supabase
```

## Data Flow — Literature Review Pipeline (①→⑩, `GET /api/research/stream`)

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as research.py (SSE)
    participant S2 as Semantic Scholar
    participant Chroma as ChromaDB
    participant LLM as LLM Provider

    FE->>API: GET /api/research/stream?query=...
    API->>S2: ① search_papers(query)
    S2-->>API: up to 100 papers
    API->>S2: ②bis select_seeds (dual-pool) + snowball backward/forward
    S2-->>API: expanded corpus (~300-400 papers)
    API->>S2: ③ batch embeddings (SPECTER v2)
    API->>Chroma: upsert papers + embeddings
    API->>LLM: ④ generate_outline (MMR-20 diverse papers)
    LLM-->>API: themes[]
    API-->>FE: SSE outline_draft event
    FE-->>API: user edits & approves outline
    loop per approved theme
        API->>Chroma: ⑤ hybrid_search (MMR + BM25 + RRF merge)
        API->>LLM: ⑥ generate_theme_content
        LLM-->>API: content with "(Source: PAPER_ID)"
    end
    API->>API: ⑦ extract_claims (regex fast-path + LLM fallback)
    API->>S2: ⑧ verify — tier 1: /snippet/search
    API->>ArxivWeb: ⑧ verify — tier 2: arXiv HTML fallback
    API->>LLM: ⑧ verify — tier 3: abstract (conservative, never "Supported")
    API->>API: ⑨ flag low_confidence claims → mandatory human review
    API->>API: ⑩ assemble review + PDF link priority + LaTeX export
    API-->>FE: SSE done event (full review content)
```

## Gap Detection Sub-graph (built, not yet wired into the API)

```mermaid
graph LR
    NStart((session_papers)) --> Extractor[extractor]
    Extractor --> Topical[topical_detector]
    Topical --> Method[method_detector]
    Method --> Contradiction[contradiction_detector]
    Contradiction --> Verifier2[verifier]
    Verifier2 --> CounterSearch[counter_search]
    CounterSearch --> Synthesizer[synthesizer]
    Synthesizer --> NEnd((GapReport))
```

Hiện `chat_integration.py` đã code sẵn cầu nối (`run_gap_detection_chat`: collect session papers → paper_check → baseline search nếu thiếu → chạy graph trên), nhưng `backend/api/chat.py` và `backend/api/__init__.py` (`gap_router` bị comment) chưa gọi tới — module compile/test được nhưng chưa expose qua API.

## Component Details

| Component | Technology | Purpose |
|---|---|---|
| Frontend | React 19 + Vite + Zustand + Tailwind v4 | Chat-style research UI, review editor, knowledge graph panel, admin dashboard |
| Backend | FastAPI (Python 3.11+) | REST + SSE API server (`backend/main.py`) |
| Agent layer | Custom Python LLM modules (`backend/agent/`) | Outline / content / claim-extraction / verification prompts — no LangChain |
| Gap Detection | LangGraph `StateGraph` (`backend/module/gap_detection/`) | 7-node linear graph for research-gap reports; built, not yet mounted on the router |
| LLM Provider | OpenAI / Anthropic / custom (`services/llm_client.py`) | Text generation for every agent step, selected via `PROVIDER` env |
| Search | Semantic Scholar API (`services/semantic_scholar.py`) | Paper search, citation snowballing, snippet verification |
| Full-text fallback | `ar5iv.labs.arxiv.org` (`services/arxiv_fetcher.py`) | Tier-2 citation verification when no snippet exists |
| Vector Store | ChromaDB, local persistent (`services/vector_store.py`) | Stores SPECTER v2 embeddings, semantic retrieval |
| Keyword Search | `rank_bm25` + RRF merge (`services/hybrid_search.py`) | Combined with semantic search per theme |
| Database / Auth | Supabase — Postgres + GoTrue + RLS | Tables: `profiles`, `reviews`, `chats`, `messages`, `notifications`, `login_logs` |
| Deployment | Docker (multi-stage) + GitHub Actions | CI: lint-be → lint-fe → test → build → deploy |
