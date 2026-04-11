"""Comparative benchmark tests for BM25F vs BM25+post-hoc baseline."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

REQUIRED_OBJECTIVES = {
    "comparison_ndcg_metric_correctness",
    "comparison_baseline_posthoc_scoring",
    "comparison_output_columns",
    "comparison_macro_and_per_query_reporting",
    "comparison_missing_index_error",
}

REQUIRED_TEST_NAMES = {
    "test_ndcg_at_5_known_value",
    "test_baseline_posthoc_scoring_deterministic",
    "test_comparison_pipeline_outputs_required_columns",
    "test_comparison_reports_macro_and_per_query",
    "test_missing_index_prints_clear_error",
}

OBJECTIVE_TRACE = {
    "comparison_ndcg_metric_correctness": {"test_ndcg_at_5_known_value"},
    "comparison_baseline_posthoc_scoring": {"test_baseline_posthoc_scoring_deterministic"},
    "comparison_output_columns": {"test_comparison_pipeline_outputs_required_columns"},
    "comparison_macro_and_per_query_reporting": {"test_comparison_reports_macro_and_per_query"},
    "comparison_missing_index_error": {"test_missing_index_prints_clear_error"},
}


def _load_benchmark_module() -> object:
    """Load benchmark script module from scripts directory."""
    script_path = Path("scripts") / "run_bm25f_comparison.py"
    spec = importlib.util.spec_from_file_location("run_bm25f_comparison", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_bm25f_comparison module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mini_index() -> dict:
    """Return deterministic index fixture for benchmark tests."""
    return {
        "_meta": {
            "num_docs": 3,
            "fields": {
                "quote_body": {"avgdl": 2.0, "weight": 1.0, "b": 0.75},
                "author": {"avgdl": 1.0, "weight": 3.0, "b": 0.75},
                "tag": {"avgdl": 1.0, "weight": 2.0, "b": 0.75},
            },
            "doc_field_lengths": {
                "0": {"quote_body": 2, "author": 1, "tag": 1},
                "1": {"quote_body": 1, "author": 1, "tag": 1},
                "2": {"quote_body": 2, "author": 1, "tag": 1},
            },
            "doc_urls": {
                "0": "https://quotes.toscrape.com/page/1/",
                "1": "https://quotes.toscrape.com/page/2/",
                "2": "https://quotes.toscrape.com/page/3/",
            },
        },
        "terms": {
            "alpha": {
                "df": 2,
                "postings": [
                    {
                        "doc_id": 0,
                        "url": "https://quotes.toscrape.com/page/1/",
                        "fields": {"quote_body": {"tf": 2, "positions": [0, 1]}},
                    },
                    {
                        "doc_id": 1,
                        "url": "https://quotes.toscrape.com/page/2/",
                        "fields": {"author": {"tf": 1, "positions": [0]}},
                    },
                ],
            },
            "beta": {
                "df": 2,
                "postings": [
                    {
                        "doc_id": 0,
                        "url": "https://quotes.toscrape.com/page/1/",
                        "fields": {"tag": {"tf": 1, "positions": [0]}},
                    },
                    {
                        "doc_id": 2,
                        "url": "https://quotes.toscrape.com/page/3/",
                        "fields": {"quote_body": {"tf": 1, "positions": [0]}},
                    },
                ],
            },
        },
    }


def _queries() -> list[dict]:
    """Return fixed query fixture list."""
    return [
        {"query_id": "q1", "query_text": "alpha"},
        {"query_id": "q2", "query_text": "beta"},
        {"query_id": "q3", "query_text": "alpha beta"},
    ]


def _qrels() -> dict:
    """Return graded relevance labels fixture."""
    return {
        "q1": {
            "https://quotes.toscrape.com/page/2/": 3,
            "https://quotes.toscrape.com/page/1/": 2,
        },
        "q2": {
            "https://quotes.toscrape.com/page/3/": 3,
            "https://quotes.toscrape.com/page/1/": 1,
        },
        "q3": {
            "https://quotes.toscrape.com/page/1/": 3,
        },
    }


def test_ndcg_at_5_known_value() -> None:
    """nDCG@5 matches deterministic hand-computed expectation."""
    module = _load_benchmark_module()
    ranked_urls = ["u1", "u2", "u3", "u4", "u5"]
    labels = {"u1": 3, "u2": 2, "u3": 0, "u4": 1, "u5": 0}

    actual = module.ndcg_at_5(ranked_urls, labels, k=5)

    dcg = (
        (2**3 - 1) / math.log2(2)
        + (2**2 - 1) / math.log2(3)
        + (2**0 - 1) / math.log2(4)
        + (2**1 - 1) / math.log2(5)
        + (2**0 - 1) / math.log2(6)
    )
    ideal_labels = [3, 2, 1, 0, 0]
    idcg = sum((2**rel - 1) / math.log2(index + 2) for index, rel in enumerate(ideal_labels))
    expected = dcg / idcg

    assert abs(actual - expected) <= 1e-9


def test_baseline_posthoc_scoring_deterministic() -> None:
    """BM25+post-hoc baseline score matches hand-computed numeric value."""
    module = _load_benchmark_module()
    index = _mini_index()

    actual = module.score_baseline_term("alpha", 1, index)

    idf = math.log((3 - 2 + 0.5) / (2 + 0.5) + 1.0)
    tf_agg = 1.0
    dl_agg = 3.0
    avgdl_agg = 4.0
    k1 = 1.5
    b_value = 0.75
    bm25 = idf * (tf_agg * (k1 + 1.0)) / (tf_agg + k1 * (1.0 - b_value + b_value * (dl_agg / avgdl_agg)))
    expected = bm25 * 3.0

    assert abs(actual - expected) <= 1e-9


def test_comparison_pipeline_outputs_required_columns() -> None:
    """Pipeline output includes required benchmark table columns."""
    module = _load_benchmark_module()
    report = module.run_comparison(_mini_index(), _queries(), _qrels(), run_count=2)

    row = report["benchmark_row"]
    assert set(row) == {
        "benchmark_name",
        "configuration",
        "result",
        "baseline_result",
        "delta",
        "units",
        "run_count",
    }


def test_comparison_reports_macro_and_per_query() -> None:
    """Report includes both macro-average and per-query entries."""
    module = _load_benchmark_module()
    report = module.run_comparison(_mini_index(), _queries(), _qrels(), run_count=2)

    assert "macro_average" in report
    assert "per_query" in report
    assert len(report["per_query"]) == 3

    macro = report["macro_average"]
    assert "bm25f_ndcg_at_5" in macro
    assert "baseline_ndcg_at_5" in macro
    assert "delta_ndcg_at_5" in macro
    assert "bm25f_mean_query_ms" in macro
    assert "baseline_mean_query_ms" in macro


def test_missing_index_prints_clear_error(tmp_path: Path, capsys) -> None:
    """Missing index path produces clear error and non-zero exit code."""
    module = _load_benchmark_module()

    queries_path = tmp_path / "queries.json"
    qrels_path = tmp_path / "qrels.json"
    out_json = tmp_path / "comparison.json"
    out_md = tmp_path / "comparison.md"

    queries_path.write_text(json.dumps(_queries()), encoding="utf-8")
    qrels_path.write_text(json.dumps(_qrels()), encoding="utf-8")

    exit_code = module.main(
        [
            "--index",
            str(tmp_path / "missing-index.json"),
            "--queries",
            str(queries_path),
            "--qrels",
            str(qrels_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: index file not found" in captured.err


def test_objective_trace_completeness() -> None:
    """All benchmark objectives are mapped to required tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES
