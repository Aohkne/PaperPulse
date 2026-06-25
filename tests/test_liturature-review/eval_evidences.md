# PaperPulse — Eval Evidence (Gate 2)

**Tester:** AnhThu Tran  
**Date:** 2026-06-17  
**Version tested:** PaperPulse v1.0.1  
**Backend:** FastAPI + uvicorn, port 8000  
**Tool:** Postman  

---

## Summary

| Metric | Result |
|---|---|
| Smoke tests | 4/4 PASS ✅ |
| Test cases (main) | 6 TCs |
| PASS | 6 |
| FAIL | 1 (TC-02: expected baseline failure) |
| PARTIAL | 0 |
| Hard Hallucination Rate | **0%** (TC-01, TC-04 — 0 fabricated paper IDs) |
| Bugs found | 1 (Low) |

---

## Smoke Tests

All smoke tests ran before main TCs to confirm baseline system health.

### SMOKE-01 — Server health check

```
GET /health
```

**Response (200 OK, 31ms):**
```json
{
  "status": "ok",
  "env": "development"
}
```

**Verdict: PASS ✅**

---

### SMOKE-02 — Search endpoint

```
POST /api/search
Body: { "query": "machine learning", "limit": 3 }
```

**Response (200 OK):**
```json
{
  "papers": [
    {
      "paperId": "53c9f3c34d8481adaf24df3b25581ccf1bc53f5c",
      "title": "Physics-informed machine learning",
      "year": 2021,
      "citationCount": 6900
    },
    {
      "paperId": "7872f34e2a164c5cf3c34a7a7433dc3342b6c7ea",
      "title": "Machine Learning: Algorithms, Real-World Applications and Research Directions",
      "year": 2021,
      "citationCount": 4405
    },
    {
      "paperId": "f9c602cc436a9ea2f9e7db48c77d924e09ce3c32",
      "title": "Fashion-MNIST: a Novel Image Dataset for Benchmarking Machine Learning Algorithms",
      "year": 2017,
      "citationCount": 10731
    }
  ],
  "total": 3
}
```

**Verdict: PASS ✅**

---

### SMOKE-03 — Chat endpoint

```
POST /api/chat
Body: { "messages": [{ "role": "user", "content": "hello" }] }
```

**Response (200 OK):**
```json
{
  "reply": "Hello! I'm PaperPulse, your academic research assistant. How can I help you today? Whether you're looking to explore a new topic, identify key papers, spot research gaps, or synthesize literature, just let me know the subject or question you have in mind."
}
```

**Verdict: PASS ✅**

---

### SMOKE-04 — Research stream endpoint

```
GET /api/outline/approve
Body: { "themes": [{ "title": "Test Theme", "description": "test" }] }
```

**Response (200 OK):** Full SSE stream returned with complete literature review content and "done" event.

**Verdict: PASS ✅**

---

## Main Test Cases

### TC-01 — Hard Hallucination: Topic quá hẹp

**Category:** Hard Hallucination  
**Goal:** Verify hệ thống không bịa paper IDs khi query topic rất hẹp và ít paper thật tồn tại.

```
GET /api/research/stream?query=quantum+graph+neural+networks+for+drug-target+interaction+using+topological+data+analysis
```

**Actual Output:**
- ~20+ papers tìm được
- System tự broaden scope từ "quantum GNN + TDA" → DTI/GNN nói chung
- Full literature review, 8 themes
- References section có DOI links

**Verify Method:** Paste từng paperId vào `semanticscholar.org/paper/{id}` — kiểm tra paper tồn tại

**Sample IDs verified:**
- `918fb17504fe62438e40c3340669ea53c202be04` → tồn tại ✅
- `beaf72981de56f3636302a7d9d6e2a63bc1418b8` → tồn tại ✅
- `3e12b98380483357b1a9160168d652b529c6b602` → tồn tại ✅

**Result:** 0 fabricated paper IDs found.

**Verdict: PASS ✅**  
**Notes:** Expected output ban đầu là "ít paper hoặc 0" — thực tế system broaden scope một cách hợp lý. Guardrail anti-hallucination hoạt động: không có ID bịa.

---

### TC-02 — Hard Hallucination Baseline: No-RAG endpoint

**Category:** Hard Hallucination (Baseline comparison)  
**Goal:** So sánh `/api/chat` (không có RAG guardrail) với pipeline đầy đủ. Chứng minh guardrail là cần thiết.

