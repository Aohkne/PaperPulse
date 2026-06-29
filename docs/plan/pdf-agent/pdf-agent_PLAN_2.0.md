# PLAN_2.0.md — PDF Agent

> Derived from `pdf-agent_SPEC_2.0.md` | MVP: Full Flow P0→P6 | Env: Local Development
> Module **độc lập** — không sửa `research-agent_PLAN_2.0.md`, chỉ import service từ đó

---

## 1. Tech Stack

| Layer | Technology | Ghi chú |
|---|---|---|
| **PDF parsing/OCR** | **MinerU** (`mineru` CLI, self-host, subprocess) | MỚI — không có fallback trả phí (đã bỏ Mathpix, xem SPEC Non-goals); PDF MinerU xử lý kém sẽ báo lỗi/warning cho user |
| **.tex parsing** | `pylatexenc` (`LatexWalker`) | MỚI |
| **Zip bundle (.tex_bundle)** | `zipfile` (stdlib) + path-traversal guard viết tay | MỚI |
| **Fuzzy citation match** | `rapidfuzz` | **Đã có** (research_agent) — tái dùng |
| **Academic lookup** | `semanticscholar`, `arxiv`, `httpx` (OpenAlex) | **Đã có** (research_agent `services/`) — tái dùng ở mode "lookup 1 paper" thay vì "search N" |
| **Link liveness check** | `httpx.AsyncClient` (đã có) | Tái dùng client, chỉ thêm hàm `HEAD` |
| **LLM** | `openai/gpt-oss-120b` qua NVIDIA NIM, `langchain-openai` `ChatOpenAI` | **Đã có** — tái dùng instance, đổi `temperature`/system prompt theo node |
| **Pipeline P0→P4** | LangGraph `StateGraph` riêng (`PDFAgentState`) | MỚI — graph riêng, KHÔNG chung `ResearchState`; không có `interrupt_before` (không có quyết định cần pause giữa batch) |
| **Pipeline P5/P6** | FastAPI endpoint thuần, KHÔNG phải graph node | MỚI — on-demand single call, đọc/sửa checkpoint qua `graph.update_state()` thay vì re-run graph |
| **Checkpointer** | LangGraph `SqliteSaver`, file riêng `pdf_agent_checkpoints.db` | MỚI — tách khỏi `checkpoints.db` của research_agent để tránh lẫn `thread_id` giữa 2 domain khác nhau (session nghiên cứu vs document upload) |
| **Streaming** | SSE qua `astream_events()` cho P0→P4 | Tái dùng pattern `research-agent_PLAN_2.0.md` §4 |
| **DB lưu review** | Bảng `reviews` (Supabase) | **Đã có** — mở rộng schema (`ALTER TABLE`, xem §6) |
| **Frontend editor** | Monaco Editor (`@monaco-editor/react`) | MỚI — cần Decorations API cho highlight inline `suggest`/`warning` |
| **LaTeX render** | Jinja2 | **Đã có** — viết template riêng theo style `latex_exporter.py`, không sửa template của research_agent |
| **Package manager** | `pyproject.toml` (uv) | **Đã có** — thêm dependencies vào group hiện có |
| **Containerization** | Docker — 1 container chung với backend (MVP, chưa tách microservice riêng cho MinerU) | MỚI — base image Python CPU-only (khớp `MINERU_DEVICE_MODE="cpu"`), model weight MinerU **bake sẵn lúc build image** (`RUN` step), KHÔNG tải lúc runtime — xem Dockerfile mẫu §8 |

---

## 2. Environment Variables

```env
# ─── Tái dùng từ .env research-agent (KHÔNG khai báo lại) ───
# LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, SEMANTIC_SCHOLAR_API_KEY, OPENALEX_EMAIL

# ─── PDF Agent riêng ───
# Cả 2 path dưới đây PHẢI mount vào Docker volume bền khi deploy — nếu không,
# container restart/redeploy sẽ mất toàn bộ checkpoint + document đang xử lý
# (annotation chưa resolve, bundle chưa save vào My Review). Xem §9 Rủi ro.
PDF_AGENT_CHECKPOINT_DB="./data/pdf_agent_checkpoints.db"
PDF_AGENT_OUTPUT_DIR="./data/pdf_agent_output"        # {doc_id}/bundle.zip + main.tex đã extract + figures/

# MinerU (self-host, chạy subprocess)
MINERU_BIN="mineru"                                    # hoặc path đầy đủ nếu không có trong PATH
MINERU_TMP_DIR="./data/mineru_tmp"
MINERU_DEVICE_MODE="cpu"                               # "cuda" nếu có GPU — tăng tốc layout detection
MINERU_TIMEOUT_S=120                                   # PDF tối đa 60 trang, timeout tránh treo subprocess

# Temperature riêng theo role (khác set của research-agent)
CRITIC_TEMPERATURE=0
EXPLAIN_TEMPERATURE=0.3
REWRITE_TEMPERATURE=0.5
PDF_JUDGE_TEMPERATURE=0

# Guardrails — sync với PDF_AGENT_GUARDRAILS trong SPEC
PDF_AGENT_MAX_FILE_SIZE_MB=20
PDF_AGENT_MAX_PAGES=60
PDF_AGENT_MAX_CITATIONS_VERIFY=150
PDF_AGENT_MAX_SECTIONS_CRITIC=20
PDF_AGENT_CITATION_LOOKUP_TIMEOUT_S=10
PDF_AGENT_LINK_CHECK_TIMEOUT_S=5
PDF_AGENT_ANCHOR_CONTEXT_CHARS=32
PDF_AGENT_MATCH_THRESHOLD_HIGH=0.85
PDF_AGENT_MATCH_THRESHOLD_LOW=0.55
```

