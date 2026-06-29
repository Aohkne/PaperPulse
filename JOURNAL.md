# JOURNAL — G069

---

## 2026-06-26 — Hotfix: research-agent trả lời sai ngôn ngữ sau merge - Lê Hữu Khoa

### Việc đã làm
- Fix `graph/nodes/intent_router.py` + `graph/nodes/reply_generator.py` — khôi phục rule "suy nghĩ và trả lời cùng ngôn ngữ với câu hỏi" (đặc biệt cho query tiếng Anh ngắn/nhiều từ viết tắt) đã bị mất khi merge.

### Bug / fix gặp phải
- **Reply trôi sang tiếng Trung/Nhật/Hàn cho query ngắn/viết tắt tiếng Anh** — nhánh guardrail tách ra từ một commit cũ hơn bản fix ngôn ngữ, nên khi merge lại vào `develop` rule thinking-language ở `intent_router` và prompt clarify/greeting ở `reply_generator` bị revert theo bản cũ.
- Fix: chép lại đúng rule ngôn ngữ vào cả 2 file, không sửa gì khác trong logic intent classification.

### Next
- Thêm test case ngắn cho rule ngôn ngữ vào eval suite — tránh regression tương tự ở lần merge song song kế tiếp.

---

## 2026-06-23 — PDF Agent: module độc lập đọc & QA PDF/.tex (.zip) - Lê Hữu Khoa

### Việc đã làm
- Dựng `backend/module/pdf_agent/` — package hoàn toàn độc lập với `research_agent/` (theo `pdf-agent_PLAN_2.0.md`/`pdf-agent_SPEC_2.0.md`): chỉ *import* service đã có (`semantic_scholar.py`, `arxiv_search.py` ở mode lookup-1-paper), không sửa file nào trong `research_agent/`.
- **Step P0** `graph/nodes/format_detect.py` — byte sniffing `%PDF` / `PK` (zip magic) / `\documentclass` để phân nhánh `pdf` / `tex_bundle` / `tex`.
- **Step P1** `graph/nodes/parse_document.py` (120 dòng) dispatch theo nhánh:
  - `services/mineru_client.py` (289 dòng) — subprocess wrapper gọi MinerU CLI, parse `content_list.json` → `Figure`/`Section`, có timeout + `proc.kill()`.
  - `services/tex_parser.py` (332 dòng) — `pylatexenc.LatexWalker` extract section, `\cite{}`+context, `\includegraphics{}`.
  - `services/zip_bundle.py` (63 dòng) — `extract_zip_safe()` validate `os.path.realpath()` từng entry nằm trong `dest_dir` *trước* `extractall()` (chặn zip-slip/path traversal), `find_main_tex()` heuristic tìm file có cả `\documentclass`+`\begin{document}`.
  - `services/pdf_parser.py` (231 dòng) — reference list thô từ MinerU → 1 LLM call dọn thành `RawCitation[]`.
- **Step P2** `graph/nodes/render_bundle.py` + `services/bundle_exporter.py` (189 dòng) + template `templates/pdf_agent_document.tex.j2` — render `main.tex` + copy `figures/` không-missing → zip.
- **Step P3** `graph/nodes/batch_analysis.py` — `asyncio.gather` 3 nhánh song song:
  - `services/critic_agent.py` (86 dòng) — 1 LLM call/section, `temperature=0`, 4 aspect cố định (clarity/terminology/flow/redundancy).
  - `services/citation_lookup.py` (187 dòng) — waterfall DOI/ID lookup → search 3 nguồn → `rapidfuzz` multi-field match → LLM judge vùng xám 0.55-0.85. Thêm hàm `lookup_by_doi()`/`lookup_by_id()` mới vào `shared/services/semantic_scholar.py` và `research_agent/services/arxiv_search.py` (không sửa `search()` cũ).
  - `services/link_checker.py` (61 dòng) — `httpx` HEAD song song, không LLM.
- **Step P4** `graph/nodes/build_annotations.py` (134 dòng) + `services/text_quote_selector.py` (51 dòng) — `build_anchor()`/`refind_anchor()` theo W3C TextQuoteSelector (`exact`+`prefix`+`suffix`), gộp 3 kết quả P3 thành `Annotation[]`; `type=warning` luôn `suggested_fix=None`.
- **Step P5** `api/selection.py` (124 dòng) — 3 endpoint `/explain`, `/rewrite`, `/apply`; `services/rewrite_validator.py` (23 dòng) validate exact-match trước khi cho ghi.
- **Step P6** `api/save.py` (127 dòng) — lưu vào bảng `reviews` có sẵn (`source_type="uploaded"`, `content_format="tex"`, `pending_annotations`); sửa `supabase/schema.sql` + `backend/api/reviews.py` cho migration additive.
- **Graph compile** `graph/graph.py` (77 dòng): `format_detect → parse_document → render_bundle → batch_analysis → build_annotations → END` — không có `interrupt_before` nào, khác hẳn `research_agent`.
- **Frontend** `frontend/src/features/pdf-agent/`: `PDFUploadZone.jsx`, `TexEditor.jsx` (129 dòng, Monaco + decorations), `AnnotationCard.jsx` (92 dòng), `SelectionToolbar.jsx`, `RewritePreview.jsx`, `useTextQuoteAnchor.js` (47 dòng, port `refind_anchor` sang JS), `usePdfAgentStore.js` (153 dòng), `pdfAgentApi.js`, trang `PDFAgentPage.jsx` (285 dòng).
- **Docker**: `Dockerfile.mineru` (37 dòng, container riêng cho MinerU self-host), sửa `Dockerfile` chính + thêm `docker-compose.dev.yml` (56 dòng) nối 2 container qua network riêng cho dev. `pyproject.toml` thêm `pylatexenc`/`mineru`/`pypdf`; frontend `npm install @monaco-editor/react monaco-editor`.

