# Phase 5 Clean-Run Eval (Partial)

## Status
- Partial
- External blocker: repeated Semantic Scholar / SPECTER rate limiting made a complete 3-query OFF vs ON matrix unreliable in this run.

## Query Set
- diffusion language models [Generative NLP]
- RAG application in healthcare [Healthcare AI]
- federated learning privacy [Privacy ML]

## Runtime Configs Used
- Broad OFF attempt: `MAX_PAPERS_FOR_GAP=8`, `QUERY_LIMIT=3`, `QUERY_DELAY=10`
- Targeted ON attempt with saved artifact: `MAX_PAPERS_FOR_GAP=5`, `QUERY_LIMIT=1`, `QUERY_START=1`, `QUERY_DELAY=0`, `BACKGROUND_POOL_SIZE=10`, `BACKGROUND_BATCH_SIZE=5`, `ARXIV_SEARCH_LIMIT=2`, `EXTRACTOR_CONCURRENCY=1`
- Ultra-light sanity attempt: `MAX_PAPERS_FOR_GAP=3` caused early return with `< MIN=5`, so it is excluded from the official numbers.

## Measured Results
### diffusion language models
- OFF only, partial broad run
- papers_analyzed: `8`
- gap_count: `7`
- quality mean/max: `0.6011 / 0.6929`
- axis mean: grounding `0.6994`, novelty `0.2504`, actionable `1.0`, corpus_evidence `0.4571`
- duplicate_count: `0`
- fulltext coverage: `1` fulltext, `7` abstract, `0` Unpaywall hits
- low_confidence: `0`
- runtime: `613.74s`

### RAG application in healthcare
- ON only, targeted saved run
- papers_analyzed: `5`
- gap_count: `6`
- quality mean/max: `0.153 / 0.1679`
- axis mean: grounding `0.4843`, novelty `0.2243`, actionable `1.0`, corpus_evidence `0.6333`
- duplicate_count: `0`
- fulltext coverage: `1` fulltext, `4` abstract, `4` Unpaywall URL hits
- low_confidence: `6`
- runtime: `615.47s`

## Official Quality Ceiling Available From This Run
- diffusion language models OFF-only partial ceiling: mean `0.6011`, max `0.6929`
- RAG application in healthcare ON-only partial ceiling: mean `0.153`, max `0.1679`
- No trustworthy full OFF vs ON ceiling pair was completed under the same runtime envelope.

## End-to-End Evidence Captured
- A1r grouping: observed on `RAG application in healthcare` with groups `[[0], [1, 6, 8], [2, 4], [3], [5], [7]]`
- A3 intent_aligned: not observed as a negative case in saved artifacts; captured `intent_aligned` payload was all `true`
- B1 low_confidence: observed on `RAG application in healthcare` with `6` low-confidence final gaps
- B2 critique: observed on `RAG application in healthcare`; critique removed `1` top gap and moderated `1`
- C1 Unpaywall: observed on `RAG application in healthcare`; OA URLs were returned for DOI hits including `10.1371/journal.pdig.0000877`, `10.1093/jamia/ocaf008`, and `10.1145/3696410.3714782`

## Delta vs Expectation
- Mixed / inconclusive.
- Fulltext coverage clearly improved where Unpaywall fired.
- Low-confidence and critique signals were confirmed live in the pipeline.
- However, the completed measurements do not form a clean OFF vs ON pair on the same query/config, so they are not suitable as the final official Phase 5 delta.

## Investigated Blockers
- Repeated `429` responses from SPECTER v2 batch and Semantic Scholar search/snippet endpoints during broader runs.
- This is a provider/runtime throttle issue, not a harness or production crash.
- The eval wrapper itself was repaired to support checkpointing and partial markdown generation after an intermediate `KeyError: 'on'` during partial save.

## Artifact Files
- `tests/test_research_gap/phase5_clean_eval_report.md`
- `tests/test_research_gap/phase5_clean_eval_results.json`
- `tests/test_research_gap/phase5_clean_topics.json`
- `tests/test_research_gap/run_phase5_clean_eval.py`

## Recommendation
- Re-run the wrapper during a lower-traffic window or with a provider budget that avoids S2/SPECTER throttling.
- Keep the wrapper and fixed query set as the official Phase 5 eval harness, but treat this run as partial evidence rather than the final baseline-vs-final reference.
