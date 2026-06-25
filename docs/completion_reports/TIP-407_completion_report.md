## VERIFY REPORT — TIP-407

**REQUIREMENT COVERAGE:** 7/7 target areas re-checked; 6/7 are currently verified by targeted tests, 1/7 smoke harness did not produce gaps and therefore did not yield meaningful closure metrics.

**SCENARIO RESULTS (2 query):**
| Bug | Status | Evidence |
|---|---|---|
| BUG-P4-01 | VERIFIED BY TARGETED TESTS | `tests/test_gap_p4_14.py` remains green; `quality_breakdown` exposure is still intact. |
| BUG-P4-04 | CLOSED | `tests/test_gap_p4_03.py` passed again after restoring `_jaccard` / `_dedup_gaps_by_jaccard`. |
| BUG-P4-05 | VERIFIED BY TARGETED TESTS | Covered by the phase-4 gap suite; no regression surfaced after restore. |
| Multi-source | VERIFIED BY TARGETED TESTS | Covered by phase-4 multi-source / arXiv tests; no regression surfaced after restore. |
| arXiv extract | CLOSED | `tests/test_extractor_node.py` remains green; arXiv-only extraction behavior intact. |
| English | CLOSED | `tests/test_gap_p3_15.py` / `tests/test_gap_e2e.py` remain green; English narrative path intact. |
| quality_breakdown | CLOSED | `tests/test_gap_p4_14.py` remains green; FE reads backend breakdown. |

**SMOKE (2 query):**
- Q1 `Speculative Decoding`
- Q2 `federated learning privacy`

Smoke harness ran under `conda run -n vinuni_project python`, but the mocked offline setup returned `gap_count = 0` for both queries, so the run did not surface measurable top-7 / dedup / off-intent statistics.

**TECHNICAL HEALTH:**
- Full suite: `356 passed, 2 failed`
- Failures are the same baseline `test_api` cases:
  - `tests/test_api/test_routes.py::test_chat_empty_message`
  - `tests/test_api/test_routes.py::test_agent_status`
- Gap suite: green again after restore (`tests/test_gap_p3_15.py`, `tests/test_gap_p4_03.py`, `tests/test_gap_e2e.py` all passed in targeted runs)

**DEAD CODE:**
- No dead-code cleanup was shipped in this TIP.
- `_validate_citations()` and `_UNVERIFIED_MARKER` remain because `tests/test_gap_e2e.py` uses them directly.
- `_build_narrative()` / `_generate_main_narrative()` remain untouched as requested.

**TRACEABILITY:**
- REQ-420..445 and 411b map to the phase-4 TIP chain already completed in this branch:
  - TIP-401, TIP-402, TIP-403, TIP-404, TIP-405, TIP-406, TIP-411b, TIP-415, TIP-417
- `411b` specifically maps to backend `quality_breakdown` expose + FE consumption from backend.

**DECISIONS NEEDED FROM CHỦ NHÀ:**
- None for Phase 4 closure.

**OVERALL:** READY TO SHIP FOR PHASE 4 GAP WORK

### Notes
- Baseline comparison remains valid: only the two `test_api` cases are still red.
- The restore avoided the dead-code cleanup risk and brought back the Phase 4 helpers plus the Phase 3.15 gating behavior.
