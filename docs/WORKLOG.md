# Work Log

## 2026-04-11 - Phase 1 (Architecture-First Lock-In)

### Why
Lock architecture and process gates before implementation to prevent design drift.

### What
- Locked module boundaries and CLI behavior contracts in architecture docs.
- Added strict phase progression gates (tests first, fail first, pass before moving on).
- Added objective-to-test mapping requirement.
- Added benchmark protocol updates:
  - required timing benchmarks
  - comparative benchmark plan (BM25F vs BM25 + post-hoc boost)
  - standard benchmark evidence table format
- Aligned environment policy to `conda` + `requirements.txt`.

### Validation
- Cross-file consistency checks completed across:
  - `ARCHITECTURE.md`
  - `CONTEXT.md`
  - `CODEX.md`

### Notes
- This phase was docs-only by design (no feature implementation).

---

## 2026-04-11 - Phase 2 (Crawler-Only TDD + Process Validation)

### Why
Deliver crawler scope with strict red-green TDD and prove the phase gate process.

### What
- Added crawler implementation:
  - `src/crawler.py`
  - `src/__init__.py`
- Added crawler tests and process checks:
  - `tests/test_crawler.py`
  - `tests/conftest.py`
- Added dependency file:
  - `requirements.txt`

### Validation
- Red state confirmed first (missing module import during initial test run).
- Crawler test suite passed:
  - `11 passed`
- Coverage gate passed:
  - `pytest --cov=src --cov-report=term-missing`
  - `TOTAL 92%`
- Process benchmark rehearsal executed and printed in required table format:
  - `benchmark_name`: `phase2_crawl_process_rehearsal`
  - `configuration`: `mocked_http,max_pages=3,attempts=3,expected_politeness_lb_s=18.0`
  - `result`: `5.131 ms`
  - `run_count`: `1`

### Notes
- Feature-comparison benchmarks intentionally deferred:
  - skip-pointer vs linear -> search phase
  - BM25F vs baseline -> final benchmark phase

---

## 2026-04-11 - Phase 3 (Indexer-Only TDD)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Implement index build logic with strict test-first workflow, without expanding scope
into persistence/CLI/search.

### What
- Added indexer implementation:
  - `src/indexer.py`
- Added indexer test suite with in-test objective trace:
  - `tests/test_indexer.py`
- Locked behaviors implemented:
  - regex tokenization (`r"[^a-z0-9]+"`) with lowercase
  - one posting per `(term, doc_id)` with nested field stats
  - per-field positions and tf
  - posting lists sorted by `doc_id`
  - `_meta` generation (`num_docs`, `built_at`, `schema_version`, `fields`,
    `doc_field_lengths`, `doc_urls`)
  - correct term-level `df`

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_indexer.py`
  - failed with `ModuleNotFoundError: No module named 'src.indexer'`
- Green state:
  - `pytest -q tests/test_indexer.py`
  - `9 passed`
- Coverage gate:
  - `pytest --cov=src --cov-report=term-missing`
  - `TOTAL 96%`

### Notes
- No CLI wiring, persistence helpers, or new benchmarks added in this phase.
- Minor quality fix applied: timezone-aware UTC timestamp in `built_at`.

---

## 2026-04-11 - Phase 4 (BM25F Scorer-Only TDD)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Implement BM25F scorer as a standalone phase before DAAT, skip pointers, and spell
correction to preserve strict phased complexity growth.

### What
- Added BM25F scorer module:
  - `src/search.py`
- Added BM25F-only test suite with in-test objective trace:
  - `tests/test_search.py`
- Locked edge behaviors implemented:
  - missing term -> `0.0`
  - missing posting for `doc_id` -> `0.0`
  - invalid corpus stats (`num_docs <= 0` or `df <= 0`) -> `0.0`
  - `avgdl == 0` field normalization denominator -> `1.0`

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_search.py`
  - failed with `ModuleNotFoundError: No module named 'src.search'`
- Green state:
  - `pytest -q tests/test_search.py`
  - `6 passed`
- Coverage gate:
  - `pytest --cov=src --cov-report=term-missing`
  - `TOTAL 94%`

### Notes
- No DAAT, skip pointers, spell correction, or query-level ranking orchestration added.
- Benchmark roadmap unchanged; comparative and skip benchmarks remain deferred to their
  planned phases.

---

## 2026-04-11 - Phase 5 (DAAT AND + Skip Pointers TDD)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Add intersection logic and skip-pointer primitives before spell-correction and CLI
integration, while keeping search-phase responsibilities isolated.

### What
- Extended `src/search.py` with:
  - `build_skip_pointers`
  - `advance_with_skips`
  - `daat_and_merge`
- Extended `tests/test_search.py` with required DAAT/skip correctness tests and
  edge-case safety tests.
- Updated objective-trace completeness mapping to include DAAT/skip objectives.

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_search.py`
  - failed with missing attribute errors for DAAT/skip APIs.
- Green state:
  - `pytest -q tests/test_search.py`
  - `14 passed`
- Coverage gate:
  - `pytest --cov=src --cov-report=term-missing`
  - `TOTAL 93%`

### Notes
- No skip-speed benchmark execution in this phase (`test_skip_pointer_vs_linear` deferred).
- No spell-correction functions added.
- No main/persistence changes added.

---

## 2026-04-11 - Phase 6 (Spell Correction-Only TDD)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Implement spelling primitives as an isolated phase before wiring query orchestration
or CLI behavior, preserving clear separation of concerns in `search.py`.

### What
- Extended `src/search.py` with:
  - `levenshtein(s1, s2)` using Damerau-style adjacent transposition support
  - `suggest(token, vocabulary, max_dist=2)` with deterministic alphabetical tie-break
  - `did_you_mean(query_tokens, index)` returning `Did you mean: "<...>"?` or `None`
- Extended `tests/test_search.py` with required spell tests and objective-trace updates.

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_search.py`
  - failed with missing spell API attributes.
- Green state:
  - `pytest -q tests/test_search.py`
  - `22 passed`
- Coverage gate:
  - `pytest --cov=src --cov-report=term-missing`
  - `TOTAL 93%`

### Notes
- Existing BM25F and DAAT/skip behavior left unchanged.
- No benchmark execution added in this phase.
- No CLI/main/persistence changes added.

---

## 2026-04-11 - Phase 7 (Main CLI Wiring TDD)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Wire command-line orchestration over completed crawler/indexer/search primitives so
coursework-required commands (`build`, `load`, `print`, `find`) become runnable.

### What
- Added `src/main.py` with command loop and handlers:
  - `build` (crawl -> index -> save -> benchmark/stat output)
  - `load` (missing-file and invalid-JSON error handling)
  - `print <word>` (aggregated tf/positions across fields per doc)
  - `find <query>` (DAAT + BM25F + did-you-mean fallback)
  - `quit` / `exit`
- Added function-level CLI tests:
  - `tests/test_main.py`
- Fixed persistence path robustness:
  - save now creates `INDEX_PATH.parent` rather than assuming fixed `data/`.

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_main.py`
  - failed with `ModuleNotFoundError: No module named 'src.main'`
- Green state:
  - `pytest -q tests/test_main.py`
  - `12 passed`
- Coverage gate:
  - `pytest --cov=src --cov-report=term-missing`
  - `TOTAL 92%`

### Notes
- No new ranking/merge/spell algorithms introduced.
- No benchmark scripts added; benchmark roadmap remains deferred.

---

## 2026-04-11 - Phase 8 (Skip-Pointer Benchmark Validation)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Provide reproducible algorithm-improvement evidence for skip pointers vs linear
pointer advance, aligned to coursework benchmarking requirements.

### What
- Extended `tests/test_search.py` with:
  - `test_skip_pointer_vs_linear`
  - benchmark objective mapping in `REQUIRED_OBJECTIVES`, `REQUIRED_TEST_NAMES`,
    and `OBJECTIVE_TRACE`
- Added linear baseline and timing helpers for stable median-based comparison across
  5 trials.
- Published benchmark evidence table row in `README.md` using required reporting
  columns.

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_search.py::test_objective_trace_completeness`
  - failed due missing benchmark objective mapping.
- Targeted green:
  - `pytest -q tests/test_search.py::test_skip_pointer_vs_linear tests/test_search.py::test_objective_trace_completeness`
  - `2 passed`
- Search suite green:
  - `pytest -q tests/test_search.py`
  - `23 passed`
- Full gate:
  - `pytest --cov=src --cov-report=term-missing -q`
  - `TOTAL 92%` (`55 passed`)
- Benchmark evidence command:
  - `pytest -q -s tests/test_search.py::test_skip_pointer_vs_linear`
  - `skip=28.809 ms`, `linear=2118.485 ms`, `speedup=73.54x`

### Notes
- Scope kept strictly to skip-pointer benchmark validation.
- BM25F vs BM25 + post-hoc boost benchmark remains deferred to next phase.

---

## 2026-04-11 - Phase 9 (BM25F vs BM25+Post-Hoc Comparative Benchmark)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Provide reproducible comparative evidence that BM25F improves ranking quality over
BM25 + post-hoc field boost, while also reporting runtime in the required format.

### What
- Added benchmark script:
  - `scripts/run_bm25f_comparison.py`
- Added fixed benchmark inputs:
  - `results/bm25f_queries.json` (10 fixed queries)
  - `results/bm25f_qrels.json` (manual graded labels 0..3)
- Added benchmark tests:
  - `tests/test_benchmark_comparison.py`
- Generated benchmark artifacts:
  - `results/bm25f_comparison_results.json`
  - `results/bm25f_comparison_table.md`
- Updated root `README.md` benchmark table with comparative row.

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_benchmark_comparison.py`
  - failed due missing `scripts/run_bm25f_comparison.py`.
- New benchmark test suite green:
  - `pytest -q tests/test_benchmark_comparison.py`
  - `6 passed`
- Comparative script execution:
  - `python scripts/run_bm25f_comparison.py --index data/index.json --queries results/bm25f_queries.json --qrels results/bm25f_qrels.json --out-json results/bm25f_comparison_results.json --out-md results/bm25f_comparison_table.md`
  - `bm25f nDCG@5 = 1.000000`
  - `baseline nDCG@5 = 0.983545`
  - `delta = +0.016455`
  - `bm25f mean query ms = 0.069`
  - `baseline mean query ms = 0.075`

### Notes
- Existing runtime APIs in `src/` search/CLI remain unchanged.
- Benchmark methodology locked to fixed corpus snapshot + fixed query/qrels files.

---

## 2026-04-11 - Phase 10 (BM25F Parameter Sweep + Final Validation Gate)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes
- Testing & Coverage gate: pass
- Code Quality & Documentation gate: pass
- Git Practices gate: pass (incremental scope maintained)

### Why
Tune BM25F parameters using a reproducible quality-first sweep, then harden final
submission validation with an executable pass/fail evidence gate and one live run.

### What
- Added parameter sweep script:
  - `scripts/run_parameter_sweep.py`
- Added validation gate script:
  - `scripts/validate_submission.py`
- Added fixed phase tests:
  - `tests/test_parameter_sweep.py`
  - `tests/test_validate_submission.py`
- Generated sweep artifacts:
  - `results/parameter_sweep_results.json`
  - `results/parameter_sweep_table.md`
  - `results/best_bm25f_config.json`
- Applied sweep winner to runtime defaults:
  - `src/search.py`: `K1 = 2.0`
  - `src/indexer.py` defaults remained aligned (`b=0.75`, default weights unchanged)
- Rebuilt index and regenerated comparison artifacts:
  - `data/index.json`
  - `results/bm25f_comparison_results.json`
  - `results/bm25f_comparison_table.md`
- Updated `README.md` benchmark section and recorded sweep winner.

### Validation
- Red state confirmed first:
  - `pytest -q tests/test_parameter_sweep.py tests/test_validate_submission.py`
  - failed due missing new scripts.
- New phase tests green:
  - `pytest -q tests/test_parameter_sweep.py tests/test_validate_submission.py`
  - `9 passed`
- Sweep execution:
  - `python scripts/run_parameter_sweep.py --index data/index.json --queries results/bm25f_queries.json --qrels results/bm25f_qrels.json --out-json results/parameter_sweep_results.json --out-md results/parameter_sweep_table.md --out-best results/best_bm25f_config.json --run-count 10`
  - winner: `k1=2.0_b=0.75_default`
- Live rebuild:
  - `main._handle_build(print)` (real crawl + rebuild)
- Comparative benchmark refresh:
  - `python scripts/run_bm25f_comparison.py --index data/index.json --queries results/bm25f_queries.json --qrels results/bm25f_qrels.json --out-json results/bm25f_comparison_results.json --out-md results/bm25f_comparison_table.md --run-count 10`
- Final validation gate with live smoke:
  - `python scripts/validate_submission.py --live-smoke`
  - all checks `PASS`
- Full coverage gate:
  - `pytest --cov=src --cov-report=term-missing -q`
  - `TOTAL 92%` (`70 passed`)

### Notes
- Sweep grid locked to 48 configs as planned.
- Selection rule locked: nDCG@5 desc, runtime asc, config id asc.

---

## Entry Template

### YYYY-MM-DD - Phase X (Title)

### Gate Check
- `DELIVERY_GATES.md` read at step start/end: yes/no
- Testing & Coverage gate: pass/fail
- Code Quality & Documentation gate: pass/fail
- Git Practices gate: pass/fail

### Why
- ...

### What
- ...

### Validation
- ...

### Notes
- ...
