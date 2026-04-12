"""Parameter sweep tests for BM25F configuration tuning."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REQUIRED_OBJECTIVES = {
    "sweep_ranking_order_by_quality_and_runtime",
    "sweep_output_schema_completeness",
    "sweep_best_config_determinism",
    "sweep_macro_and_per_query_reporting",
}

REQUIRED_TEST_NAMES = {
    "test_sweep_ranks_configs_by_ndcg_then_runtime",
    "test_sweep_outputs_required_columns",
    "test_best_config_selection_is_deterministic",
    "test_sweep_reports_macro_and_per_query",
}

OBJECTIVE_TRACE = {
    "sweep_ranking_order_by_quality_and_runtime": {"test_sweep_ranks_configs_by_ndcg_then_runtime"},
    "sweep_output_schema_completeness": {"test_sweep_outputs_required_columns"},
    "sweep_best_config_determinism": {"test_best_config_selection_is_deterministic"},
    "sweep_macro_and_per_query_reporting": {"test_sweep_reports_macro_and_per_query"},
}


def _load_sweep_module() -> object:
    """Load the sweep script as an importable module."""
    script_path = Path("scripts") / "run_parameter_sweep.py"
    spec = importlib.util.spec_from_file_location("run_parameter_sweep", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_parameter_sweep module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mini_index() -> dict:
    """Return deterministic index fixture for sweep tests."""
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
    """Return fixed query fixtures."""
    return [
        {"query_id": "q1", "query_text": "alpha"},
        {"query_id": "q2", "query_text": "beta"},
    ]


def _qrels() -> dict:
    """Return graded relevance labels."""
    return {
        "q1": {
            "https://quotes.toscrape.com/page/2/": 3,
            "https://quotes.toscrape.com/page/1/": 2,
        },
        "q2": {
            "https://quotes.toscrape.com/page/3/": 3,
            "https://quotes.toscrape.com/page/1/": 1,
        },
    }


def test_sweep_ranks_configs_by_ndcg_then_runtime() -> None:
    """Best config selection prefers higher nDCG, then lower runtime."""
    module = _load_sweep_module()
    rows = [
        {"config_id": "cfg_a", "macro_ndcg_at_5": 0.91, "macro_mean_query_ms": 0.80},
        {"config_id": "cfg_b", "macro_ndcg_at_5": 0.91, "macro_mean_query_ms": 0.70},
        {"config_id": "cfg_c", "macro_ndcg_at_5": 0.89, "macro_mean_query_ms": 0.10},
    ]
    best = module.select_best_config(rows)
    assert best["config_id"] == "cfg_b"


def test_sweep_outputs_required_columns() -> None:
    """Sweep results include required aggregate output columns."""
    module = _load_sweep_module()
    reports = module.run_sweep(
        index=_mini_index(),
        queries=_queries(),
        qrels=_qrels(),
        configs=[
            {
                "config_id": "cfg_test",
                "k1": 1.5,
                "b": 0.75,
                "weights": {"quote_body": 1.0, "author": 3.0, "tag": 2.0},
            }
        ],
        run_count=2,
    )

    first = reports[0]
    assert set(first) >= {
        "config_id",
        "k1",
        "b",
        "weights",
        "macro_ndcg_at_5",
        "macro_mean_query_ms",
        "per_query",
    }


def test_best_config_selection_is_deterministic() -> None:
    """Tie-break selection is deterministic by config id."""
    module = _load_sweep_module()
    rows = [
        {"config_id": "cfg_b", "macro_ndcg_at_5": 0.95, "macro_mean_query_ms": 0.50},
        {"config_id": "cfg_a", "macro_ndcg_at_5": 0.95, "macro_mean_query_ms": 0.50},
    ]
    first = module.select_best_config(rows)
    second = module.select_best_config(rows)
    assert first["config_id"] == "cfg_a"
    assert second["config_id"] == "cfg_a"


def test_sweep_reports_macro_and_per_query() -> None:
    """Sweep evaluation reports macro metrics and per-query metrics."""
    module = _load_sweep_module()
    reports = module.run_sweep(
        index=_mini_index(),
        queries=_queries(),
        qrels=_qrels(),
        configs=[
            {
                "config_id": "cfg_test",
                "k1": 1.5,
                "b": 0.75,
                "weights": {"quote_body": 1.0, "author": 3.0, "tag": 2.0},
            }
        ],
        run_count=2,
    )

    report = reports[0]
    assert isinstance(report["per_query"], list)
    assert len(report["per_query"]) == 2
    assert "macro_ndcg_at_5" in report
    assert "macro_mean_query_ms" in report


def test_objective_trace_completeness() -> None:
    """All sweep objectives map to required tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES
