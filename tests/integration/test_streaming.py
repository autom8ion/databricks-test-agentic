"""Layer 5: Structured Streaming behavior.

Covers three failure classes that only show up with a real streaming
pipeline, not batch tests:
  - `availableNow` lets a streaming test process everything queued and stop
    on its own, instead of running forever.
  - checkpoint recovery: killing and restarting a stream must not duplicate
    or drop rows.
  - idempotent MERGE: a source batch with duplicate keys must either be
    deduped first or fail loudly, never silently corrupt the target.
"""

import pytest
from pyspark.sql import Row
from pyspark.sql.utils import AnalysisException

from dbx_tests.transforms import dedupe_by_key


@pytest.fixture
def stream_source_table(spark, dbx_config):
    table = f"{dbx_config.catalog}.{dbx_config.schema}.dbx_tests_stream_source"
    rows = [Row(order_id=i, amount=float(i) * 10) for i in range(1, 11)]
    spark.createDataFrame(rows).write.mode("overwrite").saveAsTable(table)
    yield table
    spark.sql(f"DROP TABLE IF EXISTS {table}")


@pytest.fixture
def stream_sink_table_and_checkpoint(dbx_config):
    sink = f"{dbx_config.catalog}.{dbx_config.schema}.dbx_tests_stream_sink"
    checkpoint = f"/tmp/dbx_tests_checkpoints/{dbx_config.schema}_stream_sink"
    yield sink, checkpoint


def _run_available_now(spark, source_table, sink_table, checkpoint_path):
    query = (
        spark.readStream.table(source_table)
        .writeStream.format("delta")
        .option("checkpointLocation", checkpoint_path)
        .trigger(availableNow=True)
        .toTable(sink_table)
    )
    query.awaitTermination()


def test_available_now_trigger_drains_and_stops(
    spark, stream_source_table, stream_sink_table_and_checkpoint
):
    sink_table, checkpoint_path = stream_sink_table_and_checkpoint
    try:
        _run_available_now(spark, stream_source_table, sink_table, checkpoint_path)
        assert spark.table(sink_table).count() == spark.table(stream_source_table).count()
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {sink_table}")


def test_checkpoint_recovery_has_no_duplicates_or_gaps(
    spark, stream_source_table, stream_sink_table_and_checkpoint
):
    sink_table, checkpoint_path = stream_sink_table_and_checkpoint
    try:
        _run_available_now(spark, stream_source_table, sink_table, checkpoint_path)
        first_run_count = spark.table(sink_table).count()

        # Simulate a restart against the same checkpoint with no new source
        # data: a correctly checkpointed stream reprocesses nothing.
        _run_available_now(spark, stream_source_table, sink_table, checkpoint_path)
        second_run_count = spark.table(sink_table).count()

        assert second_run_count == first_run_count, "restart against the same checkpoint duplicated rows"
        assert spark.table(sink_table).select("order_id").distinct().count() == first_run_count
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {sink_table}")


def test_merge_fails_on_duplicate_source_keys(spark, dbx_config):
    """Documents a real Delta bug class: MERGE raises when more than one
    source row matches the same target row."""
    target = f"{dbx_config.catalog}.{dbx_config.schema}.dbx_tests_merge_target"
    spark.createDataFrame([Row(order_id=1, amount=10.0)]).write.mode("overwrite").saveAsTable(target)

    duplicate_source = spark.createDataFrame(
        [Row(order_id=1, amount=20.0), Row(order_id=1, amount=30.0)]
    )
    duplicate_source.createOrReplaceTempView("dbx_tests_dup_source")

    try:
        with pytest.raises(AnalysisException):
            spark.sql(
                f"MERGE INTO {target} t USING dbx_tests_dup_source s ON t.order_id = s.order_id "
                "WHEN MATCHED THEN UPDATE SET t.amount = s.amount "
                "WHEN NOT MATCHED THEN INSERT (order_id, amount) VALUES (s.order_id, s.amount)"
            )
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {target}")


def test_deduping_source_before_merge_avoids_the_failure(spark, dbx_config):
    target = f"{dbx_config.catalog}.{dbx_config.schema}.dbx_tests_merge_target_deduped"
    spark.createDataFrame([Row(order_id=1, amount=10.0)]).write.mode("overwrite").saveAsTable(target)

    duplicate_source = spark.createDataFrame(
        [Row(order_id=1, amount=20.0, updated_at=1), Row(order_id=1, amount=30.0, updated_at=2)]
    )
    deduped = dedupe_by_key(duplicate_source, key_column="order_id", order_by_column="updated_at")
    deduped.createOrReplaceTempView("dbx_tests_deduped_source")

    try:
        spark.sql(
            f"MERGE INTO {target} t USING dbx_tests_deduped_source s ON t.order_id = s.order_id "
            "WHEN MATCHED THEN UPDATE SET t.amount = s.amount "
            "WHEN NOT MATCHED THEN INSERT (order_id, amount) VALUES (s.order_id, s.amount)"
        )
        result = spark.table(target).collect()
        assert len(result) == 1 and result[0]["amount"] == 30.0
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {target}")
