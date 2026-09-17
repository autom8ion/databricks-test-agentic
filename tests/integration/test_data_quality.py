"""Data quality checks: null rates, ranges, and duplicate detection."""

from pyspark.sql import functions as F

NULL_RATE_THRESHOLD = 0.01


def test_null_rate_under_threshold(spark, sample_table):
    df = spark.table(sample_table)
    total = df.count()
    for col in ("fare_amount", "trip_distance"):
        nulls = df.filter(F.col(col).isNull()).count()
        rate = nulls / total if total else 0
        assert rate <= NULL_RATE_THRESHOLD, f"{col} null rate {rate:.4f} exceeds {NULL_RATE_THRESHOLD}"


def test_fare_amount_is_non_negative(spark, sample_table):
    df = spark.table(sample_table)
    bad = df.filter(F.col("fare_amount") < 0).limit(1).count()
    assert bad == 0, "found negative fare_amount values"


def test_trip_distance_is_within_plausible_range(spark, sample_table):
    df = spark.table(sample_table)
    bad = df.filter((F.col("trip_distance") < 0) | (F.col("trip_distance") > 1000)).limit(1).count()
    assert bad == 0, "found trip_distance values outside plausible range [0, 1000]"


def test_no_duplicate_rows(spark, sample_table):
    df = spark.table(sample_table)
    total = df.count()
    distinct = df.distinct().count()
    assert total == distinct, f"found {total - distinct} duplicate rows"


# Same checks, against the pipeline's own seeded structure (customers/
# orders/order_items) rather than the read-only nyctaxi sample. These are
# clean by construction today (src/dbx_tests/sample_data.py), so they act
# as regression trip-wires for whatever eventually writes real data here.


def test_seeded_customers_have_no_null_required_fields(spark, seeded_tables):
    customers = spark.table(seeded_tables["customers"])
    for col in ("name", "email", "country", "signup_date"):
        nulls = customers.filter(F.col(col).isNull()).limit(1).count()
        assert nulls == 0, f"customers.{col} has null values"


def test_seeded_customer_emails_look_like_emails(spark, seeded_tables):
    customers = spark.table(seeded_tables["customers"])
    bad = customers.filter(~F.col("email").rlike(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")).limit(1).count()
    assert bad == 0, "found customer emails that don't look like an email address"


def test_seeded_customer_signup_dates_are_not_in_the_future(spark, seeded_tables):
    customers = spark.table(seeded_tables["customers"])
    bad = customers.filter(F.col("signup_date") > F.current_date()).limit(1).count()
    assert bad == 0, "found customer signup_date values in the future"


def test_seeded_order_amounts_are_non_negative(spark, seeded_tables):
    orders = spark.table(seeded_tables["orders"])
    bad = orders.filter(F.col("amount") < 0).limit(1).count()
    assert bad == 0, "found negative order amount values"


def test_seeded_order_amounts_are_within_plausible_range(spark, seeded_tables):
    orders = spark.table(seeded_tables["orders"])
    bad = orders.filter(F.col("amount") > 100_000).limit(1).count()
    assert bad == 0, "found order amount values above the plausible range"


def test_seeded_order_items_have_positive_quantity(spark, seeded_tables):
    order_items = spark.table(seeded_tables["order_items"])
    bad = order_items.filter(F.col("quantity") <= 0).limit(1).count()
    assert bad == 0, "found order_items with non-positive quantity"


def test_seeded_order_items_have_non_negative_unit_price(spark, seeded_tables):
    order_items = spark.table(seeded_tables["order_items"])
    bad = order_items.filter(F.col("unit_price") < 0).limit(1).count()
    assert bad == 0, "found order_items with negative unit_price"


def test_no_duplicate_seeded_rows(spark, seeded_tables):
    for name in ("customers", "orders", "order_items"):
        df = spark.table(seeded_tables[name])
        total = df.count()
        distinct = df.distinct().count()
        assert total == distinct, f"found {total - distinct} duplicate rows in {name}"
