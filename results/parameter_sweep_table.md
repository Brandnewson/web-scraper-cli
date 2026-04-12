# BM25F Parameter Sweep Results

## Best Configuration

- `config_id`: `k1=2.0_b=0.75_default`
- `k1`: `2.0`
- `b`: `0.75`
- `weights`: `{'quote_body': 1.0, 'author': 3.0, 'tag': 2.0}`
- `selection_rule`: maximize `macro_ndcg_at_5`, tie-break on lower `macro_mean_query_ms`, then lexicographic `config_id`

## Ranked Configurations

| rank | config_id | k1 | b | weights | macro_ndcg_at_5 | macro_mean_query_ms |
|---|---|---|---|---|---|---|
| 1 | k1=2.0_b=0.75_default | 2.0 | 0.75 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.049615 |
| 2 | k1=1.2_b=0.75_metadata_heavy | 1.2 | 0.75 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.049847 |
| 3 | k1=1.2_b=0.9_default | 1.2 | 0.9 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.052282 |
| 4 | k1=1.5_b=0.9_default | 1.5 | 0.9 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.052326 |
| 5 | k1=2.0_b=0.9_metadata_heavy | 2.0 | 0.9 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.053190 |
| 6 | k1=2.0_b=0.75_metadata_heavy | 2.0 | 0.75 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.057133 |
| 7 | k1=1.2_b=0.9_metadata_heavy | 1.2 | 0.9 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.058054 |
| 8 | k1=2.0_b=0.9_default | 2.0 | 0.9 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.061114 |
| 9 | k1=1.5_b=0.75_metadata_heavy | 1.5 | 0.75 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.061150 |
| 10 | k1=1.5_b=0.75_default | 1.5 | 0.75 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.065599 |
| 11 | k1=1.2_b=0.75_default | 1.2 | 0.75 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.074624 |
| 12 | k1=1.8_b=0.9_metadata_heavy | 1.8 | 0.9 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.075074 |
| 13 | k1=1.8_b=0.75_metadata_heavy | 1.8 | 0.75 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.075084 |
| 14 | k1=1.8_b=0.75_default | 1.8 | 0.75 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.087748 |
| 15 | k1=1.8_b=0.9_default | 1.8 | 0.9 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 1.000000 | 0.108986 |
| 16 | k1=1.5_b=0.9_metadata_heavy | 1.5 | 0.9 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 1.000000 | 0.179369 |
| 17 | k1=2.0_b=0.9_balanced | 2.0 | 0.9 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.981923 | 0.052650 |
| 18 | k1=1.5_b=0.9_balanced | 1.5 | 0.9 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.981923 | 0.056072 |
| 19 | k1=1.8_b=0.9_balanced | 1.8 | 0.9 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.981923 | 0.085747 |
| 20 | k1=1.2_b=0.9_balanced | 1.2 | 0.9 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.981923 | 0.094448 |
| 21 | k1=1.5_b=0.5_default | 1.5 | 0.5 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 0.981495 | 0.061092 |
| 22 | k1=1.2_b=0.5_metadata_heavy | 1.2 | 0.5 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 0.981495 | 0.061791 |
| 23 | k1=2.0_b=0.5_metadata_heavy | 2.0 | 0.5 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 0.981495 | 0.061831 |
| 24 | k1=2.0_b=0.5_default | 2.0 | 0.5 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 0.981495 | 0.072527 |
| 25 | k1=1.2_b=0.5_default | 1.2 | 0.5 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 0.981495 | 0.075309 |
| 26 | k1=1.5_b=0.5_metadata_heavy | 1.5 | 0.5 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 0.981495 | 0.076321 |
| 27 | k1=1.8_b=0.5_metadata_heavy | 1.8 | 0.5 | {'quote_body': 1.0, 'author': 3.5, 'tag': 2.5} | 0.981495 | 0.116498 |
| 28 | k1=1.8_b=0.5_default | 1.8 | 0.5 | {'quote_body': 1.0, 'author': 3.0, 'tag': 2.0} | 0.981495 | 0.128477 |
| 29 | k1=1.2_b=0.5_balanced | 1.2 | 0.5 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.967682 | 0.067647 |
| 30 | k1=1.5_b=0.5_balanced | 1.5 | 0.5 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.967682 | 0.072026 |
| 31 | k1=2.0_b=0.5_balanced | 2.0 | 0.5 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.967682 | 0.074803 |
| 32 | k1=1.8_b=0.5_balanced | 1.8 | 0.5 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.967682 | 0.173409 |
| 33 | k1=1.2_b=0.75_balanced | 1.2 | 0.75 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.966944 | 0.049015 |
| 34 | k1=2.0_b=0.75_balanced | 2.0 | 0.75 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.966944 | 0.050346 |
| 35 | k1=1.8_b=0.75_balanced | 1.8 | 0.75 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.966944 | 0.051468 |
| 36 | k1=1.5_b=0.75_balanced | 1.5 | 0.75 | {'quote_body': 1.0, 'author': 2.0, 'tag': 1.5} | 0.966944 | 0.098987 |
| 37 | k1=1.5_b=0.75_body_heavy | 1.5 | 0.75 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.957842 | 0.051526 |
| 38 | k1=1.2_b=0.75_body_heavy | 1.2 | 0.75 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.957842 | 0.059393 |
| 39 | k1=2.0_b=0.75_body_heavy | 2.0 | 0.75 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.957842 | 0.069485 |
| 40 | k1=1.8_b=0.75_body_heavy | 1.8 | 0.75 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.957842 | 0.087302 |
| 41 | k1=1.8_b=0.9_body_heavy | 1.8 | 0.9 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.945802 | 0.057027 |
| 42 | k1=2.0_b=0.9_body_heavy | 2.0 | 0.9 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.945802 | 0.068257 |
| 43 | k1=1.2_b=0.9_body_heavy | 1.2 | 0.9 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.945802 | 0.075922 |
| 44 | k1=1.5_b=0.9_body_heavy | 1.5 | 0.9 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.945802 | 0.085782 |
| 45 | k1=1.2_b=0.5_body_heavy | 1.2 | 0.5 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.941658 | 0.062032 |
| 46 | k1=1.5_b=0.5_body_heavy | 1.5 | 0.5 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.941658 | 0.064843 |
| 47 | k1=2.0_b=0.5_body_heavy | 2.0 | 0.5 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.941658 | 0.070311 |
| 48 | k1=1.8_b=0.5_body_heavy | 1.8 | 0.5 | {'quote_body': 1.5, 'author': 2.0, 'tag': 1.0} | 0.941658 | 0.121419 |