### Bug / fix gặp phải
- **MinerU cần model weight riêng (~vài GB)** — không bake chung vào image API chính (sẽ kéo nặng cả service nhẹ). Fix: tách `Dockerfile.mineru` thành container riêng, gọi qua subprocess/HTTP tuỳ `MINERU_MODE`.
- **`lookup_by_doi()`/`lookup_by_id()` chưa tồn tại** ở service `research_agent` (vốn chỉ có `search()`) — phải thêm hàm mới, kiểm tra kỹ không breaking change cho `research_agent` đang chạy ổn định.
- **PATCH annotation ban đầu không chặn `action="accept"` cho `warning`** — review lại Non-goal của SPEC ("Accept sẽ ngầm gợi ý có bản sửa đúng cho citation giả, gây hiểu lầm") → thêm guard raise 400 trong `api/annotations.py`.
- **`/apply` dùng `str.replace()` thẳng, không check `old_text` còn khớp buffer hiện tại** — nếu user sửa tay đúng lúc LLM đang trả lời rewrite, patch có thể áp nhầm đoạn đã đổi. Fix: `rewrite_validator.validate()` bắt buộc exact-match, trả 409 nếu lệch.

### Quyết định kỹ thuật
- **Không gọi `interrupt()`/`interrupt_before` nào trong graph PDF Agent** — khác pattern Research Agent vì không bước nào *cần* dữ liệu user duyệt để *tiếp tục chạy graph*; mọi tương tác (accept/reject/dismiss/apply) xảy ra sau khi graph chạy xong, qua `graph.update_state()` thay vì `resume()`.
- **Checkpointer riêng schema Postgres** (`pdf_agent_checkpoints`, tách khỏi `research_agent_checkpoints`) — 2 domain khác nhau (session nghiên cứu vs document upload), tránh lẫn `thread_id`.
- **Annotation anchor bắt buộc TextQuoteSelector**, không offset số tuyệt đối — để annotation không trôi vị trí khi user sửa đoạn khác trong văn bản.

### Next
- Đo cost thật 1 document ~60 citation/~15 section, so với ước tính SPEC (~$0.003/document nhánh .pdf).
- Test security: thử payload zip-slip thật (`../../etc/passwd`) trong môi trường container để xác nhận guard hoạt động đúng.
- Gap riêng cần patch ở `research_agent` (không phải lỗi PDF Agent): Step ⑩ Intro/Conclusion sinh sau Step ⑦/⑧ nên citation trong đó chưa qua claim verification.

---

## 2026-06-21 — Plan Review interrupt + multi-source MMR + Knowledge Graph visualization (Step ⑨bis) - Lê Hữu Khoa

### Việc đã làm
- **Step 0c Plan Review**: `graph/nodes/plan_review.py` (mới) — gọi `interrupt({"sub_queries":..., "sources":..., "plan_description":...})` ngay sau khi `intent_router` sinh research plan, dừng cho user duyệt/sửa `sub_queries`/`sources` trước khi gọi API search nào — đúng goal "User confirm research scope trước khi search" của SPEC 2.0. Nối vào `graph.py`: `intent_router → plan_review → parallel_search`.
- **`services/mmr.py`** (74 dòng, mới) — Maximal Marginal Relevance thuần Python: `MMR(d) = λ·Sim(d,query) − (1−λ)·max_{s∈selected} Sim(d,s)`, chọn greedy từng round (round 1 luôn lấy candidate relevance cao nhất). Dùng cho Step ④ Outline (MMR-20) và Step ⑤ hybrid search per-theme.
- **Multi-source search thật**: thêm `services/pubmed_search.py` (115 dòng, cho domain y sinh); update `arxiv_search.py`/`openalex.py`; sửa `parallel_search_node` gọi đủ nguồn theo `sources` đã chốt ở Plan Review.
- **`services/vector_store.py`** — cải thiện batch upsert ChromaDB cho corpus lớn hơn (600-900 bài sau snowball).
- **Knowledge Graph (Step ⑨bis)** theo `knowledge-graph_PLAN_2.0.md`/`knowledge-graph_SPEC_2.0.md`:
  - Sửa `services/snowball.py`: `run_snowball()` đổi return type `list[Paper]` → `tuple[list[Paper], list[dict]]`, giữ lại `citation_edges` (`{source, target, intent, isInfluential}`) từ response S2 references/citations — trước đây chỉ giữ `papers`, bỏ qua quan hệ cite-nhau hoàn toàn.
  - `graph/state.py` thêm field `citation_edges`, `knowledge_graph`.
  - `services/graph_builder.py` (201 dòng, mới) — `build_knowledge_graph()` dùng `networkx.MultiDiGraph`: Topic node duy nhất → Theme/Paper layer chỉ lấy paper thật xuất hiện trong `theme_contents` (không phải toàn bộ `papers` post-snowball ~600-900 bài) → Claim layer 2 edge riêng (`evidenced_by` trung tính + edge mang intent: `Claim.intent` "Supporting"/"Contrasting"/"Mentioning" map sang `supports`/`contradicts`/`mentions` — Claim model không có giá trị "Extends" nên dùng "Mentioning" thay) → `nx.node_link_data()` xuất `{nodes, edges, stats}`. Claim xét gồm `included_claims + review_claims` (loại `removed_claims`) — khớp đúng tập claim mà `export_node` dùng để bài viết và graph đồng nhất nội dung.
  - `graph/nodes/build_graph.py` — node mới chèn `route_claims → build_graph → export`.
  - `shared/models/graph.py` (45 dòng) — pydantic `GraphNode`/`GraphEdge`/`GraphStats`/`GraphResponse`.
  - API: thêm `GET /api/research/graph?thread_id=` trong `api/research.py`, đọc lại `knowledge_graph` từ checkpoint, 404 nếu chưa build.
  - Frontend: `KnowledgeGraphViewer.jsx` (295 dòng, `@react-sigma/core`), `NodeDetailCard.jsx` (225 dòng, card theo 4 type node), `radialLayout.js` (84 dòng — polar coordinate: theme=150px/paper=320px/claim=480px, lưu riêng `baseX`/`baseY`), `useKnowledgeGraph.js` (116 dòng — fetch + convert node_link JSON sang Graphology), `KnowledgeGraphDrawer.jsx` (panel riêng, không phải tab trong Review). `bun add @react-sigma/core graphology`.
