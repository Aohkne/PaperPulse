# Research Gaps E2E Pipeline Architecture

## Purpose
This document describes the end-to-end research-gap discovery method used in PaperPulse. It explains how a raw topic becomes a ranked and deduplicated GapReport by shaping the query, constructing the corpus, extracting structured evidence, generating gap candidates, verifying them, scoring them, and assembling the final output. UI routes and components are out of scope except for a tiny delivery appendix at the end. Evidence for the live pipeline and graph wiring comes from the backend gap-detection modules. [backend/module/gap_detection/graph.py:38-68](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/graph.py#L38), [backend/module/gap_detection/router.py:85-143](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/router.py#L85)

## High-Level Flow
The system has two linked layers: a cold-start orchestration wrapper that builds the working corpus, and a linear LangGraph that turns that corpus into verified gaps. The cold-start wrapper can short-circuit through a relevance gate and coherence check, or fall back to search, snowballing, and ranking when the seed corpus is thin. The live graph then runs extractor -> topical detector -> method detector -> contradiction detector -> verifier -> counter search -> synthesizer. [backend/module/gap_detection/orchestrator.py:47-168](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/orchestrator.py#L47), [backend/module/gap_detection/graph.py:10-11](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/graph.py#L10)

~~~mermaid
flowchart TD
  A[Raw topic string] --> B[Query cleaning / query analysis]
  B --> C[Semantic Scholar search]
  C --> D[Optional arXiv supplement]
  D --> E{Multiple sources?}
  E -- yes --> F[Cross-source canonical resolution]
  E -- no --> G[Continue with S2 papers]
  F --> H{Corpus thin?}
  G --> H
  H -- yes --> I[Raw-topic retry / recall rescue]
  H -- no --> J[Citation snowballing]
  I --> J
  J --> K[Paper ranking before gap detection]
  K --> L[PaperRef conversion]
  L --> M[Structured extraction]
  M --> N[Topical detector]
  M --> O[Methodological detector]
  M --> P[Contradiction detector]
  N --> Q[Origin labeling]
  O --> Q
  P --> Q
  Q --> R[Verification]
  R --> S[Counter-evidence search]
  S --> T[Novelty scoring]
  T --> U[Quality scoring and ranking]
  U --> V[Jaccard deduplication]
  V --> W[Final GapReport]

  Q -. latent helper only .-> X[False-gap helper]
  U -. fallback / helper branch .-> Y[Long-form narrative helper]
~~~

## Data Flow: Input to Output
The data objects form a strict chain. Each object exists because the next stage needs a narrower and more structured representation than the previous one. Raw topic text is too ambiguous for retrieval. Raw paper candidates are too duplicated for downstream reasoning. Extracted paper data is too granular to display directly. GapItem is the unit that survives detection, verification, scoring, and final ranking. GapReport is the final package returned to the caller. [backend/module/gap_detection/schemas.py:52-63](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/schemas.py#L52), [backend/module/gap_detection/schemas.py:65-138](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/schemas.py#L65), [backend/module/gap_detection/schemas.py:211-224](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/schemas.py#L211)

| Object | What it contains | Why it exists |
|---|---|---|
| Raw topic string | User provided topic text | Starting point for query shaping and retrieval |
| GapQuery | core_topic, facets, year_range, field_of_study, recency_bias, seminal_bias, user_intent | Structured search intent used to broaden and bias retrieval |
| Raw paper candidates | Search hits from Semantic Scholar, optional arXiv, and snowball neighbors | Input to canonical resolution and ranking |
| CanonicalPaper | Cross-source merged paper record with provenance | Prevents duplicate reasoning over the same paper |
| Ranked paper list | Ordered candidate papers after pre-gap ranking | Chooses what enters the evidence pipeline first |
| PaperRef | Lightweight citation snapshot used by the graph | Seeds the LangGraph without carrying the full paper object |
| ExtractedPaperData | Topics, keywords, methodology, dataset, key_claims, limitation_statements, and related fields | Supplies the detectors with machine-readable evidence |
| Candidate GapItem | Detected gap plus origin, supporting papers, and first-pass metadata | Intermediate detector output before verification |
| Verified GapItem | Candidate gap after grounding, atomic-NLI, and counter-evidence handling | Keeps only grounded or partially grounded gaps |
| Ranked / deduped GapItem | Verified gap with quality score, novelty score, and merged evidence quotes | Final ordering unit |
| GapReport | papers_analyzed, gaps, narrative, baseline_triggered | Final response object |

## Stage 1 — Query Shaping

**Goal**
- Turn a raw topic into a structured search intent that can drive retrieval and recall expansion.

**Inputs**
- Raw topic string from the user.
- Optional cold-start context when the orchestrator already has a topic-only request.

**Technique**
- Deterministic query cleaning strips meta words such as research gap phrasing before search. The LLM-based query analyzer then converts the raw topic into a GapQuery JSON object. The prompt asks for core_topic, facets, year_range, field_of_study, recency_bias, seminal_bias, and user_intent. Facets are search angles, not final answers. [backend/module/gap_detection/retrieval.py:68-101](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L68), [backend/module/gap_detection/nodes/query_analyzer.py:18-37](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/query_analyzer.py#L18)

**Implementation Detail**
- The query analyzer is implemented in backend/module/gap_detection/nodes/query_analyzer.py and returns a GapQuery object. The schema is defined in backend/module/gap_detection/schemas.py. If the analyzer returns malformed output or throws, the code falls back to clean_query(raw_query) and uses the cleaned topic as both core_topic and the only facet. [backend/module/gap_detection/nodes/query_analyzer.py:49-87](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/query_analyzer.py#L49), [backend/module/gap_detection/schemas.py:190-205](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/schemas.py#L190)

**Outputs**
- GapQuery with a cleaned core_topic, a facet list, bias flags, and a user_intent label when the model can infer one.

**Failure / Fallback Behavior**
- Any exception in query analysis collapses to a minimal clean_query fallback. If facets are empty after parsing, the analyzer also fills them with the core topic. [backend/module/gap_detection/nodes/query_analyzer.py:52-87](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/query_analyzer.py#L52)

**Why This Matters for Gap Detection**
- Better query shaping increases recall without turning retrieval into a blind keyword search. The facets and intent label also give the synthesizer a later signal for re-ranking gaps by user intent.

Mini example:
- Input topic: multimodal learning for medical imaging
- Possible core_topic: multimodal medical imaging
- Possible facets: radiology text fusion, vision-language pretraining, report generation, weak supervision
- Possible user_intent: accuracy or robustness

## Stage 2 — Corpus Construction

**Goal**
- Build the evidence corpus that will later be analyzed for gap patterns.

**Inputs**
- GapQuery from Stage 1.
- Raw search results from Semantic Scholar and optional arXiv.
- Seed papers from the cold-start wrapper.

**Technique**
- Retrieval is Semantic Scholar first. arXiv is only a supplement when available. The cold-start wrapper may also use a relevance gate plus coherence check when it already has a good seed list. After that, the wrapper can retry the raw topic if the cleaned query is too narrow, and then snowball through citation neighbors to expand recall. [backend/module/gap_detection/retrieval.py:132-192](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L132), [backend/module/gap_detection/orchestrator.py:84-99](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/orchestrator.py#L84), [backend/module/gap_detection/orchestrator.py:117-144](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/orchestrator.py#L117)

**Implementation Detail**
- Search hits are merged and deduplicated by source resolution when multiple sources exist. The resolver uses DOI, then normalized title, then S2 paperId as merge keys. When only Semantic Scholar results exist, the pipeline can proceed directly with those papers. [backend/module/gap_detection/source_resolution.py:3-32](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/source_resolution.py#L3), [backend/module/gap_detection/source_resolution.py:133-158](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/source_resolution.py#L133)

**Outputs**
- A seed corpus of deduplicated papers ready for ranking.
- A canonical paper list when multi-source input exists.

**Failure / Fallback Behavior**
- If the cleaned query is too narrow, cold_start retries the raw topic. If search still returns too few papers, the wrapper returns early with an insufficient-data narrative instead of forcing a weak gap report. [backend/module/gap_detection/orchestrator.py:123-159](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/orchestrator.py#L123)

**Why This Matters for Gap Detection**
- Gap detection needs enough corpus diversity to compare methods, topics, and claims. Thin corpora produce brittle or hallucinated gaps, so this stage is the main recall control point.

## Stage 3 — Paper Ranking Before Gap Detection

**Goal**
- Rank candidate papers before extraction and detector stages so the most useful papers enter downstream gap analysis first.

**Inputs**
- Seed corpus from Stage 2.
- Cleaned query text.
- Optional semantic embeddings for the papers.

**Technique**
- This is a weighted hybrid paper-ranking stage, not final gap ranking. The ranker computes a semantic score from NIM nearest-neighbor order and combines it with lexical overlap, citation influence, and recency. The semantic path uses a Hypothetical Document Embeddings style query vector: the query text is expanded into a hypothetical abstract, that hypothetical representation is embedded in the same NIM space, and the nearest-neighbor order is converted into a semantic score. The code path is labeled HyDE in comments and uses generate_hyde_vector_nim(clean_query) before querying gap_nim_store. [backend/module/gap_detection/retrieval.py:347-360](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L347), [backend/module/gap_detection/hyde.py:1-24](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/hyde.py#L1)

**Implementation Detail**
- NIM is the active semantic query store in the current rank() implementation. The code upserts abstract vectors into gap_nim_store, then queries nearest neighbors with query_by_vector_nim and converts their rank position into a semantic score. SPECTER2 is also fetched and upserted into gap_specter_store, but that store is not the active query path for rank(). That makes SPECTER2 an auxiliary store and NIM the active ranking store. [backend/module/gap_detection/retrieval.py:296-317](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L296), [backend/module/gap_detection/retrieval.py:319-360](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L319), [backend/module/gap_detection/gap_specter_store.py:1-4](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/gap_specter_store.py#L1), [backend/module/gap_detection/gap_nim_store.py:1-8](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/gap_nim_store.py#L1)
- The final paper score is a weighted hybrid score. The semantic arm is weighted by get_specter2_weight() when HyDE succeeds; the remaining weight goes to a BM25-style composite approximation built from token overlap, log citation score, and recency. The lexical portion uses token overlap against title plus abstract, log-scaled citation score, and a raw year recency score. [backend/module/gap_detection/retrieval.py:368-439](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L368), [backend/module/gap_detection/settings.py:112-117](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/settings.py#L112)
- This ranking is for papers only. The later gap ranking is a separate score computed after verification and novelty scoring.

**Outputs**
- Ranked list of candidate papers to seed the rest of the pipeline.

**Failure / Fallback Behavior**
- If HyDE generation fails, the semantic weight becomes 0.0, so ranking falls back to the lexical, citation, and recency terms only. If NIM semantic lookup fails, the same lexical/citation/recency fallback still applies. [backend/module/gap_detection/retrieval.py:347-396](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L347), [backend/module/gap_detection/settings.py:112-117](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/settings.py#L112)

**Why This Matters for Gap Detection**
- Good paper ranking reduces noise before extraction. The detectors work better when the corpus is front-loaded with papers that are semantically close to the user topic and still grounded by lexical, citation, and recency signals.

## Stage 4 — PaperRef Conversion

**Goal**
- Convert ranked papers into the lightweight reference objects that the LangGraph uses as its session input.

**Inputs**
- Ranked paper list from Stage 3.

**Technique**
- The cold-start wrapper maps Paper fields into PaperRef. PaperRef keeps paper_id, title, year, url, abstract, and source. This is a lightweight citation snapshot, not a full paper object. [backend/module/gap_detection/orchestrator.py:181-209](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/orchestrator.py#L181), [backend/module/gap_detection/schemas.py:52-63](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/schemas.py#L52)

**Implementation Detail**
- The orchestrator skips any paper without a paper_id and logs that it was skipped. The resulting PaperRef list becomes the session_papers input for the graph. [backend/module/gap_detection/orchestrator.py:192-209](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/orchestrator.py#L192)

**Outputs**
- list[PaperRef] seeded into run_gap_detection.

**Failure / Fallback Behavior**
- Paper records without paper_id are dropped. The graph still runs on the surviving references.

**Why This Matters for Gap Detection**
- The graph only needs a lightweight, stable citation shape. PaperRef keeps the runtime lean and avoids carrying the full retrieval model object into every node.

## Stage 5 — Structured Evidence Extraction

**Goal**
- Turn paper text into structured evidence that the detectors can compare.

**Inputs**
- PaperRef list.
- Semantic Scholar metadata.
- Optional PDF/full-text text.
- Abstract and tldr fallback text.

**Technique**
- Extraction is fetch -> source text -> LLM JSON parse -> fallback. The extractor first fetches Semantic Scholar metadata. If open-access PDF is available, it downloads and parses the PDF text. If not, it falls back to abstract plus tldr. The prompt requests exact JSON fields including topics, keywords, methodology, dataset, population, metrics, key_claims, and limitation_statements. [backend/module/gap_detection/nodes/extractor.py:3-6](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/extractor.py#L3), [backend/module/gap_detection/nodes/extractor.py:44-75](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/extractor.py#L44), [backend/module/gap_detection/nodes/extractor.py:155-219](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/extractor.py#L155)

**Implementation Detail**
- The extractor stores raw abstract separately so later verification does not circularly depend on the same limitation statements that produced a gap. It also retries once when parsing fails. [backend/module/gap_detection/nodes/extractor.py:82-145](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/extractor.py#L82)

**Outputs**
- ExtractedPaperData objects with topics, keywords, methodology, dataset, metrics, claims, and limitation statements.

**Failure / Fallback Behavior**
- Malformed LLM JSON triggers a retry. If retry still fails, the extractor returns a minimal valid object instead of aborting the pipeline.

**Why This Matters for Gap Detection**
- The detectors rely on structured fields, not raw prose. Extraction is what makes topical, methodological, and contradiction comparison possible.

## Stage 6 — Gap Candidate Generation

**Goal**
- Generate candidate topical, methodological, and contradiction gaps from the extracted corpus.

**Inputs**
- ExtractedPaperData list.
- Paper-level topics, keywords, methodology, limitation statements, and key_claims.

**Technique**
- This stage has three detectors and all of them operate on structured evidence rather than raw papers.

Topical gaps
- The topical detector compares extracted topics, keywords, and claims and asks an LLM to identify closely related research areas that are missing from coverage. It builds a topic coverage map from the extracted papers, not from the raw documents. It requires at least two papers to compare. [backend/module/gap_detection/nodes/topical_detector.py:3-8](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/topical_detector.py#L3), [backend/module/gap_detection/nodes/topical_detector.py:38-69](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/topical_detector.py#L38)
- The prompt asks for statement, origin, supporting papers, suggested_method, and falsifiability_condition. [backend/module/gap_detection/nodes/topical_detector.py:45-69](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/topical_detector.py#L45)

Methodological gaps
- The methodological detector builds a method x domain co-occurrence matrix. The method source is methodology. The domain source is topics. The matrix builder splits compound methodology strings on comma or slash, lowercases the tokens, and counts each method-domain pair across the corpus. Pairs below the configured threshold are underexplored candidates. Limitation statements are a second input channel. [backend/module/gap_detection/co_occurrence.py:1-14](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/co_occurrence.py#L1), [backend/module/gap_detection/co_occurrence.py:28-105](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/co_occurrence.py#L28), [backend/module/gap_detection/nodes/method_detector.py:51-86](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/method_detector.py#L51)
- The prompt gives the matrix and limitation block to the LLM and asks it to return gaps with from_limitation, statement, supporting papers, suggested_method, and falsifiability_condition. [backend/module/gap_detection/nodes/method_detector.py:120-177](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/method_detector.py#L120)

Contradiction gaps
- The contradiction detector compares structured key_claims rather than whole raw papers. It asks the LLM for a contradiction statement, paper_id_a, paper_id_b, context_explanation, suggested_method, and falsifiability_condition. [backend/module/gap_detection/nodes/contradiction_detector.py:38-73](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/contradiction_detector.py#L38)
- A contradiction is only kept when both IDs exist, the IDs refer to two distinct real papers, and the context explanation is non-empty. [backend/module/gap_detection/nodes/contradiction_detector.py:80-143](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/contradiction_detector.py#L80)

**Implementation Detail**
- The graph wires the three detectors before verification. Topical and methodological detectors can emit origin hints. The contradiction detector uses two-paper evidence and structured claims to avoid raw-text hallucination.

**Outputs**
- Candidate GapItem objects with gap_type, origin hints, supporting papers, statement text, and optional method/falsifiability fields.

**Failure / Fallback Behavior**
- Each detector skips when the corpus is too thin. If the LLM output is malformed, the node keeps existing candidates rather than dropping the pipeline.

**Why This Matters for Gap Detection**
- This is the actual discovery stage. It converts structured paper evidence into candidate gaps that can be verified and ranked.

## Stage 7 — Origin Labeling

**Goal**
- Classify the gap as EXPLICIT, LIMITATION, or INFERRED so later verification can apply the right confidence policy.

**Inputs**
- Candidate GapItem objects.
- Extracted limitation statements and explicit language from papers.

**Technique**
- Origin detection is pattern based first. The explicit detector checks future-work and open-problem language, then limitation patterns, then falls back to inferred. [backend/module/gap_detection/explicit_detector.py:13-32](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/explicit_detector.py#L13), [backend/module/gap_detection/explicit_detector.py:45-74](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/explicit_detector.py#L45)

**Implementation Detail**
- Topical detector can emit explicit or inferred origin. Methodological detector maps from_limitation to LIMITATION, otherwise INFERRED. The final origin value is carried by the GapItem model. [backend/module/gap_detection/nodes/topical_detector.py:114-132](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/topical_detector.py#L114), [backend/module/gap_detection/nodes/method_detector.py:158-177](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/method_detector.py#L158), [backend/module/gap_detection/schemas.py:26-33](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/schemas.py#L26)

**Outputs**
- GapItem objects with normalized origin values.

**Failure / Fallback Behavior**
- If no explicit or limitation language is present, the gap stays INFERRED.

**Why This Matters for Gap Detection**
- Origin controls how strict verification must be and how much confidence the system can assign.

## Stage 8 — Verification

**Goal**
- Ground candidate gaps against cited evidence and remove or downgrade unsupported claims.

**Inputs**
- Candidate GapItem objects.
- Extracted paper abstracts and evidence fields.
- Origin labels.

**Technique**
- Verification is origin sensitive. Explicit gaps receive full confidence. Limitation gaps must be grounded. Inferred gaps use atomic-NLI confidence from supporting evidence. Atomic-NLI means the candidate gap statement is split into smaller subclaims, each subclaim is checked against the evidence papers, and the final confidence is constrained by the strongest verification status that survives. [backend/module/gap_detection/nodes/verifier.py:1-31](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/verifier.py#L1), [backend/module/gap_detection/nodes/verifier.py:205-356](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/verifier.py#L205)

**Implementation Detail**
- The verifier uses citation_verifier.verify_claims, prepends a decomposition step for complex claims, and upgrades or downgrades confidence according to the detected origin. The policy constants are explicit: EXPLICIT is 1.0, confirmed limitation is 0.85, partial limitation is 0.50, fallback after verification failure is 0.60, and inferred base confidence is 0.40. [backend/module/gap_detection/nodes/verifier.py:64-69](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/verifier.py#L64), [backend/module/gap_detection/nodes/verifier.py:107-147](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/verifier.py#L107)

**Outputs**
- Verified GapItem objects with confidence, verified flag, and grounded supporting papers.

**Failure / Fallback Behavior**
- If decomposition fails, the verifier falls back to the original statement as one atomic claim. If NLI or citation verification errors occur, the code uses the safe fallback confidence rather than crashing.

**Why This Matters for Gap Detection**
- Verification is the main guard against hallucinated gaps. It separates plausible inference from evidence-backed signals.

## Stage 9 — Counter-Evidence and False-Gap Handling

**Goal**
- Check whether the gap is already addressed and prevent overclaiming.

**Inputs**
- Verified GapItem objects.
- Gap statements and supporting papers.

**Technique**
- Counter-evidence search is active end-to-end behavior. For every verified gap, the node builds a query, searches Semantic Scholar, and asks whether any returned paper already addresses the gap. If evidence is found, the gap is downgraded to PARTIALLY_FILLED and confidence is penalized. If counter-search fails, the gap is preserved rather than discarded. [backend/module/gap_detection/nodes/counter_search.py:3-8](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/counter_search.py#L3), [backend/module/gap_detection/nodes/counter_search.py:78-185](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/counter_search.py#L78)

**Implementation Detail**
- The intended false-gap helper exists in backend/module/gap_detection/false_gap.py. Its design is to embed the gap statement with NIM, query gap_nim_store for nearest neighbors, compare cosine distance against a threshold, and flag likely false gaps. But the main graph wiring does not prove a live invocation of that helper. That means the helper is latent code, not confirmed active E2E behavior. [backend/module/gap_detection/false_gap.py:1-40](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/false_gap.py#L1), [backend/module/gap_detection/gap_nim_store.py:109-136](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/gap_nim_store.py#L109), [backend/module/gap_detection/graph.py:38-44](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/graph.py#L38)

**Outputs**
- Verified gaps that may be downgraded to PARTIALLY_FILLED, plus attached counter-evidence papers when found.

**Failure / Fallback Behavior**
- Search failures do not remove the gap. They only prevent counter-evidence refinement.

**Why This Matters for Gap Detection**
- Counter-evidence search keeps the pipeline from praising gaps that the literature already closes.

## Stage 10 — Novelty and Quality Scoring

**Goal**
- Measure how novel, actionable, grounded, and corpus-supported each verified gap is, then rank the final set.

**Inputs**
- Verified GapItem objects.
- Supporting papers.
- Gap statements.

**Technique**
- Novelty is computed from NIM semantic distance against the core corpus. The novelty scorer returns mean cosine distance between the gap statement and the nearest core corpus matches. [backend/module/gap_detection/novelty.py:11-40](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/novelty.py#L11)
- Quality scoring combines four normalized axes: grounding, novelty, actionable, and corpus evidence. The weighted formula is 0.3333 grounding + 0.2778 novelty + 0.2222 actionable + 0.1667 corpus evidence. [backend/module/gap_detection/quality_scorer.py:15-64](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/quality_scorer.py#L15)

**Implementation Detail**
- Grounding comes from confidence clipped to the 0-1 range.
- Novelty is novelty_score divided by 2.0 and capped at 1.0. If novelty is missing, the scorer uses 0.5 as a neutral fallback.
- Actionable is 1.0 when suggested_method exists, 0.5 when only falsifiability_condition exists, and 0.0 otherwise.
- Corpus evidence is min(supporting_papers / 5, 1.0).
- The scorer writes quality_breakdown back to each GapItem and computes quality_score from the weighted sum. [backend/module/gap_detection/quality_scorer.py:15-35](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/quality_scorer.py#L15)
- The backend scorer outputs numeric quality_score only. The UI maps that score to tiers: High quality at 0.7 or above, Medium quality at 0.4 or above, Low quality below 0.4, and no tier badge when the score is null. [frontend/src/features/gap/GapQualityBadge.jsx:1-39](/D:/vinuni/Project/Build_project/C2-App-069/frontend/src/features/gap/GapQualityBadge.jsx#L1)

**Outputs**
- GapItem objects with quality_breakdown, quality_score, and a UI-readable tier mapping.

**Failure / Fallback Behavior**
- Missing novelty data falls back to a neutral novelty contribution. Missing actionability fields reduce the actionable axis to 0 or 0.5. The scorer still returns a numeric result.

**Why This Matters for Gap Detection**
- This is the final ranking model for gaps. It determines which verified gaps are shown first and which ones sink into weak signals.

## Stage 11 — Deduplication and Final Assembly

**Goal**
- Merge near-duplicate gaps, build the final report, and emit a clean result set.

**Inputs**
- Scored verified GapItem objects.
- Supporting paper sets and evidence quotes.
- Optional user intent label.

**Technique**
- Final deduplication uses Jaccard overlap over supporting-paper ID sets. If two gaps exceed the overlap threshold of 0.6, the higher quality or confidence gap wins and evidence quotes from the loser are merged into the winner. [backend/module/gap_detection/nodes/synthesizer.py:352-385](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/synthesizer.py#L352)
- The synthesizer then sorts by quality, applies an optional intent penalty, and builds the final GapReport. [backend/module/gap_detection/nodes/synthesizer.py:170-255](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/synthesizer.py#L170)

**Implementation Detail**
- The live synthesizer_node computes novelty when needed, ranks by quality, applies intent re-scoring, deduplicates by Jaccard, and returns a GapReport with papers_analyzed, gaps, narrative, and baseline_triggered. The file also contains a longer narrative helper, but the live return path currently uses the short template narrative, not the helper. [backend/module/gap_detection/nodes/synthesizer.py:170-255](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/synthesizer.py#L170), [backend/module/gap_detection/nodes/synthesizer.py:261-319](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/synthesizer.py#L261)

**Outputs**
- GapReport with a ranked, deduplicated gaps list and a concise narrative.

**Failure / Fallback Behavior**
- If ranking fails, the synthesizer falls back to confidence ordering. If long-form narrative generation fails in the helper branch, the template summary still stands.

**Why This Matters for Gap Detection**
- This is the last quality gate before the result leaves the pipeline. It keeps the output compact, ordered, and internally consistent.

## End-to-End Example
Illustrative example only. A user asks for gaps in vision-language learning for medical imaging. Query shaping produces a core topic and facets such as radiology text fusion and report generation. Retrieval finds a small seed corpus, then raw-topic retry and snowballing expand the paper set. Extraction yields structured topics, methodology, key_claims, and limitation_statements. The topical detector emits a missing related area, the methodological detector emits an underexplored method x domain pairing, and the contradiction detector emits a conflict between two papers that report different outcomes on the same benchmark. Verification grounds the candidates, counter-evidence can downgrade one of them, novelty and quality scoring order the survivors, and Jaccard dedup merges near duplicates before the final GapReport is returned. This example mirrors the live flow but is not a literal output trace. [backend/module/gap_detection/nodes/query_analyzer.py:18-45](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/query_analyzer.py#L18), [backend/module/gap_detection/nodes/extractor.py:44-75](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/extractor.py#L44), [backend/module/gap_detection/graph.py:38-44](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/graph.py#L38)

## Live vs Latent Mechanisms
| Mechanism | Status | Evidence path |
|---|---|---|
| Query analyzer | Active | [backend/module/gap_detection/nodes/query_analyzer.py:49-87](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/query_analyzer.py#L49) |
| Semantic Scholar retrieval | Active | [backend/module/gap_detection/retrieval.py:132-192](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L132) |
| arXiv supplement | Fallback / optional | [backend/module/gap_detection/retrieval.py:132-192](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L132) |
| SPECTER2 store/upsert | Auxiliary, not active query path | [backend/module/gap_detection/retrieval.py:296-317](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L296) |
| NIM semantic ranking | Active | [backend/module/gap_detection/retrieval.py:319-360](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L319) |
| False-gap helper | Latent | [backend/module/gap_detection/false_gap.py:12-40](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/false_gap.py#L12) |
| Long-form narrative helper | Fallback / helper branch, not live return path | [backend/module/gap_detection/nodes/synthesizer.py:261-319](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/nodes/synthesizer.py#L261) |

## Minimal Delivery Appendix
The delivery layer is thin. The stream route emits progress events and the final report, and the frontend renders GapReport. The delivery layer does not define the discovery method itself. [backend/module/gap_detection/router.py:85-143](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/router.py#L85), [frontend/src/pages/ResearchGapsPage.jsx:1-8](/D:/vinuni/Project/Build_project/C2-App-069/frontend/src/pages/ResearchGapsPage.jsx#L1)

## Known Limitations
Two details remain version sensitive. First, false-gap detection is intentionally marked latent because the main orchestration path does not prove an invocation. Second, retrieval ranking has both lexical and semantic fallback behavior, so the practical paper order can depend on which search branch produced the candidate pool. [backend/module/gap_detection/graph.py:38-44](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/graph.py#L38), [backend/module/gap_detection/retrieval.py:368-439](/D:/vinuni/Project/Build_project/C2-App-069/backend/module/gap_detection/retrieval.py#L368)
