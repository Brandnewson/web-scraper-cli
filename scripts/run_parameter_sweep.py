"""Run BM25F parameter sweep and export ranked tuning results."""

from __future__ import annotations

import argparse
import copy
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

QUERY_SPLIT_PATTERN = re.compile(r"[^a-z0-9]+")

# Locked grid from Phase 10 plan so sweep results stay reproducible across reruns.
K1_VALUES = [1.2, 1.5, 1.8, 2.0]
B_VALUES = [0.5, 0.75, 0.9]
FIELD_WEIGHT_PRESETS = {
    "default": {"quote_body": 1.0, "author": 3.0, "tag": 2.0},
    "balanced": {"quote_body": 1.0, "author": 2.0, "tag": 1.5},
    "body_heavy": {"quote_body": 1.5, "author": 2.0, "tag": 1.0},
    "metadata_heavy": {"quote_body": 1.0, "author": 3.5, "tag": 2.5},
}
DEFAULT_RUN_COUNT = 10


def load_json_file(path: Path) -> Any:
    """Load JSON file from disk.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON payload.

    Raises:
        ValueError: If file is missing or not valid JSON.
    """
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}") from exc


def tokenize_query(text: str) -> list[str]:
    """Tokenize query text with project-standard splitting.

    Args:
        text: Raw query text.

    Returns:
        Lowercased alphanumeric tokens.
    """
    return [token for token in QUERY_SPLIT_PATTERN.split(text.lower()) if token]


def _normalize_queries(raw_queries: list[dict]) -> list[dict]:
    """Validate and normalize query rows."""
    if not isinstance(raw_queries, list):
        raise ValueError("queries must be a list")
    normalized: list[dict] = []
    for row in raw_queries:
        if not isinstance(row, dict):
            raise ValueError("query rows must be objects")
        query_id = row.get("query_id")
        query_text = row.get("query_text")
        if not isinstance(query_id, str) or not isinstance(query_text, str):
            raise ValueError("query rows must include string query_id/query_text")
        normalized.append({"query_id": query_id, "query_text": query_text})
    return normalized


def _normalize_qrels(raw_qrels: dict) -> dict[str, dict[str, int]]:
    """Validate and normalize qrels payload."""
    if not isinstance(raw_qrels, dict):
        raise ValueError("qrels must be an object")
    normalized: dict[str, dict[str, int]] = {}
    for query_id, labels in raw_qrels.items():
        if not isinstance(query_id, str) or not isinstance(labels, dict):
            raise ValueError("qrels must map query_id -> {url: grade}")
        normalized[query_id] = {}
        for url, grade in labels.items():
            if not isinstance(url, str) or not isinstance(grade, int):
                raise ValueError("qrels labels must be url(str) -> grade(int)")
            if grade < 0 or grade > 3:
                raise ValueError("qrels grades must be in range 0..3")
            normalized[query_id][url] = grade
    return normalized


def build_parameter_grid() -> list[dict]:
    """Build the locked 48-configuration parameter grid."""
    grid: list[dict] = []
    for k1 in K1_VALUES:
        for b_value in B_VALUES:
            for preset_name, weights in FIELD_WEIGHT_PRESETS.items():
                config_id = f"k1={k1}_b={b_value}_{preset_name}"
                grid.append(
                    {
                        "config_id": config_id,
                        "k1": k1,
                        "b": b_value,
                        "weights": weights,
                    }
                )
    return grid


def _find_posting(term_entry: dict, doc_id: int) -> dict | None:
    """Find posting dict for a term/doc pair."""
    for posting in term_entry.get("postings", []):
        if posting.get("doc_id") == doc_id:
            return posting
    return None


def _idf(num_docs: int, df: int) -> float:
    """Compute Robertson-style IDF for BM25 variants."""
    return math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)


def _field_denominator(b_value: float, field_length: float, avgdl: float) -> float:
    """Compute BM25F field normalization denominator safely."""
    if avgdl == 0.0:
        return 1.0
    denominator = 1.0 - b_value + b_value * (field_length / avgdl)
    if denominator == 0.0:
        return 1.0
    return denominator


def score_bm25f_term_with_config(
    term: str,
    doc_id: int,
    index: dict,
    fields_meta: dict[str, dict[str, float]],
    k1: float,
) -> float:
    """Score one term/doc pair with BM25F using provided config."""
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

    doc_lengths = index.get("_meta", {}).get("doc_field_lengths", {}).get(str(doc_id), {})
    pseudo_tf = 0.0
    for field_name, stats in posting.get("fields", {}).items():
        field_meta = fields_meta.get(field_name)
        if field_meta is None:
            continue
        tf_value = stats.get("tf", 0)
        if tf_value <= 0:
            continue
        denominator = _field_denominator(
            b_value=float(field_meta.get("b", 0.0)),
            field_length=float(doc_lengths.get(field_name, 0.0)),
            avgdl=float(field_meta.get("avgdl", 0.0)),
        )
        pseudo_tf += float(field_meta.get("weight", 0.0)) * tf_value / denominator

    if pseudo_tf <= 0.0:
        return 0.0
    idf = _idf(num_docs, df)
    return idf * pseudo_tf * (k1 + 1.0) / (pseudo_tf + k1)


def _candidate_doc_ids(tokens: list[str], index: dict) -> list[int]:
    """Collect AND candidates using existing DAAT + skip-pointer pipeline."""
    posting_lists: list[list[dict]] = []
    skip_lists: list[list[tuple[int, int]]] = []
    for token in tokens:
        term_entry = index.get("terms", {}).get(token)
        postings = [] if term_entry is None else term_entry.get("postings", [])
        posting_lists.append(postings)
        skip_lists.append(search.build_skip_pointers(postings))
    return search.daat_and_merge(posting_lists, skip_lists)


def rank_query_with_config(
    tokens: list[str],
    index: dict,
    fields_meta: dict[str, dict[str, float]],
    k1: float,
) -> list[tuple[str, float]]:
    """Rank query results for one config using BM25F."""
    doc_ids = _candidate_doc_ids(tokens, index)
    doc_urls = index.get("_meta", {}).get("doc_urls", {})
    ranked: list[tuple[str, float]] = []
    for doc_id in doc_ids:
        score = sum(
            score_bm25f_term_with_config(token, doc_id, index, fields_meta, k1)
            for token in tokens
        )
        ranked.append((doc_urls.get(str(doc_id), ""), score))
    ranked.sort(key=lambda pair: (-pair[1], pair[0]))
    return ranked


def ndcg_at_5(ranked_urls: list[str], relevance_by_url: dict[str, int], k: int = 5) -> float:
    """Compute nDCG@k using graded relevance labels."""
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


def _fields_meta_for_config(index: dict, config: dict) -> dict[str, dict[str, float]]:
    """Build per-field metadata overlay for one config."""
    source_fields = index.get("_meta", {}).get("fields", {})
    fields_meta = copy.deepcopy(source_fields)
    for field_name, field_meta in fields_meta.items():
        # Apply a global b in this phase to keep the sweep focused and comparable.
        field_meta["weight"] = float(config["weights"][field_name])
        field_meta["b"] = float(config["b"])
    return fields_meta


def evaluate_config(
    index: dict,
    queries: list[dict],
    qrels: dict[str, dict[str, int]],
    config: dict,
    run_count: int,
) -> dict:
    """Evaluate one parameter configuration."""
    fields_meta = _fields_meta_for_config(index, config)
    per_query: list[dict] = []

    for query_row in queries:
        query_id = query_row["query_id"]
        query_text = query_row["query_text"]
        tokens = tokenize_query(query_text)
        labels = qrels.get(query_id, {})

        timings: list[float] = []
        ranked: list[tuple[str, float]] = []
        for _ in range(run_count):
            start = time.perf_counter()
            ranked = rank_query_with_config(tokens, index, fields_meta, float(config["k1"]))
            timings.append((time.perf_counter() - start) * 1000.0)

        ranked_urls = [url for url, _score in ranked]
        per_query.append(
            {
                "query_id": query_id,
                "query_text": query_text,
                "ndcg_at_5": ndcg_at_5(ranked_urls, labels, k=5),
                "mean_query_ms": statistics.mean(timings),
            }
        )

    macro_ndcg = statistics.mean(row["ndcg_at_5"] for row in per_query)
    macro_mean_ms = statistics.mean(row["mean_query_ms"] for row in per_query)

    return {
        "config_id": config["config_id"],
        "k1": float(config["k1"]),
        "b": float(config["b"]),
        "weights": config["weights"],
        "macro_ndcg_at_5": macro_ndcg,
        "macro_mean_query_ms": macro_mean_ms,
        "per_query": per_query,
    }


def run_sweep(
    index: dict,
    queries: list[dict],
    qrels: dict[str, dict[str, int]],
    configs: list[dict],
    run_count: int = DEFAULT_RUN_COUNT,
) -> list[dict]:
    """Evaluate all provided parameter configs and return reports."""
    normalized_queries = _normalize_queries(queries)
    normalized_qrels = _normalize_qrels(qrels)
    if run_count <= 0:
        raise ValueError("run_count must be > 0")
    if not configs:
        raise ValueError("configs list cannot be empty")
    reports = [
        evaluate_config(index, normalized_queries, normalized_qrels, config, run_count)
        for config in configs
    ]
    return sorted(
        reports,
        key=lambda row: (-row["macro_ndcg_at_5"], row["macro_mean_query_ms"], row["config_id"]),
    )


def select_best_config(rows: list[dict]) -> dict:
    """Select best config by nDCG, then runtime, then config id."""
    if not rows:
        raise ValueError("rows cannot be empty")
    # Deterministic tie-break avoids "winner drift" when metrics are effectively tied.
    return sorted(
        rows,
        key=lambda row: (-row["macro_ndcg_at_5"], row["macro_mean_query_ms"], row["config_id"]),
    )[0]


def render_sweep_markdown(rows: list[dict], best_row: dict) -> str:
    """Render sweep summary markdown table."""
    lines = [
        "# BM25F Parameter Sweep Results",
        "",
        "## Best Configuration",
        "",
        f"- `config_id`: `{best_row['config_id']}`",
        f"- `k1`: `{best_row['k1']}`",
        f"- `b`: `{best_row['b']}`",
        f"- `weights`: `{best_row['weights']}`",
        (
            "- `selection_rule`: maximize `macro_ndcg_at_5`, "
            "tie-break on lower `macro_mean_query_ms`, then lexicographic `config_id`"
        ),
        "",
        "## Ranked Configurations",
        "",
        "| rank | config_id | k1 | b | weights | macro_ndcg_at_5 | macro_mean_query_ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for rank, row in enumerate(rows, start=1):
        lines.append(
            f"| {rank} | {row['config_id']} | {row['k1']} | {row['b']} | "
            f"{row['weights']} | {row['macro_ndcg_at_5']:.6f} | {row['macro_mean_query_ms']:.6f} |"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run BM25F parameter sweep.")
    parser.add_argument("--index", type=Path, default=Path("data") / "index.json")
    parser.add_argument("--queries", type=Path, default=Path("results") / "bm25f_queries.json")
    parser.add_argument("--qrels", type=Path, default=Path("results") / "bm25f_qrels.json")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("results") / "parameter_sweep_results.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path("results") / "parameter_sweep_table.md",
    )
    parser.add_argument(
        "--out-best",
        type=Path,
        default=Path("results") / "best_bm25f_config.json",
    )
    parser.add_argument("--run-count", type=int, default=DEFAULT_RUN_COUNT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run parameter sweep and write artifacts.

    Args:
        argv: Optional argument list for programmatic invocation.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = _parse_args(argv)

    if not args.index.exists():
        print(f"Error: index file not found at {args.index}", file=sys.stderr)
        return 1

    try:
        index = load_json_file(args.index)
        queries = load_json_file(args.queries)
        qrels = load_json_file(args.qrels)
        grid = build_parameter_grid()
        rows = run_sweep(index=index, queries=queries, qrels=qrels, configs=grid, run_count=args.run_count)
        best_row = select_best_config(rows)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_best.parent.mkdir(parents=True, exist_ok=True)

    out_payload = {
        "run_count": args.run_count,
        "grid_size": len(rows),
        "rows": rows,
    }
    args.out_json.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
    args.out_md.write_text(render_sweep_markdown(rows, best_row), encoding="utf-8")
    args.out_best.write_text(
        json.dumps(
            {
                "config_id": best_row["config_id"],
                "k1": best_row["k1"],
                "b": best_row["b"],
                "weights": best_row["weights"],
                "selection_rule": (
                    "maximize macro_ndcg_at_5; tie-break on lower macro_mean_query_ms; "
                    "tie-break on lexicographic config_id"
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("| rank | config_id | macro_ndcg_at_5 | macro_mean_query_ms |")
    print("|---|---|---|---|")
    for rank, row in enumerate(rows[:5], start=1):
        print(
            f"| {rank} | {row['config_id']} | "
            f"{row['macro_ndcg_at_5']:.6f} | {row['macro_mean_query_ms']:.6f} |"
        )
    print(f"Wrote: {args.out_json}")
    print(f"Wrote: {args.out_md}")
    print(f"Wrote: {args.out_best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
