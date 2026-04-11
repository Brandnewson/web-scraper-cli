"""Field-aware inverted index builder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from src.crawler import PageData

TOKEN_SPLIT_PATTERN = re.compile(r"[^a-z0-9]+")
SCHEMA_VERSION = 1
DEFAULT_FIELD_B = 0.75

FIELD_NAMES = ("quote_body", "author", "tag")
FIELD_WEIGHTS = {
    "quote_body": 1.0,
    "author": 3.0,
    "tag": 2.0,
}
FIELD_B_VALUES = {
    field_name: DEFAULT_FIELD_B for field_name in FIELD_NAMES
}


@dataclass
class FieldStats:
    """Per-field term statistics in one document."""

    tf: int
    positions: list[int]


@dataclass
class Posting:
    """Per-document posting for one term."""

    doc_id: int
    url: str
    fields: dict[str, FieldStats]


def build_index(pages: list[PageData]) -> dict:
    """Build the index dictionary from crawled page data.

    Args:
        pages: Crawler output pages in any order.

    Returns:
        Index dictionary matching the architecture schema.
    """
    term_postings: dict[str, dict[int, Posting]] = {}
    doc_field_lengths: dict[str, dict[str, int]] = {}
    doc_urls: dict[str, str] = {}
    field_length_totals = {field_name: 0 for field_name in FIELD_NAMES}

    for page in pages:
        tokens_by_field = _tokens_by_field(page)
        doc_key = str(page.doc_id)

        doc_urls[doc_key] = page.url
        doc_field_lengths[doc_key] = {
            field_name: len(tokens_by_field[field_name]) for field_name in FIELD_NAMES
        }

        for field_name in FIELD_NAMES:
            field_length_totals[field_name] += doc_field_lengths[doc_key][field_name]

        _add_page_terms(term_postings, page, tokens_by_field)

    terms = _build_terms_output(term_postings)
    num_docs = len(pages)
    fields_meta = _build_fields_meta(field_length_totals, num_docs)

    return {
        "_meta": {
            "num_docs": num_docs,
            "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "schema_version": SCHEMA_VERSION,
            "fields": fields_meta,
            "doc_field_lengths": doc_field_lengths,
            "doc_urls": doc_urls,
        },
        "terms": terms,
    }


def _tokens_by_field(page: PageData) -> dict[str, list[str]]:
    """Return token lists for all indexable fields on a page."""
    return {
        "quote_body": _tokenize(" ".join(page.quote_texts)),
        "author": _tokenize(" ".join(page.authors)),
        "tag": _tokenize(" ".join(page.tags)),
    }


def _tokenize(text: str) -> list[str]:
    """Tokenize text using lowercase and regex split."""
    lowered = text.lower()
    raw_tokens = TOKEN_SPLIT_PATTERN.split(lowered)
    return [token for token in raw_tokens if token]


def _add_page_terms(
    term_postings: dict[str, dict[int, Posting]],
    page: PageData,
    tokens_by_field: dict[str, list[str]],
) -> None:
    """Update in-memory postings with all terms from one page."""
    for field_name, tokens in tokens_by_field.items():
        for position, term in enumerate(tokens):
            doc_postings = term_postings.setdefault(term, {})
            posting = doc_postings.get(page.doc_id)

            # Keep one posting per (term, doc_id); field data is nested.
            if posting is None:
                posting = Posting(doc_id=page.doc_id, url=page.url, fields={})
                doc_postings[page.doc_id] = posting

            field_stats = posting.fields.get(field_name)
            if field_stats is None:
                field_stats = FieldStats(tf=0, positions=[])
                posting.fields[field_name] = field_stats

            field_stats.tf += 1
            field_stats.positions.append(position)


def _build_terms_output(term_postings: dict[str, dict[int, Posting]]) -> dict:
    """Build JSON-compatible terms section from posting dataclasses."""
    terms: dict[str, dict] = {}

    for term in sorted(term_postings):
        postings = sorted(term_postings[term].values(), key=lambda posting: posting.doc_id)
        terms[term] = {
            "df": len(postings),
            "postings": [_posting_to_dict(posting) for posting in postings],
        }

    return terms


def _posting_to_dict(posting: Posting) -> dict:
    """Convert a Posting dataclass to dict."""
    return {
        "doc_id": posting.doc_id,
        "url": posting.url,
        "fields": {
            field_name: {
                "tf": field_stats.tf,
                "positions": field_stats.positions,
            }
            for field_name, field_stats in posting.fields.items()
        },
    }


def _build_fields_meta(field_length_totals: dict[str, int], num_docs: int) -> dict:
    """Build `_meta.fields` with avgdl, weight, and b for each field."""
    fields_meta: dict[str, dict[str, float]] = {}

    for field_name in FIELD_NAMES:
        # avgdl is the average document length for the field across the corpus, used in BM25 scoring.
        avgdl = 0.0 if num_docs == 0 else field_length_totals[field_name] / num_docs
        fields_meta[field_name] = {
            "avgdl": avgdl,
            "weight": FIELD_WEIGHTS[field_name],
            "b": FIELD_B_VALUES[field_name],
        }

    return fields_meta