- **Admin test page**: `LiteratureReviewTestingPage.jsx` (404 dòng) + `useAdminTestStore.js` (207 dòng) — chạy thử Research Agent trực tiếp từ trang Admin để debug nhanh từng step, không cần qua chat UI.

### Bug / fix gặp phải
- **`run_snowball()` đổi sang trả tuple** — phải sửa cả `graph/nodes/snowball.py` (node wrapper) để unpack đúng `(papers, edges)`, nếu không LangGraph state nhận nhầm tuple làm `snowballed_papers`.
- **`cites` edge add thẳng vào graph không check 2 đầu đã có node chưa** — paper nằm ngoài `theme_contents` (bị loại sau dedup/outline) tạo edge trỏ tới node không tồn tại, Graphology phía frontend throw lỗi khi load. Fix: `graph_builder.py` chỉ add `cites` nếu `g.has_node(src) and g.has_node(tgt)`.
- **`nx.node_link_data()` trả key `links`** nhưng Graphology/frontend cần `edges` — viết adapter nhỏ trong `useKnowledgeGraph.js` map lại trước khi load vào Graph instance.
- **Claim có `source_paperId` ngoài `theme_contents`** (paper bị loại khỏi outline sau dedup) — nếu không check sẽ tạo claim node mồ côi, không có cạnh `evidenced_by` hợp lệ. Fix: skip claim đó có chủ đích trong `graph_builder.py`.

### Quyết định kỹ thuật
- **Knowledge Graph hiện trong drawer/panel riêng** (`KnowledgeGraphDrawer.jsx`) thay vì 1 tab cố định cạnh LaTeX viewer — graph cần canvas lớn để radial layout không bị bóp méo.
- **`renderLabels: false` mặc định** cho `SigmaContainer` — ~300 node hiện label cùng lúc sẽ rất rối, thông tin chuyển hết vào `NodeDetailCard` khi click.
- **Animation "Chuyển động" (orbit quay) optional, tắt mặc định**, tự tắt theo `prefers-reduced-motion` — theo WCAG 2.3.3/2.2.2, ưu tiên accessibility hơn hiệu ứng đẹp.

### Next
- Bắt đầu PDF Agent module — đọc kỹ `pdf-agent_SPEC_2.0.md` trước, vì đây là module hoàn toàn độc lập (entry point riêng, không nối sau Research Agent).
- Đo `stats.papers` thực tế sau khi `build_graph` chạy với corpus thật — xác nhận có rơi đúng khoảng ~60-150 như SPEC ước tính không.

---

## 2026-06-20 — Research Agent v2.0: dựng LangGraph StateGraph thay flow service tuần tự - Lê Hữu Khoa

### Việc đã làm
- Tạo `backend/module/research_agent/` — package mới gồm `graph/` (`state.py`, `graph.py`, `nodes/`), `services/`, `api/`, `models/` — thay cho 4 endpoint rời cũ (`api/search.py`, `api/snowball.py`, `api/verify.py`, `api/review.py`) + `agent/*.py`.
- Định nghĩa `ResearchState` (TypedDict, 78 dòng) và `build_research_graph()` trong `graph/graph.py` (91 dòng): pipeline node nối tiếp `intent_router → reply_generator|parallel_search → dedup → snowball → embed → outline_gen → write_themes → extract_claims → verify_claims → route_claims → export`, conditional edge sau Step 0 (`greeting`/`clarify` → `reply_generator` → END, `search` → tiếp pipeline).
- Viết 12 node trong `graph/nodes/` (mỗi node là thin wrapper gọi service tương ứng) + `narrator.py` (helper emit narration step cho SSE) + `reply_generator.py` (node mới, stream `reply_token` riêng cho greeting/clarify — tách khỏi `intent_router` để giữ 2 trách nhiệm classify-vs-reply độc lập).
- Viết lại `api/research.py` (293 dòng) — endpoint `POST /api/research/stream` dùng `astream_events(version="v2")`, map `on_chain_start`/`on_chain_end`/`on_chat_model_stream` sang SSE event (`step_start`/`step_done`/`llm_token`).
- Tạo các service còn thiếu cho flow đa nguồn: `arxiv_search.py` (76 dòng), `openalex.py` (107 dòng), `dedup_utils.py` (72 dòng, priority DOI→arXiv ID→S2 paperId→title fuzzy), `latex_utils.py`, `llm_client.py`, `supabase_client.py` riêng cho module.
- Di chuyển + đổi tên service cũ vào module mới (`content_generator.py`→`content_agent.py`, `outline_generator.py`→`outline_agent.py`) — tách rõ "agent" (LLM call) khỏi service orchestration.
- Cập nhật `ReActTrace.jsx`, `ProgressTracker.jsx`, `TypingIndicator.jsx`, `ResearchPage.jsx` ở frontend khớp event schema mới (`step_start`/`step_done` có field `node` thay vì step number cứng).
- Port `backend/agent/gap_detection/*` cũ sang `backend/module/gap_detection/` cho đồng bộ cấu trúc module (chỉ đổi đường dẫn import, không đổi logic).

### Bug / fix gặp phải
- **Restructure 2 module cùng lúc (research_agent mới + gap_detection di chuyển) trong 1 commit** — dễ sót file orphan ở `backend/agent/` cũ nếu không `git status` kỹ trước khi commit.
- **`_route_after_intent` ban đầu trả thẳng `parallel_search` cho intent=`search`** — chưa tính tới việc Plan Review (Step 0c, thêm ngày 06-21) sẽ chèn vào sau, nên phải giữ kiểu trả về (`Literal[...]`) đủ tổng quát để mai sửa route đích không đổi signature.
- **`astream_events()` ban đầu miss event của node chạy trong `asyncio.gather`** (`write_themes`, `verify_claims`) — phải set `version="v2"` mới bắt đủ.

