"""Freshness SLA: the most recent record should be within a max staleness window.

`samples.nyctaxi.trips` is a static historical dataset (fixed at workspace
creation), so it can never satisfy a wall-clock freshness SLA. The check is
still exercised here against the scratch table (which this suite writes with
a live timestamp), demonstrating the pattern to point at a real streaming/
batch table by swapping `sample_table` for the table under test.
"""

from datetime import datetime, timedelta, timezone

from pyspark.sql import Row

FRESHNESS_SLA = timedelta(hours=24)


def test_scratch_table_is_fresh(spark, scratch_table):
    now = datetime.now(timezone.utc)
    df = spark.createDataFrame([Row(id=1, updated_at=now)])
    df.write.mode("overwrite").saveAsTable(scratch_table)

    try:
        max_updated_at = spark.table(scratch_table).agg({"updated_at": "max"}).collect()[0][0]
        staleness = now - max_updated_at.replace(tzinfo=timezone.utc)
        assert staleness <= FRESHNESS_SLA, f"data is stale by {staleness}, exceeds SLA {FRESHNESS_SLA}"
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {scratch_table}")