---

## 3. LangGraph State & Graph

### PDFAgentState (graph riêng — không thêm field vào `ResearchState`)

```python
# module/pdf_agent/graph/state.py
from typing import TypedDict, Literal

class TextQuoteSelector(TypedDict):
    exact: str
    prefix: str
    suffix: str

class Figure(TypedDict):
    image_path: str
    caption: str | None
    label: str | None
    anchor: TextQuoteSelector | None
    page_number: int | None
    missing: bool

class Section(TypedDict):
    title: str
    raw_latex: str
    paragraph_ids: list[str]

class RawCitation(TypedDict):
    key: str | None
    raw_text: str
    guessed_title: str | None
    guessed_authors: list[str] | None
    guessed_year: int | None
    guessed_doi_or_url: str | None

class Annotation(TypedDict):
    id: str
    type: Literal["suggest", "warning"]
    anchor: TextQuoteSelector
    aspect: str
    comment: str
    suggested_fix: str | None
    evidence: dict | None
    status: Literal["pending", "accepted", "rejected", "dismissed"]

class PDFAgentState(TypedDict):
    doc_id: str
    input_format: Literal["pdf", "tex", "tex_bundle"]
    raw_file_path: str

    # ── Step P1 ──
    sections: list[Section]
    raw_citations: list[RawCitation]
    figures: list[Figure]

    # ── Step P2 ──
    bundle_path: str                     # .zip: main.tex + figures/
    main_tex_path: str                   # extracted main.tex, mutate trực tiếp khi Apply

    # ── Step P3/P4 ──
    annotations: list[Annotation]

    # ── Step P6 ──
    review_id: str | None

    error: str | None
```

### Graph Definition

```python
# module/pdf_agent/graph/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from module.pdf_agent.graph.state import PDFAgentState
from module.pdf_agent.graph.nodes import *

def build_pdf_agent_graph():
    g = StateGraph(PDFAgentState)

    g.add_node("format_detect",   format_detect_node)     # Step P0
    g.add_node("parse_document",  parse_document_node)    # Step P1 (rẽ nhánh nội bộ theo input_format)
    g.add_node("render_bundle",   render_bundle_node)      # Step P2
    g.add_node("batch_analysis",  batch_analysis_node)     # Step P3 (asyncio.gather P3a+P3b+P3c nội bộ)
    g.add_node("build_annotations", build_annotations_node) # Step P4

    g.set_entry_point("format_detect")
    g.add_edge("format_detect",  "parse_document")
    g.add_edge("parse_document", "render_bundle")
    g.add_edge("render_bundle",  "batch_analysis")
    g.add_edge("batch_analysis", "build_annotations")
    g.add_edge("build_annotations", END)

    # KHÔNG có interrupt_before — không có quyết định cần user pause giữa P0→P4.
    # Approval của user (accept/reject/dismiss, apply rewrite) xảy ra SAU khi graph chạy xong,
    # qua endpoint riêng dùng graph.update_state() — không phải resume() như research_agent.
    memory = SqliteSaver.from_conn_string(PDF_AGENT_CHECKPOINT_DB)
    return g.compile(checkpointer=memory)
```

**Vì sao không dùng `interrupt()` như research_agent:** research_agent cần user duyệt outline/claims GIỮA pipeline để các step sau dùng đúng input đã duyệt. PDF Agent không có bước nào phụ thuộc vào quyết định user để TIẾP TỤC chạy — P0→P4 chạy 1 lần xong hết, rồi user tương tác (accept/reject/explain/rewrite) với *kết quả đã có*, không cần graph "chờ" giữa đường.

**Cách P5/P6 sửa state mà không re-run graph:**

```python
# Đọc state hiện tại
config = {"configurable": {"thread_id": doc_id}}
current = graph.get_state(config).values

# Sửa 1 annotation (accept/reject/dismiss) — KHÔNG gọi lại graph.astream_events()
new_annotations = [
    {**a, "status": "accepted"} if a["id"] == annotation_id else a
    for a in current["annotations"]
]
graph.update_state(config, {"annotations": new_annotations})
```

---

## 4. SSE Event Protocol (P0→P4 — tái dùng schema của research-agent)

```typescript
// Tái dùng type SSEEvent đã định nghĩa ở research-agent_PLAN_2.0.md §4 — không định nghĩa lại
// Chỉ thêm node label mới:
const PDF_AGENT_NODE_LABELS = {
  format_detect:     "Nhận diện định dạng file...",
  parse_document:    "Phân tích cấu trúc văn bản...",
  render_bundle:     "Dựng file .tex editable...",
  batch_analysis:    "Kiểm tra văn phong + citation song song...",
  build_annotations: "Tổng hợp gợi ý + cảnh báo...",
};
```

Ví dụ stream khi upload xong:
```
data: {"type":"step_start","node":"format_detect","label":"Nhận diện định dạng file..."}
data: {"type":"step_done","node":"format_detect","stats":{"input_format":"pdf"}}

data: {"type":"step_start","node":"parse_document","label":"Phân tích cấu trúc văn bản..."}
data: {"type":"step_done","node":"parse_document","stats":{"sections":14,"citations":58,"figures":6}}

data: {"type":"step_start","node":"batch_analysis","label":"Kiểm tra văn phong + citation song song..."}
data: {"type":"step_done","node":"batch_analysis","stats":{"verified":49,"mismatch":5,"not_found":4,"broken_links":2}}

data: {"type":"step_done","node":"build_annotations","stats":{"total_annotations":31}}
data: {"type":"done"}
```

---

## 5. Project Structure

```
backend/module/
├── research_agent/                      # KHÔNG sửa — chỉ import services từ đây
│   └── services/
│       ├── semantic_scholar.py          # tái dùng cho citation lookup
│       ├── openalex.py                  # tái dùng
│       ├── arxiv_search.py              # tái dùng
│       └── citation_verifier.py         # tái dùng pattern LLM judge (Step ⑧)
│
└── pdf_agent/                           # ── Module MỚI ──
    ├── __init__.py
    │
    ├── graph/
    │   ├── __init__.py
    │   ├── state.py                     # PDFAgentState [MỚI]
    │   ├── graph.py                     # build_pdf_agent_graph() [MỚI]
    │   └── nodes/
    │       ├── __init__.py
    │       ├── format_detect.py         # Step P0 [MỚI]
    │       ├── parse_document.py        # Step P1 — dispatch 3 nhánh [MỚI]
    │       ├── render_bundle.py         # Step P2 [MỚI]
    │       ├── batch_analysis.py        # Step P3 — asyncio.gather P3a/b/c [MỚI]
    │       └── build_annotations.py     # Step P4 [MỚI]
    │
    ├── services/
    │   ├── __init__.py
    │   ├── tex_parser.py                # pylatexenc wrapper — sections, citations, \includegraphics [MỚI]
    │   ├── zip_bundle.py                 # extract_zip_safe(), find_main_tex(), resolve_figure_paths() [MỚI]
    │   ├── mineru_client.py              # subprocess wrapper, parse content_list.json → Figure/Section [MỚI]
    │   ├── text_quote_selector.py       # build_anchor(), refind_anchor() — TextQuoteSelector logic [MỚI]
    │   ├── citation_lookup.py            # waterfall cascade — GỌI research_agent.services ở mode lookup [MỚI]
    │   ├── critic_agent.py               # Step P3a — per-section LLM critique [MỚI]
    │   ├── link_checker.py               # Step P3c — httpx HEAD song song [MỚI]
    │   ├── rewrite_validator.py          # validate_rewrite_patch() — exact-match check [MỚI]
    │   └── bundle_exporter.py            # Jinja2 render main.tex + figures/ → zip [MỚI]
    │
    ├── api/
    │   ├── __init__.py
    │   ├── upload.py                     # POST /api/pdf-agent/upload → SSE [MỚI]
    │   ├── bundle.py                     # GET /api/pdf-agent/{doc_id}/bundle [MỚI]
    │   ├── annotations.py                # GET/PATCH /api/pdf-agent/{doc_id}/annotations[/{id}] [MỚI]
    │   ├── selection.py                  # POST .../explain, .../rewrite, .../apply [MỚI]
    │   └── save.py                       # POST /api/pdf-agent/{doc_id}/save → tái dùng reviews API [MỚI]
    │
    └── models/
        ├── __init__.py
        ├── document.py                   # ParsedDocument, Section, Figure, RawCitation (pydantic) [MỚI]
        └── annotation.py                 # Annotation, TextQuoteSelector, CitationVerdict (pydantic) [MỚI]

frontend/app/src/
├── components/
│   ├── PDFUploadZone.tsx                 # drag-drop pdf/tex/zip [MỚI]
│   ├── TexEditor.tsx                     # Monaco + decorations cho suggest/warning [MỚI]
│   ├── AnnotationCard.tsx                # render 1 annotation — Accept/Reject (suggest) hoặc Dismiss (warning) [MỚI]
│   ├── SelectionToolbar.tsx              # popup "Giải thích" / "Viết lại" khi user tô chọn [MỚI]
│   └── RewritePreview.tsx                # diff view + nút Apply [MỚI]
├── hooks/
│   └── useTextQuoteAnchor.ts             # re-tìm exact/prefix/suffix trong buffer hiện tại [MỚI]
└── pages/
    └── PDFAgent.tsx                      # trang chính: upload → editor → save [MỚI]

data/
├── pdf_agent_checkpoints.db              # LangGraph SqliteSaver — riêng với research_agent
└── pdf_agent_output/
    └── {doc_id}/
        ├── main.tex                     # mutate trực tiếp khi user Apply rewrite/accept suggest
        ├── figures/
        └── bundle.zip                   # regenerate khi user download/save
```

**`module/pdf_agent/` là Python package riêng** — không sửa file nào trong `module/research_agent/`, chỉ `import` service functions.

---

