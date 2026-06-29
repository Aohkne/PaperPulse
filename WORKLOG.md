# WORKLOG — C2-App-069

> Ghi lại các quyết định kỹ thuật, phân công task, brainstorming và bug quan trọng.
> Use this file to record **why** a technical choice was made, not just **what** was done.

---

## 2026-06-23 — PDF Agent: module độc lập đọc & QA tài liệu PDF/.tex/.zip

### Context

Research Agent chỉ tự sinh literature review mới — không có cách nào để user upload một paper có sẵn (của mình hoặc người khác) để kiểm tra văn phong/lập luận và xác minh citation có thật hay bị bịa, trước khi tin vào nó. `pdf-agent_SPEC_2.0.md` định nghĩa module mới cho nhu cầu này, với quyết định scope quan trọng: **không tự fact-check lại output của chính Research Agent** — tránh nghịch lý trust (tool tự sinh nội dung rồi tự nghi ngờ nội dung của mình). Market precedent: Elicit/Consensus (generate) vs Scite (verify) vs Paperpal (polish) luôn tách 3 sản phẩm riêng.

### Quyết định kỹ thuật

**1. Module hoàn toàn độc lập (`backend/module/pdf_agent/`), không nối sau Research Agent:**
- Entry point riêng do user upload file, chỉ *import* service đã có (`semantic_scholar.py`/`arxiv_search.py` ở mode "lookup 1 paper" thay vì "search N"), không sửa file nào trong `research_agent/`.
- **Lý do:** giữ đúng ranh giới "generate vs verify" theo market precedent ở trên.

**2. Graph LangGraph riêng KHÔNG có `interrupt_before` nào — khác hẳn `research_agent`:**
- `format_detect → parse_document → render_bundle → batch_analysis → build_annotations → END` chạy 1 lần liên tục. Mọi tương tác user (accept/reject/dismiss, apply rewrite) xảy ra SAU khi graph chạy xong, qua `graph.update_state()` — không phải `resume()`.
- **Lý do:** không bước nào trong P0→P4 phụ thuộc quyết định user để *tiếp tục chạy* — khác Research Agent cần outline/claim-review duyệt giữa pipeline để bước sau dùng đúng input đã duyệt.

**3. Annotation anchor bắt buộc W3C TextQuoteSelector (`exact`+`prefix`+`suffix`), không offset số tuyệt đối:**
- **Lý do:** offset số sẽ trôi sai vị trí ngay khi user sửa 1 ký tự ở đoạn khác trong văn bản; quote+context (chuẩn dùng bởi Hypothesis) recover được vị trí dù text trước/sau đã đổi.

**4. `type=warning` annotation luôn `suggested_fix=None`, PATCH chặn `action=accept` cho warning:**
- **Lý do:** không có "bản sửa đúng" cho citation giả/link chết — Accept sẽ ngầm gợi ý có, gây hiểu lầm.

**5. MinerU chạy qua container riêng (`Dockerfile.mineru`), không bake chung image API chính:**
- **Lý do:** model weight MinerU nặng (~vài GB) — bake chung sẽ kéo nặng cả service API nhẹ. Tách riêng, gọi qua subprocess/HTTP tuỳ `MINERU_MODE`.

**6. `/apply` validate exact-match (`old_text in current_doc`) trước khi `str.replace()`, trả 409 nếu lệch:**
- **Lý do:** nếu user sửa tay đúng đoạn đã tô ngay lúc LLM đang trả lời rewrite, ghi thẳng patch cũ sẽ đè sai lên bản user vừa sửa.

**7. Reference verification dùng waterfall (DOI/ID exact lookup → search 3 nguồn → `rapidfuzz` multi-field → LLM judge vùng xám 0.55-0.85), tái dùng tối đa service `research_agent`:**
- Chỉ thêm hàm mới `lookup_by_doi()`/`lookup_by_id()` vào `shared/services/semantic_scholar.py` và `research_agent/services/arxiv_search.py` — không sửa `search()` cũ, không ảnh hưởng Research Agent đang chạy ổn định.

### Trade-offs chấp nhận
- Không có fallback OCR trả phí (Mathpix) khi MinerU xử lý kém — chỉ báo warning rõ cho user, không tự động escalate sang service khác.
- Checkpointer riêng schema Postgres (`pdf_agent_checkpoints`, tách khỏi `research_agent_checkpoints`) — tránh lẫn `thread_id` 2 domain, nhưng phải maintain 2 schema riêng.
- Concurrency 2 PATCH annotation cùng lúc trên 1 `doc_id` chưa xử lý — chấp nhận cho MVP single-user, không phải multi-user collaborative editing.

### Bugs quan trọng được fix trong quá trình này
- Zip-slip/path traversal nếu extract `.zip` không validate path từng entry — `extract_zip_safe()` check `os.path.realpath()` mỗi entry nằm trong `dest_dir` trước `extractall()`.
- PATCH annotation ban đầu không chặn `action="accept"` cho `warning` — thêm guard raise 400 sau khi review lại Non-goal của SPEC.
- `/apply` ban đầu không kiểm tra `old_text` còn khớp buffer hiện tại — thêm `rewrite_validator.validate()` exact-match + 409.

---

## 2026-06-(20-21) — Research Agent v2.0: migrate sang LangGraph StateGraph, multi-agent parallel pipeline, Knowledge Graph (Step ⑨bis)

### Context

