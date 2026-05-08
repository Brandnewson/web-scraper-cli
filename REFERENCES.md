# REFERENCES.md — Background material

This file contains background reading, formulae, and notes that Codex should
understand but does not need to act on directly. It informs design decisions
documented in ARCHITECTURE.md.

---

## External Resources and GenAI Declaration

### External resources and libraries

- `quotes.toscrape.com`: target coursework website and corpus.
- `requests` documentation: used for HTTP request handling and timeout behavior.
- `beautifulsoup4` documentation: used for HTML parsing and CSS selector extraction.
- `pytest` documentation: used for the test suite and fixtures.
- `pytest-cov` documentation: used for coverage reporting.
- Manning, Raghavan, and Schuetze, *Introduction to Information Retrieval*: used for
  inverted index, posting list, DAAT, and skip pointer background.
- Robertson and Zaragoza BM25/BM25F material: used for ranking formula design and
  comparison against TF-IDF/BM25 baselines.

### GenAI tools declared

- ChatGPT: architecture review, implementation planning, debugging, and documentation
  drafting support.
- Claude: architecture critique, explanation refinement, and video-script planning.
- DeepSeek: independent architecture critique and alternative design review.
- Kimi: independent architecture critique and alternative design review.

GenAI output was not accepted uncritically. Decisions adopted from model suggestions
were checked against the coursework brief, repository tests, and IR references.

---

## 1. BM25 and BM25F

### BM25 origin
BM25 (Best Match 25) emerged from the Okapi research project at City University
London in the 1990s. Robertson et al. (1994, 2009) describe the probabilistic
relevance framework underlying it. It is the default ranking function in
Elasticsearch and the baseline for most modern IR benchmarks.

### BM25 formula
```
score(t, d) = IDF(t) × [ tf(t,d) × (k1 + 1) ]
                        / [ tf(t,d) + k1 × (1 - b + b × (|d| / avgdl)) ]

IDF(t) = log( (N - df(t) + 0.5) / (df(t) + 0.5) + 1 )
```
- k1 ∈ [1.2, 2.0]: controls TF saturation. Default 1.5.
- b ∈ [0, 1]: controls length normalisation. Default 0.75.
- N: total documents. df(t): docs containing term t. avgdl: mean doc length.

### Why TF saturates in BM25 but not TF-IDF
In TF-IDF, raw tf means a document mentioning a term 20 times scores 20× a document
mentioning it once. BM25 applies a hyperbolic saturation: as tf → ∞, the TF component
approaches (k1 + 1), a finite ceiling. This reflects the real-world intuition that
after ~5 mentions you are confident the document is about the topic.

### BM25F formula
BM25F (Zaragoza et al., 2004) extends BM25 to multi-field documents. Key insight:
do NOT score each field independently and sum results — this computes IDF separately
per field, which is statistically wrong. Instead, compute a single pseudo-TF across
fields first, then apply IDF and saturation once.

```
pseudo_tf(t, d) = Σ_f  wf × tf(t, d, f)
                       / (1 - b_f + b_f × (dl(d,f) / avgdl_f))

BM25F(t, d) = IDF(t) × pseudo_tf(t, d) × (k1 + 1)
                        / (pseudo_tf(t, d) + k1)
```
- wf: field weight (author=3.0, tag=2.0, quote_body=1.0 in this project)
- b_f: per-field length normalisation (0.75 for all fields here)
- dl(d, f): token count of field f in document d
- avgdl_f: mean token count of field f across all documents

### Reference
- Robertson, S. & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25
  and Beyond. Foundations and Trends in Information Retrieval, 3(4), 333–389.
- Zaragoza, H. et al. (2004). Microsoft Cambridge at TREC-13: Web and HARD tracks.
  Proceedings of TREC 2004. (Introduces BM25F.)

---

## 2. DAAT and skip pointers

### Document-at-a-time (DAAT) AND merge
Given k sorted posting lists (sorted by doc_id), DAAT finds their intersection
without loading all lists into memory simultaneously:

```
1. Maintain one pointer per posting list, all starting at index 0.
2. Let target = the doc_id at the first pointer (shortest list).
3. For each other pointer:
   a. Advance it (using skip pointers) until its current doc_id >= target.
   b. If it overshoots, set target = new doc_id, restart from step 2.
4. If all pointers agree on the same doc_id, emit it as a match and advance all.
5. Stop when any pointer exhausts its list.
```

Sorting lists by length ascending (shortest first) minimises total pointer advances
because the shortest list has the fewest candidate doc_ids to consider.

### Skip pointers
A skip pointer list is a sparse index over a sorted posting list:
```
skip_pointers = [(posting_list[i].doc_id, i)
                 for i in range(0, len(posting_list), step)]
where step = max(1, int(sqrt(len(posting_list))))
```
When advancing a pointer to reach a target doc_id, binary search the skip pointer
list for the last skip entry whose doc_id ≤ target, then jump the pointer to that
index and scan linearly from there.

**Complexity:** Without skip pointers, advancing a pointer across P entries is O(P).
With skip pointers, it is O(√P) in the common case (when skips are spaced √P apart
and the target is far ahead). For a corpus of 100 pages, the gain is negligible but
the design scales correctly to larger corpora.

**Synthetic benchmark approach:**
```python
import time
postings_large = [Posting(doc_id=i, ...) for i in range(0, 20000, 2)]  # 10,000 entries
target = 19998
# Time linear scan vs skip-pointer advance, assert skip is faster
```

### Reference
- Manning, C., Raghavan, P., & Schütze, H. (2008). Introduction to Information
  Retrieval. Cambridge University Press. Chapter 2 (skip pointers), Chapter 6 (DAAT).
  https://nlp.stanford.edu/IR-book/ (freely available online)

---

## 3. Levenshtein edit distance

Edit distance between two strings is the minimum number of single-character edits
(insertions, deletions, substitutions) needed to transform one into the other.
Computed via dynamic programming in O(m×n) where m, n are string lengths.

```python
def levenshtein(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev if s1[i-1] == s2[j-1] else 1 + min(prev, dp[j], dp[j-1])
            prev = temp
    return dp[n]
```

Threshold of 2 catches: single typos (distance 1), transpositions like "teh"→"the"
(distance 2 via substitution + substitution, or 1 via transposition in Damerau–
Levenshtein), and common two-key misses.

Scanning the full vocabulary for each query token is O(V × L) where V = vocabulary
size and L = average word length. On a ~100-page corpus, V ≈ 1,000–2,000 terms, so
this is fast enough. For production scale, a BK-tree would reduce this to O(log V).

---

## 4. Positional index and the brief

The brief states:
> "An inverted index that stores statistics (e.g. frequency, position, etc) of each
> word in each page must be created by the tool as it crawls the pages."

"e.g." indicates a non-exhaustive list, but position is explicitly named as an
example. Omitting it is a compliance risk. This project stores positions as a list
of 0-indexed token offsets within each field:

```
positions: [2, 15, 22]  # token offsets within quote_body where term appears
```

Positions enable future phrase/proximity search without requiring an index rebuild.
Even if `find` only implements AND semantics today, positions are stored for
completeness and spec alignment.

---

## 5. JSON vs binary serialisation trade-off

| Property          | JSON                        | Pickle / msgpack / custom binary |
|-------------------|-----------------------------|----------------------------------|
| Human-readable    | Yes — inspectable by marker | No                               |
| Security          | Safe to load from disk      | Pickle executes arbitrary code   |
| Size              | Larger (string keys, UTF-8) | Smaller                          |
| Load speed        | Slower on large files       | Faster                           |
| Portability       | Language-agnostic           | Python-specific (pickle)         |

For a 100-page corpus the index JSON will be ~50–200 KB. Load time is imperceptible.
JSON is the right choice here. At industrial scale (millions of documents), delta-
encoded binary posting lists or a dedicated index format (like Lucene's) would be
required, but that is out of scope.

---

## 6. Target website structure

https://quotes.toscrape.com is a static site built for scraping practice.

Page structure (listing pages):
```html
<div class="quote">
  <span class="text">"The quote body text..."</span>
  <small class="author">Author Name</small>
  <div class="tags">
    <a class="tag">tag1</a>
    <a class="tag">tag2</a>
  </div>
</div>
```

Pagination: `/page/1/` through `/page/10/`. The "Next" button is absent on page 10.
No JavaScript rendering — `requests` + `beautifulsoup4` is sufficient.
No authentication or rate-limiting beyond politeness etiquette.

BeautifulSoup selectors:
```python
soup.select("div.quote span.text")    # quote bodies
soup.select("div.quote small.author") # authors
soup.select("div.quote div.tags a.tag") # tags
soup.select("li.next a")              # next page link
```

---

## 7. Algorithm comparison summary (for video justification)

| Approach                     | Handles length | Field-aware | IDF correct | Complexity  |
|------------------------------|---------------|-------------|-------------|-------------|
| Boolean (no ranking)         | N/A           | N/A         | N/A         | O(N)        |
| TF-IDF                       | No            | No          | Yes         | O(N)        |
| BM25                         | Yes           | No          | Yes         | O(N)        |
| BM25 + post-hoc field boost  | Yes           | Partial     | Diluted     | O(N)        |
| BM25F (chosen)               | Yes           | Yes (native)| Yes         | O(N)        |
| Dense retrieval (bi-encoder) | Yes           | Yes         | N/A         | O(N) + GPU  |

BM25F is the strongest choice within the constraints of this coursework (pure Python,
no model weights, interpretable, directly citable to Robertson & Zaragoza 2009/2004).
