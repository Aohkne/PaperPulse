# Knowledge Graph — Tổng quan (Overview)

**Version:** 2.0
**Phụ thuộc:** `research-agent_SPEC_2.0.md` (Step ②bis, ④, ⑤, ⑦, ⑧, ⑨)
**Vị trí trong flow:** Step **⑨bis** — sau Routing + Human Review (Step ⑨), trước/song song Export (Step ⑩)
**Changelog từ v1.0:** xem mục [CHANGELOG](#changelog) cuối file

---

## Tóm tắt (Executive Summary)

> Literature review dạng văn xuôi (`.tex`) là tuyến tính — đọc xong 8 theme section, người dùng vẫn khó tự dựng trong đầu "ai đồng ý với ai, ai phản bác ai, cụm nào đang mâu thuẫn nhiều nhất". Đây chính là khoảng trống mà SPEC 2.0 liệt là *Non-goal* (research gap identification).

**Cách làm sai (naive approach):** vẽ lại citation network kiểu Connected Papers/Litmaps — node = paper, edge = cites. Không sai, nhưng **không khác biệt**: không gian này đã bão hoà, và edge "cites" không nói lên *tại sao* hai bài liên quan.

**Cách làm của spec này:** Pipeline v2.0 đến cuối Step ⑨ đã tự sinh ra đủ nguyên liệu ngữ nghĩa (citation intent, theme membership, claim Supports/Contradicts/Extends đã verify) — chỉ cần **lắp ráp lại thành graph**, không cần thêm LLM call mới. Output là 1 **multi-layer graph hình hệ mặt trời**: 1 Topic node trung tâm → Theme layer → Paper layer (chỉ bài thật sự xuất hiện trong review, không phải toàn corpus) → Claim/discourse layer.

---

## Mục tiêu (Goals)

| Mục tiêu | Metric | Cách đạt được |
|---|---|---|
| Visualize literature review không cần đọc tuyến tính | User thấy structure trong < 30s nhìn graph | Multi-layer node-link graph, bố cục hệ mặt trời quanh 1 Topic node |
| Lộ ra "research tension" mà không cần gap-analysis riêng | Cụm `contradicts` dày quanh 1 theme = tín hiệu trực quan | Claim layer, edge `intent` nối claim→theme, filter theo edge type |
| Không tốn thêm LLM call | Chi phí thêm ~$0/session | Tái sử dụng data đã có từ Step ②bis/④/⑤/⑦/⑧ |
| Graph nhỏ, đúng phạm vi review (không phải cả corpus search) | Paper node ~60-150 (không phải 600-900) | Paper layer chỉ lấy từ `papers_per_theme`, không lấy `snowballed_papers` toàn bộ |
| Không rối mắt khi nhìn nhiều node | Mặc định không hiện label trên graph | `renderLabels: false`, click node → mở card riêng |
| Bố cục dễ định hướng ngay từ cái nhìn đầu | Có 1 điểm gốc duy nhất để mắt bắt đầu | Topic (root) node ở tâm, layout radial tĩnh (xem mục Frontend) |

### Non-goals
- Không thay thế research gap identification có cấu trúc (vẫn defer như SPEC 2.0 đã ghi) — graph này chỉ *gợi ý* gap bằng trực quan, không *phân loại* gap.
- Không build concept-extraction NLP riêng (xem mục "Concept layer" — dùng OpenAlex Topics có sẵn trước).
- Không cần graph database (Neo4j) ở quy mô MVP — graph đã scope nhỏ (~60-150 paper + theme + claim), `networkx` in-memory dư khả năng.
- Không bắt buộc graph phải "chuyển động" liên tục — animation chỉ là tính năng optional, tắt mặc định (xem mục Frontend, lý do accessibility).

---

## Bối cảnh nghiên cứu (Landscape — đã có gì trên thế giới)

| Hướng | Đại diện | Cơ chế | Vì sao không chọn làm core / chọn làm core |
|---|---|---|---|
| **Citation-topology graph** | Connected Papers, Litmaps, ResearchRabbit (acquired by Litmaps, 11/2025), Inciteful | Node = paper, edge = cites/co-cited, force-directed layout | ❌ Không chọn làm core — chỉ là khám phá bài mới, không visualize nội dung 1 review đã hoàn thành, và không tạo khác biệt cạnh tranh |
| **Bibliometric/co-citation mapping** | VOSviewer, CiteSpace, Bibliometrix | Cluster theo co-citation, bibliographic coupling, co-word; xuất ảnh tĩnh | ⚠️ Dùng làm edge-weight phụ (đã defer ở SPEC 2.0 mục Identified Gaps #2), không phải layer chính |
| **Stance-classified citations** | **scite.ai Smart Citations** | DL model gán nhãn Supporting/Contrasting/Mentioning cho từng câu trích dẫn, ~88-92% precision, 1.4B citation statements | ✅ Prior art gần nhất với claim layer — nhưng scite làm ở mức câu trích dẫn toàn corpus; pipeline của bạn làm ở mức claim-trong-theme đã verify 3-tier → granularity tốt hơn |
| **Structured/machine-actionable KG** | ORKG (TIB Hannover) | Paper → RDF triples (problem/method/result), so sánh side-by-side | ❌ Không chọn — cần ontology curation thủ công, conflict với pipeline tự động hoàn toàn |
| **Discourse graph** | Joel Chan / Protocol Labs Research, Roam discourse-graph extension (arXiv:2407.20666) | Node = Claim/Question/Evidence (không phải document), edge = supports/opposes | ✅ **Conceptually đây là core của spec này** — khác biệt duy nhất: họ làm thủ công, bạn có claim extraction + verification tự động sẵn |
| **LLM-automated KG construction** | Microsoft GraphRAG | LLM extract entity-relation triples → Leiden community detection → hierarchical summary | ⚠️ Kỹ thuật tham khảo cho **concept layer optional** (xem mục Defer), không phải MVP — tốn thêm 1 LLM call |
| **Free concept tagging** | OpenAlex Topics | Taxonomy 4 tầng (domain>field>subfield>topic, ~4.500 topic), LLM-named cluster, có sẵn qua API | ✅ Dùng nếu cần concept-layer — **miễn phí**, lấy được ngay từ Step ① (đã gọi OpenAlex rồi), không cần LLM call riêng |
| **Radial/hierarchical layout** | D3 `d3-hierarchy` (`tree`/`cluster` + polar coordinate conversion) | Convert toạ độ cây sang toạ độ cực: góc = nhánh, bán kính = độ sâu — tạo hiệu ứng "hệ mặt trời" | ✅ Dùng làm thuật toán bố cục frontend (xem mục Frontend) — không cần thêm dependency, chỉ cần trig cơ bản vì cây chỉ sâu 4 tầng |

---

## Kiến trúc: Multi-layer Graph hình hệ mặt trời

### 4 layers (Topic root + 3 layer cũ)

| Layer | Node | Edge | Lấy từ state field nào | Insight khi nhìn vào |
|---|---|---|---|---|
| **Topic** *(MỚI)* | `topic:root` — duy nhất 1 node, label = câu query gốc | `covers` nối topic → mỗi theme | `state["query"]` | Điểm gốc để mắt bắt đầu, mọi theme toả ra từ đây |
| **Theme** | `theme:{slug}` — label = theme name | `belongs_to` nối paper ↔ theme (bipartite) | `papers_per_theme` (key) | Theme nào đang được thảo luận, theme nào nhiều/ít claim |
| **Paper** *(SỬA phạm vi)* | `paper:{paperId}` — label=title, size=`citationCount` | `cites` (màu/độ đậm theo `isInfluential`, tooltip=`intent`: methodology/background/result) — **chỉ thêm nếu cả 2 đầu đã có trong graph** | **`papers_per_theme` (value) — KHÔNG dùng `snowballed_papers` toàn bộ nữa** | Bài nào thật sự được viết/cite trong review (không phải cả corpus search ~600-900 bài) |
| **Claim/discourse** | `claim:{id}` — label=claim text rút gọn, icon theo verdict (✓Supported / ✗Refuted / ?Uncertain) | 2 edge riêng — xem dưới | `human_reviewed_claims` (sau Step ⑨, claims đã chốt include/remove) | **Layer giá trị nhất**: cụm `contradicts` dày quanh 1 theme = research tension |

### Claim có 2 edge riêng, không gộp 1 *(SỬA so với v1.0)*

v1.0 từng nối `claim → paper nguồn` và gắn nhãn `intent` lên edge đó — **sai logic**: 1 claim không thể "contradict" chính cái paper nó được trích ra. Sửa lại:

- **`claim → theme`, `type = intent`** (`supports`/`contradicts`/`extends`) — edge mang ý nghĩa, dùng cho filter "chỉ hiện contradicts". Theme đích suy ra từ `source_paperId` của claim, tra ngược qua `papers_per_theme` (paper thuộc theme nào → claim từ paper đó nối tới theme đó). Một paper có thể thuộc nhiều theme (paper liên ngành) → claim của nó nối tới tất cả theme đó.
- **`claim → paper`, `type = evidenced_by`** — edge trung tính, chỉ để biết evidence lấy từ đâu, không mang stance, dùng khi click claim mở card.

**Lưu ý:** Step ⑦ (claim extraction) hiện tại **không cần sửa schema** — không cần thêm field `theme` vào claim. Theme đích được suy luận hoàn toàn từ `papers_per_theme` đã có sẵn, không cần thêm thông tin mới từ LLM.

Frontend mặc định hiện **cả 4 layer cùng lúc** — vì Paper layer giờ đã scope nhỏ (~60-150 node, không phải 900), hiện hết vẫn tạo được đúng hiệu ứng "hệ mặt trời" mà không rối. Layer toggle vẫn giữ để decluttering theo nhu cầu, không phải để che layer mặc định nữa.

### Node/Edge JSON Schema

```json
{
  "nodes": [
    {"id": "topic:root", "type": "topic", "label": "Diffusion Language Models as Drafters in Speculative Decoding"},

    {"id": "theme:foundations", "type": "theme", "label": "Foundations of Speculative Decoding"},
    {"id": "theme:diffusion-drafters", "type": "theme", "label": "Diffusion Language Models as Drafters"},

    {"id": "paper:2211.17192", "type": "paper", "label": "Fast Inference from Transformers via Speculative Decoding", "year": 2023, "citation_count": 612, "source": "arxiv"},
    {"id": "paper:p3_demo", "type": "paper", "label": "Diffusion Drafters for Speculative Decoding", "year": 2024, "citation_count": 12, "source": "s2"},

    {"id": "claim:c1", "type": "claim", "label": "Speculative decoding preserves target model's output distribution exactly", "verdict": "Supported", "confidence": 0.95},
    {"id": "claim:c3", "type": "claim", "label": "Diffusion drafters show lower acceptance rate when draft length > 8 tokens", "verdict": "Supported", "confidence": 0.74}
  ],
  "edges": [
    {"source": "topic:root", "target": "theme:foundations", "type": "covers"},
    {"source": "topic:root", "target": "theme:diffusion-drafters", "type": "covers"},

    {"source": "paper:2211.17192", "target": "theme:foundations", "type": "belongs_to"},
    {"source": "paper:p3_demo", "target": "theme:diffusion-drafters", "type": "belongs_to"},
    {"source": "paper:p3_demo", "target": "paper:2211.17192", "type": "cites", "is_influential": true, "intent": "methodology"},

    {"source": "claim:c1", "target": "paper:2211.17192", "type": "evidenced_by"},
    {"source": "claim:c1", "target": "theme:foundations", "type": "supports"},

    {"source": "claim:c3", "target": "paper:p3_demo", "type": "evidenced_by"},
    {"source": "claim:c3", "target": "theme:diffusion-drafters", "type": "contradicts"}
  ],
  "stats": {"papers": 87, "themes": 8, "claims": 187, "contradicts_edges": 14}
}
```

---

## Tích hợp vào flow pipeline hiện tại

```
[Step ⑨] Routing + Human Review
            ↓
[Step ⑨bis] Knowledge Graph Construction  *(MỚI — spec này)*
            ↓
[Step ⑩] Merge → Literature Review + PDF Links → Export
```

**Node mới (LangGraph) — đã sửa theo kiến trúc 4-layer:**
```python
# graph/nodes/build_graph.py
async def build_graph_node(state: ResearchState) -> dict:
    g = nx.MultiDiGraph()

    # Topic layer
    topic_id = "topic:root"
    g.add_node(topic_id, type="topic", label=state["query"])

    # Theme layer + Paper layer (CHỈ paper trong papers_per_theme, không phải toàn snowballed_papers)
    paper_to_themes: dict[str, list[str]] = {}
    for theme, papers in state["papers_per_theme"].items():
        theme_id = f"theme:{slugify(theme)}"
        g.add_node(theme_id, type="theme", label=theme)
        g.add_edge(topic_id, theme_id, type="covers")
        for p in papers:
            paper_id = f"paper:{p['paperId']}"
            if not g.has_node(paper_id):
                g.add_node(paper_id, type="paper", **paper_attrs(p))
            g.add_edge(paper_id, theme_id, type="belongs_to")
            paper_to_themes.setdefault(paper_id, []).append(theme_id)

    # cites edge — chỉ thêm nếu CẢ 2 đầu đã nằm trong scope (đã có node)
    for edge in state["citation_edges"]:
        src, tgt = f"paper:{edge['source']}", f"paper:{edge['target']}"
        if g.has_node(src) and g.has_node(tgt):
            g.add_edge(src, tgt, type="cites", is_influential=edge["isInfluential"], intent=edge["intent"])

    # Claim layer — claim → paper (evidenced_by, trung tính) + claim → theme (intent, mang ý nghĩa)
    for claim in state["human_reviewed_claims"]:
        paper_id = f"paper:{claim['source_paperId']}"
        if paper_id not in paper_to_themes:
            continue  # claim của paper ngoài scope review → bỏ qua
        claim_id = f"claim:{claim['id']}"
        g.add_node(claim_id, type="claim", **claim_attrs(claim))
        g.add_edge(claim_id, paper_id, type="evidenced_by")
        for theme_id in paper_to_themes[paper_id]:
            g.add_edge(claim_id, theme_id, type=claim["intent"].lower())

    data = nx.node_link_data(g)
    stats = {
        "papers": sum(1 for _, d in g.nodes(data=True) if d["type"] == "paper"),
        "themes": sum(1 for _, d in g.nodes(data=True) if d["type"] == "theme"),
        "claims": sum(1 for _, d in g.nodes(data=True) if d["type"] == "claim"),
        "contradicts_edges": sum(1 for *_, d in g.edges(data=True) if d.get("type") == "contradicts"),
    }
    return {"knowledge_graph": {"nodes": data["nodes"], "edges": data["links"], "stats": stats}}
```

**Lý do đặt sau Step ⑨ (không phải sau Step ⑦):** claims phải đã qua verify (Step ⑧) **và** human review (Step ⑨) mới chốt được include/remove — graph dựng trên claim chưa lọc sẽ lẫn cả claim bị reject.

**Lý do không cần parallel với Step ⑩:** không có LLM call → build graph cho ~300 node bằng `networkx` chỉ tốn vài chục ms, không phải bottleneck cần tối ưu song song.

---

## Thay đổi cần thiết lên SPEC 2.0 / PLAN 2.0 hiện tại

**Gap quan trọng nhất:** `ResearchState.snowballed_papers` (`research-agent_PLAN_2.0.md:120`) hiện chỉ lưu **list paper**, không lưu **edge** (ai cite ai). Response của S2 citations/references API ở Step ②bis (`research-agent_SPEC_2.0.md:397-431`) đã có sẵn `contexts`, `intents`, `isInfluential`, `citingPaper` — nhưng `services/snowball_logic.py` hiện chỉ extract ra paper, bỏ qua quan hệ.

**Cần thêm:**
```python
# graph/state.py — thêm field mới
class ResearchState(TypedDict):
    ...
    citation_edges: list[dict]   # [{source, target, intent, isInfluential}] — MỚI
    knowledge_graph: dict        # {nodes, edges, stats} — MỚI, output Step ⑨bis
```

```python
# services/snowball_logic.py — sửa để giữ lại edge khi gọi S2 citations/references
def snowball(seed_papers: list[dict]) -> tuple[list[dict], list[dict]]:
    papers, edges = [], []
    for seed in seed_papers:
        for citation in s2_citations(seed["paperId"]):
            papers.append(citation["citingPaper"])
            edges.append({
                "source": citation["citingPaper"]["paperId"],
                "target": seed["paperId"],
                "intent": citation["intents"][0] if citation["intents"] else "background",
                "isInfluential": citation["isInfluential"],
            })
    return papers, edges  # trước đây chỉ return papers
```

Đây là thay đổi nhỏ (không phải rewrite), nhưng **phải làm trước** khi implement Step ⑨bis, nếu không Paper layer sẽ không có edge để vẽ. **Không cần sửa Step ⑦** (claim extraction) — theme đích của claim suy ra từ `papers_per_theme`, không cần LLM trả thêm field.

---

## API Endpoint

```http
GET /api/research/graph?thread_id={thread_id}
```

```json
{
  "nodes": [ ... ],
  "edges": [ ... ],
  "stats": {"papers": 87, "themes": 8, "claims": 187, "contradicts_edges": 14}
}
```

Không cần endpoint riêng để build graph — `knowledge_graph` đã có sẵn trong state sau khi graph LangGraph chạy xong Step ⑨bis, endpoint chỉ đọc lại từ checkpoint qua `thread_id`.

---

## Frontend: Visualization & Interaction

### Library

| Library | Điểm mạnh | Khi nào chọn |
|---|---|---|
| **`@react-sigma`** (Sigma.js + Graphology) | WebGL, render mượt, React bindings chính thức (`<SigmaContainer>`, `useLoadGraph`), có `nodeReducer`/`edgeReducer` để highlight động, có event `clickNode`/`clickStage`/drag mouse events | **Khuyến nghị** — đủ mọi tương tác cần (highlight, drag, click→card) không cần thêm lib |
| `react-force-graph` | WebGL, code nhanh, tốt cho 3D | MVP nhanh nếu cần demo gấp, customize kém hơn |
| `Cytoscape.js` | Bộ thuật toán graph dựng sẵn (centrality, shortest path), nhưng SVG/Canvas — chậm dần từ ~10K node | Không cần — graph đã scope nhỏ, không cần thuật toán nặng |

### Layout: hệ mặt trời tĩnh mặc định, KHÔNG tự quay

Thuật toán: convert toạ độ cây (Topic→Theme→Paper→Claim) sang **toạ độ cực** — góc = vị trí trong vòng (chia đều theo số lượng sibling), bán kính = tầng:

```
radius_theme = 150px   (vòng 1, quanh Topic)
radius_paper = 320px   (vòng 2, trong sector góc của theme nó thuộc)
radius_claim = 480px   (vòng 3, gần paper nó evidenced_by)
```

Đây chính là kỹ thuật **radial tree layout** (D3 gọi là "solar system-like effect" khi convert tree/cluster layout sang polar coordinate) — chỉ cần viết hàm trig ~30 dòng, **không cần thêm dependency** (`d3-hierarchy` không bắt buộc vì cây chỉ sâu 4 tầng, fanout nhỏ).

**Layout đứng yên theo mặc định** — không có animation liên tục. Lý do: WCAG 2.3.3 (Animation from Interactions) yêu cầu phải tắt được animation không thiết yếu; WCAG 2.2.2 (Pause, Stop, Hide) yêu cầu nút pause cho animation chạy nền liên tục; người có rối loạn tiền đình (vestibular disorder) có thể chóng mặt khi nhìn node xoay liên tục — không hợp với 1 tool cần đọc claim text cẩn thận.

**Optional toggle "▶ Chuyển động"** — tắt mặc định. Khi bật: mỗi frame (`requestAnimationFrame`) tăng góc quay chậm, gán lại `x,y`. Tự tắt nếu OS bật `prefers-reduced-motion`. Có nút pause rõ ràng khi đang bật.

### Tương tác

| Hành động | Kết quả |
|---|---|
| **Mặc định** | `renderLabels: false` — chỉ thấy chấm tròn màu theo `type`, không có chữ nào trên graph (tránh rối với ~300 node) |
| **Click vào node** | (1) `edgeReducer`/`nodeReducer` bôi đậm các edge nối tới node đó, mờ các edge khác. (2) Mở **card chi tiết** (không hiện label nổi trên graph) — nội dung theo `type` (xem bảng dưới) |
| **Click vào khoảng trống** (`clickStage`) | Đóng card, bỏ highlight |
| **Kéo node rồi buông** | Node tween (~250ms, easing) bay về lại toạ độ gốc theo radial layout — không ở yên vị trí buông tay |
| **Filter switch "chỉ hiện contradicts"** | Graph co lại chỉ còn `claim --contradicts--> theme`, cụm quanh theme đang có bất đồng |
| **Toggle layer** (checkbox Topic/Theme/Paper/Claim) | Ẩn/hiện theo nhu cầu — mặc định bật cả 4 vì graph đã scope nhỏ |

### Nội dung card theo node type

| Type | Card hiện gì |
|---|---|
| `topic` | Câu query gốc + `stats` tổng (số paper/theme/claim/contradicts) |
| `theme` | Tên theme + danh sách paper con + breakdown supports/contradicts/extends |
| `paper` | Title, year, citation count, nguồn (s2/openalex/arxiv), link PDF nếu có |
| `claim` | Claim text, verdict, confidence, evidence snippet (từ Step ⑧ 3-tier verification), link tới paper nguồn |

### Bảng màu (tránh trùng với màu mang ý nghĩa edge)

| Đối tượng | Màu | Lý do |
|---|---|---|
| Node `topic` | Vàng/hổ phách | Không dùng đỏ — tránh trùng với edge `contradicts` (đỏ), gây hiểu lầm "đây là điểm mâu thuẫn" |
| Node `theme` | Xám trung tính | Vai trò trung gian, không cần nổi bật bằng màu |
| Node `paper` | Xanh biển | Theo đề xuất ban đầu |
| Node `claim` | Tím | Theo đề xuất ban đầu |
| Edge `contradicts` | Đỏ | Quy ước mạnh: đỏ = mâu thuẫn/cảnh báo |
| Edge `supports` | Xanh lá | Đồng thuận |
| Edge `extends` | Cam | Khác xanh biển của node paper để không gây nhiễu |
| Edge `evidenced_by` | Xám nhạt, nét đứt | Trung tính — chỉ để tra nguồn, không mang stance |
| Edge `cites` / `belongs_to` / `covers` | Xám nhạt | Edge cấu trúc, không mang ý kiến |

---

## Concept Layer — Optional, KHÔNG nằm trong MVP

Nếu sau này cần thêm node "concept" (vd "Chunking", "Hallucination") thay vì chỉ topic/theme/paper/claim:

1. **Ưu tiên trước:** lấy `primary_topic` từ OpenAlex response (đã gọi ở Step ①, free, không cần LLM call mới).
2. **Chỉ nếu OpenAlex topic quá general:** áp dụng kỹ thuật GraphRAG (LLM extract entity-relation triples từ `theme_contents`, Leiden community detection để cluster) — nhưng đây tốn thêm 1 LLM call/session.

```
Chi phí concept-layer nếu enable (GraphRAG-style, KHÔNG có trong v2.0 MVP):
~15K tokens input + ~5K tokens output (tương tự scale Step ⑦)
Input:  15K × $0.039/1M = $0.0006
Output:  5K × $0.180/1M = $0.0009
Tổng:   ~$0.002/session thêm — defer cho đến khi OpenAlex topic chứng minh không đủ
```

---

## Chi phí Step ⑨bis

```
Knowledge Graph Construction: KHÔNG dùng LLM call mới
→ chi phí ~$0/session
(Tái sử dụng output đã có sẵn từ Step ②bis, ④, ⑤, ⑦, ⑧, ⑨ — chỉ lắp ráp bằng networkx)
```

---

## System Guardrails

```python
KG_GUARDRAILS = {
    "max_nodes_rendered": 500,             # giảm từ 1000 — Paper layer giờ scope nhỏ (~60-150), không phải 900
    "max_edges_rendered": 3000,
    "contradicts_cluster_min_size": 2,     # >=2 contradicting claims cùng theme → highlight cluster
    "default_visible_layers": ["topic", "theme", "paper", "claim"],  # hiện cả 4 — graph đã đủ nhỏ
    "motion_enabled_default": False,       # animation tắt mặc định — accessibility
    "respect_prefers_reduced_motion": True,
    "node_labels_default_visible": False,  # renderLabels: false — tránh rối, dùng card khi click
}
```

---

## Backing research

- **scite.ai Smart Citations** (Nicholson et al., *Quantitative Science Studies*, MIT Press, 2021): DL classifier cho citation intent (Supporting/Contrasting/Mentioning), 1.4B citation statements — prior art gần nhất cho claim layer.
- **Discourse Graphs** (arXiv:2407.20666, Protocol Labs Research): claim/evidence là unit trung tâm thay vì document — nền tảng lý thuyết của claim/discourse layer.
- **GraphRAG** (Microsoft Research, 2024): LLM entity-relation extraction + Leiden community detection — kỹ thuật tham khảo cho concept-layer optional.
- **Open Research Knowledge Graph** (arXiv:2206.01439, TIB Hannover): structured machine-actionable literature review — tham khảo, không áp dụng trực tiếp do cần ontology curation.
- **OpenAlex Topics** (Priem et al., 2022 + CWTS Leiden): taxonomy 4 tầng, free qua API — nguồn concept-layer ưu tiên.
- **VOSviewer / CiteSpace**: co-citation, bibliographic coupling — kỹ thuật edge-weight phụ, đã defer ở SPEC 2.0.
- **D3 radial tree layout** ([d3-hierarchy docs](https://d3js.org/d3-hierarchy/tree), [Observable radial tree example](https://observablehq.com/@d3/radial-tree/2)): kỹ thuật convert tree/cluster layout sang toạ độ cực, tạo hiệu ứng "solar system-like" — nền tảng cho layout hệ mặt trời ở Frontend.
- **Sigma.js reducers & events** ([sigmajs.org](https://www.sigmajs.org/)): pattern chính thức cho highlight-neighborhood-on-click và drag node — dùng cho tương tác click/drag.
- **WCAG 2.3.3 Animation from Interactions** & **2.2.2 Pause, Stop, Hide** ([W3C WAI](https://www.w3.org/WAI/WCAG21/Understanding/animation-from-interactions)): căn cứ cho quyết định tắt animation mặc định + yêu cầu nút pause khi bật.

---

## Identified Gaps — Defer post-MVP

1. **Concept layer qua LLM (GraphRAG-style)** — chỉ làm nếu OpenAlex Topics không đủ chi tiết.
2. **Co-citation + bibliographic coupling edge weighting** — đã defer ở `research-agent_SPEC_2.0.md:950`, dùng làm layout hint phụ khi implement graph này.
3. **Graph database (Neo4j) migration** — không cần thiết ở quy mô đã scope nhỏ (~300 node), chỉ xét lại nếu sau này mở rộng nhiều phiên đồng thời cần query phức tạp.
4. **ORKG-style structured comparison table** — feature riêng, không block MVP của knowledge graph này.
5. **Continuous orbit animation** — optional toggle, tắt mặc định vì lý do accessibility (xem mục Frontend) — không phải gap, là quyết định thiết kế có chủ đích.

---

## CHANGELOG

### v1.1 — sau brainstorm về frontend layout & interaction
- **Thêm Topic root node**: 1 node duy nhất ở tâm, label = query gốc, edge `covers` tới mọi theme — cho layout có điểm gốc rõ ràng.
- **Sửa phạm vi Paper layer**: chỉ lấy paper từ `papers_per_theme` (paper thật sự xuất hiện trong review), không lấy toàn bộ `snowballed_papers` (~600-900 bài) — giảm node từ ~900 xuống ~60-150, đúng mục tiêu "visualize review" thay vì "visualize corpus search".
- **Sửa edge claim**: tách `claim→theme` (mang `intent`, dùng cho filter contradicts) và `claim→paper` (`evidenced_by`, trung tính) — v1.0 từng gắn `intent` lên edge `claim→paper nguồn`, sai logic (claim không thể mâu thuẫn với chính paper nó trích ra).
- **Theme đích của claim suy ra từ `papers_per_theme`**, không cần sửa schema Step ⑦.
- **Frontend layout**: bố cục radial/hệ-mặt-trời tĩnh mặc định (D3-style polar coordinate, viết tay không cần dependency mới), KHÔNG tự quay liên tục — animation chỉ optional toggle, tắt mặc định vì lý do WCAG accessibility (2.3.3, 2.2.2) và risk vestibular disorder.
- **Frontend interaction**: `renderLabels: false` mặc định, click node → bôi đậm edge (Sigma reducer) + mở card chi tiết (không hiện label nổi trên graph), kéo-thả node tween về vị trí gốc khi buông tay.
- **Bảng màu**: đổi Topic từ đỏ sang vàng/hổ phách — tránh trùng nghĩa với edge `contradicts` (đỏ).
- **Guardrail cập nhật**: `max_nodes_rendered` giảm 1000→500, `default_visible_layers` đổi thành hiện cả 4 layer (graph đã đủ nhỏ), thêm guardrail accessibility (`motion_enabled_default`, `respect_prefers_reduced_motion`, `node_labels_default_visible`).

### v1.0 — bản đầu tiên
- Định nghĩa 3-layer graph (Paper / Theme / Claim-discourse) tái sử dụng data có sẵn từ pipeline v2.0.
- Xác định gap: `citation_edges` chưa được giữ lại ở Step ②bis — cần sửa `snowball_logic.py` trước khi implement.
- So sánh với 7 hướng đã có trên thế giới (Connected Papers/Litmaps, VOSviewer/CiteSpace, scite.ai, ORKG, Discourse Graphs, GraphRAG, OpenAlex Topics) — chọn hướng claim-centric discourse graph làm core, defer concept-layer LLM extraction.