## 6. API Endpoints

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/pdf-agent/upload` | Upload file → tạo `doc_id` → chạy graph P0→P4, SSE stream |
| `GET` | `/api/pdf-agent/{doc_id}/bundle` | Download `.zip` hiện tại (main.tex + figures/) |
| `GET` | `/api/pdf-agent/{doc_id}/annotations` | List annotations (đọc từ checkpoint) |
| `PATCH` | `/api/pdf-agent/{doc_id}/annotations/{annotation_id}` | Accept/Reject (`suggest`) hoặc Dismiss (`warning`) |
| `POST` | `/api/pdf-agent/{doc_id}/explain` | Step P5 "Giải thích" — trả text, không mutate |
| `POST` | `/api/pdf-agent/{doc_id}/rewrite` | Step P5 "Viết lại" — trả `{old_text, new_text}`, CHƯA apply |
| `POST` | `/api/pdf-agent/{doc_id}/apply` | Apply patch từ `/rewrite` — validate exact-match rồi mới ghi |
| `POST` | `/api/pdf-agent/{doc_id}/save` | Step P6 — gọi nội bộ `POST /api/reviews` với `source_type="uploaded"` |

### POST /api/pdf-agent/upload

```python
# api/upload.py
@app.post("/api/pdf-agent/upload")
async def upload_document(file: UploadFile):
    if file.size > PDF_AGENT_MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, "File quá lớn")
    doc_id = str(uuid4())
    raw_path = save_upload(file, PDF_AGENT_OUTPUT_DIR, doc_id)

    async def event_gen():
        config = {"configurable": {"thread_id": doc_id}}
        async for event in pdf_agent_graph.astream_events(
            {"doc_id": doc_id, "raw_file_path": raw_path}, config=config, version="v2",
        ):
            # mapping tương tự research-agent api/research.py — on_chain_start/end, on_chat_model_stream
            ...
        yield f"data: {json.dumps({'type': 'done', 'doc_id': doc_id})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

### PATCH /api/pdf-agent/{doc_id}/annotations/{annotation_id}

```python
# api/annotations.py
@app.patch("/api/pdf-agent/{doc_id}/annotations/{annotation_id}")
async def update_annotation(doc_id: str, annotation_id: str, body: AnnotationUpdate):
    config = {"configurable": {"thread_id": doc_id}}
    state = pdf_agent_graph.get_state(config).values
    target = next(a for a in state["annotations"] if a["id"] == annotation_id)

    if target["type"] == "warning" and body.action == "accept":
        raise HTTPException(400, "Warning không có hành động Accept — chỉ Dismiss")  # giữ Non-goals

    if body.action == "accept":
        apply_text_patch(state["main_tex_path"], target["anchor"], target["suggested_fix"])

    new_annotations = [
        {**a, "status": _action_to_status(body.action)} if a["id"] == annotation_id else a
        for a in state["annotations"]
    ]
    pdf_agent_graph.update_state(config, {"annotations": new_annotations})
    return {"id": annotation_id, "status": _action_to_status(body.action)}
```

### POST /api/pdf-agent/{doc_id}/apply

```python
# api/selection.py
@app.post("/api/pdf-agent/{doc_id}/apply")
async def apply_rewrite(doc_id: str, body: ApplyPatchRequest):
    config = {"configurable": {"thread_id": doc_id}}
    state = pdf_agent_graph.get_state(config).values
    current_tex = read(state["main_tex_path"])

    if not rewrite_validator.validate(body.old_text, current_tex):
        raise HTTPException(409, "Đoạn này đã thay đổi từ lúc tô, vui lòng tô lại")

    new_tex = current_tex.replace(body.old_text, body.new_text, 1)
    write(state["main_tex_path"], new_tex)
    return {"applied": True}
```

### POST /api/pdf-agent/{doc_id}/save

```python
# api/save.py
@app.post("/api/pdf-agent/{doc_id}/save")
async def save_to_review(doc_id: str, body: SaveRequest):
    config = {"configurable": {"thread_id": doc_id}}
    state = pdf_agent_graph.get_state(config).values
    tex_content = read(state["main_tex_path"])
    pending = [a for a in state["annotations"] if a["status"] == "pending"]

    # Gọi thẳng service layer của reviews (không HTTP loopback) — tránh round-trip không cần thiết
    review = await reviews_service.create_review(
        user_id=body.user_id, title=body.title, query=None,
        content=tex_content, source_type="uploaded", content_format="tex",
        pending_annotations=pending,
    )
    pdf_agent_graph.update_state(config, {"review_id": review["id"]})
    return review
```

---

## 7. Implementation Phases

---

### Phase 1 — Module Skeleton + Format Detection + `.tex`/`.tex_bundle` Parsing

**Mục tiêu:** Upload `.tex` hoặc `.zip` → parse ra `sections`/`raw_citations`/`figures` đúng, KHÔNG cần MinerU ở phase này.

**Tasks:**
- [ ] Tạo `module/pdf_agent/` skeleton (graph/services/api/models, theo §5)
- [ ] `services/zip_bundle.py`:
  ```python
  def extract_zip_safe(zip_path: str, dest_dir: str) -> str:
      with zipfile.ZipFile(zip_path) as zf:
          for member in zf.namelist():
              resolved = os.path.realpath(os.path.join(dest_dir, member))
              if not resolved.startswith(os.path.realpath(dest_dir) + os.sep):
                  raise SecurityError(f"Zip slip detected: {member}")   # path traversal guard — BẮT BUỘC
          zf.extractall(dest_dir)
      return dest_dir

  def find_main_tex(extract_dir: str) -> str:
      candidates = glob(f"{extract_dir}/**/*.tex", recursive=True)
      for c in candidates:
          content = read(c)
          if r"\documentclass" in content and r"\begin{document}" in content:
              return c
      raise NoMainTexFoundError()
  ```
  > **An ninh:** mọi `.zip` upload đều là input không tin cậy — PHẢI validate path từng entry trước khi extract (zip slip / path traversal, OWASP). Không dùng `zf.extractall()` trực tiếp mà không check.
