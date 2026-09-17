"""Layer 6 — performance: wall-clock duration of pipeline operations at
realistic volume, to catch regressions a small fixture wouldn't surface
(a transform gone quadratic, a write no longer partition-pruned, a query
plan that stopped pruning files).

Timings vary with cluster/serverless cold-start, so thresholds here are
deliberately generous — a single failure is more likely a cold cluster
than a regression; a *reproducible* failure across reruns is the real
signal. Don't tighten thresholds to be "more sensitive" without accepting
more cold-start false positives.

Skipped by default — same reasoning as test_reconciliation_bulk.py (real
volume, meaningfully slower, belongs in a nightly job). Run explicitly:
    DBX_TESTS_RUN_PERF=1 pytest tests/integration/test_performance.py -v
"""

import os
import time
from contextlib import contextmanager

import pytest

from dbx_tests.bulk_data import seed_bulk_orders
from dbx_tests.transforms import dedupe_by_key, flag_high_value_orders

pytestmark = pytest.mark.skipif(
    os.environ.get("DBX_TESTS_RUN_PERF") != "1",
    reason="set DBX_TESTS_RUN_PERF=1 to run the realistic-volume performance test",
)

NUM_ORDERS = 500_000  # same volume as test_reconciliation_bulk.py

# ponytail: placeholders, not measured against a real cluster/serverless
# endpoint — calibrate against a few real runs on your actual compute
# before wiring this into a nightly CI gate.
WRITE_SLA_SECONDS = 180
TRANSFORM_SLA_SECONDS = 60
QUERY_SLA_SECONDS = 30


@contextmanager
def _timed():
    start = time.perf_counter()
    result = {}
    try:
        yield result
    finally:
        result["seconds"] = time.perf_counter() - start


def test_bulk_write_completes_within_sla(spark, seeded_tables, dbx_config):
    with _timed() as t:
        seed_bulk_orders(spark, dbx_config.catalog, dbx_config.schema, num_orders=NUM_ORDERS)
    assert t["seconds"] <= WRITE_SLA_SECONDS, (
        f"writing {NUM_ORDERS} orders took {t['seconds']:.1f}s, exceeds {WRITE_SLA_SECONDS}s SLA"
    )


def test_transform_completes_within_sla(spark, seeded_tables, dbx_config):
    orders_table = seed_bulk_orders(spark, dbx_config.catalog, dbx_config.schema, num_orders=NUM_ORDERS)
    df = spark.table(orders_table)
    with _timed() as t:
        dedupe_by_key(flag_high_value_orders(df), "order_id", "order_ts").count()
    assert t["seconds"] <= TRANSFORM_SLA_SECONDS, (
        f"transform over {NUM_ORDERS} orders took {t['seconds']:.1f}s, exceeds {TRANSFORM_SLA_SECONDS}s SLA"
    )


def test_aggregation_query_completes_within_sla(spark, seeded_tables, dbx_config):
    orders_table = seed_bulk_orders(spark, dbx_config.catalog, dbx_config.schema, num_orders=NUM_ORDERS)
    with _timed() as t:
        spark.sql(f"SELECT status, COUNT(*) AS n, SUM(amount) AS total FROM {orders_table} GROUP BY status").collect()
    assert t["seconds"] <= QUERY_SLA_SECONDS, (
        f"aggregation query over {NUM_ORDERS} orders took {t['seconds']:.1f}s, exceeds {QUERY_SLA_SECONDS}s SLA"
    )
