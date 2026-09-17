"""PySpark connector to a Databricks workspace, via Databricks Connect."""

from databricks.connect import DatabricksSession
from pyspark.sql import SparkSession

from dbx_tests.config import config


def get_spark_session() -> SparkSession:
    """Build a Spark session against the configured Databricks compute.

    Uses serverless compute when DATABRICKS_SERVERLESS is set, otherwise
    targets the cluster given by DATABRICKS_CLUSTER_ID.
    """
    if not config.is_configured():
        raise RuntimeError(
            "Databricks is not configured. Set DATABRICKS_HOST, DATABRICKS_TOKEN, "
            "and either DATABRICKS_SERVERLESS=1 or DATABRICKS_CLUSTER_ID (see .env.example)."
        )

    builder = DatabricksSession.builder.host(config.host).token(config.token)
    builder = builder.serverless() if config.serverless else builder.clusterId(config.cluster_id)
    return builder.getOrCreate()
