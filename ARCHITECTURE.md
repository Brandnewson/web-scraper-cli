# ARCHITECTURE.md — Revised search engine architecture

## Project context

COMP3011 CW2 · University of Leeds · Target: 80–100%
Corpus: https://quotes.toscrape.com (paginated listing pages /page/1/ → /page/10/)
See CONTEXT.md for full feature list, TDD workflow, and acceptance criteria.
See REFERENCES.md for formula derivations, algorithm theory, and algorithm comparison.

---

## Corpus scope decision

The crawler indexes **paginated listing pages only** (`/page/N/`). Author profile
pages and tag pages are reachable but are out of scope. Justification:

- Every listing page shares the same structure (quote body + author + tags), giving
  a clean and consistent field model.
- Author pages duplicate author names already captured from listing pages.
- Tag pages contain minimal novel text beyond what listing pages provide.
- The brief says "crawl the pages of a website" — the listing pages are the primary
  content of this site. Scope is clearly stated in the video.

---

## Data structures

### PageData (crawler output)

```python
@dataclass
class PageData:
    url:         str
    doc_id:      int           # assigned sequentially: 0, 1, 2, ...
    quote_texts: list[str]     # all quote body strings on this page
    authors:     list[str]     # all author name strings on this page
    tags:        list[str]     # all tag strings on this page
```

### Posting (index entry per document per term per field)

One `Posting` object exists per (term, document) pair — not per (term, document,
field). All field data for a term in a document is nested inside a single posting.

```python
@dataclass
class FieldStats:
    tf:        int
    positions: list[int]   # 0-indexed token offsets within this field

@dataclass
class Posting:
    doc_id: int
    url:    str
    fields: dict[str, FieldStats]   # keys: "quote_body", "author", "tag"
```

**Why one posting per document (not one per field):**
DAAT AND merge advances pointers through posting lists keyed on doc_id. If the same
doc_id appeared multiple times in a list (once per field), the merge logic would
require deduplication and field aggregation at query time. With nested fields, each
doc_id appears exactly once per term, the merge is clean, and BM25F pseudo-TF
computation (which naturally sums across fields) maps directly onto the data.

### Index schema (index.json)

```json
{
  "_meta": {
    "num_docs":   10,
    "built_at":   "2026-05-01T14:23:00",
    "schema_version": 1,
    "fields": {
      "quote_body": { "avgdl": 18.4, "weight": 1.0, "b": 0.75 },
      "author":     { "avgdl": 2.1,  "weight": 3.0, "b": 0.75 },
      "tag":        { "avgdl": 6.3,  "weight": 2.0, "b": 0.75 }
    },
    "doc_field_lengths": {
      "0": { "quote_body": 22, "author": 2, "tag": 8 },
      "1": { "quote_body": 19, "author": 3, "tag": 5 }
    },
    "doc_urls": {
      "0": "https://quotes.toscrape.com/page/1/",
      "1": "https://quotes.toscrape.com/page/2/"
    }
  },
  "terms": {
    "life": {
      "df": 3,
      "postings": [
        {
          "doc_id": 0,
          "url":    "https://quotes.toscrape.com/page/1/",
          "fields": {
            "quote_body": { "tf": 3, "positions": [2, 15, 22] },
            "tag":        { "tf": 1, "positions": [1] }
          }
        }
      ]
    }
  }
}
```

**Key decisions:**
- `doc_field_lengths` keyed by string doc_id (JSON does not allow int keys).
- `avgdl`, `weight`, and `b` stored in `_meta.fields` — no hardcoded parameters
  at query time; all BM25F parameters are read from the index.
- `schema_version` allows graceful detection of incompatible index formats on `load`.
- Posting lists are sorted by `doc_id` ascending at index build time. This is an
  invariant the DAAT merger depends on.
- Positions are stored per field. Required by brief ("e.g. frequency, position, etc").
  They also future-proof the index for phrase/proximity search without a rebuild.

---

## Module contracts

### Module boundaries and ownership (locked)

This file is the single source of truth for module responsibilities:

- `crawler.py`: network retrieval, BFS traversal, politeness enforcement, and HTML
  extraction into `PageData`.
- `indexer.py`: tokenisation, term statistics, positional data, posting-list
  construction, and index `_meta` computation.
- `search.py`: retrieval and ranking algorithms only (BM25F, DAAT+skips, spelling).
- `main.py`: CLI orchestration, user I/O formatting, and command dispatch only.

