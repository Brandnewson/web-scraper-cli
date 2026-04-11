"""Search scoring utilities."""

from __future__ import annotations

import math

K1 = 1.5    # BM25 term frequency saturation parameter (see docs/ENGINEERING_RATIONALE.md for details).
DEFAULT_MAX_EDIT_DISTANCE = 2


def score_bm25f(term: str, doc_id: int, index: dict) -> float:
    """Compute BM25F score for one term-document pair.

    Args:
        term: Query term.
        doc_id: Target document id.
        index: Full index structure with `_meta` and `terms`.

    Returns:
        BM25F score for the given term and document, or 0.0 when undefined.
    """
    terms = index.get("terms", {})
    term_entry = terms.get(term)
    if term_entry is None:
        return 0.0

    num_docs = index.get("_meta", {}).get("num_docs", 0)
    # Document frequency for the term, used in IDF calculation.
    df = term_entry.get("df", 0)    
    if num_docs <= 0 or df <= 0:
        return 0.0

    posting = _find_posting_for_doc(term_entry.get("postings", []), doc_id)
    if posting is None:
        return 0.0

    pseudo_tf = _compute_pseudo_tf(doc_id, posting, index)
    if pseudo_tf <= 0.0:
        return 0.0

    # IDF stands for inverse document frequency, which downweights terms that appear in many documents.
    idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0) 
    return idf * pseudo_tf * (K1 + 1.0) / (pseudo_tf + K1)


def _find_posting_for_doc(postings: list[dict], doc_id: int) -> dict | None:
    """Return the posting dict for a document id, if present."""
    for posting in postings:
        if posting.get("doc_id") == doc_id:
            return posting
    return None


def _compute_pseudo_tf(doc_id: int, posting: dict, index: dict) -> float:
    """Compute BM25F pseudo-term-frequency across fields."""
    fields_meta = index.get("_meta", {}).get("fields", {})
    doc_lengths = index.get("_meta", {}).get("doc_field_lengths", {}).get(str(doc_id), {})
    posting_fields = posting.get("fields", {})

    total = 0.0
    for field_name, stats in posting_fields.items():
        field_meta = fields_meta.get(field_name)
        if field_meta is None:
            continue

        tf = stats.get("tf", 0)
        if tf <= 0:
            continue

        weight = field_meta.get("weight", 0.0)
        b_value = field_meta.get("b", 0.0)
        avgdl = field_meta.get("avgdl", 0.0)
        field_length = doc_lengths.get(field_name, 0)

        denominator = _field_denominator(b_value, field_length, avgdl)
        total += weight * tf / denominator

    return total


def _field_denominator(b_value: float, field_length: int, avgdl: float) -> float:
    """Compute BM25F field normalization denominator safely."""
    if avgdl == 0:
        return 1.0

    denominator = 1.0 - b_value + b_value * (field_length / avgdl)
    if denominator == 0:
        return 1.0
    return denominator


def build_skip_pointers(postings: list[dict]) -> list[tuple[int, int]]:
    """
    Build sqrt-spaced skip pointers for one posting list.
    We use sqrt spacing as a common heuristic to balance skip pointer overhead and effectiveness.
    """
    if not postings:
        return []

    step = max(1, int(math.sqrt(len(postings))))
    return [(postings[index]["doc_id"], index) for index in range(0, len(postings), step)]


def advance_with_skips(
    postings: list[dict],
    skips: list[tuple[int, int]],
    ptr: int,
    target: int,
) -> int:
    """Advance pointer to first posting with doc_id >= target.

    Raises:
        StopIteration: If the pointer exhausts the posting list.
    """
    if ptr >= len(postings):
        raise StopIteration

    current_ptr = ptr

    # Jump with skip pointers while the jump stays below target.
    for skip_doc_id, skip_index in skips:
        if skip_index <= current_ptr:
            continue
        if skip_doc_id < target:
            current_ptr = skip_index
            continue
        break

    # Finish with linear scan to land on first doc_id >= target.
    while current_ptr < len(postings) and postings[current_ptr]["doc_id"] < target:
        current_ptr += 1

    if current_ptr >= len(postings):
        raise StopIteration
    return current_ptr


def _posting_list_length_key(pair: tuple[list[dict], list[tuple[int, int]]]) -> int:
    """Return posting-list length for sorting paired posting/skip lists."""
    return len(pair[0])


def daat_and_merge(posting_lists: list[list[dict]], skip_lists: list[list[tuple[int, int]]]) -> list[int]:
    """Intersect posting lists with document-at-a-time AND semantics."""
    if not posting_lists:
        return []

    paired = sorted(
        zip(posting_lists, skip_lists, strict=True),
        key=_posting_list_length_key,
    )
    sorted_posting_lists = [pair[0] for pair in paired]
    sorted_skip_lists = [pair[1] for pair in paired]

    if any(len(postings) == 0 for postings in sorted_posting_lists):
        return []

    pointers = [0 for _ in sorted_posting_lists]
    results: list[int] = []

    while True:
        try:
            current_doc_ids = [
                postings[pointers[index]]["doc_id"]
                for index, postings in enumerate(sorted_posting_lists)
            ]
        except IndexError:
            break

        min_doc_id = min(current_doc_ids)
        max_doc_id = max(current_doc_ids)

        if min_doc_id == max_doc_id:
            results.append(max_doc_id)
            pointers = [pointer + 1 for pointer in pointers]
            if any(pointer >= len(sorted_posting_lists[index]) for index, pointer in enumerate(pointers)):
                break
            continue

        for index, current_doc_id in enumerate(current_doc_ids):
            if current_doc_id >= max_doc_id:
                continue
            try:
                pointers[index] = advance_with_skips(
                    sorted_posting_lists[index],
                    sorted_skip_lists[index],
                    pointers[index],
                    max_doc_id,
                )
            except StopIteration:
                return results

    return results


def levenshtein(s1: str, s2: str) -> int:
    """Compute edit distance with adjacent transposition support."""
    if s1 == s2:
        return 0

    m = len(s1)
    n = len(s2)
    dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            substitution_cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + substitution_cost,
            )

            # Adjacent transposition (Damerau-style) counts as one edit.
            if (
                i > 1
                and j > 1
                and s1[i - 1] == s2[j - 2]
                and s1[i - 2] == s2[j - 1]
            ):
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1)

    return dp[m][n]


def suggest(
    token: str,
    vocabulary: set[str],
    max_dist: int = DEFAULT_MAX_EDIT_DISTANCE,
) -> str | None:
    """Return the closest vocabulary candidate within max distance."""
    best_candidate: str | None = None
    best_distance = max_dist + 1

    for candidate in sorted(vocabulary):
        distance = levenshtein(token, candidate)
        if distance > max_dist:
            continue

        if distance < best_distance:
            best_distance = distance
            best_candidate = candidate
            continue

        if distance == best_distance and best_candidate is not None and candidate < best_candidate:
            best_candidate = candidate

    return best_candidate


def did_you_mean(query_tokens: list[str], index: dict) -> str | None:
    """Suggest corrected query text when unknown tokens are detected."""
    vocabulary = set(index.get("terms", {}).keys())
    if not query_tokens or not vocabulary:
        return None

    suggested_tokens: list[str] = []
    replaced_any = False

    for token in query_tokens:
        if token in vocabulary:
            suggested_tokens.append(token)
            continue

        replacement = suggest(token, vocabulary)
        if replacement is None:
            suggested_tokens.append(token)
            continue

        suggested_tokens.append(replacement)
        replaced_any = True

    if not replaced_any:
        return None

    return f'Did you mean: "{" ".join(suggested_tokens)}"?'