### Quyết định kỹ thuật
- **Mỗi node trong `graph/nodes/` là thin wrapper** — toàn bộ logic thật nằm ở `services/`, để unit test service được độc lập với LangGraph runtime.
- **Tách `reply_generator` thành node riêng khỏi `intent_router`** — 2 trách nhiệm khác hẳn (classify JSON vs stream câu trả lời tự nhiên), để chung 1 node khó debug khi 1 trong 2 sai.
- **Checkpointer dùng interface `BaseCheckpointSaver`** (không hardcode `SqliteSaver`) — chuẩn bị sẵn cho đổi sang Postgres sau này mà không phải sửa `graph.py`.

### Next
- Thêm Step 0c Plan Review (interrupt trước search) — hiện sub_queries/sources mới chỉ hiển thị, chưa có cơ chế user sửa trước khi search chạy thật.
- Gọi hết multi-source (OpenAlex/PubMed) trong `parallel_search_node` — service đã tạo nhưng chưa wire đủ.
- Sửa `snowball.py` giữ lại `citation_edges` trước khi build Knowledge Graph (Step ⑨bis) — đang chỉ trả `papers`, bỏ field này sẽ làm Paper layer thiếu cạnh `cites`.

---

## 2026-06-(15-18) — Optimize RAG pipeline, Admin pages, tích hợp PR #20-#26 - Lê Hữu Khoa

### Việc đã làm
- Viết `docs/research/SPEC.md` + `docs/research/PLAN.md` (đổi tên bản cũ thành `docs/research/version_1.0/`), document 6 fix cho flow ①→⑩ sau khi review lại SPEC gốc:
  - **Fix 1 — Seed selection dual-pool**: `select_seeds()` trong `snowball.py` chọn top-5 raw `citationCount` (Pool A, foundational) ∪ top-5 `citationCount/năm` (Pool B, recent impactful) thay vì 1 metric duy nhất → ~7-9 seeds sau dedup.
  - **Fix 2 — Backward filter time-decayed + isInfluential bypass**: thay flat `min_citations ≥ 5` (hardcode năm 2022) bằng threshold tương đối theo `current_year - N`, cho bài Semantic Scholar đánh `isInfluential` bypass threshold dù citations thấp.
  - **Fix 3 — Outline từ MMR-20 trên 300-400 bài** thay top-20 cosine trên 100 bài gốc, thêm bước user edit & approve outline trước khi generate content.
  - **Fix 4 — Query encoder đổi sang SPECTER2 adapter `proximity`** thay default adapter — fix asymmetric retrieval (query→paper) thay vì symmetric (paper↔paper).
  - **Fix 5 — Verification 3-tier fallback**: `/snippet/search` → arXiv HTML (`arxiv_fetcher.py`, qua `ar5iv.labs.arxiv.org`) → abstract (conservative, không bao giờ return `Supported`).
  - **Fix 6 — Citation Intent**: bỏ early-exit khi intent ≠ Supporting (citation drift thường nằm chính trong Supporting), Contrasting ưu tiên vào human review queue.
- Build endpoint mới `GET /api/research/stream` (`backend/api/research.py`, SSE) — orchestrate trọn flow ①→⑩, stream từng step (thought/action/observation) cho frontend.
- Build `ReActTrace.jsx` hiển thị trace theo màu/icon riêng cho mỗi step, và mock `BRAIN_MRI_STEPS` trong `useChatStore.js` để demo UI trước khi nối API stream thật.
- Thêm `openAccessPdf` vào toàn bộ S2 API call (search/batch/citations/references) + PDF link priority logic ở Step ⑩ (`openAccessPdf` GREEN/GOLD → ArXiv PDF → `openAccessPdf` BRONZE → DOI → trang S2).
- Build trang Admin: `backend/api/admin.py` (stats/users/activity, query PostgREST qua service-role key để bypass RLS), `require_admin` dependency (check `role` trong bảng `profiles`) trong `backend/auth/dependencies.py`, frontend `AdminLayout/DashboardPage/UserManagementPage` + `AdminRoute` guard.
- Refactor login/register/logout trong `auth.py`: gom việc ghi `login_logs` vào helper `_log_event()` dùng service-role key, log đủ 3 event type (register/login/logout) nhất quán.
- Merge & giữ đồng bộ branch `develop` ↔ `feat/T-007` qua PR #20-#26 (sync develop, auth feature, review-save, gap detection port, admin pages, db schema chat/messages/notifications) — review, resolve conflict, merge lên develop.

### Bug / fix gặp phải
- **`supabase-py` client fail với key format `sb_publishable_...` mới (lỗi `PGRST301`)** khi gọi PostgREST cho `require_admin` — fix bằng gọi `httpx` trực tiếp tới PostgREST với service-role key thay vì qua supabase-py client.
- **JWT decode chỉ accept `HS256/RS256`** — project Supabase issue token `ES256`, login bị 401 sai. Fix: thêm `ES256` vào `algorithms=[...]` trong `_decode_supabase_jwt`.
- **Snowball gọi đồng thời (`asyncio.gather`) cho tất cả seeds → bị Semantic Scholar rate-limit** (1 req/s không key). Fix: chạy sequential kèm `asyncio.sleep(0.15)` giữa mỗi seed.
- **Login log insert qua `supabase.table(...).insert()` fail im lặng** (RLS chặn user role ghi `login_logs`, try/except nuốt lỗi) — không biết bug tồn tại tới khi check DB thấy thiếu row. Fix: chuyển sang `_log_event()` bằng service-role key.