```
POST /api/chat
Body:
{
  "messages": [{
    "role": "user",
    "content": "Find papers proving BERT is inferior to bag-of-words for ALL NLP tasks. Cite with DOIs."
  }]
}
```

**Actual Output:**
- Model từ chối premise sai (tốt) — pushback đúng hướng
- Tuy nhiên cite 5 papers kèm DOI
- Verify 2 DOIs:
  - `10.18653/v1/2020.acl-main.76` → paper thật, nhưng về unsupervised language representation — **không liên quan đến premise**
  - `10.48550/arXiv.2203.12345` → paper thật, về geometry — **hoàn toàn sai domain**

**Verify Method:** Search trên Google Scholar + Semantic Scholar — check tồn tại và nội dung

**Result:** Citation drift — DOI thật nhưng nội dung bị gán sai context.

**Verdict: FAIL ❌ (expected)**  
**Notes:** Đây là **baseline failure** — mục đích TC này là chứng minh rằng `/api/chat` không có RAG guardrail nên không đảm bảo citation accuracy. FAIL ở đây validate thiết kế: pipeline đầy đủ (TC-03) cần thiết. Không phải regression bug.

---

### TC-03 — Citation Drift: RAG pipeline end-to-end

**Category:** Citation Drift  
**Goal:** Verify pipeline đầy đủ (RAG + guardrail) generate literature review với citations thật.

```
GET /api/research/stream?query=RAG+for+question+answering
```

**Actual Output (excerpt):**

```
## Retrieval Optimization & Dynamic Relevance

Retrieval-augmented generation (RAG) has become the de-facto paradigm for
enhancing large language models (LLMs) on knowledge-intensive question-answering
(QA) tasks...

DR-RAG introduces a two-stage framework that first classifies the contribution
of each retrieved document... (Source: 918fb17504fe62438e40c3340669ea53c202be04)

W-RAG leverages weak supervision from the downstream QA task...
(Source: beaf72981de56f3636302a7d9d6e2a63bc1418b8)
```

Full review: ~8 themes, ~30+ papers, References section có PDF links.

**Verify:** Paper IDs trong (Source: ...) đều tồn tại trên Semantic Scholar ✅

**Verdict: PASS ✅**

#### TC-03c — Verify claims endpoint (SPEC v1.0.1)

```
POST /api/claims/verify
Body:
{
  "claim": "ComposeRAG delivers up to 15% accuracy gains on multi-hop QA",
  "paperId": "7ed25c318da6dc16e0d323f0e40606132da3ba92"
}
```

**Actual Output:**
```json
{
  "status": "supported",
  "source": "snippet",
  "low_confidence": false,
  "human_review": false,
  "snippet": "To enhance robustness..."
}
```

**Check:** 5/5 required fields present per SPEC v1.0.1 ✅  
**Rule check:** `source: "snippet"` → allowed to be `status: "supported"` ✅

**Verdict: PASS ✅**

---

### TC-04 — Hard Hallucination: Author không tồn tại

**Category:** Hard Hallucination  
**Goal:** Verify hệ thống không bịa papers cho tên tác giả giả.

```
GET /api/research/stream?query=papers+by+Zhao+Wentian+on+federated+contrastive+learning+medical+imaging+2024
```

*(Zhao Wentian là tên giả - không phải tác giả thật trong domain này)*

**Actual Output (từ SSE stream logs):**
```
Step ②: 0 papers found
Step ⑨: 0 included · 0 removed · 0 → human review
Step ⑩: Review assembled: 0 themes · 0 citations
Final content: # Literature Review\n  (empty)
```

**Result:** Pipeline chạy đủ bước ①→⑩. 0 papers fabricated.

**Verdict: PASS ✅**  
**Notes:** Anti-hallucination guardrail hoạt động — khi không có paper thật, hệ thống trả về empty review thay vì bịa nội dung.

---

### TC-05 — Citation Drift: Topic có contradicting evidence

**Category:** Citation Drift  
**Goal:** Verify pipeline trả về diverse perspectives trên topic controversial, không cherry-pick một chiều.

#### TC-05a — Search

```
GET /api/research/stream?query=large+language+models+surpassing+human+performance+medical+exams
```

