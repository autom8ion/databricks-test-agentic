import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    """A plain local SparkSession — no cluster, no cost, no Databricks Connect.

    Requires the `requirements-unit.txt` environment (plain pyspark), which
    cannot coexist in the same venv as databricks-connect (see README).
    """
    session = SparkSession.builder.master("local[2]").appName("dbx-tests-unit").getOrCreate()
    yield session
    session.stop()
