# BM25F vs BM25+Post-Hoc Comparison

## Benchmark Row

| benchmark_name | configuration | result | baseline_result | delta | units | run_count |
|---|---|---|---|---|---|---|
| bm25f_vs_bm25_posthoc | index=data\index.json,queries=10,run_count=10,metric=nDCG@5,runtime_metric=mean_query_ms,bm25f_mean_ms=0.144,baseline_mean_ms=0.109 | 1.000000 | 0.983545 | +0.016455 | nDCG@5 | 10 |

## Macro Averages

| metric | bm25f | baseline | delta |
|---|---|---|---|
| nDCG@5 | 1.000000 | 0.983545 | +0.016455 |
| mean_query_ms | 0.143964 | 0.109022 | +0.034942 |

## Per Query

| query_id | query_text | bm25f_ndcg_at_5 | baseline_ndcg_at_5 | delta_ndcg_at_5 | bm25f_mean_query_ms | baseline_mean_query_ms |
|---|---|---|---|---|---|---|
| q1 | life | 1.000000 | 0.842828 | +0.157172 | 0.147840 | 0.161100 |
| q2 | love | 1.000000 | 0.992620 | +0.007380 | 0.588270 | 0.290480 |
| q3 | truth | 1.000000 | 1.000000 | +0.000000 | 0.090670 | 0.109620 |
| q4 | good friends | 1.000000 | 1.000000 | +0.000000 | 0.086310 | 0.080170 |
| q5 | heart | 1.000000 | 1.000000 | +0.000000 | 0.086020 | 0.071260 |
| q6 | mind | 1.000000 | 1.000000 | +0.000000 | 0.112600 | 0.116370 |
| q7 | time | 1.000000 | 1.000000 | +0.000000 | 0.055870 | 0.063100 |
| q8 | world | 1.000000 | 1.000000 | +0.000000 | 0.219180 | 0.139260 |
| q9 | fear | 1.000000 | 1.000000 | +0.000000 | 0.026130 | 0.028220 |
| q10 | friend | 1.000000 | 1.000000 | +0.000000 | 0.026750 | 0.030640 |
