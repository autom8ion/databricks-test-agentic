"""Layer 4: regression/reconciliation using Delta time travel.

Delta keeps table versions, so a pipeline change can be checked against its
own table's history without a separate baseline environment: compare
control totals before/after a run on the same table. Here, re-seeding with
the same fixed random seed should be a no-op business-wise — any diff in
control totals between the two versions means something changed that
shouldn't have (e.g. a seed/generator edit had an unintended side effect).
"""

from dbx_tests.sample_data import seed


def _control_totals(spark, table, version):
    return spark.sql(
        f"SELECT status, COUNT(*) AS n, SUM(amount) AS total_amount "
        f"FROM {table} VERSION AS OF {version} GROUP BY status"
    )


def test_reseeding_orders_does_not_change_control_totals(spark, seeded_tables, dbx_config):
    orders_table = seeded_tables["orders"]

    before_version = spark.sql(f"DESCRIBE HISTORY {orders_table} LIMIT 1").collect()[0]["version"]
    seed(spark, dbx_config.catalog, dbx_config.schema)  # re-run with the same fixed seed
    after_version = before_version + 1

    before = _control_totals(spark, orders_table, before_version)
    after = _control_totals(spark, orders_table, after_version)

    diff = before.exceptAll(after).unionByName(after.exceptAll(before))
    assert diff.count() == 0, "control totals changed between two identical (same-seed) re-seed runs"
