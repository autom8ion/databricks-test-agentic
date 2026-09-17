"""Schema drift detection: table's actual schema vs a pinned expected schema."""

EXPECTED_SCHEMA = {
    "tpep_pickup_datetime": "timestamp",
    "tpep_dropoff_datetime": "timestamp",
    "trip_distance": "double",
    "fare_amount": "double",
    "pickup_zip": "int",
    "dropoff_zip": "int",
}


def test_columns_match_expected_schema(spark, sample_table):
    # simpleString() gives the short SQL type name ("int", "double", ...)
    # matching EXPECTED_SCHEMA below; typeName() would return "integer" and
    # never match, flagging drift that isn't there.
    actual = {f.name: f.dataType.simpleString() for f in spark.table(sample_table).schema.fields}
    assert actual == EXPECTED_SCHEMA, f"schema drift detected: {actual} != {EXPECTED_SCHEMA}"


def test_key_columns_are_not_nullable_in_practice(spark, sample_table):
    df = spark.table(sample_table)
    for col in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        null_count = df.filter(df[col].isNull()).limit(1).count()
        assert null_count == 0, f"{col} has unexpected null values"
