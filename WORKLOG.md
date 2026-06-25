# WORKLOG — C2-App-069

> Ghi lại các quyết định kỹ thuật, phân công task, brainstorming và bug quan trọng.
> Use this file to record **why** a technical choice was made, not just **what** was done.

---

## 2026-06-(15-18) — Optimize literature review pipeline (SPEC v1.0.1), thêm Admin pages, tích hợp PR #20-#26 vào develop

### Context

Sau khi flow cơ bản ①→⑩ chạy được (xem entry "Bỏ opendeepresearch..." dưới), review lại SPEC v1.0 phát hiện 6 vấn đề ảnh hưởng chất lượng literature review: structural bias trong outline, temporal bias trong snowballing, sai loại embedding cho query, verification coverage chỉ ~30%. Đồng thời cần trang Admin để quản lý user/xem activity, và phải tích hợp liên tục các PR của team (auth, review-save, gap detection, db schema) vào `develop` / `feat/T-007` qua PR #20-#26.

### Quyết định kỹ thuật

**1. Snowball seed selection — Dual-pool thay single metric (Fix 1):**
- top-5 theo raw `citationCount` (Pool A, foundational) ∪ top-5 theo `citationCount / (năm hiện tại − năm publish)` (Pool B, recent impactful), dedup → ~7-9 seeds.
- **Lý do:** citations/year thuần túy ưu tiên bài mới, bỏ sót foundational paper (bài 2020 với 30 citations = 5/year bị rank thấp hơn bài 2024 với 20 citations = 10/year dù important hơn).
- **Trade-off:** thêm 1-2 API call; số seed thực tế có thể < 10 nếu 2 pool overlap nhiều.

**2. Backward filter — Time-decayed + isInfluential bypass thay flat threshold (Fix 2):**
- Bỏ `min_citations ≥ 5` + năm hardcode 2022, đổi sang threshold tương đối theo `current_year − N`; bài Semantic Scholar đánh `isInfluential=True` được bypass threshold (kèm guard `citations ≥ 1` ở forward để tránh false positive của classifier ~65% precision).
- **Lý do:** flat threshold loại systematically breakthrough paper mới publish chưa kịp tích citations (Ke et al. 2015: bài 1-2 năm đầu thường impact cao, citations thấp).
- **Trade-off:** corpus có thể thêm noise (preprint chưa peer-review) — chấp nhận vì MMR + RRF ở bước sau tự lọc bài ít liên quan xuống rank thấp.

**3. Outline generation — MMR-20 trên 300-400 bài + user approval thay top-20 cosine trên 100 bài gốc (Fix 3):**
- Pre-filter top-150 bằng cosine similarity → MMR (λ=0.5, k=20) chọn 20 bài diverse cho LLM generate outline. Thêm bước user edit/approve outline trước khi generate content.
- **Lý do:** outline từ 100 bài gốc (kết quả keyword search ban đầu) = structural bias, bài snowballed (foundational/cross-disciplinary) không ảnh hưởng theme → review thiếu góc nhìn. Sửa ở outline rẻ hơn sửa ở claim-level (Step ⑨).
- **Trade-off:** user phải đợi Step ①②②bis③ xong (~3-5 phút) mới thấy outline — giải quyết UX bằng streaming progress (`ReActTrace.jsx` + `GET /api/research/stream`).

**4. Query embedding — SPECTER2 adapter `proximity` thay default adapter (Fix 4):**
- Document embedding vẫn dùng SPECTER v2 qua S2 Batch API; encode **query** (theme description) đổi sang local SPECTER2 adapter `proximity`.
- **Lý do:** SPECTER v2 default train cho similarity paper↔paper (symmetric, citation triplets) — encode query là asymmetric retrieval, task model không được train cho (SciRepEval, Singh 2022, xác nhận SPECTER2 default kém hơn model retrieval chuyên dụng trên search task). Adapter `proximity` cùng model family fine-tune cho retrieval → embedding space tương thích hơn so với đổi sang model khác (BGE/E5).
- **Trade-off:** phải load thêm adapter (~500MB) — chấp nhận được cho local MVP.

**5. Citation verification — 3-tier fallback thay 1-tier (Fix 5):**
- `/snippet/search` (coverage ~30%) → arXiv HTML qua `ar5iv.labs.arxiv.org` (`backend/services/arxiv_fetcher.py`, ~80%+ cho CS/AI/ML, free, không cần key) → abstract (conservative — không bao giờ return `Supported`, chỉ detect topic mismatch/mâu thuẫn rõ ràng → `Unsupported`, còn lại → `Uncertain` + `low_confidence` + mandatory human review).
- **Lý do:** 70% paper không có snippet; abstract không đủ verify citation drift (drift thường ở paragraph level) — abstract-only trả `Supported` sẽ false positive bypass human review, nguy hiểm hơn không verify.
- **Trade-off:** thêm 1 network call (ar5iv) có thể chậm; claims `low_confidence` vẫn cần human review thủ công.

**6. Citation Intent — bỏ early-exit (Fix 6):**
- Intent (Supporting/Contrasting/Mentioning) chỉ dùng làm metadata ưu tiên human-review queue, không dùng để skip verification khi intent ≠ Supporting.
- **Lý do:** citation drift phổ biến nhất chính trong nhóm Supporting (AI oversimplify bài nó dùng để ủng hộ claim) — early-exit theo intent sẽ miss phần lớn drift thật. Correctness ưu tiên hơn tiết kiệm compute cho công cụ học thuật.

**7. Admin endpoints query PostgREST trực tiếp bằng `httpx` + service-role key, không qua `supabase-py` client:**
- **Lý do:** `supabase-py` fail với key format `sb_publishable_...` mới của Supabase (lỗi `PGRST301`). Gọi REST trực tiếp bằng service-role key bypass RLS và tránh incompatibility.
- **Trade-off:** mất type-safety/helper của supabase-py, phải tự parse header `content-range` để lấy count.

**8. Snowball chạy sequential (không `asyncio.gather` đồng thời) kèm `asyncio.sleep(0.15)` giữa mỗi seed:**
- **Lý do:** gọi đồng thời 7-9 seeds × 2 endpoint (references + citations) vượt rate limit Semantic Scholar (1 req/s không key) → 429.
- **Trade-off:** tăng latency snowball (~1.8s cho 6 seeds) nhưng đổi lại ổn định, không bị throttle.

### Trade-offs chấp nhận
- Co-citation / bibliographic coupling chưa implement (ghi nhận trong CHANGELOG của `SPEC_1.0.1.md`, defer v1.1) — cần data thực tế từ MVP để đánh giá.
- Single-hop snowballing only — 2-hop tăng recall nhưng tăng corpus size + latency, chưa đủ data để quyết định có cần không.
- Theme cross-disciplinary gap: paper chạm nhiều theme nhưng không dominate theme nào có thể bị miss ở top-10 mọi theme — MMR ở Step ⑤ chỉ partial mitigation.

### Bugs quan trọng được fix trong quá trình này
- `supabase-py` client × key `sb_publishable_...` → `PGRST301` trong `require_admin` — fix bằng gọi PostgREST qua `httpx` trực tiếp.
- JWT decode chỉ whitelist `HS256/RS256`, project Supabase issue `ES256` → login 401 sai — thêm `ES256` vào whitelist.
- `login_logs` insert qua `supabase.table().insert()` bị RLS chặn, fail im lặng (try/except nuốt lỗi) — chuyển sang `_log_event()` dùng service-role key.
- Snowball gọi đồng thời tất cả seed → 429 rate limit từ Semantic Scholar — đổi sang sequential + delay.

---

## 2026-06-(11-14) — Bỏ opendeepresearch / LangChain, xây flow tự build + đổi frontend sang Vite + React

### Context

Codebase ban đầu dựa trên **Open Deep Research** của LangChain — một LangGraph multi-agent framework cho web research (supervisor → researcher → compress). Stack này không phù hợp với flow ①→⑩ trong SPEC.md (Semantic Scholar API + ChromaDB + citation verification), gây ra:
- Dependencies nặng không dùng (`langchain`, `langgraph`, `langchain-mcp-adapters`, `tavily-python`, `mcp`)
- `backend/agents/` chứa ~700 dòng LangGraph code không liên quan đến academic literature review
- Frontend là Streamlit (`backend/frontend/app.py`) — không phù hợp với UI đa flow (search → snowball → embed → outline → review → verify)

### Quyết định kỹ thuật

**1. Xoá toàn bộ opendeepresearch:**
- Xoá `backend/agents/` (LangGraph supervisor/researcher/compressor), `backend/prompts.py` (LangChain prompts), `backend/utils.py` (Tavily search, MCP utils, token limit handlers)
- Lý do: code không được gọi từ bất kỳ API endpoint nào trong PLAN.md, cũng không thể tái dùng vì phụ thuộc `RunnableConfig` / `LangGraph State`

**2. Tạo `backend/agent/` — luồng LLM tự build:**

Tách prompt + LLM call thành một layer riêng, mỗi file tương ứng một step trong flow:

| File | Step | Nhiệm vụ |
|------|------|-----------|
| `agent/outline.py` | ④ | Top-20 papers → LLM → outline themes (JSON) |
| `agent/content.py` | ⑥ | Papers + theme → LLM → synthesis với `(Source: PAPER_ID)` |
| `agent/claim_extractor.py` | ⑦ | Content → regex fast-path → LLM fallback → list Claim |
| `agent/verifier.py` | ⑧ | Claim + snippet → LLM → Supported/Partial/Unsupported/Uncertain |
| `agent/chat.py` | — | General research chat (PaperPulse system prompt) |

`backend/services/` giữ vai trò orchestration: fetch data (ChromaDB, Semantic Scholar) → gọi agent → trả kết quả. Không còn prompt nào nằm trong services.

**3. Frontend: Streamlit → Vite + React (đã scaffold 2026-06-10):**
- `backend/frontend/app.py` (Streamlit) đã bị xoá — single-page, không đủ để hiển thị flow ①→⑩ với nhiều bước và state khác nhau
- Vite + React + Zustand phù hợp hơn: component per step, global state cho pipeline, dễ thêm PaperGraph (D3/react-force-graph) và ClaimVerifier panel

**4. Thêm Supabase Auth:**
- `backend/auth/` với `get_current_user` / `optional_user` FastAPI dependencies
- `backend/api/auth.py`: register / login / logout / refresh / me
- `supabase/schema.sql`: bảng `profiles` (trigger từ `auth.users`) + `login_logs`
- Lý do: cần user context để persist review sessions theo user, không chỉ in-memory

### Trade-offs chấp nhận
- Bỏ LangGraph mất khả năng pause/resume research agent — không cần thiết cho flow pipeline tuần tự ①→⑩
- `backend/services/llm_client.py` tự build (OpenAI + Anthropic SDK) thay vì `langchain.init_chat_model` — ít abstraction hơn nhưng không có hidden dependency, dễ debug
- `langchain*`, `langgraph`, `tavily-python`, `mcp` vẫn còn trong `pyproject.toml` — cần cleanup commit riêng sau khi confirm không còn import nào sót

### Bugs quan trọng được fix trong quá trình này
- `chromadb.PersistentClient | None` TypeError — `from __future__ import annotations`
- `uvicorn.run("src.main:app")` module not found — đổi thành `"backend.main:app"` (missed khi rename package)
- `gotrue` not found trong conda `ml` — `TYPE_CHECKING` guard

---

## 2026-06-07 — Khởi tạo repo & setup môi trường

