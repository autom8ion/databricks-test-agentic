"""Seeds a small, realistic e-commerce schema (customers/orders/order_items)
into the configured Databricks catalog/schema, so the test suite has a
multi-table structure it fully controls (unlike the read-only
`samples.nyctaxi.trips` table used elsewhere).

Run standalone:  python -m dbx_tests.sample_data
Or automatically via the `seeded_tables` pytest fixture (see conftest.py),
which calls `seed()` once per test session on first use.
"""

import random
from datetime import date, datetime, timedelta

from pyspark.sql import Row, SparkSession
from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Sam", "Jamie", "Drew", "Quinn"]
LAST_NAMES = ["Nguyen", "Smith", "Garcia", "Patel", "Kim", "Johnson", "Chen", "Brown", "Rossi", "Novak"]
COUNTRIES = ["US", "CA", "GB", "DE", "FR", "AU", "JP", "BR"]
ORDER_STATUSES = ["placed", "shipped", "delivered", "cancelled", "returned"]
PRODUCT_SKUS = [f"SKU-{n:04d}" for n in range(1, 31)]

CUSTOMERS_SCHEMA = StructType(
    [
        StructField("customer_id", IntegerType(), nullable=False),
        StructField("name", StringType(), nullable=False),
        StructField("email", StringType(), nullable=False),
        StructField("country", StringType(), nullable=False),
        StructField("signup_date", DateType(), nullable=False),
    ]
)

ORDERS_SCHEMA = StructType(
    [
        StructField("order_id", IntegerType(), nullable=False),
        StructField("customer_id", IntegerType(), nullable=False),
        StructField("order_ts", TimestampType(), nullable=False),
        StructField("amount", DoubleType(), nullable=False),
        StructField("status", StringType(), nullable=False),
    ]
)

ORDER_ITEMS_SCHEMA = StructType(
    [
        StructField("order_item_id", IntegerType(), nullable=False),
        StructField("order_id", IntegerType(), nullable=False),
        StructField("product_sku", StringType(), nullable=False),
        StructField("quantity", IntegerType(), nullable=False),
        StructField("unit_price", DoubleType(), nullable=False),
    ]
)


def _build_customers(n: int, rng: random.Random) -> list[Row]:
    rows = []
    for customer_id in range(1, n + 1):
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        email = f"{name.lower().replace(' ', '.')}{customer_id}@example.com"
        signup_date = date(2023, 1, 1) + timedelta(days=rng.randint(0, 700))
        rows.append(
            Row(customer_id=customer_id, name=name, email=email, country=rng.choice(COUNTRIES), signup_date=signup_date)
        )
    return rows


def _build_orders(customer_ids: list[int], n: int, rng: random.Random) -> list[Row]:
    rows = []
    base = datetime(2024, 1, 1)
    for order_id in range(1, n + 1):
        order_ts = base + timedelta(minutes=rng.randint(0, 60 * 24 * 400))
        rows.append(
            Row(
                order_id=order_id,
                customer_id=rng.choice(customer_ids),
                order_ts=order_ts,
                amount=round(rng.uniform(5, 500), 2),
                status=rng.choice(ORDER_STATUSES),
            )
        )
    return rows


def _build_order_items(order_ids: list[int], n: int, rng: random.Random) -> list[Row]:
    rows = []
    for order_item_id in range(1, n + 1):
        rows.append(
            Row(
                order_item_id=order_item_id,
                order_id=rng.choice(order_ids),
                product_sku=rng.choice(PRODUCT_SKUS),
                quantity=rng.randint(1, 5),
                unit_price=round(rng.uniform(2, 150), 2),
            )
        )
    return rows


def seed(
    spark: SparkSession,
    catalog: str,
    schema: str,
    num_customers: int = 50,
    num_orders: int = 200,
    num_order_items: int = 600,
    random_seed: int = 42,
) -> dict[str, str]:
    """Create (or overwrite) customers/orders/order_items tables with
    synthetic, referentially-consistent data. Idempotent — safe to re-run.

    Returns a dict mapping logical name -> fully-qualified table name.
    """
    rng = random.Random(random_seed)
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    customers = _build_customers(num_customers, rng)
    customer_ids = [row.customer_id for row in customers]
    orders = _build_orders(customer_ids, num_orders, rng)
    order_ids = [row.order_id for row in orders]
    order_items = _build_order_items(order_ids, num_order_items, rng)

    tables = {
        "customers": (customers, CUSTOMERS_SCHEMA),
        "orders": (orders, ORDERS_SCHEMA),
        "order_items": (order_items, ORDER_ITEMS_SCHEMA),
    }

    qualified_names = {}
    for name, (rows, struct) in tables.items():
        qualified_name = f"{catalog}.{schema}.{name}"
        spark.createDataFrame(rows, schema=struct).write.mode("overwrite").saveAsTable(qualified_name)
        qualified_names[name] = qualified_name

    return qualified_names


if __name__ == "__main__":
    from dbx_tests.config import config
    from dbx_tests.connector import get_spark_session

    spark = get_spark_session()
    qualified_names = seed(spark, config.catalog, config.schema)
    for logical_name, qualified_name in qualified_names.items():
        count = spark.table(qualified_name).count()
        print(f"{qualified_name}: {count} rows")