- [ ] `services/tex_parser.py`: `pylatexenc.latexwalker.LatexWalker` — extract `\section{}`, `\cite{}` + context, `\includegraphics{}` (path + caption + label nếu có `\begin{figure}`)
- [ ] `graph/nodes/format_detect.py`: byte sniffing (`%PDF` / `PK` / `\documentclass`) — xem SPEC Step P0
- [ ] `graph/nodes/parse_document.py`: dispatch theo `input_format`, nhánh `tex`/`tex_bundle` gọi `tex_parser.py` + `zip_bundle.py`; nhánh `pdf` raise `NotImplementedError` tạm (làm ở Phase 2)
- [ ] `graph/state.py`, `graph/graph.py`: build graph chỉ tới `parse_document` (chưa nối `render_bundle`)
- [ ] `models/document.py`: pydantic schema

**Kiểm tra Phase 1:**
- Upload `.tex` trần có `\includegraphics{}` không tồn tại file → `figures[0].missing == True`
- Upload `.zip` đúng cấu trúc Overleaf → `figures[0].missing == False`, `image_path` trỏ đúng file đã copy
- Upload `.zip` có entry `../../etc/passwd` → raise `SecurityError`, không extract

---

### Phase 2 — PDF Parsing via MinerU

**Mục tiêu:** Upload `.pdf` → `sections`/`raw_citations`/`figures` đúng, figure-caption pairing đúng.

**Tasks:**
- [ ] `services/mineru_client.py`:
  ```python
  async def run_mineru(pdf_path: str, output_dir: str) -> dict:
      proc = await asyncio.create_subprocess_exec(
          MINERU_BIN, "-p", pdf_path, "-o", output_dir, "-m", "auto",
          stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
      )
      try:
          await asyncio.wait_for(proc.communicate(), timeout=MINERU_TIMEOUT_S)
      except asyncio.TimeoutError:
          proc.kill()
          raise MinerUTimeoutError(f"MinerU vượt {MINERU_TIMEOUT_S}s — PDF có thể quá phức tạp/dài")
      return load_json(f"{output_dir}/{stem(pdf_path)}_content_list.json")
  ```
- [ ] `extract_sections_from_mineru()`: map Markdown headers (`#`/`##`) trong content_list → `Section`
- [ ] `extract_figures_from_mineru()`: map `img_path`/`image_caption`/`chart_caption`/`bbox`/`page_idx` → `Figure` (xem code mẫu trong SPEC Step P1)
- [ ] Reference list cleanup — 1 LLM call (`temperature=0`) parse raw reference text → `RawCitation[]` (xem SPEC Step P1 cho prompt)
- [ ] `graph/nodes/parse_document.py`: nối nhánh `pdf` vào dispatch
- [ ] Guardrail: reject PDF > `PDF_AGENT_MAX_PAGES` trước khi gọi MinerU (đọc page count qua `pypdf` nhẹ, không cần OCR để biết số trang)

**Kiểm tra Phase 2:**
- Upload PDF mẫu (paper arXiv bất kỳ, có ≥3 figure) → `figures` đúng số lượng, mỗi `caption` không rỗng
- Upload PDF > 60 trang → reject với message rõ, không gọi MinerU
- MinerU timeout giả lập (kill process) → raise đúng exception, không treo request

---

### Phase 3 — Render Editable Bundle (Step P2)

**Mục tiêu:** `ParsedDocument` (từ Phase 1 hoặc 2) → `.zip` download được, compile bằng `pdflatex` không lỗi.

**Tasks:**
- [ ] `templates/pdf_agent_document.tex.j2` (template riêng, KHÔNG sửa `literature_review.tex.j2` của research_agent)
- [ ] `services/bundle_exporter.py`: render Jinja2 + copy figures + zip (code mẫu trong SPEC Step P2)
- [ ] `graph/nodes/render_bundle.py`: gọi `bundle_exporter`, set `state["bundle_path"]`, `state["main_tex_path"]`
- [ ] `graph/graph.py`: nối `parse_document → render_bundle`
- [ ] `api/bundle.py`: `GET /api/pdf-agent/{doc_id}/bundle` → `FileResponse`

**Kiểm tra Phase 3:**
- `.zip` xuất ra compile được bằng `pdflatex main.tex` không lỗi, ảnh hiện đúng vị trí
- Tài liệu thiếu ảnh (`missing=True`) → `\includegraphics` cho ảnh đó KHÔNG xuất hiện trong `.tex` (tránh lỗi compile vì file không tồn tại)

---

### Phase 4 — Reference Verification (Step P3b)

**Mục tiêu:** Mỗi `raw_citation` → verdict (`Verified`/`Metadata Mismatch`/`Not Found`), tái dùng service đã có từ research_agent.

**Tasks:**
- [ ] `services/citation_lookup.py`:
  ```python
  from module.research_agent.services import semantic_scholar, openalex, arxiv_search

  async def verify_citation(c: RawCitation) -> dict:
      if doi := extract_doi(c["raw_text"]):
          if hit := await semantic_scholar.lookup_by_doi(doi):   # hàm mới, thêm vào service đã có
              return score_match(c, hit)
      candidates = []
      for search_fn in (semantic_scholar.search, openalex.search, arxiv_search.search):
          candidates += await search_fn(c["guessed_title"], n=5)
      best = best_fuzzy_match(c, candidates)         # rapidfuzz title + year ±1 + author overlap
      if best.score >= PDF_AGENT_MATCH_THRESHOLD_HIGH:
          return {"verdict": "Verified", "confidence": best.score, "evidence": best.paper}
      if best.score < PDF_AGENT_MATCH_THRESHOLD_LOW:
          return {"verdict": "Not Found", "confidence": best.score, "evidence": None}
      return await llm_judge_citation_match(c, best)   # vùng xám — temperature=PDF_JUDGE_TEMPERATURE
  ```
