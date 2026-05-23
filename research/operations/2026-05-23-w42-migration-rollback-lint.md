---
date: 2026-05-23
domain: operations
client_case: NB-automations hardening loop W42 — preventive lint for inline ROLLBACK marker
sources: 6
---

# W42 — Migration ROLLBACK marker presence lint

## Summary

Immediately after W37 shipped `195_organism_incident_ledger.sql` (renamed from 194 by W40 fix), a sibling agent caught a SECOND quality issue with the same file: **missing inline `-- === ROLLBACK ===` marker**. `BaseMigration.__init__` (post-2026-04-18 enforcement at `apps/backend-rag/backend/db/migration_base.py:239`) requires every migration_number > 111 to declare rollback SQL inline. Missing marker raises `ValueError` at module-import time, blocking ALL pending migrations.

Sibling fix `2d864e402` patched the file. W42 is the **preventive lint** that catches this class at commit-time, same 3-layer pattern as W41 but with **PR + push triggers from day 1** (W41 cicatrix lesson).

## Why this happened

W37 author documented the rollback procedure in `research/operations/2026-05-23-w37-incident-ledger.md` — good practice for human readers. But the runner doesn't read docs; it greps the SQL file. The discipline of "always include rollback" is enforced only by:

1. Manual code review (skipped for direct-push agents)
2. Deploy-time `ValueError` (catastrophic — blocks ALL pending)

Sibling caught it within 10min via post-deploy verification on a wa-dashboard PR that was waiting to ship. Lucky timing. W42 makes it deterministic.

## Three-layer defense

| Layer | File | Stage caught | Note |
|---|---|---|---|
| 1 | `scripts/lint_migration_rollback.py` (NEW) | building block | Standalone, inlined regex from `migration_base.py:29` |
| 2 | `.husky/pre-commit` (extended) | **commit-time** | Runs after W41 number-uniqueness check |
| 3 | `.github/workflows/lint-migration-rollback.yml` (NEW) | PR-time AND post-push | **Both triggers from day 1** — W41 lesson applied |

W41 took 1 cicatrix iteration to learn that `pull_request`-only triggers leave a direct-push gap. W42 ships the lesson preemptively: the new CI workflow has both triggers from commit zero. Total elapsed time from W41 ship to W42 ship: ~30min.

## Test coverage

14/14 PASS in 0.13s (`scripts/tests/test_lint_migration_rollback.py`):

| Test | Purpose |
|---|---|
| `test_post_cutoff_with_marker_clean` | Happy path |
| `test_post_cutoff_without_marker_flagged` | Core enforcement |
| `test_pre_cutoff_without_marker_grandfathered` | Legacy <=111 ignored |
| `test_cutoff_boundary_111_grandfathered` | Boundary inclusive |
| `test_cutoff_boundary_112_requires_marker` | Boundary exclusive |
| `test_non_numeric_filename_ignored` | README/rollback files skipped |
| `test_w37_actual_case_flagged` | Reproduces W37 pre-fix state |
| `test_2d864e402_fix_state_clean` | Reproduces sibling's fix state |
| `test_marker_regex_strict` | Bad variants (missing ===, lowercase, trailing) caught |
| `test_marker_regex_accepts_zero_whitespace` | Sanity: `--===ROLLBACK===` IS valid |
| `test_marker_regex_lenient_on_whitespace` | Leading/trailing horizontal whitespace OK |
| `test_main_exits_0_on_live_repo` | Live state green post-2d864e402 |
| `test_main_exits_1_on_synthetic_missing` | E2E CLI exit code |
| `test_drift_check_vs_canonical` | **Regex byte-equal to `migration_base.py:29`** |

The drift-check test is the load-bearing one: if `BaseMigration` ever updates its regex (e.g. relaxes case-sensitivity, adds alternative markers), the lint regex must be updated in lockstep or the test fails. This is the same drift-control pattern as W41.

## Smoke evidence

Live repo state:

```
$ python3 scripts/lint_migration_rollback.py
✅ migration-rollback lint: 74 post-cutoff migrations, all have ROLLBACK marker
```

Synthetic missing-marker file:

```
$ echo "CREATE TABLE smoke();" > migrations_v2/199_w42_smoke.sql
$ git add migrations_v2/199_w42_smoke.sql
$ .husky/pre-commit
🔢 [W41] Migration number uniqueness lint... ✅
🧯 [W42] Migration ROLLBACK marker presence lint...
❌ migration-rollback lint: 1 migration(s) > 111 missing `-- === ROLLBACK ===` marker:
  - apps/backend-rag/backend/db/migrations_v2/199_w42_smoke.sql
[exit 1]
```

Hook chain works end-to-end. Layer order matters — number-uniqueness first (cheaper, catches dup before disk-read), rollback marker second (per-file scan).

## Discovered while shipping (gotcha)

My first test version asserted that `--===ROLLBACK===` (no spaces) should be REJECTED. Smoke failed: canonical regex `^\s*--\s*===\s*ROLLBACK\s*===\s*$` actually ACCEPTS it because `\s*` matches zero whitespace at every position. Fixed by reading the canonical regex more carefully + adding `test_marker_regex_accepts_zero_whitespace` as positive control. Lesson: when locking a contract via tests, the test asserts what the canonical does, not what I think it does.

## What's still open

**W43+ candidate**: extend lint to ALSO check that the inline rollback section ACTUALLY contains DROP/ALTER statements (not empty). A migration with `-- === ROLLBACK ===` followed by zero SQL would pass W42 but still be useless at rollback time. Test case: `-- === ROLLBACK ===\n-- TODO: write rollback later`.

**W43+ candidate**: extend lint to require that rollback statements reference the SAME tables/objects as the forward migration. Currently a migration could `CREATE TABLE foo` then declare `DROP TABLE bar` rollback — would parse fine but actually destroy unrelated state. Detection: parse both halves for object names, assert overlap.

**Orchestrator pre-flight (W42 deferred)**: still want pre-flight migration-number reservation for parallel-agent waves. Separate ticket — orchestrator-level fix, not lint-level.

## Sources

1. `scripts/lint_migration_rollback.py` — NEW standalone lint
2. `scripts/tests/test_lint_migration_rollback.py` — NEW 14 tests
3. `.husky/pre-commit` — extended with W42 block after W41 block
4. `.github/workflows/lint-migration-rollback.yml` — NEW with PR + push triggers
5. `apps/backend-rag/backend/db/migration_base.py:29` — canonical ROLLBACK_MARKER_RE
6. `apps/backend-rag/backend/db/migration_base.py:239` — enforcement at constructor

## Next

- [ ] W43 candidate: enforce non-empty rollback section + object-name overlap
- [ ] W42 follow-up: monitor if the lint fires on a real new migration in next 7d — confirms detection in practice
- [ ] Still-open from W41: orchestrator pre-flight migration-number reservation (parallel-agent waves)
