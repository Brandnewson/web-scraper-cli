"""Crawler tests for Phase 2 TDD execution."""

from __future__ import annotations

import time
from collections.abc import Iterable
from unittest.mock import Mock, patch

import pytest
import requests

import src.crawler as crawler

BASE_URL = "https://quotes.toscrape.com"

REQUIRED_OBJECTIVES = {
    "crawl_listing_bfs",
    "politeness_unconditional",
    "error_handling_continuation",
    "field_extraction",
    "doc_id_sequential",
    "scope_enforcement_non_listing",
    "max_pages_stop",
    "process_benchmark_rehearsal",
}

REQUIRED_TEST_NAMES = {
    "test_bfs_visits_all_pages",
    "test_politeness_on_success",
    "test_politeness_on_error",
    "test_politeness_on_404",
    "test_skips_non_listing_pages",
    "test_stops_at_max_pages",
    "test_handles_timeout",
    "test_extracts_fields_correctly",
    "test_doc_id_sequential",
    "test_process_benchmark_rehearsal",
}

OBJECTIVE_TRACE = {
    "crawl_listing_bfs": {"test_bfs_visits_all_pages"},
    "politeness_unconditional": {
        "test_politeness_on_success",
        "test_politeness_on_error",
        "test_politeness_on_404",
    },
    "error_handling_continuation": {"test_handles_timeout"},
    "field_extraction": {"test_extracts_fields_correctly"},
    "doc_id_sequential": {"test_doc_id_sequential"},
    "scope_enforcement_non_listing": {"test_skips_non_listing_pages"},
    "max_pages_stop": {"test_stops_at_max_pages"},
    "process_benchmark_rehearsal": {"test_process_benchmark_rehearsal"},
}


def page_url(page_num: int) -> str:
    """Return an absolute listing URL for a page number."""
    return f"{BASE_URL}/page/{page_num}/"


def make_response(url: str, html: str, status_code: int = 200) -> Mock:
    """Build a minimal mocked requests.Response-like object."""
    response = Mock()
    response.url = url
    response.status_code = status_code
    response.text = html
    return response


def make_listing_html(
    listing_links: Iterable[int] = (),
    *,
    quote_text: str = '"Example quote"',
    author: str = "Example Author",
    tags: Iterable[str] = ("example",),
    extra_links: Iterable[str] = (),
) -> str:
    """Build deterministic listing-page HTML with quote fields and links."""
    page_links = "".join(
        f'<a href="/page/{page_num}/">Page {page_num}</a>' for page_num in listing_links
    )
    non_listing_links = "".join(
        f'<a href="{href}">Non listing</a>' for href in extra_links
    )
    tag_links = "".join(f'<a class="tag">{tag}</a>' for tag in tags)
    return f"""
    <html>
      <body>
        {page_links}
        {non_listing_links}
        <div class="quote">
          <span class="text">{quote_text}</span>
          <small class="author">{author}</small>
          <div class="tags">{tag_links}</div>
        </div>
      </body>
    </html>
    """


def test_bfs_visits_all_pages() -> None:
    """Crawler visits all listing pages in BFS order."""
    graph = {
        1: [2, 3],
        2: [4, 5],
        3: [6, 7],
        4: [8, 9],
        5: [10],
        6: [],
        7: [],
        8: [],
        9: [],
        10: [],
    }
    html_by_url = {
        page_url(page_num): make_listing_html(
            links, quote_text=f'"Quote {page_num}"', author=f"Author {page_num}"
        )
        for page_num, links in graph.items()
    }

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        return make_response(url, html_by_url[url], status_code=200)

    with patch("src.crawler.time.sleep"), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ):
        pages = crawler.crawl(page_url(1), max_pages=10)

    assert len(pages) == 10
    assert [page.url for page in pages] == [page_url(i) for i in range(1, 11)]


def test_politeness_on_success() -> None:
    """Sleep is called before each successful request."""
    events: list[str] = []
    html_by_url = {
        page_url(1): make_listing_html([2]),
        page_url(2): make_listing_html([]),
    }

    def sleep_side_effect(seconds: float) -> None:
        events.append(f"sleep:{seconds}")

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        events.append(f"get:{url}")
        return make_response(url, html_by_url[url], status_code=200)

    with patch("src.crawler.time.sleep", side_effect=sleep_side_effect), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ):
        crawler.crawl(page_url(1), max_pages=2)

    assert events == [
        f"sleep:{crawler.POLITENESS_SECONDS}",
        f"get:{page_url(1)}",
        f"sleep:{crawler.POLITENESS_SECONDS}",
        f"get:{page_url(2)}",
    ]


def test_politeness_on_error() -> None:
    """Sleep is called before requests that raise exceptions."""
    events: list[str] = []

    def sleep_side_effect(seconds: float) -> None:
        events.append(f"sleep:{seconds}")

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        events.append(f"get:{url}")
        raise requests.ConnectionError("boom")

    with patch("src.crawler.time.sleep", side_effect=sleep_side_effect), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ):
        pages = crawler.crawl(page_url(1), max_pages=1)

    assert pages == []
    assert events == [f"sleep:{crawler.POLITENESS_SECONDS}", f"get:{page_url(1)}"]


