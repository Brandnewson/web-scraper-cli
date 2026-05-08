# GenAI Log

Dates below are repository-evidence dates from `git log`, not original chat timestamps.
The original AI interaction timestamps were not recorded in this repository.

## Session 4

Date: 2026-04-11 (repo evidence: initial architecture and implementation commits)

What I asked: Submitted the architecture document to four LLMs (Claude, ChatGPT, DeepSeek, Gemini) and asked each to critique it.

What was generated: Four independent critiques. The most substantive shared finding was that excluding positional data from postings was a brief compliance risk because the spec explicitly names "position" as an example statistic. ChatGPT additionally flagged that one posting per (term, document, field) would break DAAT because the same doc_id would appear multiple times in a posting list.

What I changed / rejected: Adopted both fixes. Positions are now stored per field. The posting schema was redesigned to nest all field data inside one posting per (term, doc_id). The ChatGPT suggestion about the posting shape was correct but the reasoning it gave was incomplete because it said "for efficiency" but the real reason is that DAAT requires unique doc_ids per posting list. I corrected the justification before adopting the fix.

Reflection: Using four models as a critique panel rather than one produced higher-quality architectural review than any single model would have. This is an application of the LLM-as-judge pattern (Zheng et al., 2023). The disagreements between models were as informative as the agreements.

## Session 5

Date: 2026-04-11 (repo evidence: BM25F scorer commit at 21:02:57 +0100)

What I asked: Implement score_bm25f in search.py following the ARCHITECTURE.md specification. Then write test_bm25f_known_value with a hand-computed expected value to verify correctness.

What was generated: A working BM25F implementation and the test. However, the AI initially hardcoded k1=1.5 directly in the formula rather than as a module-level constant, and also hardcoded the field weights (1.0, 3.0, 2.0) at query time rather than reading them from index["_meta"]["fields"].

What I changed / rejected: Extracted k1 as a module-level constant K1. Changed field weight and b lookup to read from index metadata at query time. This matters because the parameter sweep needs to vary weights without changing code. If they were hardcoded the sweep results would be meaningless.

Reflection: The AI understood the BM25F formula correctly but did not internalise the architectural constraint that parameters are index properties, not query properties. This was a case where knowing the design intent was more important than knowing the algorithm.

## Session 6

Date: 2026-04-11 (repo evidence: DAAT/skip commits at 21:18:08 and 22:13:52 +0100)

What I asked: Implement daat_and_merge and build_skip_pointers with a synthetic benchmark proving skip-pointer advance is faster than linear scan on 10,000 entries.

What was generated: The DAAT implementation and test_skip_pointer_vs_linear. The initial advance_with_skips used binary search on the skip list, which added unnecessary complexity given that skip lists are already sparse.

What I changed / rejected: Replaced the binary search with a linear scan over the skip list (which is O(sqrt(N)) entries, not O(N)). The linear scan over a sqrt(N)-length skip list followed by a short linear scan to the exact target is simpler to reason about and produces the same asymptotic behaviour. The benchmark confirmed 73x speedup on the synthetic list.

Reflection: The AI defaulted to binary search because "skip pointer + binary search" appears in textbooks. But binary search on a sqrt(N)-length list gives O(log sqrt(N)) = O(1/2 log N) comparisons, while linear scan over sqrt(N) entries gives O(sqrt(N)). For N=10,000, log N is about 13 vs sqrt(N) is about 100, so binary search is actually faster in theory. However, the constant factor and the subsequent linear scan to the exact target make the difference negligible in practice. I kept the linear version for readability and the benchmark still shows the expected speedup.

## Session 7

Date: 2026-04-12 (repo evidence: parameter sweep/validation scripts commit at 20:54:17 +0100)

What I asked: Run a 48-configuration parameter sweep across k1 in [1.2, 1.5, 1.8, 2.0], b in [0.5, 0.75, 0.9], and four field weight presets. Select the best configuration by macro nDCG@5, then runtime as tie-break.

What was generated: scripts/run_parameter_sweep.py and the full sweep results in results/parameter_sweep_results.json. The sweep selected k1=2.0, b=0.75, default weights (quote_body=1.0, author=3.0, tag=2.0) as the winning configuration with macro nDCG@5=1.0.

What I changed / rejected: Updated K1 in search.py from 1.5 to 2.0 to reflect the sweep finding. I verified the sweep selection rule (maximize nDCG@5, tie-break on lower runtime, then lexicographic config_id) was deterministic before accepting it. I also read the benchmark_quality_evidence.md to understand the known limitations: single annotator, 10 queries, corpus saturation. These limitations are documented and acknowledged.

Reflection: The sweep was generated largely by AI but I evaluated its output rather than accepting it blindly. The nDCG@5=1.0 result looks suspiciously perfect because it reflects that the corpus is small and queries are broad, not that BM25F is a perfect ranker. Documenting this honestly is more credible than presenting the number without context.
