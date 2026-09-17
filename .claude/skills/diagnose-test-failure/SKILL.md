---
name: diagnose-test-failure
description: Given a failing test (name, traceback, or pytest output) in this repo, determine whether it's a test-framework/infra problem (fixture, env, config, flaky, stale test code) or a real bug in the data/pipeline — and say which, with evidence. Use when the user asks "is this a real bug or a test problem", "why did this test fail", pastes a traceback, or invokes "/diagnose-test-failure".
---

# Diagnose: framework issue or real bug?

This is a narrower, standalone version of the triage `databricks-test-runner`
does after a full suite run — use this when you already have one failure
(pasted output, a test name, or `pytest ... -k <name>` you just ran) and want
a verdict without re-running the whole suite.

## 1. Get the evidence

If you only have a test name, run it alone first:
`pytest <path>::<test_name> -v` in the matching environment (`.venv-unit`
for `tests/unit`, `.venv` for `tests/integration` — see `CLAUDE.md`). Read
the full traceback, not just the assertion line — where the exception
originates (fixture setup vs the test body vs a Spark job) is most of the
signal.

## 2. Classify using the existing taxonomy

Map the failure to a category from `.claude/agents/databricks-test-runner.md`
(config/auth, schema drift, data quality/referential integrity, reconciliation
drift, streaming bug class, unit/transform logic bug, schema contract break,
environment/transient). Then bucket that category:

**Framework/infra — not a data bug:**
- Config/auth (bad `.env`, expired token)
- Environment/transient (cluster still starting, permission error on scratch
  schema, pyspark/pandas version mismatch in `.venv-unit`)
- Failure originates inside a fixture (`conftest.py`, `sample_data.py`,
  `bulk_data.py`) rather than the test body — the seed/harness is broken,
  not the thing it's testing
- Test passes in isolation but fails as part of the full suite — shared
  state / ordering bug in the test, not the data
- An *intentional* change (transform, schema, threshold) that the test
  wasn't updated for — e.g. a syrupy snapshot diff after a deliberate
  `transforms.py` change

**Real bug — the pipeline or data is actually wrong:**
- Data quality / referential integrity / freshness assertion fails against
  real or seeded data with no fixture/env explanation
- Schema drift: actual columns/types differ from `EXPECTED_SCHEMA`
- Reconciliation drift between Delta versions with no intentional
  generator/seed change to explain it
- `test_merge_fails_on_duplicate_source_keys`-style streaming test failing
  to raise — the bug it's designed to catch is present
- Unit test (`tests/unit/`) failure — data there is fully synthetic and
  controlled, so a failure is almost always the transform logic itself,
  not the framework

## 3. Disambiguate when it's not obvious

- **Isolation check**: `pytest <path>::<test_name> -v` alone vs. the full
  file/suite. Passes alone, fails together → framework (test isolation),
  not data.
- **Recency check**: `git log -p --follow -- <test file>` and the fixture/
  source file(s) it depends on. If the fixture or test code changed
  recently and the source didn't, suspect the harness; if source/pipeline
  code changed and the test didn't, suspect a real regression.
- **Reproducibility**: re-run once. A `test_reconciliation_bulk.py`-style
  data-skew test or a flaky network call can differ run to run; a
  deterministic data-quality assertion on seeded data should not.

## 4. Report

One paragraph: **verdict** (framework issue / real bug), the **category**,
the **evidence** that pointed there, and the **next action** — e.g. "fix
`conftest.py`'s fixture" vs. "escalate: `orders_clean` has real nulls in
`amount`, does not belong in the test."

Never resolve a "real bug" verdict by loosening the assertion/threshold —
that's explicitly called out as wrong in `CLAUDE.md`. If genuinely unsure
after the checks above, say so rather than guessing, and suggest handing
off to `databricks-test-runner` for a full-suite pass to gather more
signal.