`research-agent_SPEC_2.0.md` xác định 3 điểm yếu của pipeline hiện có trước khi viết lại bằng LangGraph: (1) không có intent routing thật — mọi input kể cả "hello" bị đẩy thẳng vào search; (2) single-query single-source — 1 query trên Semantic Scholar bỏ sót paper nhìn từ góc khác hoặc nằm ở database khác (LSE Study arXiv:2603.20235: chỉ 20% overlap AI-chọn vs expert-chọn); (3) các bước sinh nội dung/verify claim đáng lẽ độc lập nhau nhưng chạy tuần tự, tốn 5-10 phút không cần thiết. Đồng thời `knowledge-graph_SPEC_2.0.md` đề xuất thêm Step ⑨bis — lắp ráp lại dữ liệu pipeline đã có thành 1 graph trực quan, không tốn LLM call thêm, để literature review không còn thuần tuyến tính.

### Quyết định kỹ thuật

**1. Chuyển từ 4 endpoint rời (`api/search.py`/`snowball.py`/`verify.py`/`review.py`) sang 1 LangGraph `StateGraph` duy nhất (`backend/module/research_agent/graph/graph.py`):**
- **Lý do:** pipeline 12 bước có thứ tự phụ thuộc rõ + cần 2-3 điểm dừng cho user duyệt (plan, outline, claim review) — LangGraph checkpoint + `interrupt()` giải quyết cả state persistence và human-in-loop bằng 1 cơ chế, thay vì tự build resume logic thủ công qua nhiều endpoint.
- **Trade-off:** thêm dependency `langgraph`, cả team cần học cơ chế checkpoint/interrupt để maintain tiếp.

**2. Step 0c Plan Review — interrupt thêm TRƯỚC `parallel_search`:**
- User duyệt/sửa `sub_queries`+`sources` trước khi tốn API call search thật, đúng goal "User confirm research scope trước khi search" của SPEC 2.0.
- **Trade-off:** thêm 1 round-trip chờ user, nhưng tránh tốn search call cho research plan sai hướng.

**3. `interrupt()` gọi inline trong thân node (dynamic interrupt), không dùng `interrupt_before=[...]` tĩnh ở compile:**
- **Lý do:** cho phép node tự tính payload (research plan / outline / routing summary) rồi mới dừng, gửi đúng đúng dữ liệu đó cho frontend trong 1 lần round-trip; resume qua `Command(resume=...)`. Cách tĩnh sẽ cần thêm 1 node phụ chỉ để tính dữ liệu trước khi node bị `interrupt_before` chạy.

**4. Knowledge Graph (Step ⑨bis) build bằng `networkx` thuần, không gọi LLM:**
- Pipeline tới Step ⑨ đã sinh đủ nguyên liệu ngữ nghĩa (citation intent, theme membership, claim verdict đã verify 3-tier) — chỉ cần lắp ráp lại. Paper layer scope theo paper thật xuất hiện trong `theme_contents` (không phải toàn bộ corpus post-snowball ~600-900 bài) để graph nhỏ, đúng "visualize review" thay vì "visualize corpus search".
- **Trade-off:** Paper layer sẽ không có node cho paper "liên quan" nhưng cuối cùng không được trích trong bài — đánh đổi để graph không bị loãng.

**5. Sửa `services/snowball.py` giữ lại `citation_edges` (trước đây discard hoàn toàn):**
- **Lý do:** đây là blocker bắt buộc — không giữ field này thì Paper layer của Knowledge Graph không có cạnh `cites` nào để vẽ. `run_snowball()` đổi return type từ `list[Paper]` sang `tuple[list[Paper], list[dict]]`.

**6. Knowledge Graph hiện qua drawer/panel riêng (`KnowledgeGraphDrawer.jsx`), không phải tab cố định cạnh LaTeX viewer:**
- **Lý do:** graph cần canvas rộng cho radial layout, animation orbit tắt mặc định + tự tắt theo `prefers-reduced-motion` (WCAG 2.3.3/2.2.2) — ưu tiên accessibility hơn hiệu ứng.

### Trade-offs chấp nhận
- Checkpointer vẫn chạy SQLite local (chưa migrate Postgres) ở giai đoạn này — đủ cho dev, biết sẽ phải đổi khi deploy serverless.
- Concept layer (LLM entity extraction cho Knowledge Graph) chưa làm — chỉ 4 layer topic/theme/paper/claim, defer post-MVP theo đúng SPEC.
- Multi-source search (OpenAlex/PubMed) đã có code và wire vào `parallel_search_node`, nhưng chưa benchmark coverage thật so với baseline trước đó.

### Bugs quan trọng được fix trong quá trình này
- `cites` edge add vào graph mà không check 2 đầu đã có node — paper ngoài scope review tạo edge trỏ tới node không tồn tại, Graphology frontend crash khi load. Fix: chỉ add nếu `g.has_node(src) and g.has_node(tgt)`.
- `nx.node_link_data()` trả key `links`, Graphology cần `edges` — viết adapter map lại ở `useKnowledgeGraph.js`.
- Claim với `source_paperId` ngoài `theme_contents` tạo node mồ côi — fix bằng skip có chủ đích trong `graph_builder.py`.
- `astream_events()` miss event của node chạy trong `asyncio.gather` (`write_themes`, `verify_claims`) nếu không set `version="v2"`.

---

## 2026-06-(15-18) — Optimize literature review pipeline, thêm Admin pages, tích hợp PR #20-#26 vào develop

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
- Co-citation / bibliographic coupling chưa implement (ghi nhận trong CHANGELOG của SPEC, defer post-MVP) — cần data thực tế từ MVP để đánh giá.
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
