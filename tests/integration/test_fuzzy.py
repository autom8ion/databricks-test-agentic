"""Fuzzy-match data validation: typo'd categorical values and near-duplicate
records that exact comparison (test_data_quality.py) can't catch. See
src/dbx_tests/fuzzy.py."""

from dbx_tests.fuzzy import find_near_duplicates, find_unmatched
from dbx_tests.sample_data import ORDER_STATUSES


def test_find_unmatched_flags_typos_not_new_values():
    assert find_unmatched(["shiped"], ORDER_STATUSES) == {"shiped": "shipped"}
    assert find_unmatched(ORDER_STATUSES, ORDER_STATUSES) == {}
    assert find_unmatched(["completely_unrelated_value"], ORDER_STATUSES) == {}


def test_find_near_duplicates_flags_close_names_only():
    assert find_near_duplicates(["Alex Nguyen", "Alex Nguyn", "Jordan Kim"])
    assert find_near_duplicates(["Alex Nguyen", "Jordan Kim"]) == []


def test_order_status_values_match_canonical_list_exactly(spark, seeded_tables):
    """Real/seeded order statuses should be exact members of ORDER_STATUSES,
    not near-miss typos — a fuzzy match with no exact match means a data
    entry error slipped past whatever wrote this table."""
    distinct_statuses = [row.status for row in spark.table(seeded_tables["orders"]).select("status").distinct().collect()]
    typos = find_unmatched(distinct_statuses, ORDER_STATUSES)
    assert not typos, f"found order statuses that are typos of known values: {typos}"


def test_no_near_duplicate_customer_names(spark, seeded_tables):
    """Two customers with near-identical names are a likely duplicate
    record (re-entry, typo), not two different people — exact `distinct()`
    checks (test_data_quality.py) don't catch this."""
    names = [row.name for row in spark.table(seeded_tables["customers"]).select("name").distinct().collect()]
    dupes = find_near_duplicates(names, threshold=95)
    assert not dupes, f"found near-duplicate customer names: {dupes}"
