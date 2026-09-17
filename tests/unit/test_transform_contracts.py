"""Schema contract tests: snapshot each transform's OUTPUT SCHEMA (not its
data) so an unintended column/type change shows up as a snapshot diff in
review, instead of silently reaching downstream consumers. This is the
Layer 1 answer to "schema evolution with mergeSchema can silently add
columns" — see CLAUDE.md.

A snapshot mismatch after an intentional change is expected: review the
diff, then run `pytest tests/unit/test_transform_contracts.py --snapshot-update`
to accept it.
"""

from dbx_tests.transforms import dedupe_by_key, flag_high_value_orders, normalize_prices


def test_normalize_prices_schema_contract(spark, snapshot):
    df = spark.createDataFrame(
        [("VOD LN", 7250.0, "GBp")], "ticker string, price double, currency string"
    )
    assert normalize_prices(df).schema.simpleString() == snapshot


def test_flag_high_value_orders_schema_contract(spark, snapshot):
    df = spark.createDataFrame([(1, 100.0)], "order_id int, amount double")
    assert flag_high_value_orders(df).schema.simpleString() == snapshot


def test_dedupe_by_key_schema_contract(spark, snapshot):
    df = spark.createDataFrame([(1, "2024-01-01", "a")], "order_id int, updated_at string, label string")
    result = dedupe_by_key(df, key_column="order_id", order_by_column="updated_at")
    assert result.schema.simpleString() == snapshot
