# web-scraper-cli

## Benchmark Evidence

| benchmark_name | configuration | result | baseline_result | delta | units | run_count |
|---|---|---|---|---|---|---|
| skip_pointer_vs_linear | N=10000,target_near_tail,iterations=1000,metric=median_over_5 | 28.809 | 2118.485 | 73.54x | ms | 5 |
| bm25f_vs_bm25_posthoc | index=data/index.json,queries=10,run_count=10,metric=nDCG@5,runtime_metric=mean_query_ms,bm25f_mean_ms=0.144,baseline_mean_ms=0.109 | 1.000000 | 0.983545 | +0.016455 | nDCG@5 | 10 |

Recorded from:

```bash
pytest -q -s tests/test_search.py::test_skip_pointer_vs_linear
python scripts/run_parameter_sweep.py --index data/index.json --queries results/bm25f_queries.json --qrels results/bm25f_qrels.json --out-json results/parameter_sweep_results.json --out-md results/parameter_sweep_table.md --out-best results/best_bm25f_config.json --run-count 10
python scripts/run_bm25f_comparison.py --index data/index.json --queries results/bm25f_queries.json --qrels results/bm25f_qrels.json --out-json results/bm25f_comparison_results.json --out-md results/bm25f_comparison_table.md
python scripts/validate_submission.py --live-smoke
```

Benchmark quality evidence pack:

- Labeling protocol, rubric, query coverage, and limitations:
  - `results/benchmark_quality_evidence.md`
- Snapshot/inputs hash manifest (reproducibility):
  - `results/benchmark_evidence_manifest.json`

Selected sweep winner:

- `config_id=k1=2.0_b=0.75_default`
- `k1=2.0`, `b=0.75`, `weights={quote_body: 1.0, author: 3.0, tag: 2.0}`

## What The Scores Mean

- `skip_pointer_vs_linear`: this is a synthetic pointer-advance micro-benchmark on a 10,000-posting list.
- `result=28.809 ms`: median time for skip-pointer advance.
- `baseline_result=2118.485 ms`: median time for linear scan.
- `delta=73.54x`: skip-pointer advance is ~73.54 times faster for this benchmark setup.
- `bm25f_vs_bm25_posthoc` uses ranking quality (`nDCG@5`) on fixed queries and fixed manual relevance labels.
- `result=1.000000`: BM25F ranking matched the ideal ordering for this query/label set.
- `baseline_result=0.983545`: BM25 + post-hoc field boost was also strong, but slightly worse.
- `delta=+0.016455`: BM25F improved quality by ~1.65 percentage points in `nDCG@5`.
- Runtime note: both methods are fast on this corpus (`~0.1 ms/query`); quality difference is the main signal.

## What To Investigate Next (Parameter Sweeps)

- **Field weights** (`quote_body`, `author`, `tag`):
  - Try alternatives like `author=2.0` or `tag=1.5` and re-run comparison.
  - Goal: confirm whether current boosts over-favor metadata fields.
- **BM25F saturation (`k1`)**:
  - Test values in `[1.2, 1.5, 1.8, 2.0]`.
  - Higher `k1` increases impact of repeated term frequency.
- **Length normalization (`b` per field)**:
  - Test `b` in `[0.5, 0.75, 0.9]` globally or per-field.
  - Higher `b` penalizes longer fields more strongly.
- **Evaluation robustness**:
  - Expand query set and qrels (more hard multi-term queries).
  - Re-check whether BM25F improvements persist beyond this current 10-query snapshot.
- **Runtime stability**:
  - Increase `run_count` (e.g., 30 or 50) to reduce timing noise when comparing near-equal runtimes.
