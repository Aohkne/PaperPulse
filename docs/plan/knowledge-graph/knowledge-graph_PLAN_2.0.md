# PLAN_2.0.md — Knowledge Graph

> Derived from `knowledge-graph_SPEC_2.0.md` v1.1 | Add-on lên `research-agent_PLAN_2.0.md` (Step ⑨bis) | Env: Local Development
> Changelog từ PLAN v1.0: xem mục [CHANGELOG](#changelog) cuối file

---

## 1. Tech Stack

| Layer | Technology | Ghi chú |
|---|---|---|
| **Graph assembly (backend)** | `networkx` (`MultiDiGraph`) | **MỚI** — in-memory, đủ cho graph đã scope nhỏ (~300 node, xem SPEC Non-goals) |
| **Pipeline orchestration** | LangGraph (đã có) | Thêm 1 node mới `build_graph`, không đổi framework |
| **API** | FastAPI (đã có) | Thêm 1 endpoint `GET /api/research/graph` |
| **Graph visualization (frontend)** | Sigma.js + Graphology qua `@react-sigma/core` | **MỚI** — WebGL, React bindings chính thức, có sẵn `nodeReducer`/`edgeReducer` cho highlight |
| **Radial layout (hệ mặt trời)** | Hàm trig viết tay (polar coordinate) | **MỚI** — không cần thêm dependency (`d3-hierarchy` không bắt buộc, cây chỉ sâu 4 tầng) |
| **Drag spring-back tween** | Hàm easing viết tay (`requestAnimationFrame` + lerp) | **MỚI** — không cần `framer-motion`/`react-spring`, tween đơn giản ~250ms |
| **Theme slug** | `python-slugify` | **MỚI** — tạo `id` ổn định cho theme node (`theme:rag-efficiency`) |
| **State persistence** | LangGraph SqliteSaver checkpoint (đã có) | `knowledge_graph` lưu trong state, không cần file riêng |

---

## 2. Environment Variables

```env
# Knowledge Graph guardrails (bổ sung vào .env hiện có của research-agent v2.0)
KG_MAX_NODES_RENDERED=500                          # giảm từ 1000 — Paper layer giờ scope papers_per_theme, không phải toàn corpus
KG_MAX_EDGES_RENDERED=3000
KG_CONTRADICTS_CLUSTER_MIN_SIZE=2
KG_DEFAULT_VISIBLE_LAYERS="topic,theme,paper,claim"  # hiện cả 4 — graph đã đủ nhỏ để không rối
KG_MOTION_ENABLED_DEFAULT=false                      # animation hệ mặt trời tắt mặc định — accessibility
KG_RESPECT_PREFERS_REDUCED_MOTION=true               # tự tắt nếu OS bật reduced-motion
KG_NODE_LABELS_DEFAULT_VISIBLE=false                 # renderLabels: false — dùng card khi click thay vì label nổi
```

Không cần thêm `LLM_*` hay API key mới — Step ⑨bis không gọi LLM (xem SPEC mục "Chi phí Step ⑨bis": ~$0/session).

---

## 3. State & Graph Changes

### 3.1 `ResearchState` — thêm field

```python
# graph/state.py — bổ sung vào ResearchState đã có ở research-agent_PLAN_2.0.md
class ResearchState(TypedDict):
    ...
    # ── Step ②bis: Snowball (SỬA — giữ thêm edge) ──
    citation_edges: list[dict]      # [{source, target, intent, isInfluential}] — MỚI

    # ── Step ⑨bis: Knowledge Graph (MỚI) ──
    knowledge_graph: dict           # {nodes, edges, stats} — output node build_graph
```

`state["query"]` đã có sẵn từ Step 0 — dùng trực tiếp làm label cho Topic root node, không cần field mới.

### 3.2 Graph Definition — thêm node + sửa edge

```python
# graph/graph.py — sửa trong build_graph() đã có
g.add_node("build_graph", build_graph_node)   # Step ⑨bis [MỚI]

# Trước: g.add_edge("route_claims", "export")
g.add_edge("route_claims", "build_graph")     # [SỬA]
g.add_edge("build_graph",  "export")          # [MỚI]
```

`build_graph` không cần `interrupt_before` — không có quyết định nào cần user duyệt ở step này.

---

## 4. Project Structure (phần thêm mới vào structure đã có ở `research-agent_PLAN_2.0.md`)

```
backend/module/research_agent/
├── graph/
│   ├── state.py                     # [SỬA] thêm citation_edges, knowledge_graph
│   ├── graph.py                     # [SỬA] thêm node build_graph
│   └── nodes/
│       ├── snowball.py              # [SỬA] nhận thêm citation_edges từ service
│       └── build_graph.py           # [MỚI] Step ⑨bis
│
├── services/
│   ├── snowball_logic.py            # [SỬA] snowball() trả (papers, edges) thay vì chỉ papers
│   └── graph_builder.py             # [MỚI] networkx assembly — build_graph(state) -> dict
│
├── api/
│   └── graph.py                     # [MỚI] GET /api/research/graph
│
└── models/
    └── graph.py                     # [MỚI] GraphNode, GraphEdge, GraphResponse (pydantic)

frontend/app/src/
├── components/
│   ├── KnowledgeGraphViewer.tsx      # [MỚI] <SigmaContainer> + layer toggle + filter + motion toggle
│   └── NodeDetailCard.tsx            # [MỚI, đổi tên từ ClaimEvidenceSidebar] card chung cho 4 loại node (topic/theme/paper/claim)
├── hooks/
│   └── useKnowledgeGraph.ts          # [MỚI] fetch JSON → Graphology graph instance
├── utils/
│   ├── radialLayout.ts               # [MỚI] tính toạ độ cực (hệ mặt trời) cho 4 tầng node
│   └── springBack.ts                 # [MỚI] tween node về toạ độ gốc khi buông drag
└── pages/
    └── Review.tsx                   # [SỬA] thêm tab "Knowledge Graph" cạnh LaTeXViewer
```

---

## 5. API Endpoint

```http
GET /api/research/graph?thread_id={thread_id}
```

```python
# api/graph.py
@app.get("/api/research/graph")
async def get_graph(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config).values
    if "knowledge_graph" not in state:
        raise HTTPException(404, "Graph not built yet — session chưa qua Step ⑨bis")
    return state["knowledge_graph"]
```

Không cần build lại graph trong endpoint — chỉ đọc field `knowledge_graph` đã có sẵn trong checkpoint sau khi LangGraph chạy xong Step ⑨bis (giống cách `api/export.py` đọc `.tex` đã build sẵn).

---

## 6. Implementation Phases

---

### Phase 1 — Data fix: giữ lại citation edges ở Step ②bis

**Mục tiêu:** `citation_edges` không rỗng sau snowball — đây là blocker phải làm trước, nếu không Paper layer của graph sẽ không có edge `cites`.

**Tasks:**
- [ ] `services/snowball_logic.py`: sửa `snowball()` trả về tuple `(papers, edges)` — lấy `intents`, `isInfluential` từ response S2 citations/references API (đã có sẵn trong response, hiện đang bị bỏ qua)
- [ ] `graph/nodes/snowball.py`: cập nhật để nhận `(papers, edges)`, set cả `state["snowballed_papers"]` và `state["citation_edges"]`
- [ ] `graph/state.py`: thêm field `citation_edges: list[dict]`

**Kiểm tra Phase 1:**
- Chạy lại Step ②bis với 1 seed pool mẫu → `state["citation_edges"]` có độ dài > 0
- Mỗi edge có đủ 4 field: `source`, `target`, `intent`, `isInfluential`

---

### Phase 2 — Graph Builder Service + LangGraph Node

**Mục tiêu:** `state["knowledge_graph"]` có đủ 4 layer (topic/theme/paper/claim) đúng schema JSON trong SPEC v1.1 — Paper layer chỉ chứa bài trong `papers_per_theme`, claim có 2 edge riêng (`evidenced_by` + `intent`).

**Tasks:**
- [ ] `services/graph_builder.py`:
  ```python
  import networkx as nx
  from slugify import slugify

  def build_graph(state: dict) -> dict:
      g = nx.MultiDiGraph()

      # Topic layer
      topic_id = "topic:root"
      g.add_node(topic_id, type="topic", label=state["query"])

      # Theme + Paper layer — CHỈ paper trong papers_per_theme (không phải snowballed_papers toàn bộ)
      paper_to_themes: dict[str, list[str]] = {}
      for theme, papers in state["papers_per_theme"].items():
          theme_id = f"theme:{slugify(theme)}"
          g.add_node(theme_id, type="theme", label=theme)
          g.add_edge(topic_id, theme_id, type="covers")
          for p in papers:
              paper_id = f"paper:{p['paperId']}"
              if not g.has_node(paper_id):
                  g.add_node(paper_id, type="paper", label=p["title"], year=p.get("year"),
                             citation_count=p.get("citationCount", 0), source=p.get("source"))
              g.add_edge(paper_id, theme_id, type="belongs_to")
              paper_to_themes.setdefault(paper_id, []).append(theme_id)

      # cites edge — chỉ thêm nếu CẢ 2 đầu đã có node (đã trong scope papers_per_theme)
      for edge in state["citation_edges"]:
          src, tgt = f"paper:{edge['source']}", f"paper:{edge['target']}"
          if g.has_node(src) and g.has_node(tgt):
              g.add_edge(src, tgt, type="cites", is_influential=edge["isInfluential"], intent=edge["intent"])

      # Claim layer — evidenced_by (trung tính, claim→paper) + intent (mang ý nghĩa, claim→theme)
      for claim in state["human_reviewed_claims"]:
          paper_id = f"paper:{claim['source_paperId']}"
          if paper_id not in paper_to_themes:
              continue  # claim của paper ngoài scope review → bỏ qua
          claim_id = f"claim:{claim['id']}"
          g.add_node(claim_id, type="claim", label=claim["claim"],
                     verdict=claim["verdict"], confidence=claim["confidence"])
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
      return {"nodes": data["nodes"], "edges": data["links"], "stats": stats}
  ```
- [ ] `models/graph.py`: pydantic `GraphNode`, `GraphEdge`, `GraphResponse` cho response validation (thêm `type: Literal["topic","theme","paper","claim"]`)
- [ ] `graph/nodes/build_graph.py`: thin wrapper gọi `graph_builder.build_graph(state)`, return `{"knowledge_graph": ...}`
- [ ] `graph/state.py`: thêm field `knowledge_graph: dict`
- [ ] `graph/graph.py`: thêm node `build_graph`, sửa edge `route_claims → build_graph → export`

**Kiểm tra Phase 2:**
- `state["knowledge_graph"]["nodes"]` có đủ 4 type: `topic` (đúng 1), `theme`, `paper`, `claim`
- `stats.papers` ~60-150 (không phải ~900) — xác nhận scope đã đúng theo `papers_per_theme`
- Mỗi claim node có cả edge `evidenced_by` (tới đúng 1 paper) và edge `intent` (tới ≥1 theme)
- `stats.contradicts_edges` > 0 nếu corpus có claim mâu thuẫn thật

---

### Phase 3 — API Endpoint

**Tasks:**
- [ ] `api/graph.py`: `GET /api/research/graph?thread_id=` — đọc `graph.get_state(config).values["knowledge_graph"]`
- [ ] `main.py`: mount router mới
- [ ] Trả `404` nếu session chưa chạy tới Step ⑨bis (chưa có field `knowledge_graph` trong state)

**Kiểm tra Phase 3:**
- `curl http://localhost:8000/api/research/graph?thread_id=xxx` sau khi 1 session chạy xong → JSON đúng schema, `stats` khớp số liệu thật

---

### Phase 4 — Frontend Visualization & Interaction

**Mục tiêu:** Bố cục hệ mặt trời tĩnh, mặc định không hiện label, click → highlight + card, kéo thả → tự bay về vị trí gốc.

**Tasks:**

- [ ] `npm install @react-sigma/core @react-sigma/graphology graphology`

- [ ] `utils/radialLayout.ts` — tính toạ độ cực cho 4 tầng:
  ```ts
  const RADIUS = { theme: 150, paper: 320, claim: 480 };

  function computeRadialLayout(graph: Graph) {
    graph.setNodeAttribute("topic:root", "x", 0);
    graph.setNodeAttribute("topic:root", "y", 0);

    const themes = graph.filterNodes((_, a) => a.type === "theme");
    themes.forEach((themeId, i) => {
      const angle = (2 * Math.PI * i) / themes.length;
      const [tx, ty] = [RADIUS.theme * Math.cos(angle), RADIUS.theme * Math.sin(angle)];
      graph.mergeNodeAttributes(themeId, { x: tx, y: ty, baseX: tx, baseY: ty });

      const papers = graph.filterInNeighbors(themeId, (_, a) => a.type === "paper");
      papers.forEach((paperId, j) => {
        const paperAngle = angle + (j - papers.length / 2) * 0.15; // rải trong sector quanh theme
        const [px, py] = [RADIUS.paper * Math.cos(paperAngle), RADIUS.paper * Math.sin(paperAngle)];
        graph.mergeNodeAttributes(paperId, { x: px, y: py, baseX: px, baseY: py });

        const claims = graph.filterInNeighbors(paperId, (_, a) => a.type === "claim");
        claims.forEach((claimId, k) => {
          const claimAngle = paperAngle + (k - claims.length / 2) * 0.08;
          const [cx, cy] = [RADIUS.claim * Math.cos(claimAngle), RADIUS.claim * Math.sin(claimAngle)];
          graph.mergeNodeAttributes(claimId, { x: cx, y: cy, baseX: cx, baseY: cy });
        });
      });
    });
  }
  ```
  Lưu `baseX`/`baseY` riêng — dùng làm "vị trí gốc" để spring-back khi kéo thả, tách biệt với `x`/`y` hiện tại (có thể bị kéo lệch tạm thời).

- [ ] `utils/springBack.ts` — tween node về `baseX`/`baseY` khi buông drag (~250ms, easing, `requestAnimationFrame`)

- [ ] `components/KnowledgeGraphViewer.tsx`:
  - `<SigmaContainer settings={{ renderLabels: false }}>` — mặc định không hiện label (theo `KG_NODE_LABELS_DEFAULT_VISIBLE`)
  - Gọi `computeRadialLayout()` sau khi load graph từ `useKnowledgeGraph.ts`
  - `clickNode` handler: set `selectedNodeId` state → trigger `edgeReducer` bôi đậm edge của node đó + mở `NodeDetailCard`
  - `clickStage` handler: clear `selectedNodeId`, đóng card
  - Drag handlers (`downNode`/`mousemovebody`/`mouseup`): khi `mouseup`, gọi `springBack()` thay vì giữ vị trí buông tay
  - Checkbox toggle layer (Topic/Theme/Paper/Claim) — mặc định bật cả 4 theo `KG_DEFAULT_VISIBLE_LAYERS`
  - Filter switch "chỉ hiện `contradicts`"
  - Toggle "▶ Chuyển động" — mặc định off (`KG_MOTION_ENABLED_DEFAULT`), khi bật chạy `requestAnimationFrame` tăng góc chậm, có nút pause, tự tắt nếu `window.matchMedia("(prefers-reduced-motion: reduce)").matches`
  - Màu node theo bảng màu trong SPEC (topic=vàng, theme=xám, paper=xanh biển, claim=tím); màu edge theo `type` (`contradicts`=đỏ, `supports`=xanh lá, `extends`=cam, `evidenced_by`=xám nhạt nét đứt, còn lại=xám nhạt)

- [ ] `components/NodeDetailCard.tsx` (đổi tên từ `ClaimEvidenceSidebar`): nhận `node` (full attrs từ Graphology) + `type`, render nội dung tương ứng theo bảng "Nội dung card theo node type" trong SPEC

- [ ] `pages/Review.tsx`: thêm tab "Knowledge Graph" cạnh `LaTeXViewer`

**Kiểm tra Phase 4:**
- Mở tab Knowledge Graph → thấy bố cục hệ mặt trời tĩnh, không có chữ nổi trên graph, không tự quay
- Click 1 paper node → edge của nó đậm lên, các edge khác mờ đi, card hiện đúng title/year/citation/PDF link
- Click khoảng trống → card đóng, hết highlight
- Kéo 1 node ra xa rồi buông → node tween mượt về đúng vị trí ban đầu, không đứng yên ở chỗ buông
- Bật toggle "Chuyển động" → node quay chậm, có nút pause; tắt OS-level reduced-motion giả lập → animation tự không chạy
- Filter "chỉ hiện contradicts" → graph co lại đúng các cặp `claim --contradicts--> theme`

---

### Phase 5 — Integration Testing

**Tasks:**
- [ ] E2E: query "RAG optimization techniques" → chạy full flow tới Step ⑨bis → graph có đủ 4 layer
- [ ] Đo `stats.papers` ~60-150 (xác nhận Paper layer đã scope đúng theo `papers_per_theme`, không lẫn cả corpus)
- [ ] Đo `stats.contradicts_edges` > 0 với corpus đủ lớn (xác nhận tension-detection có hoạt động)
- [ ] Đo performance: render ~300 node (topic+theme+paper+claim) trong < 1s trên máy dev thường
- [ ] Test edge case: claim mà `source_paperId` không nằm trong `papers_per_theme` nào → bị skip đúng, không tạo node mồ côi
- [ ] Test: session chưa qua Step ⑨bis → endpoint trả 404 đúng, không crash
- [ ] Test accessibility: `prefers-reduced-motion: reduce` → toggle "Chuyển động" tự disable/không chạy animation

---

### Phase 6 — Concept Layer *(Optional, post-MVP — theo SPEC mục "Concept Layer")*

**Tasks (chỉ làm nếu cần):**
- [ ] Lấy `primary_topic` từ response OpenAlex đã gọi ở Step ① → thêm node `type="concept"`
- [ ] Chỉ áp dụng GraphRAG-style LLM entity extraction nếu OpenAlex topic được xác nhận quá general (cần đo trước, không làm mặc định)

---

## 7. Key Dependencies

### `pyproject.toml` — thêm vào dependencies đã có ở `research-agent_PLAN_2.0.md`

```toml
dependencies = [
    ...
    "networkx",          # Knowledge Graph assembly
    "python-slugify",    # Theme node id slug
]
```

### Frontend (npm)

```bash
npm install @react-sigma/core @react-sigma/graphology graphology
```

Không cần thêm `d3-hierarchy`, `framer-motion`, hay `react-spring` — radial layout và spring-back tween viết tay (~50 dòng tổng), đủ nhẹ cho quy mô graph này.

---

## 8. Rủi ro & Giải pháp

| Rủi ro | Giải pháp |
|---|---|
| `citation_edges` rỗng nếu Phase 1 bị skip | Phase 2 phải block cho tới khi Phase 1 xong — Paper layer thiếu edge `cites` |
| Claim có `source_paperId` ngoài `papers_per_theme` (vd paper bị loại khỏi outline sau dedup) | `graph_builder.py` skip claim đó có chủ đích — không tạo node mồ côi, đã test ở Phase 5 |
| Render > 500 node làm browser lag | `KG_MAX_NODES_RENDERED` guardrail — nhưng với scope mới (~300 node) hiếm khi chạm ngưỡng |
| `route_claims` chưa resume (user chưa review xong) mà gọi `/api/research/graph` | Endpoint trả 404 rõ ràng, frontend disable tab "Knowledge Graph" cho tới khi nhận event `step_done` của `build_graph` |
| `networkx` `node_link_data()` format không khớp `Graphology` format frontend cần | Viết adapter nhỏ ở `useKnowledgeGraph.ts` map `links` → `edges`, test với sample JSON trước khi nối thật |
| Animation hệ mặt trời gây khó chịu/chóng mặt cho người dùng (vestibular disorder) | Tắt mặc định (`KG_MOTION_ENABLED_DEFAULT=false`), tự tắt theo `prefers-reduced-motion`, có nút pause khi bật — theo WCAG 2.3.3/2.2.2 |
| Label hiện mặc định trên graph gây rối với ~300 node | `renderLabels: false` mặc định, thông tin chỉ hiện qua `NodeDetailCard` khi click |
| Kéo node rồi buông, không tween → node "mất" vị trí gốc | Lưu `baseX`/`baseY` riêng trong `radialLayout.ts`, `springBack.ts` luôn tween về đúng giá trị này khi `mouseup` |

---

## 9. Milestones

| Milestone | Nội dung | Phụ thuộc |
|---|---|---|
| **KG-M1** | Phase 1 — Persist citation edges ở snowball | Sau M3 (`research-agent_PLAN_2.0.md`) |
| **KG-M2** | Phase 2+3 — Graph builder service (4-layer, scoped) + node + API | Sau M6 (Verification + Routing) |
| **KG-M3** | Phase 4 — Frontend `KnowledgeGraphViewer` (radial layout, highlight, card, drag spring-back) | Sau M7 (Export + StreamingPanel) |
| **KG-M4** | Phase 5 — Integration test + performance + accessibility check | Sau M8 |

---

## CHANGELOG

### v1.1 — sau brainstorm về frontend layout & interaction
- **Phase 2**: cập nhật `graph_builder.py` theo kiến trúc 4-layer (thêm Topic root), Paper layer scope lại theo `papers_per_theme` (không phải `snowballed_papers` toàn bộ), claim tách 2 edge (`evidenced_by` + `intent` qua `paper_to_themes` lookup — không cần sửa schema Step ⑦).
- **Phase 4**: viết lại hoàn toàn — thêm `radialLayout.ts` (bố cục hệ mặt trời tĩnh, polar coordinate viết tay), `springBack.ts` (tween khi buông drag), `renderLabels: false` mặc định, click→highlight (Sigma reducer) + mở `NodeDetailCard` (đổi tên từ `ClaimEvidenceSidebar`), toggle "Chuyển động" optional tắt mặc định (accessibility).
- **Env vars**: `KG_MAX_NODES_RENDERED` 1000→500, `KG_DEFAULT_VISIBLE_LAYERS` đổi thành hiện cả 4 layer, thêm `KG_MOTION_ENABLED_DEFAULT`, `KG_RESPECT_PREFERS_REDUCED_MOTION`, `KG_NODE_LABELS_DEFAULT_VISIBLE`.
- **Risks**: bỏ risk "paper cô lập không có citation edge" (không còn áp dụng vì Paper layer đã scope theo `papers_per_theme`), thêm risk về animation accessibility và label clutter.
- Không thêm dependency mới cho layout/animation — viết tay đủ nhẹ ở quy mô graph đã scope nhỏ.

### v1.0 — bản đầu tiên
- Derive từ `knowledge-graph_SPEC_2.0.md`: 6 phase implementation (data fix → graph builder → API → frontend → integration test → concept layer optional).
- Xác định Phase 1 là blocker bắt buộc: `snowball_logic.py` hiện không giữ citation edge, phải sửa trước khi build graph.
- Concept layer (Phase 6) để optional/deferred, không block MVP.
