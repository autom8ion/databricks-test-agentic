"""Property-based tests for the pure transforms — check invariants across
many generated inputs instead of a handful of hand-picked examples.
Complements test_transforms.py's example-based tests; doesn't replace them.
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from dbx_tests.transforms import dedupe_by_key, flag_high_value_orders, normalize_prices

# Each example rebuilds a small DataFrame on the shared session-scoped
# `spark` fixture, which Hypothesis's health check doesn't recognize as
# safe to reuse across examples — it is safe here (session-scoped, no
# per-example state), so it's suppressed explicitly. deadline=None because
# a Spark job per example is inherently slower than Hypothesis's default
# 200ms budget, not a performance regression to flag.
slow_settings = settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)

prices = st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False)
currencies = st.sampled_from(["GBp", "USD", "EUR", "GBP", "JPY"])


@slow_settings
@given(price=prices, currency=currencies)
def test_normalize_prices_only_rewrites_pence_quotes(spark, price, currency):
    df = spark.createDataFrame([("T", price, currency)], "ticker string, price double, currency string")
    result = normalize_prices(df).collect()[0]

    if currency == "GBp":
        assert result.currency == "GBP"
        assert result.price == price / 100
    else:
        assert result.currency == currency
        assert result.price == price


@slow_settings
@given(amount=st.floats(min_value=-1_000, max_value=1_000, allow_nan=False), threshold=prices)
def test_flag_high_value_orders_matches_threshold_comparison(spark, amount, threshold):
    df = spark.createDataFrame([(1, amount)], "order_id int, amount double")
    result = flag_high_value_orders(df, threshold=threshold).collect()[0]
    assert result.is_high_value == (amount >= threshold)


@slow_settings
@given(
    rows=st.lists(
        st.tuples(st.integers(min_value=1, max_value=5), st.integers(min_value=0, max_value=100)),
        min_size=1,
        max_size=20,
    )
)
def test_dedupe_by_key_keeps_exactly_one_row_per_key_with_max_order_by(spark, rows):
    df = spark.createDataFrame(rows, "key int, order_by int")
    result = dedupe_by_key(df, key_column="key", order_by_column="order_by").collect()

    expected_keys = {key for key, _ in rows}
    assert {r.key for r in result} == expected_keys
    assert len(result) == len(expected_keys)

    expected_max = {}
    for key, order_by in rows:
        expected_max[key] = max(expected_max.get(key, order_by), order_by)
    assert {r.key: r.order_by for r in result} == expected_max
