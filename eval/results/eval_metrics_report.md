# PaperPulse — Evaluation Metrics Report

> **Mục đích:** Báo cáo đánh giá chất lượng AI theo bộ khung đa-metric.
> Điền số thực vào cột **Actual** sau khi chạy measurement (xem `eval/HOW_TO_MEASURE.md`).

---

## 1. Bộ Khung Đánh Giá (Evaluation Framework)

| # | Metric | Định nghĩa | Cách đo | Target | Actual | Status |
|---|--------|-----------|---------|--------|--------|--------|
| 1 | **Citation Accuracy** | % paper IDs trong output verify được trên Semantic Scholar | Manual verify 5 test cases | ≥ 85% | 100% | ✅ |
| 2 | **Processing Latency** | Thời gian Req.2: retrieval + LLM summarization lặp lại cho từng cluster và cross-cluster analysis | Postman response time, resume lần 2 | ≤ 900s | 655.71s | ✅ |
| 2b | **Total Latency** | Tổng thời gian end-to-end flow | Cộng end-to-end response time | ≤ 1200s | 897s | ✅ |
| 3 | **Faithfulness Score** | LLM-as-judge đánh giá mức độ response trung thực với paper gốc (thang 1–5) | GPT judge trên 3 ground-truth papers | ≥ 3.5 / 5 | — | ⏳ |

> **Ghi chú:**
> - **Citation Accuracy ≥ 85%:** ngưỡng chấp nhận cho RAG production.
> - **Processing Latency Req.2 ≤ 900s:** Req.2 là đoạn nặng nhất — thời gian hệ thống xử lý toàn bộ các cluster bao gồm retrieval + LLM summarization lặp lại cho từng cluster và cross-cluster analysis.
> - **Total Latency ≤ 1200s:** Tổng thời gian end-to-end flow, không tính thời gian user đọc interrupt.
> - **Faithfulness ≥ 3.5/5:** mức "good enough" theo chuẩn LLM-as-judge trong RAG evaluation.

---

## 2. Pipeline Flow (để tham khảo khi đo)

Mỗi test case cần **4 requests**, có **3 interrupts**:

```
Request 1: POST /research/stream       → Interrupt 1: plan review (sub_queries + sources)
Request 2: POST /research/resume       → Interrupt 2: outline approval (themes) ◄── ĐO LATENCY REQUEST 2 Ở ĐÂY
Request 3: POST /research/resume       → Interrupt 3: routing summary
Request 4: POST /research/resume       → "type": "done" ✅
```

**Paper IDs** nằm trong response `"type": "done"` → field `"content"` (dạng `Source: PAPER_ID`).

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
- **Seg.2:** Postman response time của **Request 3** (resume lần 2 → Interrupt 3)
- **end-to-end:** Postman response time của end-to-end flow


| Case # | Query (tóm tắt) | Req.2 (giây) | end-to-end (giây) |
|--------|----------------|-------------|-------------|
| 1 | quantum GNN for drug-target interaction | 776 | 1567 |
| 2 | RAG for question answering | 736 | 1179 |
| 3 | papers by Zhao Wentian on federated contrastive learning medical imaging 2024 | 180 | 480 |
| 4 | large language models surpassing human performance medical exams | 677 | 1084 |
| 5 | hallucination detection and mitigation in LLMs for biomedical question answering | 840 | 1123 |
| 6 | contrastive self-supervised learning for medical image segmentation with limited annotations | 705 | 1140 |
| 7 | large language models for automated source code vulnerability detection and code review using fine-tuning and prompt engineering | 676 | 846 |
| | **Average** | **655.71s** | **897s** |
| | **Min** | **180s** | **480s** |
| | **Max** | **840s** | **1567s** |

---

### 3.3 Faithfulness Score (LLM-as-Judge)

**Cách đo:** Lấy `"content"` từ response `"type": "done"` của 3 trong 7 cases → paste vào ChatGPT với judge prompt bên dưới.

**Judge Prompt:**
```
You are evaluating an AI literature review system.

Ground truth paper:
- Title: [ĐIỀN TITLE]
- Key claim: [ĐIỀN KEY CLAIM từ ground-truth-data sheet]

AI system output:
[PASTE nội dung từ field "content" trong "type": "done"]

Rate on 3 dimensions (1 = very poor, 5 = excellent):
1. Faithfulness: Does the output accurately represent the paper's actual claim?
2. Relevance: Is the content on-topic to the paper's subject?
3. No hallucination: Are all cited paper IDs real (not invented)?

Respond ONLY as JSON:
{"faithfulness": X, "relevance": X, "no_hallucination": X, "reason": "one sentence"}
```

| Paper # | Title (tóm tắt) | Faithfulness | Relevance | No Hallucination | Avg |
|---------|----------------|-------------|----------|-----------------|-----|
| 1 | GraphRAG for Summarization | — | — | — | — |
| 2 | Inception-v4 & Residual Connections | — | — | — | — |
| 3 | CoroNet COVID-19 Detection | — | — | — | — |
| | **Average** | **—** | **—** | **—** | **—** |

---

## 4. Guardrail Evidence

> Phần này serve đồng thời cho deliverable **Guardrails** của BTC.

| Scenario | Test Case | Result | Ý nghĩa |
|----------|-----------|--------|---------|
| Không có guardrail | TC-02: `/api/chat` (no RAG) | ❌ FAIL — Citation drift: DOI thật nhưng nội dung bịa | Chứng minh guardrail là cần thiết |
| Có guardrail | TC-03a: `/api/research/stream` (full pipeline) | ✅ PASS — 100% paper IDs verify được | Guardrail hoạt động hiệu quả |

**Kết luận:** RAG pipeline với guardrail loại bỏ hoàn toàn hallucination trong các test cases đã chạy (TC-01, TC-03a PASS vs TC-02 FAIL khi không có guardrail).

---

## 5. Tóm Tắt

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Citation Accuracy | ≥ 85% | —% | ⏳ |
| Processing Latency Seg.2 (avg) | ≤ 90s | — s | ⏳ |
| Total Latency (avg) | ≤ 100s | — s | ⏳ |
| Faithfulness Score (avg) | ≥ 3.5 / 5 | — / 5 | ⏳ |

**Ngày đo:** ___________
**Người thực hiện:** Anh Thu Tran
**Version được test:** v1 — localhost
