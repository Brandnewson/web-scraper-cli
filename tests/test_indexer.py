"""Indexer tests for Phase 3 TDD execution."""

from __future__ import annotations

from src.crawler import PageData
import src.indexer as indexer

REQUIRED_OBJECTIVES = {
    "posting_schema_single_doc_entry",
    "position_storage",
    "posting_ordering",
    "document_frequency",
    "field_length_averages",
    "doc_field_lengths_meta",
    "case_insensitive_tokenization",
    "single_page_corpus_handling",
}

REQUIRED_TEST_NAMES = {
    "test_posting_schema",
    "test_positions_stored",
    "test_posting_lists_sorted",
    "test_df_correct",
    "test_avgdl_correct",
    "test_doc_field_lengths",
    "test_case_insensitive",
    "test_single_page_corpus",
}

OBJECTIVE_TRACE = {
    "posting_schema_single_doc_entry": {"test_posting_schema"},
    "position_storage": {"test_positions_stored"},
    "posting_ordering": {"test_posting_lists_sorted"},
    "document_frequency": {"test_df_correct"},
    "field_length_averages": {"test_avgdl_correct"},
    "doc_field_lengths_meta": {"test_doc_field_lengths"},
    "case_insensitive_tokenization": {"test_case_insensitive"},
    "single_page_corpus_handling": {"test_single_page_corpus"},
}


def make_page(
    doc_id: int,
    *,
    url: str,
    quote_texts: list[str],
    authors: list[str],
    tags: list[str],
) -> PageData:
    """Create a PageData instance with explicit field values."""
    return PageData(
        url=url,
        doc_id=doc_id,
        quote_texts=quote_texts,
        authors=authors,
        tags=tags,
    )


def test_posting_schema() -> None:
    """Term in two fields yields one posting with nested field stats."""
    pages = [
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["Life is beautiful"],
            authors=["Life Author"],
            tags=["wisdom"],
        )
    ]

    built_index = indexer.build_index(pages)
    posting = built_index["terms"]["life"]["postings"][0]

    assert len(built_index["terms"]["life"]["postings"]) == 1
    assert posting["doc_id"] == 0
    assert set(posting["fields"].keys()) == {"quote_body", "author"}


def test_positions_stored() -> None:
    """Positions are stored as 0-indexed offsets within each field."""
    pages = [
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["Life life!"],
            authors=["Life"],
            tags=["life"],
        )
    ]

    built_index = indexer.build_index(pages)
    posting = built_index["terms"]["life"]["postings"][0]

    assert posting["fields"]["quote_body"]["positions"] == [0, 1]
    assert posting["fields"]["author"]["positions"] == [0]
    assert posting["fields"]["tag"]["positions"] == [0]


def test_posting_lists_sorted() -> None:
    """Posting lists are sorted by doc_id ascending."""
    pages = [
        make_page(
            2,
            url="https://quotes.toscrape.com/page/3/",
            quote_texts=["Truth appears"],
            authors=["A"],
            tags=[],
        ),
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["Truth appears"],
            authors=["B"],
            tags=[],
        ),
        make_page(
            1,
            url="https://quotes.toscrape.com/page/2/",
            quote_texts=["Truth appears"],
            authors=["C"],
            tags=[],
        ),
    ]

    built_index = indexer.build_index(pages)
    doc_ids = [posting["doc_id"] for posting in built_index["terms"]["truth"]["postings"]]
    assert doc_ids == [0, 1, 2]


def test_df_correct() -> None:
    """DF equals number of documents containing the term."""
    pages = [
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["Hope rises"],
            authors=["A"],
            tags=[],
        ),
        make_page(
            1,
            url="https://quotes.toscrape.com/page/2/",
            quote_texts=["No match"],
            authors=["B"],
            tags=[],
        ),
        make_page(
            2,
            url="https://quotes.toscrape.com/page/3/",
            quote_texts=["Hope again"],
            authors=["C"],
            tags=[],
        ),
        make_page(
            3,
            url="https://quotes.toscrape.com/page/4/",
            quote_texts=["Still no match"],
            authors=["D"],
            tags=[],
        ),
        make_page(
            4,
            url="https://quotes.toscrape.com/page/5/",
            quote_texts=["Tag only"],
            authors=["E"],
            tags=["hope"],
        ),
    ]

    built_index = indexer.build_index(pages)
    assert built_index["terms"]["hope"]["df"] == 3


def test_avgdl_correct() -> None:
    """Per-field average document lengths are computed correctly."""
    pages = [
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["a b c"],
            authors=["x y"],
            tags=["t1", "t2"],
        ),
        make_page(
            1,
            url="https://quotes.toscrape.com/page/2/",
            quote_texts=["d e"],
            authors=["z"],
            tags=["t3"],
        ),
    ]

    built_index = indexer.build_index(pages)
    fields_meta = built_index["_meta"]["fields"]

    assert fields_meta["quote_body"]["avgdl"] == 2.5
    assert fields_meta["author"]["avgdl"] == 1.5
    assert fields_meta["tag"]["avgdl"] == 1.5


def test_doc_field_lengths() -> None:
    """doc_field_lengths stores per-doc token counts for each field."""
    pages = [
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["a b", "c"],
            authors=["x y"],
            tags=["t1", "t2 t3"],
        )
    ]

    built_index = indexer.build_index(pages)
    assert built_index["_meta"]["doc_field_lengths"]["0"] == {
        "quote_body": 3,
        "author": 2,
        "tag": 3,
    }


def test_case_insensitive() -> None:
    """Tokenization lowercases terms for case-insensitive indexing."""
    pages = [
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["Life LIFE life"],
            authors=[],
            tags=[],
        )
    ]

    built_index = indexer.build_index(pages)
    assert "life" in built_index["terms"]
    assert "Life" not in built_index["terms"]
    assert built_index["terms"]["life"]["postings"][0]["fields"]["quote_body"]["tf"] == 3


def test_single_page_corpus() -> None:
    """Single-page corpus builds a valid index with correct metadata."""
    pages = [
        make_page(
            0,
            url="https://quotes.toscrape.com/page/1/",
            quote_texts=["Only page content"],
            authors=["Only Author"],
            tags=["solo"],
        )
    ]

    built_index = indexer.build_index(pages)
    assert built_index["_meta"]["num_docs"] == 1
    assert built_index["_meta"]["doc_urls"]["0"] == "https://quotes.toscrape.com/page/1/"
    assert built_index["terms"]["only"]["df"] == 1


def test_objective_trace_completeness() -> None:
    """Process validation: all indexer objectives map to required tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES

