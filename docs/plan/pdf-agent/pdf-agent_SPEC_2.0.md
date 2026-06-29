# PDF Agent — Tổng quan (Overview)

**Version:** 2.0
**Phụ thuộc:** tái dùng `services/semantic_scholar.py`, `services/openalex.py`, `services/arxiv_search.py` (Step ① research-agent_SPEC_2.0.md), verifier prompt pattern qua `services/citation_verifier.py` (Step ⑧), `latex_exporter.py` (Step ⑩), bảng `reviews` (review-litureature_SPEC_1.0.1.md)
**Vị trí trong hệ thống:** module **độc lập**, KHÔNG nối sau Research Agent — entry point riêng do user upload file

---

## Tóm tắt (Executive Summary)

> Researcher nhận một paper PDF (bài người khác, hoặc bản thảo của chính mình) và muốn biết 2 điều trước khi tin: (1) văn phong/lập luận có vấn đề gì không, (2) các citation có thật không hay đang trích dẫn nguồn ảo. Ngoài ra cần **sửa trực tiếp trên văn bản**, không chỉ đọc báo cáo riêng.

PDF Agent nhận file `.pdf`/`.tex`/`.zip` user upload, chuyển thành `.tex` editable (giữ cả ảnh/figure nếu có), rồi hiển thị 2 loại annotation **ngay trong editor** (giống Suggesting mode của Google Docs): `suggest` (vấn đề văn phong, có thể có bản sửa đề xuất, user Accept/Reject) và `warning` (citation/link không xác minh được, KHÔNG có auto-fix, user chỉ Dismiss). User cũng có thể tô chọn 1 đoạn để hỏi LLM giải thích hoặc xin viết lại — viết lại luôn cần user approve trước khi áp vào văn bản. Cuối cùng lưu lại vào **My Review** (tái dùng bảng đã có ở `review-litureature_SPEC_1.0.1.md`).

**Quyết định scope quan trọng** (xem Non-goals): PDF Agent chỉ nhận document từ bên ngoài, không tự fact-check `literature_review.tex` mà Research Agent vừa sinh ra cho chính user đó.

---

## Mục tiêu (Goals)

| Mục tiêu | Metric |
|---|---|
| Chuyển PDF/.tex → .tex editable, giữ structure | Mở được bằng Overleaf/`pdflatex` không lỗi compile |
| Feedback văn phong cụ thể, hiển thị inline | >70% comment "specific and actionable" (benchmark MARG) |
| Phát hiện citation/link không xác minh được | Phân loại Verified / Metadata Mismatch / Not Found / Unreachable |
| **Mọi thay đổi văn bản đều qua approve của user** | 0% trường hợp tự động ghi đè text mà không có hành động Accept/Apply rõ ràng từ user |
| Annotation không trôi vị trí khi user edit chỗ khác | Anchor bằng quote+context (TextQuoteSelector), không dùng offset số tuyệt đối |
| Tái dùng tối đa infra đã có | Không xây lại S2/OpenAlex/arXiv client, LaTeX exporter, hay bảng `reviews` |
| Giữ được ảnh/figure khi convert PDF/.tex → .tex editable | Output là `.zip` (main.tex + figures/), không phải 1 file `.tex` rời rạc thiếu ảnh |

### Non-goals

> **Không tự fact-check lại output của chính Research Agent.** Lý do: tránh nghịch lý trust (tools tự sinh nội dung rồi tự nghi ngờ nội dung của mình), market precedent Elicit/Consensus/Scite/Paperpal luôn tách 3 job riêng. Lỗ hổng thật liên quan (Step ⑩ Intro/Conclusion chưa qua verify) là patch riêng cho `research-agent_SPEC_2.0.md`.
>
> - Không tự apply `suggest`/`rewrite` mà không có hành động Accept/Apply rõ ràng từ user — kể cả khi confidence cao.
> - Không tự sinh citation mới để "fix" warning Not Found — chỉ báo cáo, không có nút Accept cho warning.
> - Không kiểm tra đạo văn/plagiarism.
> - Không dùng ô chat tự do cho thao tác tô-chọn — chỉ 2 action cố định (Giải thích / Viết lại) để giảm ambiguity, xem Step P5.
> - Không tái dựng ảnh/figure thành vector/TikZ editable — ảnh chỉ được crop/copy thành asset tĩnh (PNG) và `\includegraphics{}` lại, vì PDF Agent lo văn phong + citation, không lo "sửa nội dung trong hình vẽ".
> - Không tích hợp dịch vụ OCR/PDF-parsing trả phí (Mathpix hay tương tự) — chỉ dùng MinerU self-host. PDF mà MinerU xử lý kém sẽ báo lỗi/warning rõ cho user, không tự động escalate sang service khác.