- [ ] Thêm hàm `lookup_by_doi()`/`lookup_by_arxiv_id()` vào `research_agent/services/semantic_scholar.py` và `arxiv_search.py` nếu chưa có (hiện 2 file này chỉ có hàm `search()`, cần thêm lookup-by-id — đây là **sửa nhỏ vào module research_agent**, không phải tạo mới song song)
- [ ] `graph/nodes/batch_analysis.py` (phần P3b): `asyncio.gather` tất cả citations

**Kiểm tra Phase 4:**
- Citation thật (có DOI đúng) → `Verified`, confidence > 0.85
- Citation bịa hoàn toàn (test thủ công 1 reference giả) → `Not Found`
- Citation đúng tên nhưng sai năm → `Metadata Mismatch` qua LLM judge, không rơi vào `Not Found`

---

### Phase 5 — Critic Agents + Link Check + Annotation Store (Step P3a, P3c, P4)

**Mục tiêu:** Annotation Store đầy đủ `suggest` + `warning`, anchor đúng bằng TextQuoteSelector.

**Tasks:**
- [ ] `services/text_quote_selector.py`:
  ```python
  def build_anchor(full_text: str, start: int, end: int, context_chars: int = 32) -> TextQuoteSelector:
      return {"exact": full_text[start:end],
              "prefix": full_text[max(0, start - context_chars):start],
              "suffix": full_text[end:end + context_chars]}

  def refind_anchor(current_text: str, anchor: TextQuoteSelector) -> int | None:
      """Trả offset hiện tại của anchor.exact trong current_text, disambiguated bởi prefix/suffix. None nếu không còn tồn tại."""
      candidates = [m.start() for m in re.finditer(re.escape(anchor["exact"]), current_text)]
      if len(candidates) == 1:
          return candidates[0]
      for pos in candidates:                      # disambiguate bằng prefix/suffix nếu exact lặp lại
          if current_text[max(0, pos - 32):pos].endswith(anchor["prefix"][-32:]):
              return pos
      return None
  ```
- [ ] `services/critic_agent.py`: 1 LLM call/section, `temperature=CRITIC_TEMPERATURE`, system prompt theo SPEC Step P3a
- [ ] `services/link_checker.py`: `httpx.AsyncClient().head()` song song, timeout `PDF_AGENT_LINK_CHECK_TIMEOUT_S`
- [ ] `graph/nodes/batch_analysis.py`: `asyncio.gather(critic_task, citation_task, link_task)` — P3a/b/c chạy đồng thời
- [ ] `graph/nodes/build_annotations.py`: gộp 3 kết quả → `Annotation[]`, `warning` KHÔNG set `suggested_fix` (luôn `None`)
- [ ] `graph/graph.py`: nối `render_bundle → batch_analysis → build_annotations → END`

**Kiểm tra Phase 5:**
- Mọi `Annotation` type=`warning` có `suggested_fix is None` — test assert cứng, không cho lọt qua review code
- Annotation tạo từ citation Not Found có `evidence is None`, từ Metadata Mismatch có `evidence` chứa paper gần giống
- `refind_anchor()` trả đúng offset sau khi giả lập chèn 50 ký tự vào đoạn text TRƯỚC vị trí anchor

---

### Phase 6 — Frontend Editor (Monaco + Inline Suggest/Warning)

**Mục tiêu:** User thấy `.tex` trong editor, annotation highlight đúng vị trí, Accept/Reject/Dismiss hoạt động, annotation tự ẩn nếu đoạn bị sửa tay.

**Tasks:**
- [ ] `npm install @monaco-editor/react monaco-editor`
- [ ] `hooks/useTextQuoteAnchor.ts`: port logic `refind_anchor()` sang TypeScript, chạy lại mỗi khi buffer đổi (debounce ~300ms)
- [ ] `components/TexEditor.tsx`: `<Editor>` + `deltaDecorations()` tô màu theo `type` (`suggest`=vàng nhạt, `warning`=đỏ nhạt), click decoration → mở `AnnotationCard`
- [ ] `components/AnnotationCard.tsx`: render khác nhau theo `type` — `suggest` có Accept/Reject, `warning` chỉ Dismiss (KHÔNG render nút Accept cho warning, kể cả disabled — ẩn hẳn để không gây hiểu lầm)
- [ ] `pages/PDFAgent.tsx`: gọi `/upload` → SSE → khi `done`, fetch `/bundle` + `/annotations` → render editor

**Kiểm tra Phase 6:**
- Sửa tay 1 đoạn không liên quan phía trên → annotation phía dưới KHÔNG bị lệch vị trí highlight
- Sửa đúng đoạn bị flag (user tự fix) → annotation đó tự ẩn (không tìm thấy `exact` nữa)
- Click Dismiss trên 1 `warning` → annotation biến mất, gọi đúng `PATCH .../annotations/{id}` với action dismiss

---

### Phase 7 — Selection-triggered Explain / Rewrite (Step P5)