### Setup ban đầu (Windows — Antigravity)

**Việc đã làm:**
- Clone starter template Cohort 2
- Cài pre-push hook để tự động log AI usage:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
  ```
- Tạo file `.env` từ `.env.example`, đã có sẵn `AI_LOG_SERVER` và `AI_LOG_API_KEY` của khoá học
- Xác nhận hook chạy đúng: `[ai-log] Git pre-push hook installed.`

**Tool AI đang dùng:** Antigravity IDE (tự động log — không cần thêm bước thủ công)

**Quyết định:**
- Dùng Antigravity thay Claude CLI — workflow tương đương, log tự động khi `git push`
- Trên Windows dùng `scripts\_pyrun.cmd` thay vì `bash scripts/_pyrun.sh`

### Important bugs / fixes (Windows)
- **Hook `pre-push` dùng `bash` — không chạy được trên Windows** (WSL không cài)
  - **Fix:** sửa `scripts/setup_hooks.ps1` để hook dùng `#!/bin/sh` + `scripts/_pyrun.cmd`
  - **Fix thêm:** ghi hook file với LF line endings (dùng Python) để Git có thể spawn hook
- **`cp` không có trong Windows cmd** — dùng `copy .env.example .env` thay thế

---

## 2026-06-07 — Repo setup (macOS/Linux — Claude CLI)

### Context
Fresh clone of `starter-code-template (cohort 2)` (commit `42f8720`) on branch `test/log-ai-khoa`. Upstream: `origin/main` (last sync via PR #1 — Anh Thu's personal journal).

### Technical decisions
- **Stayed on the starter template** instead of forking a custom scaffold.
  - **Why:** the template already wires up per-tool AI logging hooks (Claude, Cursor, Codex, Gemini, Antigravity, Copilot) and the `_pyrun` / `setup_hooks` cross-platform Python launchers. Re-implementing these would be wasted effort for the team.
  - **Trade-off accepted:** we're locked into the template's hook script layout; any framework we add (e.g. Next.js, Expo) has to coexist with the existing `scripts/` and `.env` flow.
- **Python launcher is the contract for hooks.**
  - `_pyrun.sh` / `_pyrun.cmd` auto-detect `python3` / `python` / `py` on PATH, so contributors don't need to alias `python3 → python`. We will treat that as a project rule: any hook helper script should be invoked through `_pyrun.*`, never with a hard-coded interpreter.

### Task assignments
- **Khoa:** ran `setup_hooks.sh`, copied `.env.example` → `.env`, verified git status clean except for `scripts/_pyrun.sh` (see below).
- **Next:** each teammate runs setup_hooks locally and confirms their `.env` has the cohort-issued `AI_LOG_SERVER` + `AI_LOG_API_KEY`. Decide project stack in next sync.

### Important bugs / fixes
- **`scripts/_pyrun.sh` came from the template without the executable bit.**
  - `git diff` shows `old mode 100644` → `new mode 100755`.
  - **Decision:** keep the chmod change in the working tree but **do not commit it in this PR** — it is repo-wide noise.

### Brainstorming — open questions
- Stack: web app vs. mobile (Expo) vs. CLI? Not decided; depends on the product idea the team settles on.
- Where do personal journals live? Anh Thu's `JOURNAL-AnhThu.md` sits next to `JOURNAL.md` — we'll follow the same pattern (`JOURNAL-<name>.md`) for each teammate.

### Plan for next entry
- Record the stack pick + repo scaffolding decisions (e.g. framework, lint/format, CI) once the team has aligned.

---

## Cấu trúc branch

| Branch | Mục đích |
|--------|----------|
| `main` | Code ổn định, đã review |
| `docs` | Cập nhật tài liệu (WORKLOG, JOURNAL, README) |

---

_Cập nhật file này mỗi khi có quyết định kỹ thuật mới, phân công task, hoặc bug quan trọng._
