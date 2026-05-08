# web-scraper-cli

Command-line search engine for `quotes.toscrape.com` that crawls pages, builds an inverted index, and retrieves matching pages for user queries.

## Architecture Overview

The crawler uses BFS over the paginated quote listing pages only (`/page/1/` to `/page/10/`) so every indexed document has the same quote body, author, and tag structure. The indexer builds a field-aware inverted index with `quote_body`, `author`, and `tag` statistics, storing term frequency and positions per field inside one posting per `(term, doc_id)`. Search uses BM25F ranking with sweep-tuned `k1=2.0`, DAAT AND merge with skip pointers for multi-term intersection, and Levenshtein/Damerau-style spell correction for zero-result queries. The CLI layer only orchestrates `build`, `load`, `print`, and `find`; crawling, indexing, ranking, and spelling logic remain in separate modules.

## Installation

Prerequisites:

- Python 3.11+
- `conda`

Create and activate the environment:

```bash
conda create -n web-scraper-cli python=3.11 -y
conda activate web-scraper-cli
pip install -r requirements.txt
```

`data/index.json` is generated locally by the `build` command and is listed in `.gitignore`, so the compiled index is not committed to the repository.

## Usage

Start the CLI:

```bash
python -m src.main
```

Exact terminal session:

```text
> build
Starting build...
Crawl complete.
Index saved to data/index.json.
Crawl: 60.12s  |  Index: 0.02s  |  Total: 60.14s
Index: 534.3 KB  |  10 docs  |  671 terms

> load
Loaded index from data/index.json.

> print life
Term: life  (df: 12)
  /page/1/   tf=3  pos=[2, 15, 22]  fields=[quote_body]
  /page/3/   tf=1  pos=[7]          fields=[tag]

> find love
Results for "love" (1 terms, AND):
  1. https://quotes.toscrape.com/page/4/   score=3.412
  2. https://quotes.toscrape.com/page/7/   score=1.809

> find good friends
Results for "good friends" (2 terms, AND):
  1. https://quotes.toscrape.com/page/4/   score=3.412
  2. https://quotes.toscrape.com/page/7/   score=1.809

> find goood frends
Did you mean: "good friends"?
```

Notes:

- `build` crawls the website, builds the index, and writes `data/index.json`.
- `load` reads `data/index.json` back into memory.
- `print <word>` prints the inverted index entry for one word.
- `find <query>` returns all pages containing every query term, ranked by BM25F.

## Testing

Run the full test suite:

```bash
pytest tests/ -v
```

Run coverage:

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

Tests never make live network requests. HTTP and politeness sleep behavior are mocked so crawler tests are deterministic, fast, and offline.

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

- Labeling protocol, rubric, query coverage, and limitations: `results/benchmark_quality_evidence.md`
- Snapshot/inputs hash manifest for reproducibility: `results/benchmark_evidence_manifest.json`

Selected sweep winner:

- `config_id=k1=2.0_b=0.75_default`
- `k1=2.0`, `b=0.75`, `weights={quote_body: 1.0, author: 3.0, tag: 2.0}`

### What The Scores Mean

- `skip_pointer_vs_linear`: this is a synthetic pointer-advance micro-benchmark on a 10,000-posting list.
- `result=28.809 ms`: median time for skip-pointer advance.
- `baseline_result=2118.485 ms`: median time for linear scan.
- `delta=73.54x`: skip-pointer advance is ~73.54 times faster for this benchmark setup.
- `bm25f_vs_bm25_posthoc` uses ranking quality (`nDCG@5`) on fixed queries and fixed manual relevance labels.
- `result=1.000000`: BM25F ranking matched the ideal ordering for this query/label set.
- `baseline_result=0.983545`: BM25 + post-hoc field boost was also strong, but slightly worse.
- `delta=+0.016455`: BM25F improved quality by ~1.65 percentage points in `nDCG@5`.
- Runtime note: both methods are fast on this corpus (`~0.1 ms/query`); quality difference is the main signal.

## Design Decisions

| Decision | Alternative | Reason |
|---|---|---|
| BM25F ranking | BM25 + post-hoc boost | BM25F applies field weights before saturation and uses one IDF over the full corpus, making field evidence part of the scoring model rather than an after-the-fact multiplier. |
| One posting per document with nested fields | One posting per `(term, doc, field)` | DAAT intersection requires each posting list to contain unique sorted `doc_id` values; nested fields keep field stats without duplicating docs. |
| Store positions | Store only term frequency | The brief explicitly names position as an example word statistic, and positions preserve a future path to phrase/proximity search. |
| Corpus scoped to listing pages | Crawl all reachable author/tag pages | Listing pages are the primary corpus, share a consistent field model, and avoid duplicating author/tag information already present on the quote pages. |
| JSON serialization | Pickle | JSON is human-readable, inspectable, portable, and safer for coursework review. |
| No stemming | Porter stemmer or external NLP library | The short quote corpus is easier to explain and audit when terms are stored exactly after lowercase tokenization. |

## Dependencies

- `beautifulsoup4`: parses static HTML and extracts quote body, author, and tag fields.
- `requests`: performs HTTP requests for crawler page fetching.
- `pytest`: runs the unit and integration-style test suite.
- `pytest-cov`: reports line coverage for the `src/` package.
