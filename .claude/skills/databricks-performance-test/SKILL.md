---
name: databricks-performance-test
description: Run and interpret Layer 6 (tests/integration/test_performance.py) — realistic-volume wall-clock duration checks for pipeline write/transform/query operations against an SLA. Use when the user asks whether the Databricks pipeline "performs well enough", about throughput/latency/duration regressions, or invokes "/databricks-performance-test".
---

# Performance testing (Layer 6)

`tests/integration/test_performance.py` times three pipeline operations at
realistic volume (500k orders, via `src/dbx_tests/bulk_data.py`) against a
wall-clock SLA constant: bulk write, a transform (`dedupe_by_key` +
`flag_high_value_orders` from `src/dbx_tests/transforms.py`), and an
aggregation query. Same env/venv as the rest of Layer 2 (`.venv`,
`requirements.txt`).

## Running it

1. Confirm `.env` is configured (see `.claude/skills/databricks-tests/SKILL.md` step for Layer 2+) — these tests skip cleanly without it.
2. It's gated like `test_reconciliation_bulk.py` — real volume, meaningfully slower, meant for a nightly job, not every merge:
   `DBX_TESTS_RUN_PERF=1 pytest tests/integration/test_performance.py -v`

## Interpreting results

- **Report the measured durations, not just pass/fail** — read them from the assertion message (`took Xs, exceeds Ys SLA`) even on a pass. A test passing at 170s against a 180s SLA is a warning sign worth surfacing, not a clean bill of health.
- **A single failure is not automatically a regression.** Cluster/serverless cold-start dominates timing variance far more than in the correctness-focused layers. Before reporting a real problem:
  1. Re-run the one failing test alone once more.
  2. If it passes on rerun, call it cold-start/transient and say so — don't treat it as a pipeline regression on one data point.
  3. If it fails reproducibly (2+ runs), treat it like any other real Layer 2 finding: report which operation, by how much it exceeded the SLA, and don't loosen the threshold to make it pass — see `CLAUDE.md`'s rule against loosening assertions on a real failure. Hand off to `/diagnose-test-failure` or the `databricks-test-runner` sub agent if the cause isn't obvious from the failing operation alone.
- **The SLA constants (`WRITE_SLA_SECONDS`, `TRANSFORM_SLA_SECONDS`, `QUERY_SLA_SECONDS`) are placeholders**, not calibrated against a specific cluster/serverless SKU — flagged with a `ponytail:` comment in the test file. If this is the first real run against the team's actual compute, say so explicitly and suggest calibrating the constants from a few clean runs before trusting the thresholds in CI, rather than silently changing them.

## Extending it

A new operation to time (e.g. a different transform, a MERGE) follows the
same pattern: reuse the `_timed()` context manager already in the file,
pick an SLA constant, assert `t["seconds"] <= SLA`. Don't add a new timing
library (stdlib `time.perf_counter()` is enough) or a new volume generator
(reuse `src/dbx_tests/bulk_data.py`) for this.
