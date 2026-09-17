"""Smoke tests: can we reach the workspace and see catalogs/schemas at all."""


def test_can_connect_and_run_query(spark):
    result = spark.sql("SELECT 1 AS ok").collect()
    assert result[0]["ok"] == 1


def test_can_list_catalogs(spark):
    catalogs = [row["catalog"] for row in spark.sql("SHOW CATALOGS").collect()]
    assert "samples" in catalogs


def test_can_list_schemas_in_sample_catalog(spark):
    schemas = [row["databaseName"] for row in spark.sql("SHOW SCHEMAS IN samples").collect()]
    assert "nyctaxi" in schemas
