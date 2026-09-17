"""Write/read roundtrip: data written to a scratch table reads back unchanged."""

from pyspark.sql import Row


def test_write_then_read_matches(spark, scratch_table):
    rows = [Row(id=1, label="a"), Row(id=2, label="b"), Row(id=3, label="c")]
    df = spark.createDataFrame(rows)
    df.write.mode("overwrite").saveAsTable(scratch_table)

    try:
        read_back = spark.table(scratch_table).orderBy("id").collect()
        assert [tuple(r) for r in read_back] == [tuple(r) for r in rows]
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {scratch_table}")