No module may duplicate another module's core logic.

### crawler.py

```
Input:  seed_url: str, max_pages: int = 10
Output: list[PageData]

Behaviour:
  - BFS over /page/N/ links only
  - Unconditional sleep of >= 6 seconds before every HTTP request
    (including after errors, non-200 responses, and redirects)
  - Catches requests.RequestException, logs warning, continues
  - Assigns doc_id sequentially in crawl order
  - Returns pages in crawl order
```

Politeness is enforced at the lowest level — the private `_fetch(url)` method sleeps
before every call, not just before successful parses. This ensures compliance even
when a request returns a 404 or triggers a redirect.

### indexer.py

```
Input:  pages: list[PageData]
Output: dict (the full index structure matching the schema above)

Behaviour:
  - Tokenise each field independently: lowercase, split on r'[^a-z0-9]+'
  - Assign positions as 0-indexed offsets within the field token list
  - Build posting lists sorted by doc_id
  - Compute per-field doc lengths and avgdl, store in _meta
  - Compute df per term across all documents
```

No stemming, no stopword removal. Justified: short quote texts; stemming would merge
"life" and "lives" silently, which is harder to demo and audit.

### search.py — three components

#### BM25F scorer

```python
def score_bm25f(term: str, doc_id: int, index: dict) -> float:
    """
    Compute BM25F score for a single (term, document) pair.
    Reads all parameters from index["_meta"]["fields"].
    """
```

Formula (see REFERENCES.md §1 for full derivation):
```
pseudo_tf = Σ_f  weight_f × tf(t,d,f)
                 / (1 - b_f + b_f × (dl(d,f) / avgdl_f))

score = IDF(t) × pseudo_tf × (k1 + 1) / (pseudo_tf + k1)

IDF(t) = log( (N - df(t) + 0.5) / (df(t) + 0.5) + 1 )
```

k1 is a module-level constant (default 1.5). All other parameters come from
`index["_meta"]`. This makes the scorer fully driven by the stored index — no
hardcoded field weights at query time.

#### DAAT AND merger with skip pointers

```python
def build_skip_pointers(postings: list[Posting]) -> list[tuple[int, int]]:
    """
    Returns list of (doc_id, list_index) pairs spaced sqrt(len(postings)) apart.
    """

def advance_with_skips(
    postings: list[Posting],
    skips:    list[tuple[int, int]],
    ptr:      int,
    target:   int
) -> int:
    """
    Advance pointer ptr in postings until postings[ptr].doc_id >= target.
    Uses skip pointers to reduce comparisons. Returns new pointer index.
    Raises StopIteration if pointer exhausts the list.
    """

def daat_and_merge(
    posting_lists: list[list[Posting]],
    skip_lists:    list[list[tuple[int, int]]]
) -> list[int]:
    """
    Returns list of doc_ids present in ALL posting lists (AND semantics).
    Posting lists must be sorted by doc_id ascending.
    Input lists sorted by length ascending before merge begins.
    """
```

#### "Did you mean?" spell corrector

```python
def levenshtein(s1: str, s2: str) -> int:
    """Standard DP edit distance. O(m×n) time and O(n) space."""

def suggest(token: str, vocabulary: set[str], max_dist: int = 2) -> str | None:
    """
    Return the vocabulary term with smallest edit distance to token,
    if that distance <= max_dist. Return None if no suggestion found.
    """

def did_you_mean(query_tokens: list[str], index: dict) -> str | None:
    """
    For each query token with no index match, call suggest().
    Return a formatted suggestion string or None.
    """
```

### main.py

Persistent REPL. Pseudocode:

```
index = None

loop:
  input = read line

  "build":
    t0 = perf_counter()
    pages = crawler.crawl(SEED_URL)
    index = indexer.build(pages)
    save(index, "data/index.json")
    print(f"Built in {perf_counter()-t0:.2f}s  |  {file_size} KB  |  {N} docs  |  {V} terms")

  "load":
    validate file exists and is valid JSON
    index = load("data/index.json")
    print confirmation

  "print <word>":
    if word not in index: print "Term not found"
    else: pretty-print posting list (format defined in CONTEXT.md)

  "find <terms...>":
    t0 = perf_counter()
    results = search(terms, index)   # DAAT + BM25F
    if not results:
      suggestion = did_you_mean(terms, index)
      print suggestion or "No results found"
    else:
      for rank, (url, score) in enumerate(results, 1):
        print(f"  {rank}. {url}   score={score:.3f}")
    print(f"  ({perf_counter()-t0:.4f}s)")

  "quit" / "exit": break
```

