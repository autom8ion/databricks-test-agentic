# databricks-test-agentic

A PySpark connector to a Databricks workspace, plus a pytest suite of
industry-standard data pipeline test scenarios, wired up as a Claude Code
project with sub agents and a skill.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your workspace host/token/compute
```

## Running the tests

```bash
pytest tests/ -v
```

Without a configured `.env`, the whole suite skips cleanly (exit code 0) so
it's safe to run in CI or a sandbox with no credentials. Once `.env` is
filled in, the suite runs against `samples.nyctaxi.trips` (present in every
Unity Catalog-enabled workspace) plus a scratch table under
`DBX_TEST_CATALOG.DBX_TEST_SCHEMA`.

## What's tested

- **Connectivity** (`test_connectivity.py`) — can connect, list catalogs/schemas.
- **Schema validation** (`test_schema_validation.py`) — column names/types match a pinned expected schema; catches schema drift.
- **Data quality** (`test_data_quality.py`) — null rates, value ranges, duplicate rows.
- **Row-count reconciliation** (`test_row_count_reconciliation.py`) — partitioned counts sum to the total.
- **Freshness** (`test_freshness.py`) — data isn't older than an SLA window.
- **Write/read roundtrip** (`test_write_read_roundtrip.py`) — data written to a scratch table reads back unchanged.
- **Referential integrity** (`test_referential_integrity.py`) — FK-style checks (every order has a valid customer, etc.) against the seeded sample structure below.

## Sample data & structure

`src/dbx_tests/sample_data.py` seeds a small, realistic e-commerce schema into
`DBX_TEST_CATALOG.DBX_TEST_SCHEMA`:

- `customers` (customer_id, name, email, country, signup_date)
- `orders` (order_id, customer_id, order_ts, amount, status)
- `order_items` (order_item_id, order_id, product_sku, quantity, unit_price)

Data is synthetic but referentially consistent (every order's `customer_id`
exists, every order_item's `order_id` exists) and reproducible (fixed random
seed). Seeding is idempotent — each run overwrites the tables from scratch.

It runs **automatically**: the `seeded_tables` pytest fixture calls `seed()`
once per test session the first time a test needs it (currently
`test_referential_integrity.py`). To populate it standalone, e.g. to browse
the tables in the workspace UI without running the test suite:

```bash
python -m dbx_tests.sample_data
```

## Claude Code integration

- `/databricks-tests` — checks config, runs the suite, summarizes results.
- **databricks-test-runner** sub agent — runs the suite and diagnoses failures (auth vs schema drift vs real data-quality issues).
- **databricks-test-writer** sub agent — scaffolds a new test module for another table, following the patterns above.
