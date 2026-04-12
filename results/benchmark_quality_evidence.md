# Benchmark Quality Evidence

## 1) Evaluation Protocol (Locked)

- Corpus snapshot: `data/index.json` built at `2026-04-11T22:00:40+00:00`
- Retrieval scope: AND semantics (same candidate set for BM25F and baseline)
- Queries: `results/bm25f_queries.json` (10 fixed queries)
- Labels: `results/bm25f_qrels.json` (graded `0..3`)
- Quality metric: `nDCG@5`
- Runtime metric: mean query latency (ms), `run_count=10`
- Scripts/results:
  - `scripts/run_bm25f_comparison.py`
  - `results/bm25f_comparison_results.json`
  - `results/bm25f_comparison_table.md`

## 2) Relevance Labeling Rubric

- `3` = highly relevant: page strongly centered on query intent.
- `2` = relevant: page clearly contains and supports query intent.
- `1` = weakly relevant: contains term(s) but limited semantic support.
- `0` = not relevant / unlabeled.

Label distribution in this snapshot:

- total labels: `26`
- grade `3`: `10`
- grade `2`: `10`
- grade `1`: `6`
- grade `0`: `0` explicitly labeled (unlabeled docs treated as `0`)

## 3) Query Coverage Notes

| query_id | query_text | labeled_docs | intent note |
|---|---|---:|---|
| q1 | life | 3 | broad conceptual term; ranking differences expected |
| q2 | love | 3 | broad conceptual term; multiple plausible pages |
| q3 | truth | 3 | topical term with clearer high-signal pages |
| q4 | good friends | 2 | strict multi-term intent, narrow page set |
| q5 | heart | 2 | narrower topical query |
| q6 | mind | 3 | conceptual query with several valid pages |
| q7 | time | 3 | conceptual query, medium ambiguity |
| q8 | world | 3 | broad term, several related pages |
| q9 | fear | 2 | narrower topical query |
| q10 | friend | 2 | narrow term with small candidate set |

## 4) Why This Is Reasonable Evidence

- Fixed snapshot + fixed query/qrels removes run-to-run drift in quality scoring.
- Graded labels (`1/2/3`) make nDCG@5 more informative than binary relevance alone.
- Per-query and macro outputs are both reported, not only one aggregate number.
- Reproducibility manifest with SHA256 hashes is stored in:
  - `results/benchmark_evidence_manifest.json`

## 5) Known Limits (Important for Video Discussion)

- Single annotator labels can introduce subjectivity.
- Query set is only 10 queries; signal is useful but not exhaustive.
- Many queries already saturate near-perfect ranking, so marginal gains are concentrated in fewer queries.
- Runtime differences are tiny at this corpus size and should be interpreted cautiously.

## 6) Recommended Next Strengthening (Optional)

- Add a second annotation pass (or peer review) for qrels and report disagreements.
- Expand query set with harder multi-term and ambiguous cases.
- Add one secondary quality metric (e.g., `MRR@5`) alongside nDCG@5.
