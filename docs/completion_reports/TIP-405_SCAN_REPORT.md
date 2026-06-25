# SCAN REPORT — TIP-405

## A. RESEARCH_AGENT MERGE
**Nguồn:**
- Semantic Scholar: [`backend/shared/services/semantic_scholar.py:49`](D:\vinuni\Project\Build_project\C2-App-069\backend\shared\services\semantic_scholar.py:49)
- OpenAlex: [`backend/module/research_agent/services/openalex.py:84`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\openalex.py:84)
- arXiv: [`backend/module/research_agent/services/arxiv_search.py:17`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\arxiv_search.py:17)
- PubMed: [`backend/module/research_agent/services/pubmed_search.py:19`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\pubmed_search.py:19)
- Parallel fan-out: [`backend/module/research_agent/graph/nodes/parallel_search.py:22`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\graph\nodes\parallel_search.py:22), [`backend/module/research_agent/graph/nodes/parallel_search.py:30`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\graph\nodes\parallel_search.py:30)

**Khóa dedup:**
- DOI → ArXiv ID → paperId → title fuzzy
- Rule summary: [`backend/module/research_agent/services/dedup_utils.py:1`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:1)
- DOI branch: [`backend/module/research_agent/services/dedup_utils.py:45`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:45)
- ArXiv branch: [`backend/module/research_agent/services/dedup_utils.py:51`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:51)
- paperId branch: [`backend/module/research_agent/services/dedup_utils.py:57`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:57)
- title fuzzy branch: [`backend/module/research_agent/services/dedup_utils.py:63`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:63)

**Có normalize/fuzzy?:**
- Có fuzzy title bằng `rapidfuzz` ratio `>= 90`: [`backend/module/research_agent/services/dedup_utils.py:7`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:7), [`backend/module/research_agent/services/dedup_utils.py:19`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:19)
- Không thấy normalize title sâu kiểu NFC/punctuation strip trong `research_agent`; chỉ lower + fuzzy so trực tiếp trên title: [`backend/module/research_agent/services/dedup_utils.py:65`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\dedup_utils.py:65)

**Xử lý non-S2 id?:**
- Có.
- OpenAlex: DOI nếu có, còn không fallback `OA_...`: [`backend/module/research_agent/services/openalex.py:52`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\openalex.py:52), [`backend/module/research_agent/services/openalex.py:67`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\openalex.py:67)
- arXiv: `paperId=f"arxiv_{arxiv_id}"`, DOI giữ trong `externalIds`: [`backend/module/research_agent/services/arxiv_search.py:45`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\arxiv_search.py:45), [`backend/module/research_agent/services/arxiv_search.py:53`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\arxiv_search.py:53)
- PubMed: `paperId=f"pubmed_{pmid}"` hoặc title prefix fallback: [`backend/module/research_agent/services/pubmed_search.py:94`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\pubmed_search.py:94)

## B. CODEBASE PATTERN
**Normalize title khác:**
- `gap_detection/source_resolution.py` có normalize title chuẩn hơn: NFC + lowercase + strip punctuation + collapse whitespace: [`backend/agent/gap_detection/source_resolution.py:90`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\source_resolution.py:90)
- Key hierarchy: DOI → normalized title → S2 paperId: [`backend/agent/gap_detection/source_resolution.py:106`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\source_resolution.py:106), [`backend/agent/gap_detection/source_resolution.py:114`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\source_resolution.py:114), [`backend/agent/gap_detection/source_resolution.py:117`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\source_resolution.py:117)

**Fuzzy lib đã có:**
- Có `rapidfuzz` trong backend dependency: [`pyproject.toml:47`](D:\vinuni\Project\Build_project\C2-App-069\pyproject.toml:47)
- Không thấy backend dùng `difflib`, `SequenceMatcher`, hoặc lib fuzzy khác trong scan này.

**Util paper identity chung:**
- Không thấy một shared util chung cho paper identity/matching.
- Pattern hiện tách theo module:
  - `backend/module/research_agent/services/dedup_utils.py`
  - `backend/agent/gap_detection/source_resolution.py`

## C. KG MATCHING
- KG không tự fuzzy-match; nó dùng `paper_id` làm khóa node.
- `paper_by_id = {p.paper_id: p for p in papers}` là lookup chính: [`backend/module/research_agent/services/graph_builder.py:76`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\graph_builder.py:76)
- Node paper được tạo bằng `paper:{pid}`: [`backend/module/research_agent/services/graph_builder.py:99`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\graph_builder.py:99)
- Citation edges cũng match theo `paper:{source}` / `paper:{target}`: [`backend/module/research_agent/services/graph_builder.py:117`](D:\vinuni\Project\Build_project\C2-App-069\backend\module\research_agent\services\graph_builder.py:117)
- Insight: KG phụ thuộc hoàn toàn vào upstream canonicalization/dedup; nếu upstream để lọt title gần-giống, KG sẽ kế thừa trùng.

## D. EXTRACTOR ID
- `extractor_node` gọi `get_paper_detail(paper_ref.paper_id)`: [`backend/agent/gap_detection/nodes/extractor.py:157`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\nodes\extractor.py:157)
- `get_paper_detail()` URL-encode toàn bộ `paper_id`: [`backend/agent/gap_detection/s2_client.py:55`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\s2_client.py:55), [`backend/agent/gap_detection/s2_client.py:64`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\s2_client.py:64)
- `cold_start` map `Paper -> PaperRef` giữ nguyên `paper.paper_id` và skip paper thiếu id: [`backend/agent/gap_detection/orchestrator.py:179`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\orchestrator.py:179), [`backend/agent/gap_detection/orchestrator.py:197`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\orchestrator.py:197)
- `PaperRef` session dedup cũng chỉ theo `paper_id`/`paperId`: [`backend/agent/gap_detection/nodes/paper_check.py:35`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\nodes\paper_check.py:35), [`backend/agent/gap_detection/nodes/paper_check.py:43`](D:\vinuni\Project\Build_project\C2-App-069\backend\agent\gap_detection\nodes\paper_check.py:43)
- Chưa thấy path rõ ràng cho non-S2 id trong extractor gap pipeline.

## KHUYẾN NGHỊ CHO CHỦ THẦU
- Có pattern sẵn để học không? Có.
- Hai pattern đáng học:
  - `gap_detection/source_resolution.py` cho canonical merge đa nguồn bằng DOI → normalized title → S2 paperId.
  - `research_agent/services/dedup_utils.py` cho priority dedup có fuzzy title.
- Fuzzy match: backend đã có `rapidfuzz`, nên nếu muốn áp dụng fuzzy trong gap thì không cần thêm dependency mới.
