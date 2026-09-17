"""Layer 1: unit tests for pure transformation logic. Local Spark, no
cluster, no Databricks Connect — see tests/unit/conftest.py."""

from pyspark.testing import assertDataFrameEqual

from dbx_tests.transforms import dedupe_by_key, flag_high_value_orders, normalize_prices


def test_pence_quotes_convert_to_pounds(spark):
    raw = spark.createDataFrame(
        [("VOD LN", 7250.0, "GBp"), ("AAPL US", 190.5, "USD")],
        "ticker string, price double, currency string",
    )
    expected = spark.createDataFrame(
        [("VOD LN", 72.50, "GBP"), ("AAPL US", 190.5, "USD")],
        "ticker string, price double, currency string",
    )
    assertDataFrameEqual(normalize_prices(raw), expected)


def test_flags_orders_at_or_above_threshold(spark):
    raw = spark.createDataFrame(
        [(1, 299.99), (2, 300.0), (3, 500.0)], "order_id int, amount double"
    )
    result = flag_high_value_orders(raw, threshold=300.0).orderBy("order_id")
    flags = [row.is_high_value for row in result.collect()]
    assert flags == [False, True, True]


def test_dedupe_by_key_keeps_latest_row_per_key(spark):
    raw = spark.createDataFrame(
        [(1, "2024-01-01", "old"), (1, "2024-06-01", "new"), (2, "2024-03-01", "only")],
        "order_id int, updated_at string, label string",
    )
    result = dedupe_by_key(raw, key_column="order_id", order_by_column="updated_at").orderBy("order_id")
    assertDataFrameEqual(
        result,
        spark.createDataFrame(
            [(1, "2024-06-01", "new"), (2, "2024-03-01", "only")],
            "order_id int, updated_at string, label string",
        ),
    )
