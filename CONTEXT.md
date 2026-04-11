# CONTEXT.md — Current task

## Assignment

COMP3011 Coursework 2 — Search Engine Tool
University of Leeds · 30% of module mark · Due 8 May 2026

Build a command-line search tool in Python that:
1. Crawls https://quotes.toscrape.com
2. Builds an inverted index of all word occurrences
3. Allows the user to find pages containing search terms

Assessed via a 5-minute video demonstration, a GitHub repository, and a submitted
index file. Target grade: 80–100.

---

### Environment policy

- Use `conda` as the environment manager (Python runtime and activation workflow).
- Keep `requirements.txt` as the dependency source of truth for coursework submission.
- Do not switch to `uv` for this project.

## Corpus definition (important)

The corpus is the **paginated quote listing pages only**:
`/page/1/` through `/page/10/` (approximately 10 pages, ~100 quotes total).

The crawler follows only `/page/N/` links from the root. It does not follow author
profile pages or tag pages. This is a deliberate, justified scope decision:

- The brief asks to crawl "the pages of a website" and index word occurrences.
  The paginated listing pages are the primary content pages of this site.
- Limiting scope makes the field model clean: every crawled page has the same
  structure (quote bodies, authors, tags).
- The crawler is easily extended if a broader scope is required later.

---

## Mandatory CLI commands

| Command           | Behaviour                                                       |
|-------------------|-----------------------------------------------------------------|
| `build`           | Crawl corpus, build index, save to `data/index.json`            |
| `load`            | Load `data/index.json` into memory                              |
| `print <word>`    | Print the inverted index entry for a single term                |
| `find <query>`    | AND search across all query terms; return BM25F-ranked URL list |

### `print` output format (exact)
```
Term: life  (df: 12)
  /page/1/   tf=3  pos=[2, 15, 22]  fields=[quote_body]
  /page/3/   tf=1  pos=[7]          fields=[tag]
```

### `find` output format (exact)
```
Results for "good friends" (2 terms, AND):
  1. https://quotes.toscrape.com/page/4/   score=3.412
  2. https://quotes.toscrape.com/page/7/   score=1.809
```

Zero results triggers the spell corrector (see below).

---

## Feature set

### Core (required by brief)

1. **BFS crawler** with politeness window
   - Minimum 6-second sleep before every HTTP request, unconditionally.
   - Handles non-200 responses, timeouts, and redirect loops gracefully.

2. **Field-aware inverted index**
   - Three fields per page: `quote_body`, `author`, `tag`
   - Each posting stores: `doc_id` (int), `url` (str), per-field `tf` and `positions`
   - Posting lists sorted by `doc_id` ascending (required for DAAT)
   - Positions stored even though `find` uses AND semantics — required by brief spec
     ("statistics e.g. frequency, position, etc")

3. **`build` / `load` persistence**
   - JSON serialisation to `data/index.json`
   - `load` validates file exists and is well-formed JSON; prints clear error otherwise

4. **`print <word>`** — human-readable posting list dump

5. **`find <query>`** — AND semantics, BM25F ranked output

### Novel (distinction features)

6. **BM25F ranking**
   - Single IDF over full corpus; per-field pseudo-TF with independent length
     normalisation; saturation applied once. Parameters: k1=1.5, b_f=0.75 for all
     fields, field weights: quote_body=1.0, author=3.0, tag=2.0.
   - Justified over plain BM25 + post-hoc field boost: IDF computed correctly once.

7. **DAAT AND merge with skip pointers**
   - Posting lists sorted by doc_id; skip pointer every ⌊√N⌋ entries.
   - Used by `find` for all multi-term queries.
   - Micro-benchmark in `tests/test_search.py` demonstrates O(√N) skip vs O(N) scan
     on a synthetic posting list of 10,000 entries. Printed in video demo.

8. **"Did you mean?" spell correction**
   - Levenshtein edit distance, max distance 2, against full index vocabulary.
   - Triggered only on zero results.
   - Returns at most one suggestion per query token.

---

## TDD workflow

Work in this sequence for each feature:

1. Write failing tests in the appropriate test file.
2. Run `pytest` — confirm they fail for the right reason.
3. Implement the feature in `src/`.
4. Run `pytest` — confirm they pass.
5. Run `pytest --cov=src --cov-report=term-missing` — check coverage.
6. Commit: `type(scope): description`

Do not proceed to the next feature until the current one is green and committed.

### Phase progression gates (mandatory)

For each phase in the implementation order:

1. All phase tests must be written before implementation begins.
2. Tests must fail first for the expected reason.
3. Implementation must be production-complete for that phase (no stubs/placeholders).
4. All phase tests must pass.
5. Each test must map to a concrete objective in the assessment criteria.
6. Only then may work proceed to the next phase.

### Objective-achievement rule for tests

Test status alone is not enough. Each phase must include objective evidence mapping:

- Positive-path tests proving expected behaviour.
- Edge/failure-path tests proving robustness and error handling.
- Explicit link from each assessed objective to one or more test assertions.

### Feature implementation order

```
1. crawler.py       - BFS + politeness
2. indexer.py       - field tokeniser + posting schema + index build
3. search.py        - BM25F scorer
4. search.py        - DAAT AND merge + skip pointers
5. search.py        - "Did you mean?" spell corrector
6. main.py          - CLI REPL shell wiring everything together
7. benchmarks       - synthetic timing test for skip pointer comparison
8. benchmarks       - BM25F vs BM25 + post-hoc boost comparison report
```

---

## Benchmarking requirements

Each of the following must be measurable and documented:

| Measurement           | How                                              | Where reported     |
|-----------------------|--------------------------------------------------|--------------------|
| `build` total time    | `time.perf_counter()` wrapping crawl + index     | Printed to stdout  |
| `find` query time     | `time.perf_counter()` per query                  | Printed to stdout  |
| Skip pointer speedup  | Synthetic list of 10,000 postings, scan vs skip  | `test_search.py`   |
| Index file size       | `os.path.getsize()` after `build`                | Printed to stdout  |

### Comparative benchmark requirement (algorithm improvement proof)

In addition to the required benchmarks above, run and report:

- BM25F vs BM25 + post-hoc field boost on a fixed corpus snapshot and fixed query set.
- Include one ranking quality metric (`nDCG@5` or `MRR@5`) and one runtime metric
  (mean per-query milliseconds).
- Report baseline, BM25F result, and delta in a reproducible table for README/video.

### Benchmark reporting format

Use a consistent table with columns:

- `benchmark_name`
- `configuration`
- `result`
- `baseline_result` (comparative cases)
- `delta`
- `units`
- `run_count`

---

## Acceptance criteria checklist

Before the final commit:

- [ ] `build` crawls all 10 paginated pages, writes valid `data/index.json`
- [ ] `load` reads `data/index.json` without error
- [ ] `print life` returns a non-empty posting list
- [ ] `find love` returns at least one URL
- [ ] `find good friends` returns only pages containing both words
- [ ] `find xyznonexistent` triggers "Did you mean?" or "No results found"
- [ ] `find` with no arguments prints usage message, does not crash
- [ ] `load` before `build` prints informative error, does not crash
- [ ] `pytest --cov=src` reports ≥85% line coverage
- [ ] All commits follow `type(scope): description` format
- [ ] `data/index.json` is in `.gitignore`


