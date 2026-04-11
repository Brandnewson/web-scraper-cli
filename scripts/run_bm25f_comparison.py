"""Run BM25F vs BM25+post-hoc comparative benchmark and export evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import search

BENCHMARK_NAME = "bm25f_vs_bm25_posthoc"
QUERY_SPLIT_PATTERN = re.compile(r"[^a-z0-9]+")
DEFAULT_RUN_COUNT = 10
BASELINE_K1 = 1.5
BASELINE_B = 0.75


def load_json_file(path: Path) -> Any:
    """Load JSON file contents.

    Args:
        path: Path to JSON file.

    Returns:
        Decoded JSON object.

    Raises:
        ValueError: If the file is missing or invalid.
    """
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}") from exc


def validate_index(index: dict) -> None:
    """Validate index shape required for comparative benchmark.

    Args:
        index: Loaded index object.

    Raises:
        ValueError: If required schema fields are missing.
    """
    if not isinstance(index, dict):
        raise ValueError("index must be a JSON object")

    meta = index.get("_meta")
    terms = index.get("terms")
    if not isinstance(meta, dict) or not isinstance(terms, dict):
        raise ValueError("index missing required keys: _meta/terms")

    if not isinstance(meta.get("num_docs"), int):
        raise ValueError("index _meta.num_docs missing or invalid")
    if not isinstance(meta.get("fields"), dict):
        raise ValueError("index _meta.fields missing or invalid")
    if not isinstance(meta.get("doc_field_lengths"), dict):
        raise ValueError("index _meta.doc_field_lengths missing or invalid")
    if not isinstance(meta.get("doc_urls"), dict):
        raise ValueError("index _meta.doc_urls missing or invalid")


def tokenize_query(text: str) -> list[str]:
    """Tokenize query text with project-standard splitting.

    Args:
        text: Raw query text.

    Returns:
        Lowercased alphanumeric tokens.
    """
    return [token for token in QUERY_SPLIT_PATTERN.split(text.lower()) if token]


def _normalize_queries(raw_queries: list[dict]) -> list[dict]:
    """Normalize raw query objects to required keys."""
    normalized: list[dict] = []
    for row in raw_queries:
        if not isinstance(row, dict):
            raise ValueError("queries must be list[object]")
        query_id = row.get("query_id")
        query_text = row.get("query_text")
        if not isinstance(query_id, str) or not isinstance(query_text, str):
            raise ValueError("each query requires string query_id/query_text")
        normalized.append({"query_id": query_id, "query_text": query_text})
    return normalized


def _normalize_qrels(raw_qrels: dict) -> dict[str, dict[str, int]]:
    """Normalize qrels mapping to graded int labels."""
    if not isinstance(raw_qrels, dict):
        raise ValueError("qrels must be an object mapping query_id -> {url: grade}")
    normalized: dict[str, dict[str, int]] = {}
    for query_id, label_map in raw_qrels.items():
        if not isinstance(query_id, str) or not isinstance(label_map, dict):
            raise ValueError("qrels keys must be query_id strings with object values")
        normalized[query_id] = {}
        for url, grade in label_map.items():
            if not isinstance(url, str):
                raise ValueError("qrels URL keys must be strings")
            if not isinstance(grade, int):
                raise ValueError("qrels grades must be integers")
            if grade < 0 or grade > 3:
                raise ValueError("qrels grades must be in range 0..3")
            normalized[query_id][url] = grade
    return normalized


def _find_posting(term_entry: dict, doc_id: int) -> dict | None:
    """Return posting dict for term/doc pair."""
    for posting in term_entry.get("postings", []):
        if posting.get("doc_id") == doc_id:
            return posting
    return None


def _idf(num_docs: int, df: int) -> float:
    """Compute Robertson-style IDF."""
    return math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)


def score_baseline_term(term: str, doc_id: int, index: dict) -> float:
    """Score one term-doc pair with BM25 + post-hoc field boost.

    Args:
        term: Query term.
        doc_id: Target document id.
        index: Loaded index.

    Returns:
        Baseline score contribution for this term/doc, else 0.0.
    """
    term_entry = index.get("terms", {}).get(term)
    if term_entry is None:
        return 0.0

    num_docs = index.get("_meta", {}).get("num_docs", 0)
    df = term_entry.get("df", 0)
    if num_docs <= 0 or df <= 0:
        return 0.0

    posting = _find_posting(term_entry, doc_id)
    if posting is None:
        return 0.0

    fields_meta = index.get("_meta", {}).get("fields", {})
    doc_lengths = index.get("_meta", {}).get("doc_field_lengths", {}).get(str(doc_id), {})
    posting_fields = posting.get("fields", {})

    tf_agg = 0.0
    matched_weights: list[float] = []
    for field_name, stats in posting_fields.items():
        tf_value = stats.get("tf", 0)
        if tf_value <= 0:
            continue
        tf_agg += tf_value
        field_weight = fields_meta.get(field_name, {}).get("weight")
        if isinstance(field_weight, (int, float)):
            matched_weights.append(float(field_weight))

    if tf_agg <= 0.0:
        return 0.0

    avgdl_agg = 0.0
    dl_agg = 0.0
    for field_name, meta in fields_meta.items():
        avgdl_agg += float(meta.get("avgdl", 0.0))
        dl_agg += float(doc_lengths.get(field_name, 0.0))

    if avgdl_agg <= 0.0:
        return 0.0

    denominator = tf_agg + BASELINE_K1 * (1.0 - BASELINE_B + BASELINE_B * (dl_agg / avgdl_agg))
    if denominator <= 0.0:
        return 0.0

    bm25 = _idf(num_docs, df) * (tf_agg * (BASELINE_K1 + 1.0)) / denominator
    multiplier = max(matched_weights) if matched_weights else 1.0
    return bm25 * multiplier


def _candidate_doc_ids(tokens: list[str], index: dict) -> list[int]:
    """Return AND candidate doc IDs using DAAT + skip pointers."""
    posting_lists: list[list[dict]] = []
    skip_lists: list[list[tuple[int, int]]] = []

    for token in tokens:
        term_entry = index.get("terms", {}).get(token)
        postings = [] if term_entry is None else term_entry.get("postings", [])
        posting_lists.append(postings)
        skip_lists.append(search.build_skip_pointers(postings))

    return search.daat_and_merge(posting_lists, skip_lists)


def _score_query(tokens: list[str], doc_id: int, index: dict, method: str) -> float:
    """Score one document for one query with selected method."""
    if method == "bm25f":
        return sum(search.score_bm25f(token, doc_id, index) for token in tokens)
    if method == "baseline":
        return sum(score_baseline_term(token, doc_id, index) for token in tokens)
    raise ValueError(f"unknown scoring method: {method}")


def rank_query(tokens: list[str], index: dict, method: str) -> list[tuple[str, float]]:
    """Rank query results with selected scoring method.

    Args:
        tokens: Tokenized query.
        index: Loaded index.
        method: `bm25f` or `baseline`.

    Returns:
        Sorted list of `(url, score)` results.
    """
    doc_ids = _candidate_doc_ids(tokens, index)
    doc_urls = index.get("_meta", {}).get("doc_urls", {})
    ranked: list[tuple[str, float]] = []
    for doc_id in doc_ids:
        score = _score_query(tokens, doc_id, index, method)
        url = doc_urls.get(str(doc_id), "")
        ranked.append((url, score))
    ranked.sort(key=lambda pair: (-pair[1], pair[0]))
    return ranked


def ndcg_at_5(ranked_urls: list[str], relevance_by_url: dict[str, int], k: int = 5) -> float:
    """Compute nDCG@k using graded relevance labels.

    Args:
        ranked_urls: Ranked URLs in descending score order.
        relevance_by_url: Mapping of URL to graded relevance label.
        k: Ranking cutoff.

    Returns:
        nDCG value in range [0, 1].
    """
    cutoff = min(k, len(ranked_urls))
    dcg = 0.0
    for rank in range(cutoff):
        rel = relevance_by_url.get(ranked_urls[rank], 0)
        dcg += (2**rel - 1) / math.log2(rank + 2)

    ideal_rels = sorted(relevance_by_url.values(), reverse=True)[:k]
    if not ideal_rels:
        return 0.0
    idcg = 0.0
    for rank, rel in enumerate(ideal_rels):
        idcg += (2**rel - 1) / math.log2(rank + 2)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def run_comparison(
    index: dict,
    queries: list[dict],
    qrels: dict[str, dict[str, int]],
    run_count: int = DEFAULT_RUN_COUNT,
    index_label: str = "data/index.json",
) -> dict:
    """Run benchmark comparison and return report payload.

    Args:
        index: Loaded index object.
        queries: Query rows with `query_id` and `query_text`.
        qrels: Relevance labels keyed by query id and URL.
        run_count: Number of timed runs per query per method.
        index_label: Human-readable index identifier for reporting.

    Returns:
        Dict containing benchmark row, macro averages, and per-query details.
    """
    query_rows = _normalize_queries(queries)
    relevance_rows = _normalize_qrels(qrels)
    if run_count <= 0:
        raise ValueError("run_count must be > 0")

    per_query: list[dict] = []

    for query_row in query_rows:
        query_id = query_row["query_id"]
        query_text = query_row["query_text"]
        tokens = tokenize_query(query_text)
        labels = relevance_rows.get(query_id, {})

        bm25f_ranked: list[tuple[str, float]] = []
        baseline_ranked: list[tuple[str, float]] = []
        bm25f_timings: list[float] = []
        baseline_timings: list[float] = []

        for _ in range(run_count):
            bm25f_start = time.perf_counter()
            bm25f_ranked = rank_query(tokens, index, method="bm25f")
            bm25f_timings.append((time.perf_counter() - bm25f_start) * 1000.0)

            baseline_start = time.perf_counter()
            baseline_ranked = rank_query(tokens, index, method="baseline")
            baseline_timings.append((time.perf_counter() - baseline_start) * 1000.0)

        bm25f_urls = [url for url, _score in bm25f_ranked]
        baseline_urls = [url for url, _score in baseline_ranked]
        bm25f_ndcg = ndcg_at_5(bm25f_urls, labels, k=5)
        baseline_ndcg = ndcg_at_5(baseline_urls, labels, k=5)
        bm25f_mean_ms = statistics.mean(bm25f_timings)
        baseline_mean_ms = statistics.mean(baseline_timings)

        per_query.append(
            {
                "query_id": query_id,
                "query_text": query_text,
                "bm25f_ndcg_at_5": bm25f_ndcg,
                "baseline_ndcg_at_5": baseline_ndcg,
                "delta_ndcg_at_5": bm25f_ndcg - baseline_ndcg,
                "bm25f_mean_query_ms": bm25f_mean_ms,
                "baseline_mean_query_ms": baseline_mean_ms,
                "delta_mean_query_ms": bm25f_mean_ms - baseline_mean_ms,
            }
        )

    bm25f_macro_ndcg = statistics.mean(row["bm25f_ndcg_at_5"] for row in per_query)
    baseline_macro_ndcg = statistics.mean(row["baseline_ndcg_at_5"] for row in per_query)
    bm25f_macro_ms = statistics.mean(row["bm25f_mean_query_ms"] for row in per_query)
    baseline_macro_ms = statistics.mean(row["baseline_mean_query_ms"] for row in per_query)

    macro_average = {
        "bm25f_ndcg_at_5": bm25f_macro_ndcg,
        "baseline_ndcg_at_5": baseline_macro_ndcg,
        "delta_ndcg_at_5": bm25f_macro_ndcg - baseline_macro_ndcg,
        "bm25f_mean_query_ms": bm25f_macro_ms,
        "baseline_mean_query_ms": baseline_macro_ms,
        "delta_mean_query_ms": bm25f_macro_ms - baseline_macro_ms,
    }

    benchmark_row = {
        "benchmark_name": BENCHMARK_NAME,
        "configuration": (
            f"index={index_label},queries={len(query_rows)},run_count={run_count},"
            f"metric=nDCG@5,runtime_metric=mean_query_ms,"
            f"bm25f_mean_ms={bm25f_macro_ms:.3f},baseline_mean_ms={baseline_macro_ms:.3f}"
        ),
        "result": bm25f_macro_ndcg,
        "baseline_result": baseline_macro_ndcg,
        "delta": bm25f_macro_ndcg - baseline_macro_ndcg,
        "units": "nDCG@5",
        "run_count": run_count,
    }

    return {
        "benchmark_row": benchmark_row,
        "macro_average": macro_average,
        "per_query": per_query,
    }


def render_markdown(report: dict) -> str:
    """Render report payload as markdown tables."""
    benchmark_row = report["benchmark_row"]
    macro = report["macro_average"]
    per_query = report["per_query"]

    lines = [
        "# BM25F vs BM25+Post-Hoc Comparison",
        "",
        "## Benchmark Row",
        "",
        "| benchmark_name | configuration | result | baseline_result | delta | units | run_count |",
        "|---|---|---|---|---|---|---|",
        (
            f"| {benchmark_row['benchmark_name']} | {benchmark_row['configuration']} | "
            f"{benchmark_row['result']:.6f} | {benchmark_row['baseline_result']:.6f} | "
            f"{benchmark_row['delta']:+.6f} | {benchmark_row['units']} | {benchmark_row['run_count']} |"
        ),
        "",
        "## Macro Averages",
        "",
        "| metric | bm25f | baseline | delta |",
        "|---|---|---|---|",
        (
            f"| nDCG@5 | {macro['bm25f_ndcg_at_5']:.6f} | {macro['baseline_ndcg_at_5']:.6f} | "
            f"{macro['delta_ndcg_at_5']:+.6f} |"
        ),
        (
            f"| mean_query_ms | {macro['bm25f_mean_query_ms']:.6f} | {macro['baseline_mean_query_ms']:.6f} | "
            f"{macro['delta_mean_query_ms']:+.6f} |"
        ),
        "",
        "## Per Query",
        "",
        "| query_id | query_text | bm25f_ndcg_at_5 | baseline_ndcg_at_5 | delta_ndcg_at_5 | bm25f_mean_query_ms | baseline_mean_query_ms |",
        "|---|---|---|---|---|---|---|",
    ]

    for row in per_query:
        lines.append(
            f"| {row['query_id']} | {row['query_text']} | {row['bm25f_ndcg_at_5']:.6f} | "
            f"{row['baseline_ndcg_at_5']:.6f} | {row['delta_ndcg_at_5']:+.6f} | "
            f"{row['bm25f_mean_query_ms']:.6f} | {row['baseline_mean_query_ms']:.6f} |"
        )

    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run BM25F vs baseline comparative benchmark.")
    parser.add_argument("--index", type=Path, default=Path("data") / "index.json")
    parser.add_argument("--queries", type=Path, default=Path("results") / "bm25f_queries.json")
    parser.add_argument("--qrels", type=Path, default=Path("results") / "bm25f_qrels.json")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("results") / "bm25f_comparison_results.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path("results") / "bm25f_comparison_table.md",
    )
    parser.add_argument("--run-count", type=int, default=DEFAULT_RUN_COUNT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run benchmark entrypoint.

    Args:
        argv: Optional argument list for programmatic invocation.

    Returns:
        Exit code: 0 on success, 1 on recoverable failure.
    """
    args = _parse_args(argv)

    if not args.index.exists():
        print(f"Error: index file not found at {args.index}", file=sys.stderr)
        return 1

    try:
        index = load_json_file(args.index)
        validate_index(index)
        queries = load_json_file(args.queries)
        qrels = load_json_file(args.qrels)
        report = run_comparison(
            index=index,
            queries=queries,
            qrels=qrels,
            run_count=args.run_count,
            index_label=str(args.index),
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")

    benchmark_row = report["benchmark_row"]
    print("| benchmark_name | configuration | result | baseline_result | delta | units | run_count |")
    print("|---|---|---|---|---|---|---|")
    print(
        f"| {benchmark_row['benchmark_name']} | {benchmark_row['configuration']} | "
        f"{benchmark_row['result']:.6f} | {benchmark_row['baseline_result']:.6f} | "
        f"{benchmark_row['delta']:+.6f} | {benchmark_row['units']} | {benchmark_row['run_count']} |"
    )
    print(f"Wrote: {args.out_json}")
    print(f"Wrote: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
