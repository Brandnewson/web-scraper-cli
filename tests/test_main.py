"""CLI orchestration tests for Phase 7 TDD execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from src.crawler import PageData
import src.main as main

REQUIRED_OBJECTIVES = {
    "cli_build_persistence_and_stats",
    "cli_load_success",
    "cli_load_missing_file_error",
    "cli_load_invalid_json_error",
    "cli_print_aggregated_term_output",
    "cli_print_unknown_term",
    "cli_find_single_term_ranking",
    "cli_find_multi_term_and",
    "cli_find_no_results_spell_suggestion",
    "cli_find_empty_usage",
    "cli_quit_exit_behavior",
}

REQUIRED_TEST_NAMES = {
    "test_build_writes_index_and_prints_stats",
    "test_load_success",
    "test_load_missing_file_prints_clear_error",
    "test_load_invalid_json_prints_clear_error",
    "test_print_existing_term_aggregates_fields_tf_positions",
    "test_print_unknown_term",
    "test_find_single_term_returns_ranked_results",
    "test_find_multi_term_and_only_shared_docs",
    "test_find_no_results_shows_did_you_mean",
    "test_find_empty_args_prints_usage",
    "test_quit_exit_terminates_loop",
}

OBJECTIVE_TRACE = {
    "cli_build_persistence_and_stats": {"test_build_writes_index_and_prints_stats"},
    "cli_load_success": {"test_load_success"},
    "cli_load_missing_file_error": {"test_load_missing_file_prints_clear_error"},
    "cli_load_invalid_json_error": {"test_load_invalid_json_prints_clear_error"},
    "cli_print_aggregated_term_output": {"test_print_existing_term_aggregates_fields_tf_positions"},
    "cli_print_unknown_term": {"test_print_unknown_term"},
    "cli_find_single_term_ranking": {"test_find_single_term_returns_ranked_results"},
    "cli_find_multi_term_and": {"test_find_multi_term_and_only_shared_docs"},
    "cli_find_no_results_spell_suggestion": {"test_find_no_results_shows_did_you_mean"},
    "cli_find_empty_usage": {"test_find_empty_args_prints_usage"},
    "cli_quit_exit_behavior": {"test_quit_exit_terminates_loop"},
}


def _run_session(commands: list[str]) -> list[str]:
    """Run a CLI session and collect printed output lines."""
    outputs: list[str] = []
    iterator = iter(commands)

    def fake_input() -> str:
        try:
            return next(iterator)
        except StopIteration as exc:
            raise EOFError from exc

    main.run_repl(input_fn=fake_input, output_fn=outputs.append)
    return outputs


def _write_index(path: Path, index: dict) -> None:
    """Write JSON index fixture to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index), encoding="utf-8")


def _base_index() -> dict:
    """Return a minimal valid index fixture."""
    return {
        "_meta": {
            "num_docs": 2,
            "built_at": "2026-04-11T12:00:00+00:00",
            "schema_version": 1,
            "fields": {
                "quote_body": {"avgdl": 2.0, "weight": 1.0, "b": 0.75},
                "author": {"avgdl": 1.0, "weight": 3.0, "b": 0.75},
                "tag": {"avgdl": 1.0, "weight": 2.0, "b": 0.75},
            },
            "doc_field_lengths": {
                "0": {"quote_body": 2, "author": 1, "tag": 1},
                "1": {"quote_body": 2, "author": 1, "tag": 1},
            },
            "doc_urls": {
                "0": "https://quotes.toscrape.com/page/1/",
                "1": "https://quotes.toscrape.com/page/2/",
            },
        },
        "terms": {},
    }


def test_build_writes_index_and_prints_stats(tmp_path: Path) -> None:
    """Build command writes index file and prints timing/size stats."""
    pages = [
        PageData(
            url="https://quotes.toscrape.com/page/1/",
            doc_id=0,
            quote_texts=["One"],
            authors=["A"],
            tags=["t"],
        )
    ]
    built_index = _base_index()
    built_index["terms"] = {"one": {"df": 1, "postings": []}}

    with patch.object(main, "INDEX_PATH", tmp_path / "data" / "index.json"), patch(
        "src.main.crawler.crawl", return_value=pages
    ), patch("src.main.indexer.build_index", return_value=built_index):
        outputs = _run_session(["build", "quit"])

    assert (tmp_path / "data" / "index.json").exists()
    assert any("Starting build..." in line for line in outputs)
    assert any("Crawl complete." in line for line in outputs)
    assert any("Index saved to data/index.json." in line for line in outputs)
    assert any("Crawl:" in line and "Index:" in line and "Total:" in line for line in outputs)
    assert any("docs" in line and "terms" in line for line in outputs)


def test_load_success(tmp_path: Path) -> None:
    """Load command reads a valid index and confirms success."""
    index = _base_index()
    index_path = tmp_path / "data" / "index.json"
    _write_index(index_path, index)

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "quit"])

    assert outputs[0] == "Tip: type 'quit' or 'exit' to leave the CLI."
    assert "Loaded index from data/index.json." in outputs


def test_load_missing_file_prints_clear_error(tmp_path: Path) -> None:
    """Load on missing file prints clear error and keeps REPL alive."""
    with patch.object(main, "INDEX_PATH", tmp_path / "data" / "index.json"):
        outputs = _run_session(["load", "quit"])

    assert any("Error:" in line and "not found" in line for line in outputs)


def test_load_invalid_json_prints_clear_error(tmp_path: Path) -> None:
    """Load on invalid JSON prints clear error and keeps REPL alive."""
    index_path = tmp_path / "data" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("{not-json", encoding="utf-8")

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "quit"])

    assert any("Error:" in line and "not valid JSON" in line for line in outputs)


def test_print_existing_term_aggregates_fields_tf_positions(tmp_path: Path) -> None:
    """Print command aggregates tf and positions across fields for one doc."""
    index = _base_index()
    index["terms"] = {
        "life": {
            "df": 1,
            "postings": [
                {
                    "doc_id": 0,
                    "url": "https://quotes.toscrape.com/page/1/",
                    "fields": {
                        "quote_body": {"tf": 2, "positions": [2, 4]},
                        "tag": {"tf": 1, "positions": [1]},
                    },
                }
            ],
        }
    }
    index_path = tmp_path / "data" / "index.json"
    _write_index(index_path, index)

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "print life", "quit"])

    assert "Term: life  (df: 1)" in outputs
    assert any(
        "tf=3" in line and "pos=[1, 2, 4]" in line and "fields=[quote_body, tag]" in line
        for line in outputs
    )


def test_print_unknown_term(tmp_path: Path) -> None:
    """Print command reports unknown term without crashing."""
    index_path = tmp_path / "data" / "index.json"
    _write_index(index_path, _base_index())

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "print unknown", "quit"])

    assert "Term not found" in outputs


def test_find_single_term_returns_ranked_results(tmp_path: Path) -> None:
    """Find returns ranked results for one term."""
    index = _base_index()
    index["terms"] = {
        "focus": {
            "df": 2,
            "postings": [
                {
                    "doc_id": 0,
                    "url": "https://quotes.toscrape.com/page/1/",
                    "fields": {"quote_body": {"tf": 1, "positions": [0]}},
                },
                {
                    "doc_id": 1,
                    "url": "https://quotes.toscrape.com/page/2/",
                    "fields": {"author": {"tf": 1, "positions": [0]}},
                },
            ],
        }
    }
    index_path = tmp_path / "data" / "index.json"
    _write_index(index_path, index)

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "find focus", "quit"])

    assert any('Results for "focus" (1 terms, AND):' in line for line in outputs)
    ranking_lines = [line for line in outputs if line.startswith("  1.") or line.startswith("  2.")]
    assert ranking_lines[0].startswith("  1. https://quotes.toscrape.com/page/2/")


def test_find_multi_term_and_only_shared_docs(tmp_path: Path) -> None:
    """Find with multi-term query returns only shared documents."""
    index = _base_index()
    index["terms"] = {
        "good": {
            "df": 2,
            "postings": [
                {
                    "doc_id": 0,
                    "url": "https://quotes.toscrape.com/page/1/",
                    "fields": {"quote_body": {"tf": 1, "positions": [0]}},
                },
                {
                    "doc_id": 1,
                    "url": "https://quotes.toscrape.com/page/2/",
                    "fields": {"quote_body": {"tf": 1, "positions": [0]}},
                },
            ],
        },
        "friends": {
            "df": 1,
            "postings": [
                {
                    "doc_id": 1,
                    "url": "https://quotes.toscrape.com/page/2/",
                    "fields": {"quote_body": {"tf": 1, "positions": [1]}},
                }
            ],
        },
    }
    index_path = tmp_path / "data" / "index.json"
    _write_index(index_path, index)

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "find good friends", "quit"])

    ranking_lines = [line for line in outputs if line.startswith("  1.") or line.startswith("  2.")]
    assert len(ranking_lines) == 1
    assert "https://quotes.toscrape.com/page/2/" in ranking_lines[0]


def test_find_no_results_shows_did_you_mean(tmp_path: Path) -> None:
    """No-result find path prints did-you-mean suggestion when available."""
    index = _base_index()
    index["terms"] = {
        "good": {"df": 1, "postings": []},
        "friends": {"df": 1, "postings": []},
    }
    index_path = tmp_path / "data" / "index.json"
    _write_index(index_path, index)

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "find goood frends", "quit"])

    assert 'Did you mean: "good friends"?' in outputs


def test_find_empty_args_prints_usage(tmp_path: Path) -> None:
    """Find with no arguments prints usage hint."""
    index_path = tmp_path / "data" / "index.json"
    _write_index(index_path, _base_index())

    with patch.object(main, "INDEX_PATH", index_path):
        outputs = _run_session(["load", "find", "quit"])

    assert "Usage: find <query>" in outputs


def test_quit_exit_terminates_loop() -> None:
    """Quit command stops loop without executing later commands."""
    outputs = _run_session(["quit", "build"])
    assert outputs == ["Tip: type 'quit' or 'exit' to leave the CLI."]


def test_objective_trace_completeness() -> None:
    """Process validation: all CLI objectives map to required tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES
