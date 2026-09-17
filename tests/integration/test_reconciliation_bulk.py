"""Layer 4 at realistic volume — nightly only (see README's CI mapping).

The same idea as test_reconciliation.py, but at ~500k rows generated with
polars instead of ~200 built row-by-row in Python: proves a re-seed at
realistic volume doesn't silently change control totals, catching
data-skew/performance issues a small fixture wouldn't surface.

Skipped by default — meaningfully slower/costlier than the rest of the
suite, and belongs in a nightly job, not every merge. Run explicitly with:
    DBX_TESTS_RUN_BULK=1 pytest tests/integration/test_reconciliation_bulk.py -v
"""

import os

import pytest

from dbx_tests.bulk_data import seed_bulk_orders

pytestmark = pytest.mark.skipif(
    os.environ.get("DBX_TESTS_RUN_BULK") != "1",
    reason="set DBX_TESTS_RUN_BULK=1 to run the realistic-volume nightly reconciliation test",
)

NUM_ORDERS = 500_000


def _control_totals(spark, table, version):
    return spark.sql(
        f"SELECT status, COUNT(*) AS n, SUM(amount) AS total_amount "
        f"FROM {table} VERSION AS OF {version} GROUP BY status"
    )


def test_reseeding_bulk_orders_does_not_change_control_totals(spark, seeded_tables, dbx_config):
    # seeded_tables ensures the small customers table (id range 1..50)
    # exists first, so orders_bulk's customer_id values are valid.
    orders_table = seed_bulk_orders(spark, dbx_config.catalog, dbx_config.schema, num_orders=NUM_ORDERS)

    before_version = spark.sql(f"DESCRIBE HISTORY {orders_table} LIMIT 1").collect()[0]["version"]
    seed_bulk_orders(spark, dbx_config.catalog, dbx_config.schema, num_orders=NUM_ORDERS)
    after_version = before_version + 1

    before = _control_totals(spark, orders_table, before_version)
    after = _control_totals(spark, orders_table, after_version)

    diff = before.exceptAll(after).unionByName(after.exceptAll(before))
    assert diff.count() == 0, "control totals changed between two identical (same-seed) bulk re-seed runs"