---

## Bối cảnh nghiên cứu (Landscape — đã có gì trên thế giới)

### A. PDF/.tex → .tex editable

| Hướng | Đại diện | Cơ chế | Vì sao chọn/không chọn |
|---|---|---|---|
| VLM end-to-end nhẹ | Nougat, GOT-OCR2.0 (580M, StepFun) | Ảnh trang → text + LaTeX math trực tiếp | GOT-OCR2.0 nhẹ, open-weight, nhưng yếu table phức tạp |
| Pipeline nhiều model chuyên biệt | **MinerU** (default) | Layout detection → OCR → reading-order → formula→LaTeX, output Markdown/JSON, đã refactor caption↔figure pairing | ✅ Free, self-host, output có structure block sẵn (`img_path`, `image_caption`/`chart_caption`, `bbox`, `page_idx`) |
| VLM ingest quy mô lớn | olmOCR (AllenAI) | Tối ưu throughput, không chú trọng giữ structure | Không hợp — cần structure đẹp hơn tốc độ |
| SaaS thương mại | Mathpix | PDF→LaTeX trực tiếp, xử lý tốt 2-column + table chứa math, mở thẳng Overleaf | ❌ Không dùng — quyết định chỉ self-host (MinerU), không tích hợp dịch vụ trả phí; PDF MinerU xử lý kém → báo lỗi/warning cho user thay vì tự động escalate |
| Pipeline tương tự MinerU | Marker | Tốc độ nhanh hơn MinerU, table layout tốt | ❌ Không dùng — weight model license `cc-by-nc-sa-4.0` (miễn phí chỉ dưới $5M doanh thu/funding) — rủi ro pháp lý nếu scale, không phù hợp làm core dependency |
| Enterprise document processing | Docling (IBM) | MIT license, ecosystem LangChain/LlamaIndex tốt, không cần GPU | ❌ Không dùng — benchmark độc lập cho thấy yếu hơn ở table phức tạp, đúng điểm yếu quan trọng nhất với paper khoa học (nhiều table kết quả) |
| Pipeline thuật toán + 1 model nhẹ | OpenDataLoader-pdf | Apache 2.0 permissive hoàn toàn, không cần GPU, nhanh hơn MinerU (60+ trang/giây), accuracy cao nhất benchmark độc lập (0.907 tổng, 0.928 table) trên 200 PDF gồm scientific paper/multi-column | ⚠️ Đã cân nhắc kỹ, có thể là phương án tốt hơn về license/tốc độ — nhưng quyết định **giữ MinerU** vì track record dài hơn (nhiều người dùng production hơn); thay vào đó xử lý rủi ro deploy của MinerU bằng Docker (bake model weight lúc build, xem `pdf-agent_PLAN_2.0.md` §1/§8) |

Benchmark đối chiếu: **OmniDocBench** (arXiv:2412.07626) — so cả text/formula/table/reading-order giữa các công cụ trên.

### B. Model nhận xét văn phong/lập luận

| Hệ thống | Cơ chế | Áp dụng vào PDF Agent |
|---|---|---|
| **MARG** (arXiv:2401.04259) | Leader điều phối + Worker agent/section + Expert agent/aspect (clarity, experiments, impact) | ✅ Core pattern Step P3a — 1 Critic Agent/section chạy song song, giảm generic comment 60%→29% |
| Reviewer2 | Aspect-specific prompt cố định (novelty/soundness/clarity/significance) | Dùng làm khung 4 aspect cho output JSON của Critic Agent |
| ICLR Review Feedback Agent (arXiv:2504.09737) | LLM feedback giúp review cụ thể/actionable hơn, test thật 20K review | Bằng chứng pattern "agent feedback on writing" hoạt động ở quy mô lớn |
| ⚠️ LLM-REVal (arXiv:2510.12367) | LLM reviewer tự thiên vị, hạ điểm văn bản con người viết có phê bình gắt | Critic Agent phải temp=0 + prompt conservative, không chấm điểm tổng, chỉ liệt kê issue cụ thể |

### C. Phát hiện citation/link giả