### CLI command contract (exact behaviour)

Commands are case-sensitive and space-delimited.

- `build`
  - Runs crawl -> index -> save (`data/index.json`) in one command.
  - Prints benchmark evidence for crawl time, index time, total build time, and index
    file size/docs/terms summary.
- `load`
  - Loads `data/index.json` into memory.
  - On missing/invalid JSON, prints a clear human-readable error and keeps the REPL
    running.
- `print <word>`
  - If term exists, output must match the exact format in `CONTEXT.md`.
  - If term does not exist, print `Term not found`.
  - If argument is missing, print usage hint and do not crash.
- `find <query>`
  - Uses AND semantics over all query tokens and ranks with BM25F.
  - If matches exist, output must match the exact format in `CONTEXT.md`.
  - If no matches exist, print spell suggestion (if available) or `No results found`.
  - Print per-query timing after execution.
- `quit` / `exit`
  - Exit REPL without traceback.

---

## Testing plan

### test_crawler.py

| Test | Description |
|------|-------------|
| `test_bfs_visits_all_pages` | Mock 10 pages, assert 10 PageData returned in order |
| `test_politeness_on_success` | Assert sleep called before each successful request |
| `test_politeness_on_error` | Assert sleep called even when request raises exception |
| `test_politeness_on_404` | Assert sleep called before request that returns 404 |
| `test_skips_non_listing_pages` | Mock a page linking to /author/X/, assert not followed |
| `test_stops_at_max_pages` | With max_pages=3, assert only 3 pages crawled |
| `test_handles_timeout` | requests.Timeout → page skipped, crawl continues |
| `test_extracts_fields_correctly` | Known HTML → expected quote/author/tag lists |
| `test_doc_id_sequential` | doc_ids are 0, 1, 2, ... in crawl order |

### test_indexer.py

| Test | Description |
|------|-------------|
| `test_posting_schema` | Term appears in two fields → single posting with both fields |
| `test_positions_stored` | Known input → positions match expected token offsets |
| `test_posting_lists_sorted` | All posting lists in output are sorted by doc_id |
| `test_df_correct` | Term in 3 of 5 docs → df=3 |
| `test_avgdl_correct` | Known field lengths → avgdl computed correctly |
| `test_doc_field_lengths` | _meta.doc_field_lengths matches per-doc field token counts |
| `test_case_insensitive` | "Life" and "life" are the same term |
| `test_single_page_corpus` | Edge case: only one page indexed |

### test_search.py

| Test | Description |
|------|-------------|
| `test_bm25f_known_value` | Hand-computed score for known posting → assert within 1e-6 |
| `test_bm25f_author_boost` | Author match scores higher than quote_body match (same tf) |
| `test_bm25f_length_penalty` | Long doc scores lower than short doc with same tf |
| `test_daat_single_term` | Single-term find → all docs with that term returned |
| `test_daat_multi_term_and` | Two terms → only docs with both returned |
| `test_daat_no_results` | Disjoint term sets → empty result |
| `test_skip_pointer_build` | 100-entry list → skip every 10 entries |
| `test_skip_pointer_advance` | Advance to target near end → pointer lands correctly |
| `test_skip_pointer_vs_linear` | 10,000-entry synthetic list → skip faster than scan |
| `test_levenshtein_exact` | distance("cat","cat") == 0 |
| `test_levenshtein_one_edit` | distance("cat","car") == 1 |
| `test_levenshtein_transpose` | distance("teh","the") == 1 |
| `test_suggest_finds_close` | "environmnt" → "environment" |
| `test_suggest_no_match` | "xyzxyzxyz" → None |
| `test_suggest_max_dist` | distance 3 term not returned |
| `test_did_you_mean_format` | Zero results → formatted suggestion string |
| `test_find_ranked_by_score` | Higher-scoring doc appears first in results |

---

### Objective evidence mapping (required for phase sign-off)

Before any implementation phase is marked complete:

- Each assessed objective must have at least one positive-path and one edge/failure
  test that explicitly proves the objective.
- Tests passing is necessary but not sufficient; each test must be mapped to an
  objective in the assessment criteria.
- Coverage supports confidence but never replaces objective-mapped assertions.

### Phase progression gates (must pass before moving on)

For each phase in the fixed implementation order from `CONTEXT.md`:

1. Write all planned tests for that phase first.
2. Run tests and confirm failures are for the expected reason.
3. Implement full production behaviour for that phase (no stubs/placeholders).
4. Re-run tests until all phase tests pass.
5. Confirm objective-evidence mapping is complete for the phase.
6. Only then move to the next phase.

## Benchmarking

### Build-time benchmark (printed during `build`)
```
Crawl:    42.3s  (7 pages × 6.0s politeness + parse time)
Index:    0.04s
Total:    42.34s
Index:    87 KB  |  10 docs  |  1,247 terms
```

### Query-time benchmark (printed after each `find`)
```
Results for "love" (1 term, AND):
  1. /page/4/   score=3.412
  2. /page/7/   score=1.809
  (0.0003s)
```

### Comparative ranking ablation (BM25F vs BM25 + post-hoc boost)

Purpose: demonstrate measurable benefit of the chosen BM25F design against a simpler
baseline scorer.

Protocol (locked):

- Corpus snapshot: fixed `/page/1/` to `/page/10/` listing-page corpus captured once
  and reused by both scorers.
- Query set: fixed set of at least 10 queries (single-term and multi-term).
- Relevance labels: manual binary labels (`relevant`/`not_relevant`) for top-k output
  per query, created once and reused.
- Baseline scorer: BM25 with post-hoc field boost using same field weights.
- Comparison scorer: BM25F as defined in this architecture.
- Runtime measurement: mean per-query scorer time over identical candidate docs.
- Quality measurement: nDCG@5 (or MRR@5 if labels are sparse).
- Reporting: per-query and macro-average table with baseline, BM25F, and delta.

### Skip pointer micro-benchmark (in test_search.py)
```python
def test_skip_pointer_vs_linear_scan():
    N = 10_000
    postings = [Posting(doc_id=i*2, url=f"/page/{i}/", fields={}) for i in range(N)]
    skips    = build_skip_pointers(postings)
    target   = N*2 - 2    # near end

    t0 = time.perf_counter()
    for _ in range(1000): advance_linear(postings, 0, target)
    linear_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    for _ in range(1000): advance_with_skips(postings, skips, 0, target)
    skip_ms = (time.perf_counter() - t0) * 1000

    print(f"\nLinear: {linear_ms:.1f}ms  |  Skip: {skip_ms:.1f}ms  |  Speedup: {linear_ms/skip_ms:.1f}x")
    assert skip_ms < linear_ms
```

This benchmark runs as part of the test suite, prints timing, and is shown in the
video to satisfy the 80–100 band requirement for "complexity analysis and benchmarking."

---

### Benchmark evidence output format (README/video)

All benchmark evidence should be reported in a compact table with:

- `benchmark_name`
- `configuration`
- `result`
- `baseline_result` (comparative benchmarks only)
- `delta`
- `units`
- `run_count`

## Design decisions log

| Decision | Alternative | Reason |
|---|---|---|
| One posting per (term, doc), fields nested | One per (term, doc, field) | DAAT requires unique doc_id per posting. Nested fields map cleanly to BM25F pseudo-TF sum. |
| BM25F | BM25 + post-hoc boost | IDF computed once over full corpus. Weighting before saturation is theoretically correct. See REFERENCES.md §1. |
| Positions stored, phrase search not implemented | Positions omitted | Brief explicitly lists "position" as an example statistic. Positions cost O(token_count) space, future-proof the index. |
| Corpus = paginated listing pages only | Crawl all reachable pages | Consistent field structure across all documents. Clean scope justification for video. |
| Politeness at `_fetch()` level, unconditional | Sleep only on success | Ensures compliance even on errors and non-200s. A failed request still consumes a server slot. |
| JSON serialisation | Pickle | Human-readable, inspectable, secure. At 100 pages the file is <200 KB — performance is not a constraint. |
| No stemming | NLTK PorterStemmer | Short quote corpus. Stemming merges terms silently and makes demo harder to audit. |
| Levenshtein max_dist=2 | Soundex, SymSpell | No external dependency. Sufficient for single-key and two-key typos. Vocabulary is O(1,000–2,000) terms. |
| k1=1.5, b=0.75 stored in _meta | Hardcoded at query time | Parameters are index properties, not query properties. Storing them enables parameter tuning without code changes. |
