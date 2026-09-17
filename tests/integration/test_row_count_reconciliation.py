"""Row-count reconciliation: a common pipeline sanity check adapted to run
against a single sample table (in a real pipeline, `source_count` and
`target_count` would come from two different systems, e.g. a landing table
vs its curated counterpart)."""

from pyspark.sql import functions as F

TOLERANCE = 0.0  # exact match expected for a pure filter/partition split


def test_partition_counts_sum_to_total(spark, sample_table):
    df = spark.table(sample_table)
    total_count = df.count()

    short_trips = df.filter(F.col("trip_distance") <= 5).count()
    long_trips = df.filter(F.col("trip_distance") > 5).count()

    reconciled = short_trips + long_trips
    diff_ratio = abs(total_count - reconciled) / total_count if total_count else 0
    assert diff_ratio <= TOLERANCE, (
        f"row count mismatch: total={total_count}, partitions summed={reconciled}"
    )
