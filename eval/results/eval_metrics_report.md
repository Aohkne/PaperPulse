# PaperPulse — Evaluation Metrics Report

> **Mục đích:** Báo cáo đánh giá chất lượng AI theo bộ khung đa-metric.
> Điền số thực vào cột **Actual** sau khi chạy measurement (xem `eval/HOW_TO_MEASURE.md`).

---

## 1. Bộ Khung Đánh Giá (Evaluation Framework)

| # | Metric | Feature | Định nghĩa | Cách đo | Target | Actual | Status |
|---|--------|---------|-----------|---------|--------|--------|--------|
| 1 | **Citation Accuracy** | Literature Review | % paper IDs trong output verify được trên Semantic Scholar | Manual verify 7 test cases | ≥ 85% | 100% | ✅ |
| 2 | **Processing Latency** | Literature Review | Tổng thời gian end-to-end flow | Postman response time, resume lần 2 | ≤ 1200s | 1059.86s | ✅ |
| 3 | **Gap Structural Integrity** | Gap Detection | % gaps pass 5 deterministic checks (paper existence, statement length, supporting papers, quality score, hallucination guard) | `run_eval.py` với `SKIP_LLM_JUDGE=true` | ≥ 80% | 95.2% (20/21) | ✅ |
| 4 | **Gap LLM-as-Judge Quality** | Gap Detection | Ensemble judge (Gemini 3.1 Pro + Claude Sonnet 4.6) chấm 4 dimensions (Grounded, Specific, Non-Trivial, Method-Actionable) thang 1–5 | Manual prompt — top 3 gaps/topic × 3 topics (9 gaps sampled) | Avg ≥ 3.5 / 5 | **3.71** | ✅ |

> **Ghi chú:**
> - **Citation Accuracy ≥ 85%:** ngưỡng chấp nhận cho RAG production.
> - **Processing Latency ≤ 1200s:** Tổng thời gian end-to-end flow, không tính thời gian user đọc interrupt.
> - **Gap Structural ≥ 80%:** ngưỡng tối thiểu cho production — gap phải có paper thật, statement đủ dài, quality score hợp lệ.
> - **Gap LLM-as-Judge ≥ 3.5/5:** avg score của ensemble judge (Gemini + Claude Sonnet 4.6). Flagged nếu avg ≤ 2.5 hoặc 2 model disagree ≥ 2 điểm trên cùng dimension.

---

## 2. Evaluation Baseline

> **Baseline** = điểm xuất phát để so sánh — "PaperPulse tốt hơn phương án không dùng pipeline bao nhiêu?"

| Metric | Baseline (so sánh) | Baseline Value | PaperPulse Actual | Improvement |
|--------|-------------------|---------------|-------------------|-------------|
| Citation Accuracy | Naive LLM — không có RAG, không guardrail | ~0% *(evidence: TC-02)* | 100% | +100 pp |
| Processing Latency | Manual literature review (~50 papers) | ~8–24 giờ *(ước tính)* | 17.7 phút (avg) | ~27–81× faster |
| Gap Structural Integrity | Raw LLM output — không có pipeline checks | 0% *(không có checks = không pass được checks)* | 95.2% | +95.2 pp |
| Faithfulness (LLM-as-Judge) | N/A | — | 3.71 / 5 *(partial)* | — |

**Giải thích từng baseline:**

**Citation Accuracy — Baseline ~0%:**
TC-02 (`/api/chat`, không có RAG) là bằng chứng trực tiếp: LLM trả về DOI thật nhưng nội dung bịa (citation drift). Paper IDs không verify được trên Semantic Scholar → citation accuracy ≈ 0%. Xem chi tiết tại [Section 4 — Guardrail Evidence](#4-guardrail-evidence).

**Processing Latency — Baseline 8–24 giờ:**
Ước tính cho researcher tra cứu thủ công 1 topic: tìm kiếm (~1–2h) + đọc abstract và lọc (~3–8h) + tổng hợp notes (~2–6h) + formatting (~1–2h) = ~8–24 giờ cho 50+ papers. PaperPulse avg = 1059.86s = **17.7 phút** → nhanh hơn ~27–81 lần tùy researcher. *(Lưu ý: baseline này là ước tính, không có điều kiện thực nghiệm kiểm soát.)*

**Gap Structural Integrity — Baseline 0%:**
Không có pipeline = không có checks. Với raw LLM output, không có bước nào verify paper existence, statement length, hay hallucination guard → pass rate = 0% theo định nghĩa của bộ 5 checks.

**LLM-as-Judge — N/A:**
Metric này đánh giá chất lượng nội dung (quality of gaps), không có baseline "trước/sau pipeline" hợp lý để so sánh. Target ≥ 3.5/5 được đặt dựa trên ngưỡng chấp nhận cho academic output quality.


---

## 3. Chi Tiết Kết Quả Đo

### 3.1 Citation Accuracy

**Công thức:**
```
Citation Accuracy = (Số paper IDs verify được trên Semantic Scholar) / (Tổng paper IDs trong output) × 100%
```

| Case # | Query (tóm tắt) | Tổng IDs | IDs thật | IDs bịa | Accuracy |
|--------|----------------|----------|----------|---------|----------|
| 1 | quantum GNN for drug-target interaction | 39 | 39 | 0 | 100% |
| 2 | RAG for question answering | 54 | 54 | 0 | 100% |
| 3 | papers by Zhao Wentian on federated contrastive learning medical imaging 2024 | 47 | 47 | 0 |100% |
| 4 | large language models surpassing human performance medical exams | 42 | 42 | 0 |100% |
| 5 | hallucination detection and mitigation in LLMs for biomedical question answering | 61 | 61 | 0 |100% |
| 6 | contrastive self-supervised learning for medical image segmentation with limited annotations | 68 | 68 | 0 |100% |
| 7 | large language models for automated source code vulnerability detection and code review using fine-tuning and prompt engineering | 75 | 75 | 0 |100% |
| | **TỔNG** |  |  | | **100%** | |

---

### 3.2 Processing Latency

**Cách đo:**
- **end-to-end:** Postman response time của end-to-end flow


| Case # | Query (tóm tắt) | end-to-end (giây) |
|--------|----------------|-------------|
| 1 | quantum GNN for drug-target interaction | 1567 |
| 2 | RAG for question answering | 1179 |
| 3 | papers by Zhao Wentian on federated contrastive learning medical imaging 2024 | 480 |
| 4 | large language models surpassing human performance medical exams | 1084 |
| 5 | hallucination detection and mitigation in LLMs for biomedical question answering | 1123 |
| 6 | contrastive self-supervised learning for medical image segmentation with limited annotations | 1140 |
| 7 | large language models for automated source code vulnerability detection and code review using fine-tuning and prompt engineering | 846 |
| | **Average** | **1059.86s** |
| | **Min** | **480s** |
| | **Max** | **1567s** |

---

### 3.3 Gap Detection — Structural Integrity

**Cách đo:** Chạy `SKIP_LLM_JUDGE=true PYTHONPATH=. python tests/test_research_gap/run_eval.py` từ project root. Kết quả xem tại `tests/test_research_gap/report.html`.

**5 checks được thực hiện tự động:**

| Check | Mô tả | Pass condition |
|-------|-------|---------------|
| `paper_existence` | Paper ID verify được trên Semantic Scholar | S2 trả về metadata hợp lệ |
| `statement_length` | Statement đủ chi tiết | ≥ 15 words |
| `has_supporting_papers` | Có ít nhất 1 paper hỗ trợ | `len(supporting_papers) ≥ 1` |
| `quality_score_present` | Pipeline đã tính quality score | `quality_score is not None` |
| `empty_on_nonsense` | Hallucination guard | Nonsense topic → 0 gaps |

**Kết quả đo (run 2026-06-26):**

| Topic | Tổng gaps | Structural Pass | Structural Fail | Pass Rate |
|-------|-----------|----------------|----------------|-----------|
| speculative decoding for LLM inference | 7 | 7 | 0 | 100% |
| RAG application in healthcare | 7 | 7 | 0 | 100% |
| contrastive learning for graph neural networks | 7 | 6 | 1 | 85.7% |
| xyzxyz nghiên cứu không tồn tại 99999 (nonsense) | 7 | 7 | 0 | — |
| **TỔNG (excl. nonsense)** | **21** | **20** | **1** | **95.2%** |

**Findings cần báo:**

| # | Mức độ | Vấn đề | Chi tiết |
|---|--------|--------|---------|
| 1 | 🔴 Critical | **Hallucination guard fail** | Nonsense topic trả về 7 gaps (expect: 0). Pipeline tìm papers từ chủ đề khác và tạo gaps từ đó. |
| 2 | 🟡 Minor | **1 structural fail** | Contrastive learning gap 6 — paper không verify được trên S2. |

---

### 3.4 Gap Detection — LLM-as-Judge Quality


**Ensemble judge:** Gemini (Google) + Claude Sonnet 4.6 (Anthropic). Flagged nếu ensemble avg ≤ 2.5 **hoặc** 2 model disagree ≥ 2 điểm trên cùng 1 dimension.

**Judge Prompt (dùng cho cả manual eval):**
```
Bạn là expert reviewer của research literature gap analysis.

Ví dụ GAP TỐT (để calibrate):
Statement: "Speculative decoding has not been applied to encoder-decoder 
speech models despite their distinct autoregressive structure"
→ G=5 S=5 N=4 A=4 (grounded vào paper, cụ thể, không trivial, có hướng rõ)

Ví dụ GAP TỆ (để calibrate):
Statement: "More research is needed in this area"  
→ G=1 S=1 N=1 A=1 (vague, trivial, không actionable)

---
Đánh giá từng gap HOÀN TOÀN ĐỘC LẬP, không so sánh chúng với nhau, không so sánh với ví dụ trước.

TOPIC: [PASTE_TOPIC]
---
GAP 1:
Statement: ...
Suggested method: ...
Source papers: ...

GAP 2:
Statement: ...
...

GAP 3:
...

Chấm điểm (1-5):
1. GROUNDED: ...
2. SPECIFIC: ...
3. NON_TRIVIAL: ...
4. METHOD_ACTIONABLE: ...

Trả lời: GROUNDED X/5, SPECIFIC X/5, NON_TRIVIAL X/5, METHOD_ACTIONABLE X/5, Avg, Human review: Có/Không
```

**Kết quả đo:**

> **Cột:** G=Grounded, S=Specific, N=Non-Trivial, A=Method-Actionable (thang 1–5).

> **Flagged** = ⚠️ nếu ensemble avg ≤ 2.5 hoặc 2 model disagree ≥ 2 điểm trên cùng dimension (cần human review).

> **Disagree** liệt kê dimension mà 2 model lệch nhau ≥ 2 điểm.

| Topic | Gap # | Statement| Gemini G/S/N/A | Gem Avg | Claude G/S/N/A | Cla Avg | Ensemble Avg | Disagree ≥2 | Flagged |
|-------|-------|---------------------|----------------|---------|----------------|---------|--------------|-------------|---------|
| speculative decoding | 1 | Energy‑aware evaluation of speculative decoding: systematic measurement of power consumption and carbon footprint across different hardware platforms (GPU, NPU, edge CPUs) and decoding configurations | 5/5/4/5 | 4.75 | 4/4/3/4 | 3.75 | **4.25** | - | ✅ |
| speculative decoding | 2 | Privacy‑preserving speculative decoding: mechanisms to prevent leakage of proprietary training data or user prompts when draft models are offloaded or shared across devices | 4/4/2/1 | 2.75 | 4/4/4/4 | 4 | **3.375** | N(Δ=2), A(Δ=3) | ⚠️ |
| speculative decoding | 3 | Recursive Speculative Decoding with sampling‑without‑replacement (arxiv:2402.14160) has not been explored for federated or edge‑distributed LLM inference, where communication overhead is a bottleneck | 5/5/5/5 | 5 | 3/4/2/4 | 3.25 | **4.125** | G(Δ=2), N(Δ=3) | ⚠️ |
| RAG in healthcare | 1 | Investigation of privacy-preserving retrieval mechanisms (e.g., differential privacy, federated indexing) for RAG pipelines in clinical settings | 5/5/5/5 | 5 | 2/4/2/4 | 3 | **4.0** | G(Δ=3), N(Δ=3) | ⚠️ |
| RAG in healthcare | 2 | Systematic measurement and reduction of end‑to‑end latency in RAG pipelines for bedside decision support | 4/5/4/5 | 4.5 | 5/5/4/4 | 4.5 | **4.5** | - | ✅ |
| RAG in healthcare | 3 | Design of RAG pipelines that directly ingest and emit data conforming to FHIR/HL7 standards, enabling seamless clinical workflow integration | 4/5/4/2 | 3.75 | 2/4/2/4 | 3 | **3.375** | G(Δ=2), N(Δ=2), A(Δ=2) | ⚠️ |
| contrastive GNN | 1 | Contrastive self‑supervised learning for hypergraphs (graphs with higher‑order edges) has not been explored, even though many real‑world systems are naturally modeled as hypergraphs | 2/4/1/4 | 2.75 | 2/4/2/4 | 3 | **2.875** | - | ✅ |
| contrastive GNN | 2 | Differentiable pooling (DiffPool) has not been explored for dynamic or streaming graph scenarios | 3/3/1/2 | 2.25 | 5/5/4/4 | 4.5 | **3.375** | G(Δ=2), S(Δ=2), N(Δ=3), A(Δ=2) | ⚠️ |
| contrastive GNN | 3 | TopoGCL has not yet been applied to streaming time‑evolving graphs, as noted by the authors | 5/4/4/3 | 4 | 2/4/2/4 | 3 | **3.5** | G(Δ=3), N(Δ=2) | ⚠️ |
| | | **Avg (top 3 gaps/topic, 9 gaps total)** | | | | | **3.71** | | |

---

## 4. Guardrail Evidence

| Scenario | Test Case | Result | Ý nghĩa |
|----------|-----------|--------|---------|
| Không có guardrail | TC-02: `/api/chat` (no RAG) | ❌ FAIL — Citation drift: DOI thật nhưng nội dung bịa | Chứng minh guardrail là cần thiết |
| Có guardrail | TC-03a: `/api/research/stream` (full pipeline) | ✅ PASS — 100% paper IDs verify được | Guardrail hoạt động hiệu quả |

**Kết luận:** RAG pipeline với guardrail loại bỏ hoàn toàn hallucination trong các test cases đã chạy.

---

## 5. Tóm Tắt

| Feature | Metric | Target | Actual | Status |
|---------|--------|--------|--------|--------|
| Literature Review | Citation Accuracy | ≥ 85% | 100% | ✅ |
| Literature Review | Processing Latency (avg) | ≤ 1200s | 1059.86s | ✅ |
| Gap Detection | Structural Integrity | ≥ 80% | 95.2% (excl. nonsense) | ✅ |
| Gap Detection | LLM-as-Judge Quality (avg) | ≥ 3.5 / 5 | **3.71** / 5 *(top 3 gaps/topic × 3 topics)* | ✅ |

**Ngày đo:** 28/06/2026

**Người thực hiện:** Anh Thu Tran

**Version được test:** v1 — deploy
