import pytest

from dbx_tests import config as config_module
from dbx_tests.connector import get_spark_session

SAMPLE_TABLE = "samples.nyctaxi.trips"


def pytest_collection_modifyitems(config, items):
    if config_module.config.is_configured():
        return
    skip = pytest.mark.skip(reason="Databricks not configured (see .env.example)")
    for item in items:
        item.add_marker(skip)


@pytest.fixture(scope="session")
def spark():
    return get_spark_session()


@pytest.fixture(scope="session")
def dbx_config():
    return config_module.config


@pytest.fixture(scope="session")
def sample_table():
    """A table that ships with every Unity Catalog-enabled workspace's samples."""
    return SAMPLE_TABLE


@pytest.fixture
def scratch_table(dbx_config):
    """Qualified name for a throwaway table under the configured test schema."""
    return f"{dbx_config.catalog}.{dbx_config.schema}.dbx_tests_scratch"


@pytest.fixture(scope="session")
def seeded_tables(spark, dbx_config):
    """Populates customers/orders/order_items with synthetic data on first
    use, once per test session. See dbx_tests.sample_data.seed()."""
    from dbx_tests.sample_data import seed

    return seed(spark, dbx_config.catalog, dbx_config.schema)
