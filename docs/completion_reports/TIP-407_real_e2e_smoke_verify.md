## VERIFY REPORT — Real E2E Smoke

**REQUIREMENT COVERAGE:** 7/7 checks observed from the real smoke output

**SCENARIO RESULTS (2 query):**
| Bug | Status | Số thật |
|---|---|---|
| BUG-P4-01 | CLOSED | Q1 `gap_count=7`, `quality_range=0.5441..0.6794`; Q2 `gap_count=7`, `quality_range=0.5450..0.6843` |
| BUG-P4-04 | NOT CLOSED | `same_paper_max=3` ở cả 2 query, tức top-7 vẫn có 3 gaps cùng paper ở mức tối đa |
| BUG-P4-05 | CLOSED | `off_intent_carbon=0` ở cả 2 query |
| Multi-source | CLOSED | `arxiv_source_present=true` ở cả 2 query |
| arXiv extract | CLOSED | `papers_analyzed=20` và `16`, pipeline đi tới detection; arXiv vẫn vào corpus |
| English | CLOSED | narrative trả về English: `Showing top 7/... research gaps by quality...` |
| quality_breakdown | CLOSED | `breakdown_present=true` ở cả 2 query |

**TECHNICAL HEALTH:**
- Q1 `Speculative Decoding`: `papers_analyzed=20`, `gap_count=7`, `top7_count=7`, `novelty_range=0.2552..0.5499`
- Q2 `federated learning privacy...`: `papers_analyzed=16`, `gap_count=7`, `top7_count=7`, `novelty_range=0.4069..0.5176`
- Smoke thực tế có nhiều `429` từ Semantic Scholar / SPECTER v2, nhưng pipeline vẫn hoàn tất
- Có 1 lỗi extract thật được log: `ExtractedPaperData.dataset` nhận `list` thay vì `string`
- Có các lỗi fetch PDF thật nhưng không chặn pipeline: `418` / HTML response

**DEAD CODE:**
- Không đụng trong verify này

**TRACEABILITY:**
- `411b` đã xác nhận qua `breakdown_present=true`
- `406` / `415` / `417` tiếp tục phản ánh trong output smoke và narrative
- `403` dedup vẫn có dấu hiệu hoạt động, nhưng AC top-7 theo output này vẫn còn chạm ngưỡng `same_paper_max=3`

**OVERALL:** NEEDS FIXES

Kết luận ngắn:
- Real e2e smoke đã chạy được và sinh gap thật
- Nhưng Phase 4 chưa nên đóng hẳn vì `BUG-P4-04` עדיין chưa đạt tiêu chí `top-7 KHÔNG ≥3 gaps cùng paper`