**Mục tiêu:** Tô chọn text → 2 action hoạt động, Rewrite cần Apply riêng, exact-match validate đúng.

**Tasks:**
- [ ] `services/rewrite_validator.py`: `validate(old_text, current_doc) -> bool` — `old_text in current_doc`
- [ ] `api/selection.py`: 3 endpoint `/explain`, `/rewrite`, `/apply` (code mẫu §6)
- [ ] `components/SelectionToolbar.tsx`: popup nổi khi Monaco có selection, 2 nút cố định
- [ ] `components/RewritePreview.tsx`: hiện diff `old_text`→`new_text`, nút Apply gọi `/apply`; nếu `409` → toast "đoạn này đã thay đổi, vui lòng tô lại"

**Kiểm tra Phase 7:**
- Giải thích: trả text trong 1-3s, KHÔNG có nút Apply nào hiện ra
- Viết lại: trả patch, bấm Apply → text trong editor đổi đúng đoạn đã chọn, không ảnh hưởng đoạn khác
- Giả lập user sửa tay đoạn đã tô NGAY TRƯỚC khi bấm Apply → nhận `409`, không ghi đè sai

---

### Phase 8 — Save to My Review (Step P6)

**Mục tiêu:** Lưu `.tex` hiện tại + annotation chưa resolve vào bảng `reviews`, resume được.

**Tasks:**
- [ ] Migration: `ALTER TABLE reviews ADD COLUMN source_type ..., content_format ..., pending_annotations ..., ALTER COLUMN query DROP NOT NULL` (xem SQL đầy đủ trong SPEC Step P6)
- [ ] `reviews_service.create_review()`: thêm param `source_type`, `content_format`, `pending_annotations` — sửa hàm đã có trong module review (không tạo service mới song song)
- [ ] `api/save.py`: `POST /api/pdf-agent/{doc_id}/save` (code mẫu §6)
- [ ] Export PDF cho `content_format="tex"`: nhánh mới trong `api/reviews/export.py` (đã có) — chạy `pdflatex` thay vì `weasyprint`

**Kiểm tra Phase 8:**
- Save xong → `GET /api/reviews/:id` trả đúng `content_format="tex"`, `pending_annotations` còn ≥1 nếu chưa resolve hết
- Mở lại review đã lưu → annotation cũ hiện lại đúng vị trí (test `refind_anchor` trên content đã lưu)
- Export `?format=pdf` cho review `content_format=tex` → ra file PDF compile từ `pdflatex`, không lỗi

---

### Phase 9 — Integration Testing

**Tasks:**
- [ ] E2E nhánh `.tex` trần: upload → có warning `missing_asset` nếu thiếu ảnh
- [ ] E2E nhánh `.zip`: upload project Overleaf mẫu → bundle xuất ra giữ đúng ảnh
- [ ] E2E nhánh `.pdf`: upload paper arXiv thật → figures + reference verification đúng
- [ ] Test security: `.zip` chứa zip-slip payload → reject, không extract ra ngoài `dest_dir`
- [ ] Test concurrency: 2 PATCH annotation cùng lúc trên 1 `doc_id` → không mất update (SQLite single-writer đủ cho MVP single-user, ghi rõ giới hạn này — xem §8 Rủi ro)
- [ ] Đo cost thực tế 1 document ~60 citation, ~15 section — so với ước tính SPEC (~$0.003/document nhánh `.pdf`)
- [ ] Đo latency P0→P4 cho PDF 60 trang (gồm MinerU) — guardrail timeout có kích hoạt đúng không

---

## 8. Key Dependencies

### `pyproject.toml` — thêm vào dependencies đã có ở `research-agent_PLAN_2.0.md`

```toml
dependencies = [
    # ... (giữ nguyên dependencies research_agent)

    # PDF Agent
    "pylatexenc",                # .tex parsing
    "mineru",                    # PDF OCR/layout — CLI invoked qua subprocess
    "pypdf",                     # đọc số trang PDF nhanh, trước khi quyết định gọi MinerU
]
```

> `mineru` cần model weights riêng tải lần đầu (~vài GB) — xem hướng dẫn cài đặt chính thức tại thời điểm implement, có thể đổi sang cấu hình GPU nếu cần tốc độ.

### Dockerfile (mẫu — bake model weight lúc build, không tải lúc runtime)

```dockerfile
FROM python:3.11-slim

# System deps: pdflatex (compile bundle khi export PDF) + zip handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-extra && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv sync

# Bake model weight MinerU NGAY LÚC BUILD — đây là bước quan trọng nhất,
# tránh container đầu tiên nhận request phải tự tải model (chậm, cần internet,
# không deterministic). Lệnh chính xác: xem docs chính thức MinerU tại thời điểm
# implement (đã đổi qua vài lần theo version).
RUN mineru-models-download --auto || true   # placeholder — xác nhận lệnh thật khi code

COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml (mẫu) — volume bền cho checkpoint + output, BẮT BUỘC
# (xem cảnh báo ở §2 Environment Variables)
services:
  pdf-agent:
    build: .
    volumes:
      - pdf_agent_data:/app/data          # chứa pdf_agent_checkpoints.db + pdf_agent_output/
    environment:
      - MINERU_DEVICE_MODE=cpu
volumes:
  pdf_agent_data:
```

**Quyết định kiến trúc (MVP):** MinerU chạy **chung 1 container** với backend FastAPI (subprocess gọi trong cùng image) — đơn giản, khớp code hiện tại ở `mineru_client.py`. Tách MinerU thành microservice riêng (để scale OCR độc lập khỏi API nhẹ) là defer, chỉ cần khi có data thực tế cho thấy OCR là bottleneck thật.

