---
name: databricks-tests
description: Set up and run the Databricks pytest suite in this project (connectivity, schema, data quality, freshness, roundtrip tests), and summarize results. Use when the user says "/databricks-tests", "run the databricks tests", or asks to check whether the Databricks connector/pipeline is working.
---

# Running the Databricks test suite

1. **Check configuration.** Confirm `.env` exists (copy from `.env.example` if not) and that `DATABRICKS_HOST` / `DATABRICKS_TOKEN` / compute (`DATABRICKS_SERVERLESS` or `DATABRICKS_CLUSTER_ID`) are set. If not configured, tell the user the suite will run but every test will skip, and point them at `.env.example`.
2. **Install dependencies** if `databricks-connect` isn't already installed: `pip install -r requirements.txt`.
3. **Seed sample data if needed.** `tests/test_referential_integrity.py` (and anything else using the `seeded_tables` fixture) automatically populates `customers`/`orders`/`order_items` in `DBX_TEST_CATALOG.DBX_TEST_SCHEMA` on first use via `dbx_tests.sample_data.seed()` — no manual step required. To (re-)populate it standalone (e.g. to browse the data in the workspace), run `python -m dbx_tests.sample_data`.
4. **Run the suite**: `pytest tests/ -v` from the repo root.
5. **Summarize**: report pass/fail/skip counts, and list any failing test names with a one-line reason each.
6. **On failures**, hand off to the `databricks-test-runner` sub agent for root-cause diagnosis rather than re-running tests repeatedly yourself.
7. **To add coverage for a new table**, hand off to the `databricks-test-writer` sub agent instead of writing test files directly here.
