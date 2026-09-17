---
name: databricks-tests
description: Set up and run this project's layered Databricks/ETL test suite (unit transform tests, plus integration connectivity/schema/data-quality/freshness/roundtrip/referential-integrity/reconciliation/streaming tests), and summarize results. Use when the user says "/databricks-tests", "run the databricks tests", or asks to check whether the Databricks connector/pipeline is working.
---

# Running the Databricks test suite

This project has two independently-runnable layers, each in its own Python
environment (see `CLAUDE.md`). Ask (or infer from context) which the user
wants — "run the tests" with no other signal means run both.

## Layer 1 — unit tests (no Databricks needed)

1. `uv venv .venv-unit && source .venv-unit/bin/activate` (skip venv creation if it already exists — just activate it).
2. `uv pip install -r requirements-unit.txt`.
3. `pytest tests/unit -v` (add `--cov=dbx_tests --cov-report=term-missing` for coverage).
4. These should always pass; a failure here is a real bug in `src/dbx_tests/transforms.py`, not a config/environment issue. This includes property-based tests (Hypothesis) and schema-contract snapshots (syrupy) — a syrupy failure after an *intentional* transform change is expected, not a bug: re-run with `--snapshot-update` on that file after confirming the new schema is correct.

## Layer 2+ — integration, reconciliation, streaming (needs a workspace)

1. **Check configuration.** Confirm `.env` exists (copy from `.env.example` if not) and that `DATABRICKS_HOST` / `DATABRICKS_TOKEN` / compute (`DATABRICKS_SERVERLESS` or `DATABRICKS_CLUSTER_ID`) are set. If not configured, tell the user the suite will run but every test will skip, and point them at `.env.example`.
2. `uv venv .venv && source .venv/bin/activate` (skip if it exists), `uv pip install -r requirements.txt`.
3. **Seed sample data if needed.** `test_referential_integrity.py` and `test_reconciliation.py` (and anything else using the `seeded_tables` fixture) automatically populate `customers`/`orders`/`order_items` in `DBX_TEST_CATALOG.DBX_TEST_SCHEMA` on first use via `dbx_tests.sample_data.seed()` — no manual step required. To (re-)populate it standalone, run `python -m dbx_tests.sample_data`.
4. **Run the suite**: `pytest tests/integration -v` from the repo root. This excludes `test_reconciliation_bulk.py` by default (it needs `DBX_TESTS_RUN_BULK=1` — it seeds ~500k rows with polars and is meant for a nightly job, not routine runs; only run it if the user explicitly asks for the realistic-volume/nightly check).

## Wrapping up

- **Summarize**: report pass/fail/skip counts per layer, and list any failing test names with a one-line reason each.
- **On failures**, hand off to the `databricks-test-runner` sub agent for root-cause diagnosis rather than re-running tests repeatedly yourself.
- **To add coverage** (a new table, transform, or check), hand off to the `databricks-test-writer` sub agent instead of writing test files directly here.
- Layer 3 (`pipelines/*.sql`, Lakeflow expectations) isn't run by pytest — it's deployed with the pipeline. Mention it only if the user is asking about production data-quality enforcement, not when just "running the tests."
