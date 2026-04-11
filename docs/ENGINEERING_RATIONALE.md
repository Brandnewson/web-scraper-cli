# Engineering Rationale

This file records *why* we chose specific tools, libraries, patterns, and algorithms.

## Runtime and Dependency Strategy

- **Python 3.11+**
  - Matches coursework constraints and supports modern typing/dataclasses cleanly.
- **Conda environment + `requirements.txt`**
  - `conda` handles local environment setup.
  - `requirements.txt` remains the coursework-compatible dependency source of truth.

## Core Libraries

- **`requests`**
  - Simple, explicit HTTP client for predictable crawler behavior.
  - Easy to mock in tests.
- **`beautifulsoup4`**
  - Appropriate for static HTML extraction (`quotes.toscrape.com` has no JS rendering need).
  - CSS selector support maps directly to required fields.
- **`pytest`**
  - Strong fit for TDD, readable tests, and fast feedback loops.
- **`pytest-cov`**
  - Enforces coverage target and highlights untested lines quickly.

## Testing Patterns

- **`unittest.mock.patch`**
  - Temporarily replaces external side effects (`requests.get`, `time.sleep`) during tests.
  - Keeps tests deterministic, fast, and offline.
  - Lets us verify behavior (call order/count/arguments), not just output.
- **Objective-to-test trace mapping**
  - Proves tests correspond to assessment objectives, not only code paths.

## Data and Code Patterns

- **`@dataclass` (`PageData`)**
  - Explicit schema for crawler output with clear field names and types.
- **BFS traversal (`deque`)**
  - Natural fit for page-by-page crawl order requirements.
  - Efficient queue operations (`append`/`popleft`).
- **`visited`/`queued` sets**
  - Prevent duplicate processing/enqueue in average O(1) membership checks.
- **URL canonicalization**
  - Normalizes listing URLs (`/page/N/` form) to avoid duplicate logical pages.

## Crawler Algorithm Choices

- **Scope restriction to listing pages only (`/page/N/`)**
  - Aligns with defined corpus and keeps field structure consistent.
- **Unconditional politeness sleep before each request attempt**
  - Satisfies requirement even on failures/non-200 responses.
- **Graceful exception handling (`requests.RequestException`)**
  - Prevents crawl termination on transient network issues.

## Benchmarking Approach (Current Phase)

- **Process benchmark rehearsal under mocked I/O**
  - Validates timing instrumentation and reporting format early.
  - Defers algorithm-comparison benchmarks (skip pointers, BM25F ablation) to relevant phases.

## Indexer Design Choices

- **One posting per `(term, doc_id)` with nested field stats**
  - Keeps DAAT-ready posting lists with unique doc IDs.
  - Avoids query-time deduplication across fields.
- **Per-field position storage**
  - Meets coursework requirement for positional statistics.
  - Preserves future path for phrase/proximity features without rebuild.
- **Regex tokenization (`r"[^a-z0-9]+"`)**
  - Transparent, deterministic baseline aligned with coursework constraints.