### Next
- Implement co-citation / bibliographic coupling (ghi nhận là gap trong CHANGELOG, defer post-MVP v1.1).
- Đánh giá single-hop vs 2-hop snowballing dựa trên data thực tế từ MVP.
- Nối `useChatStore.js` từ mock `BRAIN_MRI_STEPS` sang `/api/research/stream` thật khi frontend stream UI ổn định.
- Theo dõi BUG-01 (Anh Thư log trong eval 06-17) — `source: "snippet"` + `snippet: null` ở Case C, liên quan tới 3-tier fallback ở Fix 5.

---

## 2026-06-17 — T-0XX: Manual Eval — Anti-Hallucination & Citation Guardrail - Trần Nguyễn Anh Thư
### Việc đã làm
- Chạy 4 smoke tests (GET /health, POST /api/search, POST /api/chat, GET /api/outline/approve) — tất cả PASS trước khi vào test chính.
- Design và execute 6 test cases tập trung vào 2 mảng: **hard hallucination** (hệ thống có bịa paper ID không?) và **citation guardrail** (claim verify có đúng rule không?).
- TC-01: Test query topic cực hẹp (`quantum GNN + TDA + drug-target`) — verify 3 paper IDs trên Semantic Scholar, xác nhận 0 fabricated ID.
- TC-02: Test `/api/chat` không có RAG làm baseline — verify 2 DOIs, xác nhận citation drift (DOI thật nhưng sai domain). Documented là **expected failure** để so sánh với pipeline đầy đủ.
- TC-03: Test RAG pipeline end-to-end với query `RAG for question answering` — verify paper IDs trong `(Source: ...)` của output. TC-03c verify `/api/claims/verify` đủ 5 fields theo SPEC.
- TC-04: Dùng tên tác giả giả (`Zhao Wentian`) — xác nhận pipeline trả về 0 papers, không bịa nội dung.
- TC-05: Test topic controversial (`LLMs surpassing human on medical exams`) — verify output có cả pro lẫn contra perspective. TC-05b verify claim trái chiều với `/api/claims/verify`.
- TC-06: Test rule "status không bao giờ = supported khi không có evidence" — dùng paper không có snippet.
- Tổng hợp kết quả vào `eval/EVAL_EVIDENCE.md` và commit lên repo.
### Bug / issue gặp phải
- **TC-06 lần đầu: không trigger được Case C** — mọi response đều trả về `source: "snippet"` dù `snippet: null`. Không biết đây là bug hay Case C chưa implement → báo dev. Re-test với paper khác (`57b47dfb...`) → `status: "unsupported"`, rule không bị vi phạm → PASS.
- **`source: "snippet"` + `snippet: null`** — inconsistency vẫn còn trong response. Core rule đúng nhưng field `source` misleading. Logged là BUG-01 (Low severity), báo dev.
- **TC-05b ban đầu judge là PARTIAL** vì `intent: null` — sau khi clarify với dev mới biết pass criteria chỉ cần `human_review: true` + `low_confidence: true` + `status ≠ supported`. Không cần verify intent detection. → Update verdict thành PASS.
- **TC-04: "Pipeline error at outline step"** xuất hiện ở một số run, không consistent — không reproduce được, note lại nhưng không block test.
### Học được
- **Clarify pass criteria với team trước khi judge verdict** — TC-05b mất thời gian vì tự assume criteria từ SPEC thay vì hỏi. Một câu hỏi sớm tiết kiệm cả buổi.
- **Expected failure cũng có giá trị** — TC-02 FAIL không phải bug cần fix, mà là evidence chứng minh RAG guardrail necessary. Documenting *tại sao* fail quan trọng hơn verdict.
- **Verify bằng Semantic Scholar URL** (`/paper/{id}`) là cách nhanh nhất để confirm paper ID thật — không cần đọc full paper, chỉ cần confirm tồn tại.
- Testing một hệ thống RAG khác với testing API thông thường: output không deterministic, cần verify *property* của output (ID có thật không, status đúng không) thay vì match exact string.
### Quyết định kỹ thuật
- **Dùng `/api/research/stream` cho TC-01 và TC-04** thay vì gọi từng endpoint riêng — stream output cho đủ context để verify behavior end-to-end, không bị miss edge case giữa các bước.
- **TC-02 là baseline, không phải bug** — quyết định document rõ trong file thay vì bỏ qua, để reviewer hiểu design intent của guardrail.
- **BUG-01 giữ lại ở Low severity** thay vì escalate — core rule không bị vi phạm, inconsistency chỉ ở response field. Không block Gate 2.
### Next
- Commit `eval/EVAL_EVIDENCE.md` lên repo (branch `develop` hoặc theo convention của team).
- Báo dev về BUG-01 để confirm expected behavior hay cần fix.
- Nếu còn thời gian trước deadline: test Case B (claim verify qua ArXiv ID) để có full coverage A/B/C trong SPEC.

---

## 2026-06-(14-15) — Dọn LangChain, tách agent layer, fix bugs khởi động - Lê Hữu Khoa

### Việc đã làm
- Xoá `backend/agents/` (toàn bộ LangGraph/opendeepresearch), `backend/prompts.py`, `backend/utils.py`.
- Tạo `backend/agent/` mới gồm 5 module LLM thuần: `outline.py`, `content.py`, `claim_extractor.py`, `verifier.py`, `chat.py`.
- Refactor 4 service files thành orchestration-only — không còn prompt nào nằm trong services.
- Thêm Supabase Auth: `backend/auth/`, `backend/api/auth.py` (register / login / logout / refresh / me), `backend/services/supabase_client.py`, `supabase/schema.sql`.

### Bug / fix gặp phải
- **`chromadb.PersistentClient | None` → `TypeError` at import** — `PersistentClient` là function, không phải class, nên `|` fail ở runtime. Fix: `from __future__ import annotations`.
- **`uvicorn.run("src.main:app", ...)` → module not found** — package đã đổi từ `src` → `backend` nhưng dòng này bị bỏ sót. Fix: đổi thành `"backend.main:app"`.
- **`ModuleNotFoundError: No module named 'gotrue'`** trong conda env `ml` — fix bằng `TYPE_CHECKING` guard để tránh runtime import.
- **`SUPABASE_URL` dùng PostgreSQL URL** 

