"""BM25F scorer tests for Phase 4 TDD execution."""

from __future__ import annotations

import math

import src.search as search

REQUIRED_OBJECTIVES = {
    "bm25f_numeric_correctness",
    "bm25f_field_weight_effect",
    "bm25f_length_normalization_effect",
    "bm25f_missing_term_behavior",
    "bm25f_missing_doc_behavior",
}

REQUIRED_TEST_NAMES = {
    "test_bm25f_known_value",
    "test_bm25f_author_boost",
    "test_bm25f_length_penalty",
    "test_bm25f_missing_term_returns_zero",
    "test_bm25f_missing_doc_returns_zero",
}

OBJECTIVE_TRACE = {
    "bm25f_numeric_correctness": {"test_bm25f_known_value"},
    "bm25f_field_weight_effect": {"test_bm25f_author_boost"},
    "bm25f_length_normalization_effect": {"test_bm25f_length_penalty"},
    "bm25f_missing_term_behavior": {"test_bm25f_missing_term_returns_zero"},
    "bm25f_missing_doc_behavior": {"test_bm25f_missing_doc_returns_zero"},
}


def test_bm25f_known_value() -> None:
    """BM25F score matches hand-computed value for a controlled fixture."""
    index = {
        "_meta": {
            "num_docs": 10,
            "fields": {
                "quote_body": {"avgdl": 2.0, "weight": 1.0, "b": 0.75},
                "author": {"avgdl": 1.0, "weight": 3.0, "b": 0.75},
                "tag": {"avgdl": 1.0, "weight": 2.0, "b": 0.75},
            },
            "doc_field_lengths": {
                "0": {"quote_body": 2, "author": 1, "tag": 1},
            },
        },
        "terms": {
            "life": {
                "df": 2,
                "postings": [
                    {
                        "doc_id": 0,
                        "url": "https://quotes.toscrape.com/page/1/",
                        "fields": {
                            "quote_body": {"tf": 2, "positions": [0, 1]},
                            "author": {"tf": 1, "positions": [0]},
                        },
                    }
                ],
            }
        },
    }

    idf = math.log((10 - 2 + 0.5) / (2 + 0.5) + 1.0)
    pseudo_tf = 2.0 + 3.0
    expected = idf * pseudo_tf * (search.K1 + 1.0) / (pseudo_tf + search.K1)

    actual = search.score_bm25f("life", 0, index)
    # Allow small floating-point differences in the assertion.
    assert abs(actual - expected) <= 1e-6


def test_bm25f_author_boost() -> None:
    """Author-field hit scores higher than quote_body hit with same tf."""
    index = {
        "_meta": {
            "num_docs": 2,
            "fields": {
                "quote_body": {"avgdl": 1.0, "weight": 1.0, "b": 0.75},
                "author": {"avgdl": 1.0, "weight": 3.0, "b": 0.75},
                "tag": {"avgdl": 1.0, "weight": 2.0, "b": 0.75},
            },
            "doc_field_lengths": {
                "0": {"quote_body": 1, "author": 1, "tag": 1},
                "1": {"quote_body": 1, "author": 1, "tag": 1},
            },
        },
        "terms": {
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
        },
    }

    quote_score = search.score_bm25f("focus", 0, index)
    author_score = search.score_bm25f("focus", 1, index)
    assert author_score > quote_score


def test_bm25f_length_penalty() -> None:
    """Longer field length reduces score when tf is constant."""
    index = {
        "_meta": {
            "num_docs": 2,
            "fields": {
                "quote_body": {"avgdl": 2.0, "weight": 1.0, "b": 0.75},
                "author": {"avgdl": 1.0, "weight": 3.0, "b": 0.75},
                "tag": {"avgdl": 1.0, "weight": 2.0, "b": 0.75},
            },
            "doc_field_lengths": {
                "0": {"quote_body": 1, "author": 1, "tag": 1},
                "1": {"quote_body": 4, "author": 1, "tag": 1},
            },
        },
        "terms": {
            "depth": {
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
                        "fields": {"quote_body": {"tf": 2, "positions": [0, 1]}},
                    },
                ],
            }
        },
    }

    short_doc_score = search.score_bm25f("depth", 0, index)
    long_doc_score = search.score_bm25f("depth", 1, index)
    assert short_doc_score > long_doc_score


def test_bm25f_missing_term_returns_zero() -> None:
    """Unknown terms return zero score."""
    index = {
        "_meta": {"num_docs": 3, "fields": {}, "doc_field_lengths": {}},
        "terms": {},
    }
    assert search.score_bm25f("missing", 0, index) == 0.0


def test_bm25f_missing_doc_returns_zero() -> None:
    """Term with no posting for doc_id returns zero score."""
    index = {
        "_meta": {
            "num_docs": 3,
            "fields": {
                "quote_body": {"avgdl": 1.0, "weight": 1.0, "b": 0.75},
            },
            "doc_field_lengths": {
                "1": {"quote_body": 1},
            },
        },
        "terms": {
            "known": {
                "df": 1,
                "postings": [
                    {
                        "doc_id": 1,
                        "url": "https://quotes.toscrape.com/page/2/",
                        "fields": {"quote_body": {"tf": 1, "positions": [0]}},
                    }
                ],
            }
        },
    }
    assert search.score_bm25f("known", 99, index) == 0.0


def test_objective_trace_completeness() -> None:
    """Process validation: all BM25F objectives map to required tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES

