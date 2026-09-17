"""Referential integrity checks against the seeded customers/orders/order_items
structure (see dbx_tests.sample_data). Runs automatically: the seeded_tables
fixture populates the tables on first use."""


def test_customer_ids_are_unique(spark, seeded_tables):
    customers = spark.table(seeded_tables["customers"])
    assert customers.count() == customers.select("customer_id").distinct().count()


def test_order_ids_are_unique(spark, seeded_tables):
    orders = spark.table(seeded_tables["orders"])
    assert orders.count() == orders.select("order_id").distinct().count()


def test_order_item_ids_are_unique(spark, seeded_tables):
    order_items = spark.table(seeded_tables["order_items"])
    assert order_items.count() == order_items.select("order_item_id").distinct().count()


def test_every_order_has_a_valid_customer(spark, seeded_tables):
    orders = spark.table(seeded_tables["orders"])
    customers = spark.table(seeded_tables["customers"])
    orphans = orders.join(customers, "customer_id", "left_anti").count()
    assert orphans == 0, f"found {orphans} orders referencing a nonexistent customer"


def test_every_order_item_has_a_valid_order(spark, seeded_tables):
    order_items = spark.table(seeded_tables["order_items"])
    orders = spark.table(seeded_tables["orders"])
    orphans = order_items.join(orders, "order_id", "left_anti").count()
    assert orphans == 0, f"found {orphans} order_items referencing a nonexistent order"


def test_order_status_values_are_known(spark, seeded_tables):
    from dbx_tests.sample_data import ORDER_STATUSES

    orders = spark.table(seeded_tables["orders"])
    bad = orders.filter(~orders.status.isin(ORDER_STATUSES)).limit(1).count()
    assert bad == 0, "found orders with an unrecognized status value"