### Next
- Confirm xoá `langchain*`, `langgraph`, `tavily-python`, `mcp` khỏi `pyproject.toml`.
- Wire Supabase Auth vào các protected endpoints.
- Test end-to-end flow ①→⑩ với topic thực.

---
## 2026-06-15 — T-007: Polish auth UI + theme support - Trần Nguyễn Anh Thư

### Việc đã làm
- **Thay hardcoded color bằng CSS variables** trong `LoginPage.jsx` và `SignupPage.jsx`: toàn bộ background, input, button, label, text đều dùng `var(--color-paper-bg/dark/mid/surface)` thay vì `#FFFCF0`, `#291100`, `#657733`, `#D7E3A4` — giờ tự động đổi theo light/dark mode.
- **Logo theme-aware** trên cả hai trang auth: import `useThemeStore`, resolve `isDark`, render `paperpulse-logo_dark.png` hoặc `paperpulse-logo_light.png` tương ứng.
- **LandingPage header sau khi đăng nhập**: import `useAuthStore`, khi `isAuthenticated === true` thay cụm "Log in + Get Started" bằng một nút "Go to App →" dẫn thẳng vào `/app`.
- **Eye icon ẩn/hiện password**: thêm vào `LoginPage` (password) và `SignupPage` (password + confirm password) dùng `mdi:eye` / `mdi:eye-off` từ `@iconify/react`.
- **Confirm password field** trong `SignupPage`: thêm field riêng, validate match + min length 6 trước khi submit.
- **Verification screen — link mở Gmail**: nút "Open email app →" dùng `href="https://mail.google.com"` mở tab mới, kèm nút phụ "Go to sign in" để fallback.
- **Dynamic redirectTo**: khi register, frontend truyền `window.location.origin + '/login'` làm `redirect_to` → backend pass vào Supabase `sign_up` qua `options.email_redirect_to`. Sau khi verify email, user về đúng domain (tự động đúng khi deploy).
- **Favicon PaperPulse**: thay SVG bolt tím (mặc định Vite) bằng SVG chữ "P" trên nền nâu `#291100`. `index.html` thêm 2 `<link rel="icon">` với media query `prefers-color-scheme` trỏ vào `paperpulse-logo_light/dark.png` cho browser hỗ trợ.

### Bug / fix gặp phải
- **`onFocus/onBlur` dùng string literal CSS variable** trong inline event handler — `e.target.style.borderColor = 'var(--color-paper-mid)'` hoạt động bình thường vì inline style resolve CSS variable ở runtime qua computed style.
- **`handleResponse` trả 202 như success** — backend raise `HTTPException(202, …)` khi cần email confirm, `res.ok` = true nên không throw. `SignupPage` không dùng return value của `register()` nên flow hiển thị verification screen vẫn đúng; không cần fix.

### Quyết định kỹ thuật
- **Không tạo `PasswordInput` component riêng** — eye toggle chỉ dùng ở 3 chỗ (login + 2 field signup), inline đủ gọn, không cần abstraction.
- **`redirectTo = window.location.origin + '/login'`** thay vì chỉ `origin` — user sau khi verify email được drop thẳng vào login page, không phải landing.
- **Gmail hardcode** thay vì `mailto:` — `mailto:` mở native mail app có thể không cài; Gmail web là fallback an toàn hơn cho target user sinh viên.

### Next
- Thêm route `/auth/callback` hoặc query param `?verified=1` trên `/login` để hiện toast "Email verified — please sign in".
- Cân nhắc thêm Supabase `redirectTo` vào allowed list trong dashboard khi deploy lên Railway.

---

## 2026-06-15 — T-008: Build giao diện chính PaperPulse - Trần Nguyễn Anh Thư

### Việc đã làm
- Phân tích codebase branch `develop`: đọc `SurveyPage.jsx`, `useSurveyStore.js`, `ResultsList.jsx` để hiểu pattern đang có trước khi code.
- Quyết định redesign toàn bộ UI từ paradigm *search + results list* sang *chatbot interface* — phù hợp hơn với product vision.
- Build design system mới trong `index.css`: bảng màu Classic Minimalism (`#FBF2DA`, `#291100`, `#657733`, `#D7E3A4`), import font Inknut Antiqua.
- Scaffold các component chính: `ChatLayout`, `Sidebar` (collapse thành icon bar), `ChatMessage`, `MessageList`, `ChatInput`, `ChatPage`.
- Thêm Knowledge Graph panel (SVG force-directed, mock data) toggle bằng icon button.
- Build `LandingPage`, `LoginPage`, `SignupPage` với mock auth (Zustand store).
- Setup React Router: `/` → Landing, `/login`, `/signup`, `/app` (protected route).
- Thêm resize handle kéo được giữa 3 panel bằng vanilla JS mouse events (không dùng thư viện — `react-resizable-panels` bị bug layout).
- PR lên branch `feat/T-008-ui` → base `develop`.

### Bug / fix gặp phải
- **`react-resizable-panels` không giữ đúng default size** — thư viện load lại layout cũ từ localStorage, `defaultSize` mới không có tác dụng. Fix: bỏ thư viện, tự implement resize bằng `mousedown/mousemove/mouseup`.
- **Sidebar có `width: 220px` hardcode bên trong** — khi ChatLayout đổi `sidebarW%` thì sidebar không co lại. Fix: lift collapsed state lên ChatLayout, Sidebar dùng `width: 100%`.
- **`userSelect: 'none'` trên root div** làm toàn bộ text trong app không select/copy được. Fix: chỉ apply khi đang drag (dùng `isDragging` state).
- **Toggle graph panel tạo gap thừa** — toggle strip nằm giữa chat và resize handle. Fix: strip di chuyển vào trong GraphPanel khi graph mở, thay bằng absolute button khi graph đóng.
- **Sau login nhảy thẳng vào session cũ** thay vì welcome screen. Fix: gọi `newSession()` trước khi `navigate('/app')`.

