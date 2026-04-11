# BM25F vs BM25+Post-Hoc Comparison

## Benchmark Row

| benchmark_name | configuration | result | baseline_result | delta | units | run_count |
|---|---|---|---|---|---|---|
| bm25f_vs_bm25_posthoc | index=data\index.json,queries=10,run_count=10,metric=nDCG@5,runtime_metric=mean_query_ms,bm25f_mean_ms=0.069,baseline_mean_ms=0.075 | 1.000000 | 0.983545 | +0.016455 | nDCG@5 | 10 |

## Macro Averages

| metric | bm25f | baseline | delta |
|---|---|---|---|
| nDCG@5 | 1.000000 | 0.983545 | +0.016455 |
| mean_query_ms | 0.069135 | 0.074668 | -0.005533 |

## Per Query

| query_id | query_text | bm25f_ndcg_at_5 | baseline_ndcg_at_5 | delta_ndcg_at_5 | bm25f_mean_query_ms | baseline_mean_query_ms |
|---|---|---|---|---|---|---|
| q1 | life | 1.000000 | 0.842828 | +0.157172 | 0.120570 | 0.124270 |
| q2 | love | 1.000000 | 0.992620 | +0.007380 | 0.109140 | 0.120040 |
| q3 | truth | 1.000000 | 1.000000 | +0.000000 | 0.053590 | 0.062800 |
| q4 | good friends | 1.000000 | 1.000000 | +0.000000 | 0.069460 | 0.067190 |
| q5 | heart | 1.000000 | 1.000000 | +0.000000 | 0.045420 | 0.043080 |
| q6 | mind | 1.000000 | 1.000000 | +0.000000 | 0.063800 | 0.061470 |
| q7 | time | 1.000000 | 1.000000 | +0.000000 | 0.066530 | 0.081080 |
| q8 | world | 1.000000 | 1.000000 | +0.000000 | 0.077030 | 0.094230 |
| q9 | fear | 1.000000 | 1.000000 | +0.000000 | 0.041530 | 0.048320 |
| q10 | friend | 1.000000 | 1.000000 | +0.000000 | 0.044280 | 0.044200 |
