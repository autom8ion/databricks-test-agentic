# CLAUDE.md

Guidance for Claude Code working in this repo. See `README.md` for the
human-facing setup/usage docs; this file is about how to work here.

## What this is

A layered test suite for a Databricks ETL pipeline, plus the PySpark
connector it tests against. There isn't one "Databricks testing tool" —
each layer (`README.md` has the full table) catches a different failure
class. When adding test coverage, place it in the layer that actually
catches the failure, don't default to Layer 2 for everything.

## Two environments, never mixed

`requirements.txt` (Databricks Connect) and `requirements-unit.txt` (plain
PySpark) cannot be installed in the same virtualenv — Databricks Connect
replaces the `pyspark` package with a remote-only client. Concretely:

- Editing/running `tests/unit/**` → use `.venv-unit` (`pip install -r requirements-unit.txt`).
- Editing/running `tests/integration/**` or `src/dbx_tests/{connector,sample_data}.py` → use `.venv` (`pip install -r requirements.txt`).
- Never add a bare `pyspark` dependency to `requirements.txt`, and never add `databricks-connect` to `requirements-unit.txt`.
- `pyproject.toml` deliberately has no default `testpaths` — always run `pytest tests/unit` or `pytest tests/integration` explicitly, never bare `pytest`.

If you touch `requirements-unit.txt`, know that pandas is pinned
(`pandas==2.1.4`) because `pyspark.testing.assertDataFrameEqual` transitively
imports pyspark's pandas-on-Spark compat layer, which breaks on pandas>=2.2
as of pyspark 4.0.1. Don't loosen that pin without re-running
`pytest tests/unit` in a clean venv first.

## Conventions

- **Transformation logic is pure functions**, `DataFrame -> DataFrame`, in `src/dbx_tests/transforms.py` — no I/O, no notebook-only code. This is what makes Layer 1 possible; don't add pipeline logic that only works inside a notebook.
- **Tests never construct their own SparkSession or import `databricks.connect`/`pyspark` connection code directly.** They take `spark` from a fixture (`tests/unit/conftest.py` for local Spark, `tests/integration/conftest.py` for the Databricks Connect session).
- **New integration tests reuse `seeded_tables`** (customers/orders/order_items, `src/dbx_tests/sample_data.py`) when they need multi-table/FK/known-good data, instead of writing new ad-hoc seeding logic. Reach for `sample_table` (`samples.nyctaxi.trips`) only when a test genuinely wants read-only, workspace-provided data.
- **Scratch/throwaway tables get dropped in a `finally` block** by the test that created them (see `scratch_table` usage in `test_write_read_roundtrip.py`, `test_streaming.py`). Seeded structural tables (`seeded_tables`) are not dropped — they're meant to persist for inspection and are idempotently overwritten on the next seed.
- **A failing data-quality/referential-integrity/reconciliation test is often correct, not a bug in the test.** Don't loosen an assertion or threshold to make a failure go away without saying explicitly that's what you're doing and why it's the right call.
- **Config always flows through `src/dbx_tests/config.py`** (env vars, loaded via `.env`). Never hardcode a host/token/catalog/schema in a test or script.

## Claude Code project layout

- `.claude/agents/databricks-test-runner.md` — runs `tests/integration` and diagnoses failures (auth vs schema drift vs real data-quality issues vs transient). Prefer delegating to it over manually re-running failing tests.
- `.claude/agents/databricks-test-writer.md` — scaffolds new integration test modules following existing patterns and fixtures.
- `.claude/skills/databricks-tests/SKILL.md` — `/databricks-tests`, the orchestration entry point (check config → seed if needed → run → summarize → hand off on failure).

## Verifying a change

- Transform logic (`src/dbx_tests/transforms.py`) or `tests/unit/**`: `source .venv-unit/bin/activate && pytest tests/unit -v`.
- Connector, config, sample data, or `tests/integration/**`: `source .venv/bin/activate && pytest tests/integration -v` — should show all-skipped without a configured `.env`, and should actually exercise the assertions once one is set up. If you don't have a live workspace to test against, say so rather than claiming the integration suite passed.
