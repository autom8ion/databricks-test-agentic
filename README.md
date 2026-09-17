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
| 1. Unit | Pure transform functions (`DataFrame -> DataFrame`), local Spark: example-based, property-based (Hypothesis), and schema-contract (syrupy) tests | `tests/unit/` | `requirements-unit.txt`, no Databricks |
| 2. Integration | Connectivity, schema drift, data quality, freshness, roundtrip, referential integrity | `tests/integration/` | `requirements.txt`, a real workspace |
| 3. In-pipeline expectations | Lakeflow Declarative Pipelines constraints, enforced on every production load | `pipelines/*.sql` | Deployed as a pipeline, not run by pytest |
| 4. Reconciliation | Delta time-travel control-total comparisons, at both small and realistic (polars-generated) volume | `tests/integration/test_reconciliation*.py` | Same as Layer 2 |
| 5. Streaming | `availableNow` triggers, checkpoint recovery, idempotent MERGE | `tests/integration/test_streaming.py` | Same as Layer 2 |
| 6. Performance | Wall-clock duration of write/transform/query at realistic volume vs. an SLA | `tests/integration/test_performance.py` | Same as Layer 2, `DBX_TESTS_RUN_PERF=1` |

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
uv venv .venv-unit && source .venv-unit/bin/activate
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

**Layer 1 — unit** (`tests/unit/`), three complementary styles against the
same pure functions in `src/dbx_tests/transforms.py`:
- **Example-based** (`test_transforms.py`) — hand-picked inputs, checked with `pyspark.testing.assertDataFrameEqual`.
- **Property-based** (`test_transforms_properties.py`, [Hypothesis](https://hypothesis.readthedocs.io/)) — generates hundreds of inputs (arbitrary prices/currencies/keys) and checks invariants (e.g. "output is never `GBp`", "exactly one row per key, always the max") instead of a handful of examples — catches edge cases hand-picked examples miss.
- **Schema contracts** (`test_transform_contracts.py`, [syrupy](https://github.com/tophat/syrupy)) — snapshots each transform's *output schema*, so an unintended column/type change shows as a snapshot diff instead of silently reaching downstream consumers (the "schema evolution with `mergeSchema` can silently add columns" pitfall). Accept an intentional change with `pytest tests/unit/test_transform_contracts.py --snapshot-update`.

Run with coverage: `pytest tests/unit --cov=dbx_tests --cov-report=term-missing`.

**Layer 2 — integration** (`tests/integration/`):
- **Connectivity** (`test_connectivity.py`) — can connect, list catalogs/schemas.
- **Schema validation** (`test_schema_validation.py`) — column names/types match a pinned expected schema; catches schema drift.
- **Data quality** (`test_data_quality.py`) — null rates, value ranges, duplicate rows.
- **Row-count reconciliation** (`test_row_count_reconciliation.py`) — partitioned counts sum to the total.
- **Freshness** (`test_freshness.py`) — data isn't older than an SLA window.
- **Write/read roundtrip** (`test_write_read_roundtrip.py`) — data written to a scratch table reads back unchanged.
- **Referential integrity** (`test_referential_integrity.py`) — FK-style checks against the seeded sample structure below.
- **Fuzzy validation** (`test_fuzzy.py`, [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)) — typo'd categorical values (e.g. `"shiped"` vs `"shipped"`) and near-duplicate records (e.g. two customers whose names are a typo of each other) that exact `distinct()`/set-membership checks can't catch.

**Layer 3 — in-pipeline expectations** (`pipelines/orders_clean_expectations.sql`):
a Lakeflow Declarative Pipelines example with `EXPECT` constraints and
`ON VIOLATION DROP ROW` / `FAIL UPDATE` clauses. Deployed with the pipeline,
not run by pytest — this is what protects production data on every load.
[DQX](https://github.com/databrickslabs/dqx) (Databricks Labs) is an
alternative worth knowing for quarantine/annotate-style checks with a rule
profiler, but it's an unsupported Labs project and isn't wired into this
repo.

**Layer 4 — reconciliation**: compares Delta table versions via time travel
to prove a change didn't alter control totals it shouldn't have.
- `test_reconciliation.py` — small scale (~200 orders), runs on every merge.
- `test_reconciliation_bulk.py` — ~500k orders generated with [polars](https://pola.rs/) (`src/dbx_tests/bulk_data.py`; plain-Python row-by-row generation doesn't scale to that volume), catching data-skew/performance issues a small fixture can't. Skipped unless `DBX_TESTS_RUN_BULK=1` — meant for the nightly job, not every merge: `DBX_TESTS_RUN_BULK=1 pytest tests/integration/test_reconciliation_bulk.py -v`.

**Layer 5 — streaming** (`tests/integration/test_streaming.py`):
`availableNow` trigger draining, checkpoint-recovery duplicate detection,
and the "MERGE fails on duplicate source keys" bug class (and its fix via
`dedupe_by_key`).

**Layer 6 — performance** (`tests/integration/test_performance.py`): times
bulk write, a transform, and an aggregation query at realistic volume (500k
orders, `src/dbx_tests/bulk_data.py`) against wall-clock SLA constants —
catches a transform gone quadratic or a write/query that stopped pruning
partitions, not just wrong output. Skipped unless `DBX_TESTS_RUN_PERF=1` —
nightly-tier like `test_reconciliation_bulk.py`, not every merge:
`DBX_TESTS_RUN_PERF=1 pytest tests/integration/test_performance.py -v`.

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
- **Merge to main:** Layer 2 integration tests (plus the small-scale `test_reconciliation.py`) against a test workspace/catalog.
- **Nightly:** `test_reconciliation_bulk.py` (`DBX_TESTS_RUN_BULK=1`) — Layer 4 at realistic data volume; `test_performance.py` (`DBX_TESTS_RUN_PERF=1`) — Layer 6 SLA checks.
- **Every production load:** Layer 3 expectations, running inside the pipeline itself.

## Library choices

Added beyond the base `pytest`/Databricks Connect/PySpark stack, each for a
specific gap rather than by default:
- **[Hypothesis](https://hypothesis.readthedocs.io/)** — property-based tests for the pure transforms (Layer 1).
- **[syrupy](https://github.com/tophat/syrupy)** — schema-contract snapshots for the pure transforms (Layer 1).
- **[polars](https://pola.rs/)** — fast synthetic data generation at realistic volume for nightly reconciliation (Layer 4). Not used for the small-scale seed (`sample_data.py`) — plain Python is simpler and plenty fast at that size.
- **pytest-cov** — coverage reporting for Layer 1 (`--cov=dbx_tests`).
- **[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)** — fuzzy-match data validation (Layer 2, `src/dbx_tests/fuzzy.py`): typo'd categorical values and near-duplicate records that exact comparison misses. Chosen over fuzzywuzzy (unmaintained, GPL-licensed dependency) — rapidfuzz is the maintained MIT-licensed successor with a faster C++ core.

Considered and deliberately **not** added:
- **Great Expectations** — would duplicate what Layer 2 (plain `assert`) and Layer 3 (native Lakeflow expectations) already cover; see the rule in `.claude/agents/databricks-test-writer.md`. [DQX](https://github.com/databrickslabs/dqx) remains the noted alternative if a rule-profiler/quarantine workflow is ever needed.
- **chispa** — pyspark's built-in `pyspark.testing.assertDataFrameEqual` (used throughout Layer 1) already covers what chispa is for; adding both would be redundant.
- **Faker** — the hardcoded name/country/status lists in `sample_data.py` are already plausible and deterministic; Faker would add a dependency for a cosmetic improvement, not a capability gap.

## Claude Code integration

- `/databricks-tests` — checks config, runs the suite, summarizes results.
- `/diagnose-test-failure` — given one failing test, verdicts test-framework/infra issue vs. real data/pipeline bug, with evidence.
- `/databricks-performance-test` — runs Layer 6, reports measured durations vs. SLA, and distinguishes cold-start noise from a reproducible regression.
- **databricks-test-runner** sub agent — runs the suite and diagnoses failures (auth vs schema drift vs real data-quality issues).
- **databricks-test-writer** sub agent — scaffolds a new test module for another table, following the patterns above.

See `CLAUDE.md` for repo conventions.
