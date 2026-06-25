# Team C2-App-069 — PaperPulse

> Tổng quan tài liệu (Literature Review) tự động bằng LLM + RAG → giúp nhà nghiên cứu tiết kiệm hàng tuần đọc bài báo, vẫn đảm bảo trích dẫn đúng nguồn (chống hallucination).

## Vấn đề (Problem)

- Nhà nghiên cứu mất hàng tuần để tổng quan tài liệu cho một chủ đề: tìm bài, đọc hàng trăm abstract/full-text, nhóm theo phương pháp/kết quả, rồi viết lại có trích dẫn.
- Risk lớn nhất khi dùng LLM để hỗ trợ: **bịa trích dẫn** (citation hallucination) hoặc trích dẫn lệch ý bài gốc (citation drift) — nguy hiểm cho công cụ học thuật.
- Các chatbot LLM thông thường (không RAG, không verify) không đủ tin cậy cho tác vụ này.

## Giải pháp (Solution)

**Tính năng chính hiện tại: Tổng quan tài liệu (Literature Review)** — pipeline ①→⑩ tự động, end-to-end:

| Step | Việc làm |
|---|---|
| ① | Search Semantic Scholar (lên tới 100 bài) |
| ②/②bis | Lọc + citation snowballing (dual-pool seed, backward/forward expand) |
| ③ | Embed bài báo (SPECTER v2) → lưu ChromaDB |
| ④ | Generate outline (LLM, MMR-diverse 20 bài) → **user approve outline** |
| ⑤/⑥ | Hybrid search (semantic + BM25 + RRF) theo theme → LLM viết nội dung kèm `(Source: PAPER_ID)` |
| ⑦ | Tách claims từ nội dung sinh ra |
| ⑧/⑨ | Verify từng claim (snippet → arXiv full text → abstract, 3-tier fallback) → flag `low_confidence` cần human review |
| ⑩ | Export review hoàn chỉnh (Markdown / LaTeX) kèm PDF links |

Toàn bộ flow stream real-time qua SSE (`GET /api/research/stream`) — frontend hiển thị từng step (thought/action/observation) kiểu ReAct trace.

Các module khác (Research Gap Detection, Knowledge Graph, Admin dashboard, Chat) đã có code nhưng **Literature Review là tính năng được wire đầy đủ và là trọng tâm hiện tại**.

## Target User

- **Primary:** Sinh viên / nhà nghiên cứu cần viết tổng quan tài liệu cho luận văn, paper, hoặc literature survey.
- **Secondary:** Giảng viên / reviewer muốn kiểm tra nhanh corpus tài liệu của một chủ đề.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| LLM agent layer | Module LLM tự build (`backend/agent/`) — không qua LangChain, trừ `gap_detection` dùng LangGraph `StateGraph` |
| Vector DB | ChromaDB (local persistent) |
| Search | Semantic Scholar API + BM25 (`rank_bm25`) + RRF merge |
| Embedding | SPECTER v2 (Semantic Scholar Batch API, document) + SPECTER2 adapter `proximity` (local, query) |
| Auth & DB | Supabase (Postgres + Auth + RLS) |
| Frontend | React 19 + Vite + Zustand + Tailwind v4, `react-markdown`, `framer-motion` |
| Package manager (FE) | Bun |
| Deployment | Docker (multi-stage) + GitHub Actions CI/CD |

## Thành viên

- Nguyễn Phan Duy Bảo
- Lê Hữu Khoa - 2A202600863
- Trần Nguyễn Anh Thư - 2A202600915

