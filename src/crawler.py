"""Crawler module for listing pages on quotes.toscrape.com."""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

POLITENESS_SECONDS = 6.0
REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_PAGES = 10
LISTING_PATH_PATTERN = re.compile(r"^/page/\d+/?$")

LOGGER = logging.getLogger(__name__)


@dataclass
class PageData:
    """Structured crawler output for one listing page."""

    url: str
    doc_id: int
    quote_texts: list[str]
    authors: list[str]
    tags: list[str]


def crawl(seed_url: str, max_pages: int = DEFAULT_MAX_PAGES) -> list[PageData]:
    """Crawl listing pages in BFS order and return extracted page data.

    Args:
        seed_url: Initial listing page URL.
        max_pages: Maximum number of successfully parsed listing pages.

    Returns:
        List of extracted `PageData` values in crawl order.
    """
    if max_pages <= 0:
        return []

    seed = _canonicalize_url(seed_url)
    queue: deque[str] = deque([seed])
    # Tracks URLs currently queued so we can avoid duplicates in O(1).
    queued: set[str] = {seed}
    visited: set[str] = set()
    pages: list[PageData] = []

    while queue and len(pages) < max_pages:
        current_url = queue.popleft()
        queued.discard(current_url)

        if current_url in visited:
            continue
        # Mark as visited before fetch so failed requests are not retried indefinitely.
        visited.add(current_url)

        response = _fetch(current_url)
        if response is None or response.status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        pages.append(_extract_page_data(current_url, len(pages), soup))

        for link_url in _extract_listing_links(soup, current_url):
            if link_url in visited or link_url in queued:
                continue
            queue.append(link_url)
            queued.add(link_url)

    return pages


def _fetch(url: str) -> requests.Response | None:
    """Fetch one URL with unconditional politeness sleep and exception handling."""
    # Politeness rule applies before every request attempt, regardless of outcome.
    time.sleep(POLITENESS_SECONDS)
    try:
        return requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        LOGGER.warning("Request failed for %s: %s", url, exc)
        return None


def _extract_page_data(url: str, doc_id: int, soup: BeautifulSoup) -> PageData:
    """Extract quote text, author names, and tags from one listing page soup."""
    quote_texts = [quote.get_text(strip=True) for quote in soup.select("div.quote span.text")]
    authors = [author.get_text(strip=True) for author in soup.select("div.quote small.author")]
    tags = [tag.get_text(strip=True) for tag in soup.select("div.quote div.tags a.tag")]
    return PageData(
        url=url,
        doc_id=doc_id,
        quote_texts=quote_texts,
        authors=authors,
        tags=tags,
    )


def _extract_listing_links(soup: BeautifulSoup, current_url: str) -> list[str]:
    """Extract unique, normalized listing links from a page."""
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not href:
            continue
        normalized_url = _canonicalize_url(urljoin(current_url, href))
        # Restrict traversal to listing pages only (/page/N/).
        if not _is_listing_url(normalized_url):
            continue
        if normalized_url in seen:
            continue
        seen.add(normalized_url)
        links.append(normalized_url)

    return links


def _is_listing_url(url: str) -> bool:
    """Return True if URL path is a listing page path of the form /page/N/."""
    path = urlparse(url).path
    return bool(LISTING_PATH_PATTERN.match(path))


def _canonicalize_url(url: str) -> str:
    """Normalize URL for stable queue/visited comparisons."""
    parsed = urlparse(url)
    path = parsed.path or "/"

    if LISTING_PATH_PATTERN.match(path) and not path.endswith("/"):
        # Normalize listing URLs to a single canonical form.
        path = f"{path}/"

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            "",
            "",
            "",
        )
    )
