"""CLI orchestration for build/load/print/find commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from typing import Callable

from src import crawler, indexer, search

SEED_URL = "https://quotes.toscrape.com/page/1/"
INDEX_SCHEMA_VERSION = 1
DATA_DIR = Path("data")
INDEX_PATH = DATA_DIR / "index.json"
QUERY_SPLIT_PATTERN = re.compile(r"[^a-z0-9]+")
FIELD_ORDER = {"quote_body": 0, "author": 1, "tag": 2}


def run_repl(
    input_fn: Callable[[], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Run persistent CLI loop."""
    loaded_index: dict | None = None
    output_fn("Tip: type 'quit' or 'exit' to leave the CLI.")

    while True:
        try:
            raw_line = input_fn()
        except EOFError:
            break

        command_line = raw_line.strip()
        if not command_line:
            continue

        loaded_index, should_exit = _handle_command(command_line, loaded_index, output_fn)
        if should_exit:
            break


def _handle_command(
    command_line: str,
    loaded_index: dict | None,
    output_fn: Callable[[str], None],
) -> tuple[dict | None, bool]:
    """Dispatch one command line and return updated state and exit flag."""
    parts = command_line.split()
    command = parts[0]
    args = parts[1:]

    if command in {"quit", "exit"}:
        return loaded_index, True

    if command == "build":
        return _handle_build(output_fn), False

    if command == "load":
        new_index = _handle_load(output_fn)
        if new_index is not None:
            return new_index, False
        return loaded_index, False

    if command == "print":
        _handle_print(args, loaded_index, output_fn)
        return loaded_index, False

    if command == "find":
        _handle_find(args, loaded_index, output_fn)
        return loaded_index, False

    output_fn("Unknown command")
    return loaded_index, False


def _handle_build(output_fn: Callable[[str], None]) -> dict:
    """Execute crawl/index/save and print build benchmark lines."""
    output_fn("Starting build...")
    total_start = time.perf_counter()
    crawl_start = time.perf_counter()
    pages = crawler.crawl(SEED_URL, max_pages=crawler.DEFAULT_MAX_PAGES)
    crawl_elapsed = time.perf_counter() - crawl_start
    output_fn("Crawl complete.")

    index_start = time.perf_counter()
    built_index = indexer.build_index(pages)
    index_elapsed = time.perf_counter() - index_start

    _save_index(built_index)
    output_fn("Index saved to data/index.json.")
    total_elapsed = time.perf_counter() - total_start

    file_size_kb = os.path.getsize(INDEX_PATH) / 1024
    num_docs = built_index.get("_meta", {}).get("num_docs", 0)
    vocab_size = len(built_index.get("terms", {}))

    output_fn(
        f"Crawl: {crawl_elapsed:.2f}s  |  Index: {index_elapsed:.2f}s  |  Total: {total_elapsed:.2f}s"
    )
    output_fn(f"Index: {file_size_kb:.1f} KB  |  {num_docs} docs  |  {vocab_size} terms")

    return built_index


def _save_index(index_data: dict) -> None:
    """Persist index JSON to disk."""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index_data, indent=2), encoding="utf-8")


def _handle_load(output_fn: Callable[[str], None]) -> dict | None:
    """Load index from disk and validate schema/version."""
    if not INDEX_PATH.exists():
        output_fn("Error: index file not found at data/index.json.")
        return None

    try:
        loaded = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        output_fn("Error: index file is not valid JSON.")
        return None

    if not _is_valid_loaded_index(loaded):
        output_fn("Error: index schema/version missing or invalid.")
        return None

    output_fn("Loaded index from data/index.json.")
    return loaded


def _is_valid_loaded_index(index_data: dict) -> bool:
    """Return True when loaded index has required top-level schema fields."""
    meta = index_data.get("_meta")
    terms = index_data.get("terms")
    if not isinstance(meta, dict) or not isinstance(terms, dict):
        return False
    return meta.get("schema_version") == INDEX_SCHEMA_VERSION


def _handle_print(
    args: list[str],
    loaded_index: dict | None,
    output_fn: Callable[[str], None],
) -> None:
    """Handle print command for one term."""
    if loaded_index is None:
        output_fn("Error: no index loaded. Run 'build' or 'load' first.")
        return
    if not args:
        output_fn("Usage: print <word>")
        return

    term = args[0].lower()
    term_entry = loaded_index.get("terms", {}).get(term)
    if term_entry is None:
        output_fn("Term not found")
        return

    output_fn(f"Term: {term}  (df: {term_entry.get('df', 0)})")
    for posting in term_entry.get("postings", []):
        tf_total = 0
        merged_positions: list[int] = []
        field_names: list[str] = []

        for field_name, stats in posting.get("fields", {}).items():
            field_names.append(field_name)
            tf_total += stats.get("tf", 0)
            merged_positions.extend(stats.get("positions", []))

        merged_positions.sort()
        field_names.sort(key=lambda name: FIELD_ORDER.get(name, 999))
        fields_text = ", ".join(field_names)
        output_fn(
            f"  {posting.get('url', '')}   tf={tf_total}  pos={merged_positions}  fields=[{fields_text}]"
        )


def _handle_find(
    args: list[str],
    loaded_index: dict | None,
    output_fn: Callable[[str], None],
) -> None:
    """Handle find command using DAAT AND + BM25F + did-you-mean fallback."""
    if loaded_index is None:
        output_fn("Error: no index loaded. Run 'build' or 'load' first.")
        return

    if not args:
        output_fn("Usage: find <query>")
        return

    query_tokens = _tokenize_query(" ".join(args))
    if not query_tokens:
        output_fn("Usage: find <query>")
        return

    query_start = time.perf_counter()
    posting_lists: list[list[dict]] = []
    skip_lists: list[list[tuple[int, int]]] = []

    for token in query_tokens:
        term_entry = loaded_index.get("terms", {}).get(token)
        postings = [] if term_entry is None else term_entry.get("postings", [])
        posting_lists.append(postings)
        skip_lists.append(search.build_skip_pointers(postings))

    doc_ids = search.daat_and_merge(posting_lists, skip_lists)
    if not doc_ids:
        suggestion = search.did_you_mean(query_tokens, loaded_index)
        output_fn(suggestion if suggestion is not None else "No results found")
        output_fn(f"  ({time.perf_counter() - query_start:.4f}s)")
        return

    scored_results: list[tuple[str, float]] = []
    for doc_id in doc_ids:
        score = sum(search.score_bm25f(token, doc_id, loaded_index) for token in query_tokens)
        url = loaded_index.get("_meta", {}).get("doc_urls", {}).get(str(doc_id), "")
        scored_results.append((url, score))

    scored_results.sort(key=lambda pair: (-pair[1], pair[0]))

    output_fn(f'Results for "{" ".join(query_tokens)}" ({len(query_tokens)} terms, AND):')
    for rank, (url, score) in enumerate(scored_results, start=1):
        output_fn(f"  {rank}. {url}   score={score:.3f}")
    output_fn(f"  ({time.perf_counter() - query_start:.4f}s)")


def _tokenize_query(text: str) -> list[str]:
    """Tokenize query text using same lowercase/split rule as indexer."""
    return [token for token in QUERY_SPLIT_PATTERN.split(text.lower()) if token]


if __name__ == "__main__":
    run_repl()