## MVP Demo & Others
[https://drive.google.com/drive/folders/1pyk0bb9EIuCNFU364qKrl0t8S8Mfb7CG?usp=sharing](https://drive.google.com/drive/folders/1pyk0bb9EIuCNFU364qKrl0t8S8Mfb7CG?usp=sharing)

---

## Quick Start

### 1. Thiết lập môi trường ảo & cài đặt thư viện Python

```bash
# Tạo virtual environment
python -m venv .venv

# Kích hoạt venv (macOS/Linux)
source .venv/bin/activate

# Kích hoạt venv (Windows PowerShell)
.venv\Scripts\activate

# Cài đặt toàn bộ dependencies từ pyproject.toml (bao gồm cả dev tools)
pip install -e ".[dev]"
```

### 2. Cấu hình biến môi trường

```bash
# macOS / Linux / Git Bash
cp .env.example .env

# Windows (cmd/PowerShell)
copy .env.example .env
```

Xem chi tiết từng biến ở mục [Environment Variables](#environment-variables) dưới đây.

### 3. Khởi động Backend (FastAPI)

```bash
python backend/main.py
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs) · Health check: [http://localhost:8000/health](http://localhost:8000/health)

#### (Optional) MinerU + ChromaDB qua Docker, backend vẫn chạy native

Mặc định backend chạy native dùng MinerU CLI (`MINERU_MODE=cli`) + ChromaDB embedded
(`CHROMA_MODE=embedded`) — không cần Docker. Nếu không muốn cài MinerU's deps nặng
(torch/paddle/onnxruntime) vào env dev, chạy 2 service này riêng trong Docker và set
`MINERU_MODE=http` + `CHROMA_MODE=http` trong `.env`:

```bash
docker compose -f docker-compose.dev.yml up -d   # MinerU :8001, ChromaDB :8002
```

`docker-compose.yml` (không có `-f`) là bản full container — toàn bộ backend +
MinerU CLI + ChromaDB embedded gói chung 1 image, dùng cho production:

```bash
docker compose up -d
```

### 4. Khởi động Frontend — React/Vite

Yêu cầu cài [Bun](https://bun.sh):

```bash
# macOS / Linux
curl -fsSL https://bun.sh/install | bash

# Windows (PowerShell)
powershell -c "irm bun.sh/install.ps1 | iex"
```

Chạy frontend:

```bash
cd frontend
bun install
bun run dev
```

Truy cập: [http://localhost:5173](http://localhost:5173)

---

## Environment Variables

Biến **bắt buộc** để chạy được flow Literature Review end-to-end: `LLM_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`. Còn lại có default hợp lý cho local dev.

| Variable | Default | Mô tả |
|---|---|---|
| `PROVIDER` | `openai` | LLM provider: `openai` \| `anthropic` \| `google` \| `custom` |
| `LLM_API_KEY` | — | **Bắt buộc.** API key cho provider đã chọn |
| `LLM_MODEL` | `gpt-4o-mini` | Model dùng cho outline/content/claim/verify agents |
| `LLM_BASE_URL` | — | Base URL nếu dùng custom/self-hosted endpoint |
| `LLM_TEMPERATURE` | `0.7` | Temperature cho LLM calls |
| `EMBEDDING_MODEL` | `nv-embed-v1` | Model embedding fallback (khi không dùng SPECTER batch) |
| `EMBEDDING_BASE_URL` | — | Base URL nếu dùng custom embedding endpoint |
| `SEMANTIC_SCHOLAR_API_KEY` | — | Optional nhưng nên có — tăng rate limit (100 req/10s so với 1 req/s) |
| `CHROMA_PERSIST_PATH` | `./data/chroma` | Đường dẫn lưu ChromaDB local |
| `SUPABASE_URL` | — | **Bắt buộc.** URL project Supabase (`https://<ref>.supabase.co`) |
| `SUPABASE_KEY` | — | **Bắt buộc.** Anon hoặc service-role key |
| `SUPABASE_SERVICE_KEY` | — | Service-role key — cần cho `/api/admin/*` (bypass RLS) |
| `CORS_ORIGINS` | `http://localhost:5173` | Danh sách origin được phép gọi API, ngăn cách bằng dấu phẩy |
| `APP_ENV` | `development` | `development` \| `production` \| `test` |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `AI_LOG_SERVER`, `AI_LOG_API_KEY`, `AI_LOG_DIR` | — | AI usage logging cho khoá học (giảng viên cấp) |


---

## API Endpoints (flow Literature Review)

| Method | Path | Step | Mô tả |
|---|---|---|---|
| GET | `/health` | — | Health check |
| GET | `/api/research/stream?query=...` | ①→⑩ | **Chạy toàn bộ pipeline**, stream SSE từng step (ReAct trace) |
| POST | `/api/search` | ① | Search Semantic Scholar, trả về tối đa `limit` bài |
| POST | `/api/snowball` | ②bis | Citation snowballing từ seed papers |
| POST | `/api/embed` | ③ | Lấy SPECTER v2 embeddings, lưu ChromaDB |
| POST | `/api/outline` | ④ | Sinh outline (themes) từ top-K bài |
| POST | `/api/review/theme` | ⑤⑥ | Hybrid search + sinh nội dung theo theme, kèm `(Source: PAPER_ID)` |
| POST | `/api/claims/extract` | ⑦ | Tách claims từ nội dung đã sinh |
| POST | `/api/claims/verify` | ⑧ | Verify từng claim (snippet → arXiv → abstract) |
| GET | `/api/review/export` | ⑩ | Export review hiện tại dưới dạng Markdown |
| POST/GET/PATCH/DELETE | `/api/reviews` | — | CRUD review đã lưu (theo user), export, duplicate |
| POST | `/api/chat` | — | Chat tự do với PaperPulse (không qua RAG pipeline) |
| POST | `/api/auth/{register,login,logout,refresh}` | — | Supabase Auth |
| GET | `/api/admin/{stats,users,activity}` | — | Admin dashboard (yêu cầu role `admin`) |

Đầy đủ schema request/response: xem Swagger UI tại `/docs` sau khi chạy backend.

---

## Sample Queries

**Chạy toàn bộ Literature Review pipeline (khuyến nghị — dùng để demo):**

```bash
curl -N "http://localhost:8000/api/research/stream?query=Retrieval-Augmented%20Generation%20for%20question%20answering"
```

Trả về stream SSE, mỗi event có dạng:

```
data: {"type": "step", "step_type": "thought", "stepNum": "①", "content": "..."}
data: {"type": "step", "step_type": "action", "stepNum": "②", "label": "search_papers", "args": "..."}
data: {"type": "outline_draft", "themes": [...]}
data: {"type": "done", "content": "## Literature Review ..."}
```

**Chạy riêng từng step (debug / tích hợp UI):**

```bash
# Step ① — search papers
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "graph neural networks for drug discovery", "limit": 50}'

# Step ④ — generate outline từ top-20 bài đã embed
curl -X POST http://localhost:8000/api/outline \
  -H "Content-Type: application/json" \
  -d '{"query": "graph neural networks for drug discovery", "top_k": 20}'

# Step ⑦+⑧ — extract & verify claims trong nội dung đã sinh
curl -X POST http://localhost:8000/api/claims/extract \
  -H "Content-Type: application/json" \
  -d '{"content": "GNNs improve binding affinity prediction (Source: 1a2b3c4d).", "theme": "GNN methods"}'
```

**Chat tự do (không RAG — chỉ để so sánh baseline):**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What are research gaps in LLM-based literature review tools?"}]}'
```

---

## Project Structure

```
├── backend/
│   ├── agent/            # LLM call layer: outline, content, claim_extractor, verifier, chat, gap_detection (LangGraph)
│   ├── api/              
│   ├── auth/              # Supabase JWT dependencies (get_current_user, require_admin)
│   ├── models/            # Pydantic schemas (paper, claim, review)
│   ├── services/          # Orchestration: semantic_scholar, snowball, embedding, hybrid_search, citation_verifier, vector_store, llm_client
│   ├── config.py
│   └── main.py             # FastAPI entry point
├── frontend/               # React + Vite + Zustand
├── supabase/                # schema.sql, insert.sql
├── docs/research/           
├── tests/
├── eval/                    # Evaluation evidence
├── JOURNAL.md / WORKLOG.md
└── Dockerfile / docker-compose.yml
```

## API Docs

Sau khi chạy backend, truy cập tài liệu Swagger UI tự động tại: [http://localhost:8000/docs](http://localhost:8000/docs)