| Hệ thống | Cơ chế | Áp dụng vào PDF Agent |
|---|---|---|
| **CheckIfExist** (arXiv:2602.15871) | Multi-source CrossRef+S2+OpenAlex, multi-field match (title/author/year/DOI/venue) → confidence score | ✅ Multi-field scoring algorithm — core logic chấm điểm match |
| **CiteCheck** (arXiv:2605.27700) | Waterfall cascade (arXiv→CrossRef→S2→OpenAlex→web) + LLM verifier 0-10 + reviewer-pass cho case khó | ✅ Pattern waterfall + 2-pass verify — đã có sẵn 90% hạ tầng (Step ①+⑧ research-agent), chỉ đổi mode "lookup" thay vì "discover" |
| Reference Hallucination in Deep Research Agents (arXiv:2604.03173) | Benchmark 13 LLM × 40 domain: hallucination rate 14%–95% | Lý do bước này bắt buộc, không phải nice-to-have |

### D. Inline suggestion-mode editing & human-in-the-loop apply

| Hướng | Đại diện | Cơ chế | Áp dụng vào PDF Agent |
|---|---|---|---|
| Track-changes UX kinh điển | Google Docs Suggesting mode | Insert/delete hiển thị inline (gạch ngang/màu), Accept (✓)/Reject (✗) từng suggestion hoặc Accept All | Mượn UX affordance cho `type=suggest` |
| **LLM text-editing framework có nghiên cứu** | **InkSync** (arXiv:2309.15337) — "Warn, Verify, Audit" | Edit hiển thị **ngay trong văn bản** (không qua chat riêng); **Warn** khi LLM thêm info không có trong gốc; **Verify** cho author tự fact-check qua search tích hợp; **Audit** lưu trace toàn bộ auto-generated content | ✅ Map gần 1-1: Warn↔`warning` (citation), Verify↔evidence hiển thị từ P3b, Audit↔lịch sử trong `pending_annotations`. Usability study: "more agency", "more accurate, efficient editing" so với chat thường |
| LaTeX-native track changes | `changes` package (`\added`/`\deleted`/`\replaced`), `latexdiff` | Compile ra PDF có màu, so sánh 2 file tĩnh | ❌ Không hợp cho editor tương tác live trên web — chỉ dùng cho tính năng "export diff PDF" tương lai (deferred) |
| IDE/coding-agent diff-apply | Cursor, GitHub Copilot, Claude Code "Edit tool" | LLM xuất diff có ràng buộc (`old_text` phải match chính xác buffer hiện tại) → preview → user confirm Apply | ✅ Pattern dùng cho Step P5 "Viết lại" — không cho LLM tự do generate lại nguyên đoạn |
| **Anchor annotation bền với edit** | **W3C Web Annotation Data Model — TextQuoteSelector** (`exact`+`prefix`+`suffix`), dùng bởi Hypothesis | Định vị bằng quote + context xung quanh, KHÔNG dùng offset số tuyệt đối — recover được vị trí dù text trước/sau đã đổi | ✅ **Bắt buộc dùng cho mọi annotation** — nếu dùng offset số, mọi suggestion/warning sẽ trôi sai vị trí ngay khi user sửa 1 ký tự ở đoạn khác |

---

## Flow chính

```
[Step P0] Upload + Format Detection (pdf | tex | tex_bundle)
            ↓
[Step P1] Parse → Structured Document (gồm figures)
            ↓
[Step P2] Render Editable .tex (+ figures/ nếu có ảnh) → output là .zip
            ↓  (user download/edit tay được ngay tại đây)
[Step P3] Batch Analysis Pass (song song)
            Critic Agents ∥ Reference Verification ∥ Link Liveness Check
            ↓
[Step P4] Annotation Store — anchor bằng TextQuoteSelector
            type=suggest  (Accept/Reject — áp dụng new_text nếu Accept)
            type=warning  (Dismiss/Acknowledge — KHÔNG có Accept)
            ↓
     User tương tác tự do với editor:
       • Accept/Reject từng suggest, Dismiss từng warning
       • Tô chọn 1 đoạn → trigger Step P5
            ↓
[Step P5] Selection-triggered Explain / Rewrite (on-demand, KHÔNG phải batch)
            Giải thích → trả text, không patch, không cần approve
            Viết lại  → trả {old_text, new_text}, cần Apply (approve) mới ghi vào doc
            ↓
[Step P6] Save to My Review — tái dùng bảng `reviews` (review-litureature_SPEC_1.0.1.md)
            ↓
[Output] .zip (.tex đã chỉnh sửa + figures/) + annotation history, lưu trong My Review
```

---

## Chi tiết Step P0/P1/P2 — Parse & Render (gồm xử lý ảnh/figure)