### Học được
- Frontend và backend có thể làm song song hoàn toàn nhờ mock data — UI define data shape, backend chỉ cần match.
- Vibecoding với AI rất hiệu quả nhưng cần hiểu *tại sao* bug xảy ra trước khi đưa prompt fix, không thì fix mù sẽ loop.
- Khi gặp bug layout phức tạp, đơn giản hoá trước (hardcode tỉ lệ cố định) rồi mới add tính năng nâng cao (resize) sau.

### Quyết định kỹ thuật
- **Không dùng `react-resizable-panels`** — vanilla mouse events đủ dùng, ít dependency hơn, không có hidden state bug.
- **Mock auth bằng Zustand** thay vì integrate Supabase Auth ngay — chờ backend confirm endpoint rồi swap.
- **Knowledge Graph dùng plain JS physics** (không import D3) — đủ cho demo, giảm bundle size.

### Next
- Đợi backend `/api/survey/search` xong → swap mock `sendMessage()` trong `useChatStore` bằng `fetch` thật.
- Add resizable panel persistence (localStorage) sau khi layout ổn định.
- Integrate Supabase Auth vào `useAuthStore` khi backend wire xong.

---

## 2026-06-08 — Setup Claude CLI hooks trên macOS - Lê Hữu Khoa

### Việc đã làm
- Chạy `/hooks` trong Claude Code để xem dialog hooks → dismiss (đã có sẵn cấu hình trong `.claude/settings.json`, không cần thêm thủ công).
- Xác nhận `.claude/settings.json` đã wire 3 hook events cho logging:
  - `UserPromptSubmit`
  - `PostToolUse` (matcher `.*`)
  - `Stop`
  - Cả 3 đều gọi `bash scripts/_pyrun.sh scripts/log_hook.py --tool=claude` → Python launcher auto-detect interpreter.
- **Fix `_pyrun.sh` executable bit:**
  - File đến từ template (`42f8720`) ở mode `100644`, cần `100755` để Git có thể spawn trực tiếp.
  - Đã `chmod +x scripts/_pyrun.sh` để hook chạy được khi `bash` invoke.
  - **Quyết định:** chưa commit thay đổi mode này trong PR — repo-wide noise, để dành cho một cleanup commit riêng.

### Quyết định kỹ thuật
- **Dùng Python launcher (`_pyrun.sh` / `_pyrun.cmd`) làm contract cho mọi hook helper.**
  - Lý do: cross-platform, không phụ thuộc alias `python3 → python` trên máy từng thành viên.
  - Hooks nào trong tương lai cũng invoke qua `_pyrun.*`, không hard-code interpreter.
- **Mặc định trust `.claude/settings.json` của template.** Không tự thêm/sửa hook trừ khi có yêu cầu rõ ràng.

### Bug / fix gặp phải
- **`scripts/_pyrun.sh` không có executable bit khi clone từ template trên macOS.**
  - Triệu chứng tiềm ẩn: hook `bash scripts/_pyrun.sh …` fail với `Permission denied` nếu gọi trực tiếp (không qua `bash`).
  - Fix: `chmod +x scripts/_pyrun.sh`.
  - **Lưu ý:** chưa commit — tránh pollute PR hiện tại với một chmod change.

### AI logging end-to-end fix (cùng ngày)
- Kiểm tra trạng thái submit log → phát hiện 2 vấn đề chặn submit lên server (log chỉ nằm local ở `.ai-log/session.jsonl`):
  1. **`python-dotenv` chưa cài** → `submit_log.py` gọi `load_dotenv()` fail im lặng → `AI_LOG_SERVER` rỗng → pre-push hook báo `[ai-log] AI_LOG_SERVER not set — skipping submission.`
  2. **Python 3.14 macOS thiếu cert bundle** → khi dotenv fix xong, hook gọi được tới server nhưng fail `SSL: CERTIFICATE_VERIFY_FAILED`.
- **Fix #1:** `python3 -m pip install --user --break-system-packages python-dotenv` (system python3 là interpreter `_pyrun.sh` dùng — không phải `.venv`).
- **Fix #2:** chạy `/Applications/Python 3.14/Install Certificates.command` (script có sẵn của python.org build) → symlink certifi bundle vào `~/.certifi/cacert.pem` cho OpenSSL.
- **Verify:** `bash scripts/_pyrun.sh scripts/submit_log.py` → `[ai-log] Submitted 1 entries → 202` (server accepted). Entry tự động rotate vào `.ai-log/archive/2026-06-08.jsonl`.
- **Lưu ý:** `.venv` đã tạo nhưng `_pyrun.sh` ưu tiên `python3` system, không tìm trong `.venv/bin`. Tạm thời ổn — nếu sau này thêm deps thì cân nhắc sửa `_pyrun.sh` ưu tiên `.venv/bin/python`.

### Open questions
- Team chưa quyết stack (web/mobile/CLI) — sẽ note vào `WORKLOG.md` sau khi align.
- Có cần thêm hook cho `SessionStart` / `Notification` không? Hiện tại 3 event trên đã đủ cho AI usage logging theo yêu cầu khoá học.

### Next
- Đợi team align stack, sau đó bắt đầu scaffold (FastAPI? Expo? CLI?) trên branch riêng.
- Cleanup commit riêng cho `_pyrun.sh` executable bit khi có dịp.

---

## 2026-06-10 — Scaffold frontend (Vite + React) + Zustand store - Lê Hữu Khoa

### Việc đã làm
- Cài **Bun 1.3.14** qua official script (`curl -fsSL https://bun.sh/install | bash`) — Bun chưa có sẵn trên máy, cài xong PATH được thêm vào `~/.zshrc`.
- Scaffold **Vite + React 19** template vào `/Users/huuw_khoa/Desktop/Project/Vinuni/C2-App-069/frontend/`:
  - `bun create vite frontend-tmp --template react` → rsync nội dung vào `frontend/` (vì `frontend/` đã tồn tại rỗng trong monorepo, Bun không overwrite).
  - `bun install` cho base deps (~5 phút vì lockfile Vite mới).