def test_politeness_on_404() -> None:
    """Sleep is called before requests that return non-200 responses."""
    events: list[str] = []

    def sleep_side_effect(seconds: float) -> None:
        events.append(f"sleep:{seconds}")

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        events.append(f"get:{url}")
        return make_response(url, "<html></html>", status_code=404)

    with patch("src.crawler.time.sleep", side_effect=sleep_side_effect), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ):
        pages = crawler.crawl(page_url(1), max_pages=1)

    assert pages == []
    assert events == [f"sleep:{crawler.POLITENESS_SECONDS}", f"get:{page_url(1)}"]


def test_skips_non_listing_pages() -> None:
    """Crawler does not follow author or tag links."""
    html_by_url = {
        page_url(1): make_listing_html(
            [2],
            extra_links=(
                "/author/albert-einstein/",
                "/tag/life/",
            ),
        ),
        page_url(2): make_listing_html([]),
    }

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        return make_response(url, html_by_url[url], status_code=200)

    with patch("src.crawler.time.sleep"), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ) as mock_get:
        crawler.crawl(page_url(1), max_pages=10)

    fetched_urls = [call.args[0] for call in mock_get.call_args_list]
    assert fetched_urls == [page_url(1), page_url(2)]


def test_stops_at_max_pages() -> None:
    """Crawler does not fetch beyond max_pages."""
    html_by_url = {
        page_url(1): make_listing_html([2]),
        page_url(2): make_listing_html([3]),
        page_url(3): make_listing_html([4]),
        page_url(4): make_listing_html([]),
    }

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        return make_response(url, html_by_url[url], status_code=200)

    with patch("src.crawler.time.sleep"), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ) as mock_get:
        pages = crawler.crawl(page_url(1), max_pages=3)

    assert len(pages) == 3
    assert [page.url for page in pages] == [page_url(1), page_url(2), page_url(3)]
    assert mock_get.call_count == 3


def test_handles_timeout() -> None:
    """Timeouts are handled and crawl continues without crashing."""
    html_by_url = {
        page_url(1): make_listing_html([2]),
    }

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        if url == page_url(2):
            raise requests.Timeout("timed out")
        return make_response(url, html_by_url[url], status_code=200)

    with patch("src.crawler.time.sleep"), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ):
        pages = crawler.crawl(page_url(1), max_pages=3)

    assert [page.url for page in pages] == [page_url(1)]


def test_extracts_fields_correctly() -> None:
    """Crawler extracts quote text, authors, and tags from listing pages."""
    html = """
    <html>
      <body>
        <div class="quote">
          <span class="text">"Quote one"</span>
          <small class="author">Author One</small>
          <div class="tags">
            <a class="tag">inspire</a>
            <a class="tag">life</a>
          </div>
        </div>
        <div class="quote">
          <span class="text">"Quote two"</span>
          <small class="author">Author Two</small>
          <div class="tags">
            <a class="tag">truth</a>
          </div>
        </div>
      </body>
    </html>
    """

    with patch("src.crawler.time.sleep"), patch(
        "src.crawler.requests.get",
        return_value=make_response(page_url(1), html, status_code=200),
    ):
        pages = crawler.crawl(page_url(1), max_pages=1)

    assert len(pages) == 1
    assert pages[0].quote_texts == ['"Quote one"', '"Quote two"']
    assert pages[0].authors == ["Author One", "Author Two"]
    assert pages[0].tags == ["inspire", "life", "truth"]


def test_doc_id_sequential() -> None:
    """doc_id values are sequential in crawl order."""
    html_by_url = {
        page_url(1): make_listing_html([2]),
        page_url(2): make_listing_html([]),
    }

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        return make_response(url, html_by_url[url], status_code=200)

    with patch("src.crawler.time.sleep"), patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ):
        pages = crawler.crawl(page_url(1), max_pages=2)

    assert [page.doc_id for page in pages] == [0, 1]


def test_process_benchmark_rehearsal() -> None:
    """Benchmark rehearsal captures timing and politeness metadata."""
    html_by_url = {
        page_url(1): make_listing_html([2]),
        page_url(2): make_listing_html([3]),
        page_url(3): make_listing_html([]),
    }

    def get_side_effect(url: str, timeout: float, allow_redirects: bool) -> Mock:
        return make_response(url, html_by_url[url], status_code=200)

    with patch("src.crawler.time.sleep") as mock_sleep, patch(
        "src.crawler.requests.get", side_effect=get_side_effect
    ) as mock_get:
        started = time.perf_counter()
        pages = crawler.crawl(page_url(1), max_pages=3)
        elapsed_ms = (time.perf_counter() - started) * 1000

    request_attempts = mock_get.call_count
    expected_politeness_lb_seconds = request_attempts * crawler.POLITENESS_SECONDS

    print("\n| benchmark_name | configuration | result | units | run_count |")
    print("|---|---|---:|---|---:|")
    print(
        "| phase2_crawl_process_rehearsal | "
        f"mocked_http,max_pages=3,attempts={request_attempts},"
        f"expected_politeness_lb_s={expected_politeness_lb_seconds:.1f} | "
        f"{elapsed_ms:.3f} | ms | 1 |"
    )

    assert len(pages) == 3
    assert request_attempts == 3
    assert mock_sleep.call_count == request_attempts
    assert expected_politeness_lb_seconds == 18.0
    assert elapsed_ms >= 0.0


def test_objective_trace_completeness() -> None:
    """Process validation: all crawler objectives are mapped to crawler tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES

