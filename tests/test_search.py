"""Search tests for BM25F and DAAT/skip primitives."""

from __future__ import annotations

import math
import statistics
import time

import src.search as search

REQUIRED_OBJECTIVES = {
    "bm25f_numeric_correctness",
    "bm25f_field_weight_effect",
    "bm25f_length_normalization_effect",
    "bm25f_missing_term_behavior",
    "bm25f_missing_doc_behavior",
    "skip_pointer_building",
    "skip_pointer_advance",
    "daat_single_term_intersection",
    "daat_multi_term_intersection",
    "daat_no_result_intersection",
    "daat_empty_input_behavior",
    "skip_pointer_empty_input_behavior",
    "skip_pointer_exhaust_behavior",
    "spell_distance_exact_match",
    "spell_distance_single_edit",
    "spell_distance_transposition",
    "spell_suggest_close_match",
    "spell_suggest_no_match",
    "spell_suggest_max_distance",
    "spell_did_you_mean_format",
    "spell_did_you_mean_no_change",
    "skip_pointer_speedup_benchmark",
}

REQUIRED_TEST_NAMES = {
    "test_bm25f_known_value",
    "test_bm25f_author_boost",
    "test_bm25f_length_penalty",
    "test_bm25f_missing_term_returns_zero",
    "test_bm25f_missing_doc_returns_zero",
    "test_skip_pointer_build",
    "test_skip_pointer_advance",
    "test_daat_single_term",
    "test_daat_multi_term_and",
    "test_daat_no_results",
    "test_skip_pointer_build_empty_list",
    "test_advance_with_skips_exhausts_raises_stopiteration",
    "test_daat_empty_input_lists_returns_empty",
    "test_levenshtein_exact",
    "test_levenshtein_one_edit",
    "test_levenshtein_transpose",
    "test_suggest_finds_close",
    "test_suggest_no_match",
    "test_suggest_max_dist",
    "test_did_you_mean_format",
    "test_did_you_mean_no_replacement_returns_none",
    "test_skip_pointer_vs_linear",
}

OBJECTIVE_TRACE = {
    "bm25f_numeric_correctness": {"test_bm25f_known_value"},
    "bm25f_field_weight_effect": {"test_bm25f_author_boost"},
    "bm25f_length_normalization_effect": {"test_bm25f_length_penalty"},
    "bm25f_missing_term_behavior": {"test_bm25f_missing_term_returns_zero"},
    "bm25f_missing_doc_behavior": {"test_bm25f_missing_doc_returns_zero"},
    "skip_pointer_building": {"test_skip_pointer_build"},
    "skip_pointer_advance": {"test_skip_pointer_advance"},
    "daat_single_term_intersection": {"test_daat_single_term"},
    "daat_multi_term_intersection": {"test_daat_multi_term_and"},
    "daat_no_result_intersection": {"test_daat_no_results"},
    "daat_empty_input_behavior": {"test_daat_empty_input_lists_returns_empty"},
    "skip_pointer_empty_input_behavior": {"test_skip_pointer_build_empty_list"},
    "skip_pointer_exhaust_behavior": {"test_advance_with_skips_exhausts_raises_stopiteration"},
    "spell_distance_exact_match": {"test_levenshtein_exact"},
    "spell_distance_single_edit": {"test_levenshtein_one_edit"},
    "spell_distance_transposition": {"test_levenshtein_transpose"},
    "spell_suggest_close_match": {"test_suggest_finds_close"},
    "spell_suggest_no_match": {"test_suggest_no_match"},
    "spell_suggest_max_distance": {"test_suggest_max_dist"},
    "spell_did_you_mean_format": {"test_did_you_mean_format"},
    "spell_did_you_mean_no_change": {"test_did_you_mean_no_replacement_returns_none"},
    "skip_pointer_speedup_benchmark": {"test_skip_pointer_vs_linear"},
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


def _make_postings(doc_ids: list[int]) -> list[dict]:
    """Build minimal posting dict list for DAAT/skip tests."""
    return [
        {"doc_id": doc_id, "url": f"https://quotes.toscrape.com/page/{doc_id}/", "fields": {}}
        for doc_id in doc_ids
    ]


def _advance_linear(postings: list[dict], ptr: int, target: int) -> int:
    """Advance pointer linearly to first doc_id >= target."""
    current_ptr = ptr
    while current_ptr < len(postings) and postings[current_ptr]["doc_id"] < target:
        current_ptr += 1

    if current_ptr >= len(postings):
        raise StopIteration
    return current_ptr


def _time_linear_advance(postings: list[dict], target: int, iterations: int) -> float:
    """Measure linear pointer-advance time in milliseconds."""
    start = time.perf_counter()
    for _ in range(iterations):
        _advance_linear(postings, ptr=0, target=target)
    return (time.perf_counter() - start) * 1000.0


def _time_skip_advance(
    postings: list[dict],
    skips: list[tuple[int, int]],
    target: int,
    iterations: int,
) -> float:
    """Measure skip-pointer pointer-advance time in milliseconds."""
    start = time.perf_counter()
    for _ in range(iterations):
        search.advance_with_skips(postings, skips, ptr=0, target=target)
    return (time.perf_counter() - start) * 1000.0


def test_skip_pointer_build() -> None:
    """Skip pointers are emitted at sqrt-spaced indices."""
    postings = _make_postings(list(range(100)))
    skips = search.build_skip_pointers(postings)

    expected = [(doc_id, doc_id) for doc_id in range(0, 100, 10)]
    assert skips == expected


def test_skip_pointer_build_empty_list() -> None:
    """Empty postings produce an empty skip list."""
    assert search.build_skip_pointers([]) == []


def test_skip_pointer_advance() -> None:
    """Skip-based advance lands on first doc_id >= target."""
    postings = _make_postings([0, 2, 4, 6, 8, 10, 12, 14])
    skips = search.build_skip_pointers(postings)

    new_ptr = search.advance_with_skips(postings, skips, ptr=0, target=11)
    assert postings[new_ptr]["doc_id"] == 12


def test_advance_with_skips_exhausts_raises_stopiteration() -> None:
    """Advance raises StopIteration when target is beyond list end."""
    postings = _make_postings([1, 3, 5])
    skips = search.build_skip_pointers(postings)

    try:
        search.advance_with_skips(postings, skips, ptr=0, target=9)
        raised = False
    except StopIteration:
        raised = True
    assert raised


def test_daat_single_term() -> None:
    """Single posting list returns all doc_ids in order."""
    posting_lists = [_make_postings([1, 3, 5])]
    skip_lists = [search.build_skip_pointers(posting_lists[0])]

    assert search.daat_and_merge(posting_lists, skip_lists) == [1, 3, 5]


def test_daat_multi_term_and() -> None:
    """DAAT AND returns only shared doc_ids across all lists."""
    posting_lists = [
        _make_postings([1, 2, 4, 7]),
        _make_postings([2, 4, 5, 7]),
        _make_postings([0, 2, 4, 7, 9]),
    ]
    skip_lists = [search.build_skip_pointers(postings) for postings in posting_lists]

    assert search.daat_and_merge(posting_lists, skip_lists) == [2, 4, 7]


def test_daat_no_results() -> None:
    """DAAT AND returns empty when no shared doc_ids exist."""
    posting_lists = [
        _make_postings([1, 3, 5]),
        _make_postings([2, 4, 6]),
    ]
    skip_lists = [search.build_skip_pointers(postings) for postings in posting_lists]

    assert search.daat_and_merge(posting_lists, skip_lists) == []


def test_daat_empty_input_lists_returns_empty() -> None:
    """DAAT AND returns empty for empty input list collection."""
    assert search.daat_and_merge([], []) == []


def test_skip_pointer_vs_linear() -> None:
    """Skip-pointer advance beats linear advance on a 10,000-posting synthetic list."""
    postings = _make_postings(list(range(0, 20_000, 2)))
    skips = search.build_skip_pointers(postings)
    target = postings[-2]["doc_id"]
    iterations = 1_000
    trial_count = 5

    linear_trials = [
        _time_linear_advance(postings, target=target, iterations=iterations)
        for _ in range(trial_count)
    ]
    skip_trials = [
        _time_skip_advance(postings, skips, target=target, iterations=iterations)
        for _ in range(trial_count)
    ]

    median_linear_ms = statistics.median(linear_trials)
    median_skip_ms = statistics.median(skip_trials)
    speedup = median_linear_ms / median_skip_ms

    print(
        "\n| benchmark_name | configuration | result | baseline_result | delta | units | run_count |"
    )
    print("|---|---|---|---|---|---|---|")
    print(
        "| skip_pointer_vs_linear "
        "| N=10000,target_near_tail,iterations=1000,metric=median_over_5 "
        f"| {median_skip_ms:.3f} | {median_linear_ms:.3f} | {speedup:.2f}x | ms | {trial_count} |"
    )

    assert median_skip_ms < median_linear_ms


def test_levenshtein_exact() -> None:
    """Exact matches have zero edit distance."""
    assert search.levenshtein("cat", "cat") == 0


def test_levenshtein_one_edit() -> None:
    """Single substitution has edit distance one."""
    assert search.levenshtein("cat", "car") == 1


def test_levenshtein_transpose() -> None:
    """Adjacent transposition counts as one edit (Damerau behavior)."""
    assert search.levenshtein("teh", "the") == 1


def test_suggest_finds_close() -> None:
    """Closest vocabulary term is returned within max distance."""
    vocabulary = {"environment", "friend", "truth"}
    assert search.suggest("environmnt", vocabulary, max_dist=2) == "environment"


def test_suggest_no_match() -> None:
    """No suggestion is returned when nothing is within max distance."""
    vocabulary = {"environment", "friend", "truth"}
    assert search.suggest("xyzxyzxyz", vocabulary, max_dist=2) is None


def test_suggest_max_dist() -> None:
    """Candidates outside max distance are not returned."""
    vocabulary = {"environment"}
    assert search.suggest("enviroxyz", vocabulary, max_dist=2) is None


def test_did_you_mean_format() -> None:
    """Did-you-mean returns the required formatted full-query suggestion."""
    index = {
        "terms": {
            "good": {"df": 1, "postings": []},
            "friends": {"df": 1, "postings": []},
        }
    }
    suggestion = search.did_you_mean(["goood", "frends"], index)
    assert suggestion == 'Did you mean: "good friends"?'


def test_did_you_mean_no_replacement_returns_none() -> None:
    """Did-you-mean returns None when no replacements are made."""
    index = {
        "terms": {
            "good": {"df": 1, "postings": []},
            "friends": {"df": 1, "postings": []},
        }
    }
    assert search.did_you_mean(["good", "friends"], index) is None


def test_objective_trace_completeness() -> None:
    """Process validation: all phase objectives map to required tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES
