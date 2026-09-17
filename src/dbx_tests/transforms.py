"""Pure ETL transformation logic: DataFrame in, DataFrame out, no I/O.

Kept out of notebooks/jobs specifically so it can be unit tested with a
plain local SparkSession (see tests/unit/), with no cluster and no
Databricks Connect. Jobs/pipelines should just call these functions.
"""

from pyspark.sql import DataFrame, functions as F


def normalize_prices(df: DataFrame) -> DataFrame:
    """Converts GBp (pence) quotes to GBP; leaves other currencies untouched."""
    is_pence = F.col("currency") == "GBp"
    return df.withColumn(
        "price", F.when(is_pence, F.col("price") / 100).otherwise(F.col("price"))
    ).withColumn("currency", F.when(is_pence, F.lit("GBP")).otherwise(F.col("currency")))


def flag_high_value_orders(df: DataFrame, threshold: float = 300.0) -> DataFrame:
    """Adds a boolean `is_high_value` column for orders at or above threshold."""
    return df.withColumn("is_high_value", F.col("amount") >= threshold)


def dedupe_by_key(df: DataFrame, key_column: str, order_by_column: str) -> DataFrame:
    """Keeps only the latest row per key_column, ranked by order_by_column.

    Use before a Delta MERGE whose source may contain duplicate keys —
    MERGE raises an error if more than one source row matches the same
    target row.
    """
    from pyspark.sql import Window

    window = Window.partitionBy(key_column).orderBy(F.col(order_by_column).desc())
    return (
        df.withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
