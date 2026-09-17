"""Data quality checks: null rates, ranges, and duplicate detection."""

from pyspark.sql import functions as F

NULL_RATE_THRESHOLD = 0.01


def test_null_rate_under_threshold(spark, sample_table):
    df = spark.table(sample_table)
    total = df.count()
    for col in ("fare_amount", "trip_distance"):
        nulls = df.filter(F.col(col).isNull()).count()
        rate = nulls / total if total else 0
        assert rate <= NULL_RATE_THRESHOLD, f"{col} null rate {rate:.4f} exceeds {NULL_RATE_THRESHOLD}"


def test_fare_amount_is_non_negative(spark, sample_table):
    df = spark.table(sample_table)
    bad = df.filter(F.col("fare_amount") < 0).limit(1).count()
    assert bad == 0, "found negative fare_amount values"


def test_trip_distance_is_within_plausible_range(spark, sample_table):
    df = spark.table(sample_table)
    bad = df.filter((F.col("trip_distance") < 0) | (F.col("trip_distance") > 1000)).limit(1).count()
    assert bad == 0, "found trip_distance values outside plausible range [0, 1000]"


def test_no_duplicate_rows(spark, sample_table):
    df = spark.table(sample_table)
    total = df.count()
    distinct = df.distinct().count()
    assert total == distinct, f"found {total - distinct} duplicate rows"