### Step P0 — Upload + Format Detection

3 format được nhận, không phải 2:

```python
def detect_format(raw_bytes: bytes) -> Literal["pdf", "tex", "tex_bundle"]:
    if raw_bytes.startswith(b"%PDF"):
        return "pdf"
    if raw_bytes.startswith(b"PK"):           # zip magic bytes
        return "tex_bundle"                    # main.tex + figures/ + references.bib (kiểu export từ Overleaf)
    text_head = raw_bytes[:2000].decode("utf-8", errors="ignore")
    if r"\documentclass" in text_head or r"\begin{document}" in text_head:
        return "tex"                           # .tex trần, KHÔNG có ảnh kèm
    raise UnsupportedFormatError("Không nhận diện được format")
```

`tex` trần (không zip) vẫn được chấp nhận — nhưng nếu trong văn bản có `\includegraphics{}` mà không resolve được file, sẽ bị flag ở P1 (xem dưới), không raise lỗi cứng.

### Step P1 — Parse → Structured Document

**Schema chung cho cả 3 nhánh:**

```python
class ParsedDocument(TypedDict):
    sections: list[Section]
    raw_citations: list[RawCitation]
    figures: list[Figure]

class Figure(TypedDict):
    image_path: str                  # path tới file ảnh đã crop/copy, lưu trong output bundle
    caption: str | None
    label: str | None                 # giữ \label{} để \ref{} trong văn bản còn hoạt động
    anchor: "TextQuoteSelector | None" # vị trí trong flow text (đoạn trước/sau) để chèn đúng chỗ
    page_number: int | None           # chỉ có ở nhánh .pdf
    missing: bool                     # True nếu .tex trần tham chiếu ảnh nhưng không có file
```

**Nhánh `tex_bundle` (zip):**
```python
def parse_tex_bundle(zip_path: str) -> ParsedDocument:
    extract_dir = unzip(zip_path)
    main_tex = find_main_tex(extract_dir)   # heuristic: chứa \documentclass + \begin{document}
    doc = parse_tex(read(main_tex))
    for fig in extract_includegraphics(doc):
        resolved_path = resolve_relative(extract_dir, fig.raw_path)   # vd "figures/architecture.png"
        if exists(resolved_path):
            fig.image_path = copy_to_output_bundle(resolved_path)
            fig.missing = False
        else:
            fig.missing = True   # path có trong .tex nhưng file không có trong zip
    return doc
```

**Nhánh `tex` trần (không zip) — `\includegraphics{}` không resolve được:**
```python
# Không raise lỗi — đánh dấu missing=True, để Step P4 tạo warning thay vì chặn cả pipeline
fig.missing = True
```
Annotation sinh ra ở P4 (tái dùng cơ chế `warning` đã có, không cần thiết kế affordance mới):
```json
{"type": "warning", "aspect": "missing_asset", "anchor": {"exact": "\\includegraphics{figures/architecture.png}", ...},
 "comment": "Ảnh được tham chiếu nhưng không có file đi kèm. Vui lòng upload dạng .zip kèm thư mục ảnh.", "suggested_fix": null}
```

**Nhánh `pdf` (MinerU) — ảnh được crop + ghép caption sẵn, không cần tự xây:**
```bash
mineru -p uploaded.pdf -o ./output/ -m auto
# output/uploaded_content_list.json — mỗi block ảnh có sẵn: img_path, image_caption/chart_caption,
# bbox, page_idx — MinerU đã refactor logic ghép caption↔figure, tỷ lệ mất caption gần 0
```
```python
def extract_figures_from_mineru(content_list: list[dict]) -> list[Figure]:
    figures = []
    for block in content_list:
        if block["type"] in ("image", "table_image", "chart"):
            figures.append(Figure(
                image_path=block["img_path"],                                   # đã crop sẵn thành file riêng
                caption=block.get("image_caption") or block.get("chart_caption"),
                label=None,                                                       # PDF không có \label gốc, để trống
                anchor=build_anchor_from_surrounding_text(block, content_list),   # đoạn text ngay trước/sau bbox
                page_number=block["page_idx"],
                missing=False,
            ))
    return figures
```

> **Giới hạn cần biết:** ảnh trích từ PDF luôn là **raster crop** (PNG), dù bản gốc là vector — không tái dựng lại TikZ/vector (xem Non-goals). Nếu MinerU nhận nhầm bảng/công thức phức tạp thành ảnh thay vì bảng/LaTeX math (lỗi layout-detection đã biết), figure đó sẽ bị "đóng băng" thành ảnh tĩnh thay vì nội dung editable — không có dịch vụ trả phí để fallback ở MVP (xem Non-goals), user sẽ thấy warning rõ ràng thay vì kết quả bị âm thầm sai.

### Step P2 — Render Editable .tex → output là `.zip`

```python
def render_editable_bundle(doc: ParsedDocument) -> str:   # trả path tới .zip
    main_tex = latex_template.render(
        sections=[{"heading": s.title, "body": s.raw_latex} for s in doc.sections],
        figures=doc.figures,   # template chèn \begin{figure}...\end{figure} tại đúng anchor
        bibliography=doc.raw_citations,
    )
    bundle_dir = make_temp_dir()
    write(bundle_dir / "main.tex", main_tex)
    for fig in doc.figures:
        if not fig.missing:
            copy(fig.image_path, bundle_dir / "figures" / basename(fig.image_path))
    return zip_dir(bundle_dir)   # → {doc_id}.zip: main.tex + figures/
```

Jinja2 template (đoạn figure):
```latex
{% for figure in figures if not figure.missing %}
\begin{figure}[h]
  \centering
  \includegraphics[width=0.8\textwidth]{figures/{{ figure.image_path | basename }}}
  {% if figure.caption %}\caption{ {{ figure.caption }} }{% endif %}
  {% if figure.label %}\label{ {{ figure.label }} }{% endif %}
\end{figure}
{% endfor %}
```

Caption text (nếu có) là 1 paragraph bình thường → vẫn đi qua Critic Agent (P3a) như mọi đoạn văn khác. Ảnh (pixel) thì không — Critic Agent không có gì để "nhận xét văn phong" trên 1 file ảnh.

---

## Chi tiết Step P3/P4 — render Suggest vs Warning

**Step P3 — 3 nhánh chạy song song (`asyncio.gather`):**

- **P3a Critic Agent** — 1 agent/section, temp=0, conservative, output JSON issue list theo 4 aspect (clarity/terminology/flow/redundancy). Context isolation: mỗi agent chỉ thấy section của nó.
  > **Lưu ý độ tin cậy:** *pattern* "chia per-section + aspect cố định giảm generic comment" có nghiên cứu chứng minh (MARG: 60%→29%). Nhưng **4 nhãn cụ thể** `clarity/terminology/flow/redundancy` là suy ra theo scope (đổi từ aspect đánh giá khoa học của Reviewer2 — `novelty/soundness/significance` — sang aspect văn phong để khớp Non-goals), **chưa có benchmark độc lập** kiểm chứng đúng 4 nhãn này. Xem Identified Gaps #11.
- **P3b Reference Verification** — waterfall cascade tái dùng `semantic_scholar.py`/`openalex.py`/`arxiv_search.py` (Step ① research-agent) ở mode "lookup 1 paper" + multi-field match (title/year/author, `rapidfuzz`) + LLM judge (temp=0) cho vùng xám giữa 2 threshold.
- **P3c Link Liveness Check** — HTTP HEAD song song cho raw URL không phải citation học thuật, không dùng LLM.

**Output P3 ghi vào Annotation Store có thể mutate (không phải `annotations.json` tĩnh):**

```python
class Annotation(TypedDict):
    id: str
    type: Literal["suggest", "warning"]
    anchor: TextQuoteSelector            # {exact, prefix, suffix} — KHÔNG dùng offset số
    aspect: str                          # clarity|terminology|flow|redundancy (suggest)
                                          # citation_not_found|metadata_mismatch|broken_link|missing_asset (warning)
    comment: str
    suggested_fix: str | None            # CHỈ suggest mới có, warning luôn None
    evidence: dict | None                # warning: kết quả lookup từ P3b
    status: Literal["pending", "accepted", "rejected", "dismissed"]

class TextQuoteSelector(TypedDict):
    exact: str      # đoạn text gốc bị flag
    prefix: str     # ~32 ký tự ngay trước (để disambiguate nếu exact lặp lại nhiều nơi)
    suffix: str     # ~32 ký tự ngay sau
```

**Render trên frontend:** editor (Monaco/CodeMirror) re-tìm `exact` (disambiguated bởi `prefix`/`suffix`) trong buffer hiện tại mỗi lần render — annotation tự "neo lại" đúng vị trí dù user đã sửa đoạn khác ở trên/dưới. Nếu không tìm thấy `exact` nữa (user đã tự sửa đúng đoạn đó) → annotation tự ẩn, không báo lỗi.

**Affordance khác nhau theo type:**

| | `suggest` | `warning` |
|---|---|---|
| Nút hành động | Accept ✓ / Reject ✗ | Dismiss (chỉ 1 nút) |
| Khi Accept | Ghi `suggested_fix` vào doc tại vị trí `anchor` | — (không áp dụng gì, vì không có) |
| Lý do tách | Có bản sửa cụ thể, an toàn để áp nếu user đồng ý | Không có "bản sửa đúng" cho citation giả — Accept sẽ ngầm gợi ý có, gây hiểu lầm (xem Non-goals) |

**4 verdict categories cho `warning` citation (không binary đúng/sai):**

| Verdict | Ý nghĩa |
|---|---|
| `Verified` | Match cao trên ≥1 source — không tạo warning |
| `Metadata Mismatch` | Tìm thấy paper gần giống nhưng lệch field (năm/tác giả sai) |
| `Not Found` | Không khớp ở cả 3 source — khả năng cao bị hallucinate, **kèm caveat không tuyệt đối** (paper hiếm/sách/non-indexed vẫn có thể không có) |
| `Unreachable` | Raw URL trả lỗi HTTP |

---

## Step P5 — Selection-triggered Explain / Rewrite

**2 action cố định khi user tô chọn text** (không dùng ô chat tự do, để giảm ambiguity và giới hạn rõ scope LLM được phép làm):

### Action "Giải thích"

```http
POST /api/pdf-agent/{doc_id}/explain
{"selected_text": "...", "anchor": {"exact": "...", "prefix": "...", "suffix": "..."}}
```

```http
POST https://integrate.api.nvidia.com/v1/chat/completions
{
  "model": "openai/gpt-oss-120b", "temperature": 0.3, "stream": true,
  "messages": [
    {"role": "system", "content": "Explain what this excerpt from an academic paper is arguing/about, in 2-4 sentences. Do not suggest edits."},
    {"role": "user", "content": "{selected_text}\n\nContext xung quanh: {prefix} [...] {suffix}"}
  ]
}
```

Trả về plain text, hiển thị tooltip/sidebar — **không có patch, không cần approve** (không có gì để mutate).

### Action "Viết lại"

```http
POST /api/pdf-agent/{doc_id}/rewrite
{"selected_text": "...", "anchor": {...}, "instruction": "ngắn gọn hơn"}  // instruction optional
```

```http
POST https://integrate.api.nvidia.com/v1/chat/completions
{
  "model": "openai/gpt-oss-120b", "temperature": 0.5, "stream": false,
  "messages": [
    {"role": "system", "content": "Rewrite ONLY the given excerpt. Output JSON: {\"old_text\": <verbatim copy of input>, \"new_text\": <rewritten version>}. Do not expand scope beyond the excerpt."},
    {"role": "user", "content": "{selected_text}"}
  ]
}
```

**Ràng buộc bắt buộc trước khi cho phép Apply** (giống Edit tool của coding agent):
```python
def validate_rewrite_patch(patch: dict, current_doc: str) -> bool:
    return patch["old_text"] in current_doc   # phải match chính xác buffer HIỆN TẠI
    # Nếu False (user đã sửa tay từ lúc tô tới lúc LLM trả lời) → reject patch,
    # báo user "đoạn này đã thay đổi, vui lòng tô lại"
```

Patch hiển thị dạng diff (giống Accept/Reject của `suggest`) — **chỉ ghi vào doc khi user bấm Apply**.

**Chi phí Step P5:** on-demand, không phải batch — mỗi lần trigger ~300-800 input + 100-300 output tokens ≈ **~$0.0001/lần gọi**, không tính vào cost cố định/document.

---

## Step P6 — Save to My Review (tái dùng `review-litureature_SPEC_1.0.1.md`)

**Không tạo bảng mới.** Mở rộng bảng `reviews` đã có để chứa cả output PDF Agent:

```sql
ALTER TABLE reviews
  ADD COLUMN source_type TEXT NOT NULL DEFAULT 'generated'
    CHECK (source_type IN ('generated', 'uploaded')),     -- 'generated'=Research Agent, 'uploaded'=PDF Agent
  ADD COLUMN content_format TEXT NOT NULL DEFAULT 'markdown'
    CHECK (content_format IN ('markdown', 'tex')),
  ADD COLUMN pending_annotations JSONB,                    -- annotation chưa resolve, để resume sau
  ALTER COLUMN query DROP NOT NULL;                        -- document upload không có query gốc
```

> Nếu bảng `reviews` đã có dữ liệu production và không muốn đổi schema cột cũ: thêm cột mới như trên là additive, an toàn migrate. Không cần rename `markdown_content` — chỉ cần `content_format='tex'` thì FE biết đọc cột đó là LaTeX thay vì Markdown.

**Vì sao cần lưu `pending_annotations`, khác với spec gốc chỉ lưu content cuối:** nếu chỉ lưu `markdown_content`/`tex_content` như review-litureature_SPEC_1.0.1.md, mọi warning citation đã phát hiện (tốn API calls để verify) sẽ mất khi user đóng tab — mở lại phải chạy lại toàn bộ Step P3. Lưu kèm annotation cho phép resume đúng chỗ đang dừng.

**API:** tái dùng 100% endpoint đã có (`POST/GET/PATCH/DELETE /api/reviews`, `/export`, `/duplicate`) — chỉ thêm field `source_type`/`content_format` vào body khi tạo, và export PDF nhánh `content_format=tex` chạy qua `pdflatex` thay vì `weasyprint` (markdown→PDF).

---

## Kiến trúc: tích hợp với hệ thống hiện tại

```
ORCHESTRATOR (Research Agent)              PDF AGENT (entry point độc lập)
   Step 0 → ⑩                                 Step P0 → P6
        │                                          │
        └──────────────── shared services ─────────┤
                services/semantic_scholar.py        │
                services/openalex.py                │
                services/arxiv_search.py             │
                services/citation_verifier.py         │
                services/latex_exporter.py             │
                                                       │
                                          bảng `reviews` (Supabase) ──┘
                                          (mở rộng source_type/content_format)
```

```python
class PDFAgentState(TypedDict):
    doc_id: str
    input_format: Literal["pdf", "tex", "tex_bundle"]
    raw_file_path: str
    sections: list[Section]
    raw_citations: list[RawCitation]
    figures: list[Figure]
    bundle_path: str                     # .zip: main.tex + figures/
    main_tex_path: str                   # extracted main.tex, mutate trực tiếp khi Apply
    annotations: list[Annotation]        # mutable — accept/reject/dismiss cập nhật status
    review_id: str | None                # set sau khi Step P6 save thành công
    error: str | None
```

*(Schema đồng bộ 100% với `PDFAgentState` ở `pdf-agent_PLAN_2.0.md` §3 — không định nghĩa lại field name khác nhau giữa 2 tài liệu.)*

---

## System Guardrails

```python
PDF_AGENT_GUARDRAILS = {
    "max_file_size_mb": 20, "max_pages": 60, "max_citations_verify": 150,
    "max_sections_critic": 20, "citation_lookup_timeout_s": 10, "link_check_timeout_s": 5,
    "critic_temperature": 0, "llm_judge_temperature": 0,
    "match_threshold_high": 0.85, "match_threshold_low": 0.55,
    "rewrite_temperature": 0.5,
    "explain_temperature": 0.3,
    "anchor_context_chars": 32,          # độ dài prefix/suffix cho TextQuoteSelector
    "require_exact_match_before_apply": True,   # patch.old_text phải match buffer hiện tại
    "warning_has_no_accept_action": True,        # warning chỉ Dismiss, không bao giờ có Accept
}
```

---

## Chi phí ước tính

| Step | Task | Chi phí |
|---|---|---|
| P1 (chỉ nhánh `.pdf`) | Reference list cleanup | ~$0.0008/document |
| P3a | Critic Agents (15 section, parallel) | ~$0.0017/document |
| P3b | LLM judge (vùng xám, ~12 citation) | ~$0.0003/document |
| P3c | Link check | $0 (không LLM) |
| P5 | Explain (mỗi lần trigger) | ~$0.00005 |
| P5 | Rewrite (mỗi lần trigger) | ~$0.0001 |
| P6 | Save to My Review | $0 (DB write, không LLM) |
| **TOTAL cố định/document** | | **~$0.003** (nhánh `.pdf`) · **~$0.002** (nhánh `.tex`) |

Selection actions (P5) là on-demand, không cộng vào cost cố định/document — chỉ tính khi user thực sự dùng. Rẻ hơn 1 session Research Agent (~$0.02) vì tái dùng search infra miễn phí.

---

## Backing research

- **MinerU** ([github.com/opendatalab/mineru](https://github.com/opendatalab/mineru)) — pipeline layout+OCR+formula→LaTeX, self-host free, caption↔figure pairing.
- **OmniDocBench** (arXiv:2412.07626) — benchmark đối chiếu công cụ PDF parsing.
- **MARG** (arXiv:2401.04259) — multi-agent feedback per-section, giảm generic comment 60%→29%.
- **ICLR Review Feedback Agent** (arXiv:2504.09737) — 20K review thật, 89% được đánh giá tốt hơn.
- **LLM-REVal** (arXiv:2510.12367) — cảnh báo self-bias của LLM reviewer.
- **CheckIfExist** (arXiv:2602.15871) — multi-field matching algorithm cho citation verification.
- **CiteCheck** (arXiv:2605.27700) — waterfall cascade + LLM verifier 2-pass, 88.9% accuracy.
- **Reference Hallucination in Deep Research Agents** (arXiv:2604.03173) — benchmark 14%-95% hallucination rate.
- **InkSync** (arXiv:2309.15337) — "Warn, Verify, Audit" framework cho LLM text-editing.
- **W3C Web Annotation Data Model — TextQuoteSelector** ([w3.org/TR/annotation-model](https://www.w3.org/TR/annotation-model/)) — chuẩn anchor annotation, dùng bởi Hypothesis.
- **OpenDataLoader-pdf** ([opendataloader.org](https://opendataloader.org/)) — đã cân nhắc thay MinerU, Apache 2.0 + không cần GPU + accuracy cao nhất benchmark độc lập, nhưng giữ MinerU vì track record dài hơn (xem Landscape A).
- IDE diff-apply pattern (Cursor/Copilot/Claude Code Edit tool) — constrained diff generation + exact-match validation.
- Market precedent: Elicit/Consensus (generate) vs Scite (verify) vs Paperpal (polish) tách biệt 3 sản phẩm — backing cho Non-goals.

---

## Identified Gaps — Defer post-MVP

1. **Patch research-agent_SPEC_2.0.md (ưu tiên cao):** Step ⑩ sinh Introduction/Conclusion (temp=0.7, dùng `\cite{}`) SAU Step ⑦/⑧ → citation trong Intro/Conclusion chưa từng qua claim extraction/verification. Việc của Research Agent, không phải PDF Agent.
2. **Citation-context fit** — câu có cite nhưng nội dung paper không thật sự support câu đó. MVP chỉ flag qua Critic Agent (aspect "flow"), chưa có verified score riêng.
3. **MinerU accuracy limit, không có fallback** — PDF scan chất lượng thấp/layout dị mà MinerU xử lý kém sẽ không có service trả phí để escalate (đã quyết định không dùng Mathpix). MVP chỉ báo lỗi/warning rõ cho user; đánh giá lại nếu sau này data thực tế cho thấy tỷ lệ PDF xử lý kém quá cao.
4. **Suspicious-domain detection** cho raw URL — MVP chỉ check HTTP status.
5. **Track-changes style auto-fix** — MVP chỉ xuất comment tách riêng, chưa apply trực tiếp vào `.tex`.
6. **Export diff PDF dùng `latexdiff`/`changes` package** — hữu ích để share dạng PDF tĩnh, không phải core MVP.
7. **Migration `reviews` table** — quyết định rename `markdown_content`→`content` hay giữ cột cũ + thêm cột mới — cần xác nhận trạng thái thực tế của bảng trước khi viết migration.
8. **Đa người dùng cùng sửa 1 document** (collaborative editing) — hiện thiết kế P4/P5 giả định single-user session.
9. **Heuristic tìm `main.tex` trong zip** khi project có nhiều file `.tex`/`\input{}`/`\include{}` — hiện chỉ tìm file đầu tiên có `\documentclass`+`\begin{document}`.
10. **Re-pairing caption nếu MinerU ghép sai** — chưa có bước review tay cho trường hợp model ghép caption nhầm.
11. **4-label taxonomy của Critic Agent chưa có benchmark độc lập** — `clarity/terminology/flow/redundancy` là adaptation theo pattern MARG/Reviewer2 (đã được nghiên cứu chứng minh ở pattern chung), không phải 4 nhãn gốc đã test trực tiếp. Cần đánh giá lại độ chính xác/hữu ích thực tế sau khi có data từ Phase 9 (research-agent_PLAN_2.0.md style integration test).
12. **OpenDataLoader-pdf** — đã nghiên cứu làm phương án thay MinerU (license tốt hơn, không cần GPU, accuracy cao hơn theo benchmark độc lập), nhưng quyết định giữ MinerU vì track record dài hơn. Có thể đánh giá lại nếu sau MVP phát hiện MinerU không ổn định/chậm hơn kỳ vọng trong thực tế deploy.
