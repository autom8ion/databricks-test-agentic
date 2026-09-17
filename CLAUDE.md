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
replaces the `pyspark` package with a remote-only client. Both are managed
with [uv](https://docs.astral.sh/uv/) as two separate `uv venv` + `uv pip
install` environments, **not** a single `uv sync`/`uv.lock` project: a
shared lock forces one dependency resolution to satisfy both files, which
broke a previous pandas version pin (needed only in `requirements-unit.txt`)
in the integration env. If you're tempted to add a
`[project]`/`[dependency-groups]` table to `pyproject.toml` to "properly"
manage this as one uv project, don't — this was tried and reverted for
exactly that reason.

Both environments currently target Python 3.14 (`uv venv`'s default here).

- Editing/running `tests/unit/**` → use `.venv-unit` (`uv venv .venv-unit && uv pip install -r requirements-unit.txt`).
- Editing/running `tests/integration/**` or `src/dbx_tests/{connector,sample_data}.py` → use `.venv` (`uv venv .venv && uv pip install -r requirements.txt`).
- Never add a bare `pyspark` dependency to `requirements.txt`, and never add `databricks-connect` to `requirements-unit.txt`.
- `pyproject.toml` deliberately has no default `testpaths` — always run `pytest tests/unit` or `pytest tests/integration` explicitly, never bare `pytest`.

`requirements-unit.txt` requires `pyspark>=4.2`: earlier pyspark 4.0.x's
pandas-on-Spark compat layer (a transitive import of
`pyspark.testing.assertDataFrameEqual`) broke on pandas>=2.2, and pandas
versions old enough to avoid that have no Python 3.14 wheel. pyspark>=4.2
resolves against current pandas fine (just a `FutureWarning` about
pandas>=3.0 support, not an error). Don't drop below `pyspark>=4.2` in that
file without re-running `pytest tests/unit` in a clean venv first.

## Conventions

- **Transformation logic is pure functions**, `DataFrame -> DataFrame`, in `src/dbx_tests/transforms.py` — no I/O, no notebook-only code. This is what makes Layer 1 possible; don't add pipeline logic that only works inside a notebook.
- **Tests never construct their own SparkSession or import `databricks.connect`/`pyspark` connection code directly.** They take `spark` from a fixture (`tests/unit/conftest.py` for local Spark, `tests/integration/conftest.py` for the Databricks Connect session).
- **New transform functions get three things in `tests/unit/`, not just one:** an example-based test (`test_transforms.py`), a property-based test with Hypothesis (`test_transforms_properties.py` — test invariants like "output is never X" or "count is preserved," not a reimplementation of the function's logic), and a schema-contract snapshot with syrupy (`test_transform_contracts.py`). Hypothesis tests over a `spark` fixture need `@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])` — a Spark job per example is slower than Hypothesis's default budget, and the session-scoped fixture is safe to reuse across examples despite the health check's default assumption otherwise.
- **New integration tests reuse `seeded_tables`** (customers/orders/order_items, `src/dbx_tests/sample_data.py`) when they need multi-table/FK/known-good data, instead of writing new ad-hoc seeding logic. Reach for `sample_table` (`samples.nyctaxi.trips`) only when a test genuinely wants read-only, workspace-provided data. For realistic-volume (hundreds of thousands of rows) needs, use `src/dbx_tests/bulk_data.py` (polars-based, vectorized) rather than a Python loop — see `test_reconciliation_bulk.py`.
- **A test that needs real volume to be meaningful (data-skew, performance, large-scale reconciliation) belongs behind an env-var skip** (see `DBX_TESTS_RUN_BULK` in `test_reconciliation_bulk.py`), not in the default integration run — it's meant for a nightly job, not every merge.
- **Scratch/throwaway tables get dropped in a `finally` block** by the test that created them (see `scratch_table` usage in `test_write_read_roundtrip.py`, `test_streaming.py`). Seeded structural tables (`seeded_tables`, `orders_bulk`) are not dropped — they're meant to persist for inspection and are idempotently overwritten on the next seed.
- **A failing data-quality/referential-integrity/reconciliation test is often correct, not a bug in the test.** Don't loosen an assertion or threshold to make a failure go away without saying explicitly that's what you're doing and why it's the right call.
- **Config always flows through `src/dbx_tests/config.py`** (env vars, loaded via `.env`). Never hardcode a host/token/catalog/schema in a test or script.
- **Don't add Great Expectations, DQX, chispa, or Faker** without a concrete gap none of the existing tools cover — see "Library choices" in `README.md` for why each was already considered and left out.

## Claude Code project layout

- `.claude/agents/databricks-test-runner.md` — runs `tests/integration` and diagnoses failures (auth vs schema drift vs real data-quality issues vs transient). Prefer delegating to it over manually re-running failing tests.
- `.claude/agents/databricks-test-writer.md` — scaffolds new integration test modules following existing patterns and fixtures.
- `.claude/skills/databricks-tests/SKILL.md` — `/databricks-tests`, the orchestration entry point (check config → seed if needed → run → summarize → hand off on failure).

## Verifying a change

- Transform logic (`src/dbx_tests/transforms.py`) or `tests/unit/**`: `source .venv-unit/bin/activate && pytest tests/unit -v` (create the venv first if it doesn't exist: see setup commands above).
- Connector, config, sample data, or `tests/integration/**`: `source .venv/bin/activate && pytest tests/integration -v` — should show all-skipped without a configured `.env`, and should actually exercise the assertions once one is set up. If you don't have a live workspace to test against, say so rather than claiming the integration suite passed.
