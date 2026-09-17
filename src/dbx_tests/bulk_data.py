"""Fast, vectorized synthetic data generation for realistic-volume testing.

sample_data.py's small fixture (customers/orders/order_items) proves
pipeline *logic* is correct; testing at realistic volume additionally
catches data-skew and performance problems a small fixture can't (see
README's CI mapping — this is the "nightly, Layer 4 at realistic volume"
piece). Pure-Python row-by-row generation doesn't scale to hundreds of
thousands of rows; polars' vectorized operations do.
"""

import numpy as np
import polars as pl
from pyspark.sql import SparkSession

from dbx_tests.sample_data import ORDER_STATUSES, ORDERS_SCHEMA


def generate_orders_polars(customer_ids: list[int], n: int, random_seed: int = 42) -> pl.DataFrame:
    """Vectorized equivalent of sample_data._build_orders, for large n."""
    rng = np.random.default_rng(random_seed)
    base = np.datetime64("2024-01-01T00:00:00", "us")
    minute_offsets = rng.integers(0, 60 * 24 * 400, size=n).astype("timedelta64[m]").astype("timedelta64[us]")

    return pl.DataFrame(
        {
            "order_id": np.arange(1, n + 1, dtype=np.int32),
            "customer_id": rng.choice(customer_ids, size=n).astype(np.int32),
            "order_ts": base + minute_offsets,
            "amount": np.round(rng.uniform(5, 500, size=n), 2),
            "status": rng.choice(ORDER_STATUSES, size=n),
        }
    )


def seed_bulk_orders(
    spark: SparkSession,
    catalog: str,
    schema: str,
    num_customers: int = 50,
    num_orders: int = 500_000,
    random_seed: int = 42,
) -> str:
    """Overwrites <catalog>.<schema>.orders_bulk with num_orders synthetic
    rows. Assumes customer ids 1..num_customers already exist (i.e.
    sample_data.seed() has run with a matching num_customers) — this only
    generates orders, not the customers table itself.

    Returns the fully-qualified table name.
    """
    customer_ids = list(range(1, num_customers + 1))
    orders = generate_orders_polars(customer_ids, num_orders, random_seed=random_seed)

    qualified_name = f"{catalog}.{schema}.orders_bulk"
    spark.createDataFrame(orders.to_pandas(), schema=ORDERS_SCHEMA).write.mode("overwrite").saveAsTable(
        qualified_name
    )
    return qualified_name