### Frontend (npm)

```bash
npm install @monaco-editor/react monaco-editor
```

### Service files research_agent CẦN SỬA NHỎ (không phải viết mới)

`semantic_scholar.py` và `arxiv_search.py` hiện chỉ có hàm `search()` — Phase 4 cần thêm `lookup_by_doi()`/`lookup_by_id()`. Đây là bổ sung hàm, không đổi hàm cũ, không ảnh hưởng `research-agent_PLAN_2.0.md` đã implement.

---

## 9. Rủi ro & Giải pháp

| Rủi ro | Giải pháp |
|---|---|
| **Zip slip / path traversal** khi extract `.zip` user upload | `extract_zip_safe()` validate `os.path.realpath()` mỗi entry nằm trong `dest_dir` trước khi extract — bắt buộc, không dùng `extractall()` trần (xem Phase 1) |
| MinerU subprocess treo với PDF dị dạng | `asyncio.wait_for(timeout=MINERU_TIMEOUT_S)` + `proc.kill()`, guardrail `max_pages` chặn trước khi gọi |
| MinerU không đủ chính xác cho PDF scan/layout dị, **không có fallback trả phí** (đã quyết định không dùng Mathpix) | Báo lỗi/warning rõ cho user (vd "PDF này MinerU xử lý kém, vui lòng thử lại với .tex hoặc PDF chất lượng tốt hơn") — không tự động retry bằng service khác ở MVP |
| `pylatexenc` không parse được macro tự định nghĩa lạ trong `.tex` | `try/except` quanh `LatexWalker`, fallback: vẫn cho user edit `.tex` thô (không structure theo section), không chặn cả pipeline |
| `update_state()` đua nhau khi 2 request PATCH annotation cùng lúc | MVP single-user session — SQLite single-writer đủ an toàn; ghi rõ giới hạn này, KHÔNG xử lý multi-user concurrent (đã ghi ở SPEC Identified Gaps #8) |
| Patch `/apply` ghi nhầm nếu `old_text` xuất hiện nhiều lần trong doc | `str.replace(old_text, new_text, 1)` chỉ thay occurrence đầu — nếu cần chính xác hơn, dùng offset từ `anchor` đã refind thay vì `replace()` thuần (cải tiến nếu test Phase 7 phát hiện sai lệch) |
| MinerU model weights nặng, lần đầu setup chậm | **Đã quyết định:** bake vào Docker image lúc build (`RUN` step trong Dockerfile, xem §8) — không tải lúc runtime, tránh request đầu tiên timeout/cần internet từ server production |
| Container restart/redeploy mất checkpoint + document đang xử lý nếu thiếu volume mount | `PDF_AGENT_CHECKPOINT_DB`/`PDF_AGENT_OUTPUT_DIR` PHẢI mount vào Docker volume bền (xem `docker-compose.yml` mẫu §8) — không phải path tạm sống trong container |
| MinerU chạy chung container với backend → image API nhẹ bị kéo nặng theo (vài GB) | Chấp nhận ở MVP (đơn giản, ít vận hành); tách microservice riêng cho MinerU là defer, chỉ làm khi OCR thực sự là bottleneck cần scale độc lập |
| `lookup_by_doi()` chưa có sẵn trong research_agent service | Thêm hàm mới (không sửa hàm `search()` cũ) — kiểm tra `research-agent_PLAN_2.0.md` không bị breaking change |
| Reference list OCR ra quá nhiễu, LLM cleanup (Phase 2) parse sai nhiều field | Giữ `raw_text` gốc luôn đi kèm — citation verification (Phase 4) fallback dùng `raw_text` full-text search nếu `guessed_title` rỗng/sai |
| Threshold `0.85`/`0.55` (match citation) sai ở domain ngoài CS/AI | Đánh giá lại sau khi có data thật từ Phase 9, threshold hiện lấy theo CheckIfExist/CiteCheck benchmark — không có gì đảm bảo đúng 100% mọi domain |

---

## 10. Milestones

| Milestone | Nội dung | Phụ thuộc |
|---|---|---|
| **PA-M1** | Phase 1 — Module skeleton + `.tex`/`.tex_bundle` parsing | Không phụ thuộc gì khác |
| **PA-M2** | Phase 2 — MinerU PDF parsing + figure extraction | Sau PA-M1 |
| **PA-M3** | Phase 3 — Render editable bundle (.zip) | Sau PA-M2 |
| **PA-M4** | Phase 4 — Reference verification (tái dùng research_agent services) | Cần `research-agent_PLAN_2.0.md` đã có `semantic_scholar.py`/`openalex.py`/`arxiv_search.py` chạy được |
| **PA-M5** | Phase 5 — Critic Agent + Link check + Annotation Store | Sau PA-M3 + PA-M4 |
| **PA-M6** | Phase 6 — Frontend Monaco editor + inline annotation | Sau PA-M5 |
| **PA-M7** | Phase 7 — Explain/Rewrite on-demand | Sau PA-M6 |
| **PA-M8** | Phase 8 — Save to My Review (`ALTER TABLE reviews`) | Cần `review-litureature_SPEC_1.0.1.md` đã implement bảng `reviews` |
| **PA-M9** | Phase 9 — Integration test + security test (zip slip) | Sau tất cả |
