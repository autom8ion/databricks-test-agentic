"""Fuzzy-match data validation: catches near-duplicate or mistyped string
values that exact comparison (test_data_quality.py's null/range/duplicate
checks) misses — e.g. "USA" vs "United States", a misspelled order status,
a customer entered twice with a typo'd name. Uses rapidfuzz (C++ core, MIT
license; the maintained, non-GPL successor to fuzzywuzzy).
"""

from rapidfuzz import fuzz, process


def find_unmatched(values: list[str], allowed: list[str], threshold: int = 85) -> dict[str, str]:
    """Values not exactly in `allowed` but close to one of them (score >=
    threshold) — likely typos/variants rather than genuinely new values.
    Returns {value: best_matching_allowed_value}.
    """
    allowed_set = set(allowed)
    unmatched = {}
    for value in values:
        if value in allowed_set:
            continue
        match = process.extractOne(value, allowed, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            unmatched[value] = match[0]
    return unmatched


def find_near_duplicates(values: list[str], threshold: int = 90) -> list[tuple[str, str, float]]:
    """Distinct values that fuzzy-match each other above `threshold` —
    candidate duplicate records (e.g. two customer names that are typos of
    the same person). Returns (value_a, value_b, score) triples.
    """
    # ponytail: O(n^2) pairwise scan, fine for the hundreds of distinct
    # values a data-quality check pulls; add blocking/MinHash if this ever
    # runs over full-table cardinality instead of a distinct-values list.
    distinct = list(dict.fromkeys(values))
    pairs = []
    for i, value in enumerate(distinct):
        for match, score, _ in process.extract(
            value, distinct[i + 1 :], scorer=fuzz.ratio, score_cutoff=threshold
        ):
            pairs.append((value, match, score))
    return pairs


if __name__ == "__main__":
    assert find_unmatched(["shiped", "delivered"], ["shipped", "delivered", "cancelled"]) == {"shiped": "shipped"}
    assert find_unmatched(["placed"], ["placed"]) == {}
    dupes = find_near_duplicates(["Alex Nguyen", "Alex Nguyn", "Jordan Kim"])
    assert dupes and dupes[0][:2] == ("Alex Nguyen", "Alex Nguyn")
    assert find_near_duplicates(["Alex Nguyen", "Jordan Kim"]) == []
    print("ok")
