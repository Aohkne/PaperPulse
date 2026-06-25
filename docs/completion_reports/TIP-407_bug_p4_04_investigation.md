## COMPLETION REPORT — TIP-407 BUG-P4-04 INVESTIGATION

**STATUS:** DONE

**FILES CHANGED:**
- Created: `docs/completion_reports/TIP-407_bug_p4_04_investigation.md` - investigation report for same_paper_max=3 and dataset type mismatch

**TEST RESULTS:**
- Acceptance criteria tested: 2/2 completed
- Details:
  - Real smoke dump collected for both queries
  - 3-gap Jaccard analysis completed for both queries

**ISSUES DISCOVERED:**
- Same-paper metric too coarse: medium — `same_paper_max=3` is explained by three distinct gaps sharing one seminal paper, but their pairwise Jaccard scores are below the dedup threshold used by TIP-403
- ExtractedPaperData.dataset type mismatch: medium — extractor sometimes receives `dataset` as `list` while schema expects `str | None`

**DEVIATIONS FROM SPEC:**
- BUG-P4-04 classification: AC is too coarse — real evidence shows the top-7 can contain 3 distinct gaps sharing a foundational paper without being near-duplicates
- dataset field shape: extractor output violates schema expectation on some runs, causing `ValidationError` for `dataset`

**SUGGESTIONS FOR CHỦ THẦU:**
- BUG-P4-04: refine the acceptance criterion to measure near-duplicate overlap, not just shared paper presence; current evidence supports `AC quá thô`
- dataset mismatch: decide whether to coerce `list -> str` in extractor, change schema to `list[str]`, or fix the upstream LLM prompt/output to always return a string

**BẢNG KẾT QUẢ**

Q1: `accelerating LLM inference using Diffusion Language Models as drafters in Speculative Decoding`
- 3 gaps sharing one paper:
  - `Suffix dropout, a training-free attention reduction technique used for diffusion language models (DPad), has not been explored for standard autoregressive language models, where it could reduce the quadratic attention cost on long sequences.`
  - `Length regularization for variable-length generation has been proposed for diffusion language models (LR-DLLM) but not for autoregressive models, where controlling output length could improve generation consistency and reduce over-generation.`
  - `The delayed key-value caching mechanism (dKV-Cache) designed for diffusion language models has not been evaluated on standard autoregressive generation, where it could similarly improve cache efficiency for long-range generation.`
- Supporting sets:
  - `{88fe27bff57a196d31db45855ef71ec2fe417381, 1e4a739236fa6000687b63380e67c7d651924f0f}`
  - `{arxiv:2602.07546, 1e4a739236fa6000687b63380e67c7d651924f0f}`
  - `{773fdb9a909abe5065262c94b873572dc9eb7e82, 1e4a739236fa6000687b63380e67c7d651924f0f}`
- Jaccard pairwise:
  - `0-1 = 0.3333`
  - `0-2 = 0.3333`
  - `1-2 = 0.3333`
- Gap types / origin:
  - `methodological / explicit`
  - `methodological / inferred`
  - `methodological / inferred`

Q2: `federated learning privacy guarantees under heterogeneous data distributions`
- 3 gaps sharing one paper:
  - `Integration of Trusted Execution Environments (TEE) with differential-privacy-enabled secure aggregation for federated learning.`
  - `Privacy amplification by shuffling has not been combined with secure quantized aggregation (ScionFL) or with threshold functional-encryption based secure aggregation (TAPFed).`
  - `One paper asserts that secure aggregation can be performed with essentially zero client-side overhead, while another claims that any secure aggregation of vector-linear functions necessarily incurs a non-trivial randomness cost for each client, implying inherent overhead.`
- Supporting sets:
  - `{705cb221e5cf35a78bc6c2d7c7fe05ff31ff811d, 597913f516dba8ad9f32a2fb78fa35d72e135ca0, arxiv:2210.07376}`
  - `{arxiv:2012.12803, arxiv:2210.07376, 597913f516dba8ad9f32a2fb78fa35d72e135ca0}`
  - `{arxiv:2210.07376, a47357735a96cefbf8416099137292a41a80b8ff}`
- Jaccard pairwise:
  - `0-1 = 0.5000`
  - `0-2 = 0.2500`
  - `1-2 = 0.2500`
- Gap types / origin:
  - `topical / inferred`
  - `methodological / inferred`
  - `contradiction / inferred`

**OVERALL:** READY TO SHIP FOR THE INVESTIGATION, but BUG-P4-04 should be treated as `AC quá thô`, not `BUG 403`