- Cài thêm runtime + dev deps bằng `bun add`:
  - Runtime: `zustand@5.0.14`, `@iconify/react@6.0.2`, `clsx@2.1.1`.
  - Dev: `tailwindcss@4.3.0`, `@tailwindcss/vite@4.3.0`.
- Cấu hình **Tailwind v4**:
  - Thêm `tailwindcss()` plugin trong `vite.config.js`.
  - `src/index.css` chỉ cần `@import "tailwindcss";` + block `@theme` cho brand color (purple `#7c3aed` family) và font — không cần `tailwind.config.js` (v4 zero-config).
- Refactor `src/` sang **feature-based structure** (xóa `App.css`, `assets/` mẫu, file `App.jsx` stub):
  ```
  src/
  ├── components/   (Button.jsx, Input.jsx — dùng chung)
  ├── features/survey/  (SearchBar.jsx, ResultsList.jsx)
  ├── hooks/        (chưa dùng, để sẵn)
  ├── layouts/      (AppLayout.jsx — header/main/footer)
  ├── pages/        (SurveyPage.jsx — wire store ↔ UI)
  ├── store/        (useSurveyStore.js — Zustand)
  └── utils/        (cn.js — clsx wrapper)
  ```
- Cập nhật `vite.config.js`: thêm alias `@` → `src/` và dev proxy `/api` → `http://localhost:8000` (FastAPI backend).
- Tạo **`useSurveyStore`** (Zustand) cho feature Literature Review:
  - State: `query`, `results`, `status` (`idle`/`loading`/`success`/`error`), `error`, `history` (capped 10).
  - Actions: `setQuery`, `runSearch` (hiện mock với TODO gọi `/api/survey/search`), `clearResults`, `reset`.
  - Page subscribe đúng field bằng `useSurveyStore((s) => s.query)` — tránh re-render dư.
- **Verify build:** `bun run build` → 28 modules transformed, CSS 14 kB, JS 215 kB, build trong ~75ms.
- **Verify AI logging:** `.ai-log/session.jsonl` đã có 21 entries cho session hiện tại, archive ngày trước cũng còn → pipeline hoạt động bình thường.

### Quyết định kỹ thuật
- **Tailwind v4 + `@tailwindcss/vite`** thay vì v3 + PostCSS plugin — zero-config (không cần `tailwind.config.js` / `postcss.config.js`), build nhanh hơn, syntax `@theme` trực tiếp trong CSS.
- **Dùng arrow function + functional component** cho toàn bộ components (kể cả `Input` dùng `forwardRef` vẫn trả arrow function) — theo convention trong system prompt.
- **`cn()` helper** (wrap `clsx`) ở `utils/cn.js` thay vì import `clsx` trực tiếp — single import path cho mọi chỗ cần conditional className.
- **`AppLayout` mặc định render `<SurveyPage />` qua `children ?? <SurveyPage />`.**
  - Lý do: hiện single-page, nhưng sau này gắn React Router thì chỉ cần pass page qua `children` ở router outlet — không phải refactor layout.
- **Store chia theo domain (`useSurveyStore`), không gom `useStore` tổng.**
  - Lý do: Zustand selector cho phép subscribe đúng field, scale tốt khi thêm feature khác (`useAuthStore`, `useUIStore`…).
- **Mock `runSearch` thay vì gọi API thật ngay.**
  - Lý do: backend FastAPI chưa có endpoint survey search; mock cho phép wire UI end-to-end sớm, khi backend ready chỉ thay 1 block `TODO` trong store.

### Bug / fix gặp phải
- **`bun create vite` không ghi đè thư mục đã tồn tại** (kể cả rỗng) → phải scaffold ra `frontend-tmp/` rồi rsync vào.
  - Lý do: Bun check dest dir tồn tại và thoát, không cho overwrite.
  - Fix: scaffold vào tmp → `rsync -a frontend-tmp/ frontend/` → `rm -rf frontend-tmp`.
- **zsh không có `shopt -s dotglob`** nên pattern `mv .[!.]*` ban đầu fail.
  - Fix: dùng `rsync` thay thế — xử lý dotfiles tự động.
- **`File has been modified since read`** khi Write `package.json` lần đầu (do `bun add` đã update nó trong khi tôi đang đọc).
  - Fix: Read lại file → Write lại với nội dung mới nhất.

### Open questions
- Có cần thêm **React Router** ngay từ đầu không? Hiện single-page (Survey) đã đủ, nhưng nếu backend sẽ có nhiều flow (search, summary, gap-detection, export) thì setup router sớm đỡ refactor.
- **Proxy `/api` → `http://localhost:8000`** chỉ hoạt động khi chạy `bun dev` — production build cần backend serve frontend hoặc config CORS riêng. Để dành cho bước Docker.
- Có cần **TypeScript** không? Convention hiện tại trong system prompt nói JS + JSX, nhưng nếu team khác dùng TS thì align sớm.

### Next
- Tạo **API client thật** (`src/utils/api.js` hoặc `src/services/surveyApi.js`) thay thế TODO trong `useSurveyStore.runSearch` — call `POST /api/survey/search`.
- Commit scaffold frontend lên branch `feat/config-pipeline` (đang làm việc) — chia thành 2 commit: (1) Vite scaffold + deps, (2) feature-based refactor + Survey store, để reviewer dễ diff.

---

## 2026-06-07 — Khởi tạo repo (tham khảo WORKLOG)

Đã đọc qua 2 entry setup trong `WORKLOG.md` (Windows/Antigravity + macOS/Claude CLI) để hiểu context chung. Mọi quyết định chung của team ghi ở WORKLOG; journal này chỉ ghi việc cá nhân + bug mình gặp.

---

_Cập nhật journal mỗi khi có setup/fix cá nhân, học được gì mới, hoặc quyết định riêng trong ngày._