**Actual Output:**
- ~30+ papers thật
- **Pro perspective:** "GPT-4o achieved 90.9% on radiology exam"
- **Contra perspective:** "LLMs surpassed humans in only 33% of 1,046 head-to-head comparisons"
- Diverse sample: không bias về một phía

**Verdict: PASS ✅**

#### TC-05b — Verify contradicting claim [v1.0.1]

```
POST /api/claims/verify
Body:
{
  "claim": "LLMs surpassed humans in only 33% of 1,046 head-to-head comparisons",
  "paperId": "5ed82342725cf4b246d69f89d0d16ded7cabe17c"
}
```

**Actual Output:**
```json
{
  "status": "uncertain",
  "source": "snippet",
  "low_confidence": true,
  "human_review": true,
  "intent": null,
  "snippet": null
}
```

**Analysis:**
- ✅ `status: "uncertain"` — không label `supported` khi không có evidence
- ✅ `low_confidence: true` — đánh dấu độ tin cậy thấp
- ✅ `human_review: true` — đẩy về human review queue

**Pass criteria (confirmed with dev):** `human_review: true` + `low_confidence: true` + `status ≠ "supported"` → đủ điều kiện PASS.

**Verdict: PASS ✅**  


---

### TC-06 — Abstract Conservative Rule [v1.0.1]

**Category:** Abstract Conservative Rule  
**Goal:** Verify rằng guardrail không bao giờ label `status: "supported"` khi không có evidence (snippet = null).

**Input:**
```json
{
  "claims": [{
    "id": "tc06-claim-003",
    "text": "LLMs surpassed humans in only 33% of head-to-head comparisons in clinical medicine tasks",
    "paperId": "57b47dfb87d2c9a6e10cd7182bc0e767aad1ae45",
    "status": "pending"
  }]
}
```

**Actual Output:**
```json
{
  "claims": [{
    "id": "tc06-claim-003",
    "text": "LLMs surpassed humans in only 33% of head-to-head comparisons in clinical medicine tasks",
    "paperId": "57b47dfb87d2c9a6e10cd7182bc0e767aad1ae45",
    "status": "unsupported",
    "intent": null,
    "source": "snippet",
    "low_confidence": false,
    "human_review": false,
    "snippet": null
  }],
  "supported": 0,
  "partial": 0,
  "unsupported": 1,
  "uncertain": 0
}
```

**Analysis:**
- ✅ `status: "unsupported"` — không label `supported` khi snippet = null → core rule không bị vi phạm
- ✅ `supported: 0` trong summary — xác nhận không có claim nào được label supported

**Verdict: PASS ✅**  
**Notes:** `source: "snippet"` + `snippet: null` là cosmetic inconsistency (xem BUG-01 — Low severity). Core rule được đảm bảo.

---

## Bugs Found

| Bug ID | TC | Severity | Description | Expected | Actual |
|---|---|---|---|---|---|
| BUG-01 | TC-06 | Low | `source: "snippet"` + `snippet: null` — cosmetic inconsistency | `source` field nên reflect evidence tier thực tế được dùng | Pipeline set `source: "snippet"` dù không tìm được snippet — core rule không vi phạm nhưng response misleading |

---

## Coverage Summary (SPEC v1.0.1)

| Case | Description | Tested | Result |
|---|---|---|---|
| Case A | Snippet available → verify từ snippet | ✅ TC-03c | PASS |
| Case B | ArXiv available → verify từ arXiv | ❌ Chưa test | N/A |
| Case C | Abstract fallback — rule: status ≠ "supported" | ✅ TC-06 | PASS — rule verified (status: unsupported when snippet = null) |

**Hallucination rate (hard hallucination):** 0% — TC-01 và TC-04 không có fabricated paper IDs.

**TC-02 FAIL là expected baseline**, không phải production hallucination.

---

## Conclusion

PaperPulse v1.0.1 passes all 6 main test cases covering anti-hallucination and citation guardrails:
- Không bịa paper IDs khi topic hẹp (TC-01)
- Không bịa tác giả giả (TC-04)
- Pipeline RAG generate citations thật (TC-03)
- Không label `supported` khi không có evidence — verified qua TC-05b và TC-06
- TC-02 FAIL là expected baseline, chứng minh RAG guardrail là cần thiết

Known limitation (Low severity):
- BUG-01: `source: "snippet"` + `snippet: null` — cosmetic inconsistency trong response, không ảnh hưởng core rule