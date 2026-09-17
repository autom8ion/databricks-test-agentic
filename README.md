# databricks-test-agentic

A PySpark connector to a Databricks workspace, a layered ETL/data-pipeline
test suite following industry-standard practice, and a Claude Code project
(sub agents + a skill) for running and extending it. See `CLAUDE.md` for how
Claude Code should work in this repo.

## The testing layers

Each layer catches a different kind of failure; no single tool covers all of
them.

| Layer | What | Where | Needs |
|---|---|---|---|
| 1. Unit | Pure transform functions (`DataFrame -> DataFrame`), local Spark | `tests/unit/` | `requirements-unit.txt`, no Databricks |
| 2. Integration | Connectivity, schema drift, data quality, freshness, roundtrip, referential integrity | `tests/integration/` | `requirements.txt`, a real workspace |
| 3. In-pipeline expectations | Lakeflow Declarative Pipelines constraints, enforced on every production load | `pipelines/*.sql` | Deployed as a pipeline, not run by pytest |
| 4. Reconciliation | Delta time-travel control-total comparisons | `tests/integration/test_reconciliation.py` | Same as Layer 2 |
| 5. Streaming | `availableNow` triggers, checkpoint recovery, idempotent MERGE | `tests/integration/test_streaming.py` | Same as Layer 2 |

**Layer 1 and Layers 2/4/5 must run in separate Python environments.**
Databricks Connect replaces the `pyspark` package with a remote-only client,
so it cannot be installed alongside plain `pyspark` (which Layer 1 needs for
a local, no-cluster SparkSession).

## Setup

Uses [uv](https://docs.astral.sh/uv/) to manage both environments.

```bash
# Integration/reconciliation/streaming tests (Layers 2, 4, 5) — needs a real workspace
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # fill in your workspace host/token/compute

# Unit tests (Layer 1) — separate venv, no workspace needed
uv venv .venv-unit --python 3.12 && source .venv-unit/bin/activate
uv pip install -r requirements-unit.txt
```

These are deliberately two independent `uv pip install` calls, not one `uv
sync`/`uv.lock` project — Databricks Connect and plain PySpark have
incompatible pinned dependencies (see the pandas note in
`requirements-unit.txt`), so resolving them together would force one
resolution to satisfy both and break the other.

## Running the tests

```bash
# Layer 1 — no credentials needed, runs anywhere
source .venv-unit/bin/activate && pytest tests/unit -v

# Layers 2/4/5 — skips cleanly (exit 0) without a configured .env,
# runs for real once .env is filled in
source .venv/bin/activate && pytest tests/integration -v
```

`tests/integration` runs against `samples.nyctaxi.trips` (present in every
Unity Catalog-enabled workspace) plus the seeded structure and scratch
tables under `DBX_TEST_CATALOG.DBX_TEST_SCHEMA`.

## What's tested

**Layer 1 — unit** (`tests/unit/test_transforms.py`): `normalize_prices`,
`flag_high_value_orders`, `dedupe_by_key` — pure functions in
`src/dbx_tests/transforms.py`, checked with `pyspark.testing.assertDataFrameEqual`.

**Layer 2 — integration** (`tests/integration/`):
- **Connectivity** (`test_connectivity.py`) — can connect, list catalogs/schemas.
- **Schema validation** (`test_schema_validation.py`) — column names/types match a pinned expected schema; catches schema drift.
- **Data quality** (`test_data_quality.py`) — null rates, value ranges, duplicate rows.
- **Row-count reconciliation** (`test_row_count_reconciliation.py`) — partitioned counts sum to the total.
- **Freshness** (`test_freshness.py`) — data isn't older than an SLA window.
- **Write/read roundtrip** (`test_write_read_roundtrip.py`) — data written to a scratch table reads back unchanged.
- **Referential integrity** (`test_referential_integrity.py`) — FK-style checks against the seeded sample structure below.

**Layer 3 — in-pipeline expectations** (`pipelines/orders_clean_expectations.sql`):
a Lakeflow Declarative Pipelines example with `EXPECT` constraints and
`ON VIOLATION DROP ROW` / `FAIL UPDATE` clauses. Deployed with the pipeline,
not run by pytest — this is what protects production data on every load.
[DQX](https://github.com/databrickslabs/dqx) (Databricks Labs) is an
alternative worth knowing for quarantine/annotate-style checks with a rule
profiler, but it's an unsupported Labs project and isn't wired into this
repo.

**Layer 4 — reconciliation** (`tests/integration/test_reconciliation.py`):
compares Delta table versions via time travel to prove a change didn't alter
control totals it shouldn't have.

**Layer 5 — streaming** (`tests/integration/test_streaming.py`):
`availableNow` trigger draining, checkpoint-recovery duplicate detection,
and the "MERGE fails on duplicate source keys" bug class (and its fix via
`dedupe_by_key`).

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
once per test session the first time a test needs it. To populate it
standalone, e.g. to browse the tables in the workspace UI without running
the test suite:

```bash
python -m dbx_tests.sample_data
```

## CI mapping

- **Pull request:** Layer 1 unit tests — local, seconds, no cluster.
- **Merge to main:** Layer 2 integration tests against a test workspace/catalog.
- **Nightly:** Layer 4 reconciliation at realistic data volume.
- **Every production load:** Layer 3 expectations, running inside the pipeline itself.

## Claude Code integration

- `/databricks-tests` — checks config, runs the suite, summarizes results.
- **databricks-test-runner** sub agent — runs the suite and diagnoses failures (auth vs schema drift vs real data-quality issues).
- **databricks-test-writer** sub agent — scaffolds a new test module for another table, following the patterns above.

See `CLAUDE.md` for repo conventions.
