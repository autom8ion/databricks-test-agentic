"""Environment-driven configuration for connecting to a Databricks workspace."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    host: str | None = os.environ.get("DATABRICKS_HOST")
    token: str | None = os.environ.get("DATABRICKS_TOKEN")
    cluster_id: str | None = os.environ.get("DATABRICKS_CLUSTER_ID")
    serverless: bool = os.environ.get("DATABRICKS_SERVERLESS", "").lower() in ("1", "true", "yes")
    catalog: str = os.environ.get("DBX_TEST_CATALOG", "main")
    schema: str = os.environ.get("DBX_TEST_SCHEMA", "default")

    def is_configured(self) -> bool:
        """True once enough env vars are set to attempt a connection."""
        has_compute = self.serverless or bool(self.cluster_id)
        return bool(self.host and self.token and has_compute)


config = Config()
