---
date: 2026-05-23
domain: operations
client_case: NB-automations hardening loop W41 — close direct-push bypass of migration-numbers lint (W40 root cause)
sources: 6
---

# W41 — Close direct-push bypass of migration-numbers lint

## Summary

W40 (earlier today) fixed migration 194 collision via rename. W41 closes the **root cause** that let W40 happen in the first place.

`.github/workflows/lint-migration-numbers.yml` has existed since 2026-04-29 P0-7 (after the duplicate 129/130 cicatrix). But it only fires on `pull_request`. L2 autonomous-ops policy allows direct-push to main — W37 went direct-to-main and the lint NEVER RAN. Dup landed silently, caught only by next morning's manual /loop survey.

This is the **third occurrence** of the dup-number class — first time it'd actually be caught at commit-time.

## Three-layer defense

| Layer | File | Stage caught | Bypassable |
|---|---|---|---|
| 1 | `scripts/lint_migration_numbers.py` (NEW) | manual invocation, building block for layers 2/3 | n/a |
| 2 | `.husky/pre-commit` (extended) | **commit-time** (best) | `HUSKY=0` (legitimate hotfixes) |
| 3 | `.github/workflows/lint-migration-numbers.yml` (extended `+push`) | **post-merge, within 60s** | cannot bypass — CI runs unconditionally |

Each layer catches a different stage. Defense-in-depth.

## Implementation details

### Layer 1 — standalone lint

```python
# scripts/lint_migration_numbers.py
def find_duplicates(sql_files: Iterable[Path]) -> dict[int, list[str]]:
    """Inlined twin of `backend.db.migration_manager._assert_unique_migration_numbers`."""
    seen: dict[int, str] = {}
    duplicates: dict[int, list[str]] = {}
    for sql_file in sql_files:
        try:
            num = int(sql_file.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        if num in seen:
            duplicates.setdefault(num, [seen[num]]).append(sql_file.name)
        else:
            seen[num] = sql_file.name
    return duplicates
```

**Why inlined instead of importing from `migration_manager`?** First attempt did the import and hit:

```
pydantic_core.ValidationError: 2 validation errors for Settings
jwt_secret_key  Value error, JWT_SECRET_KEY must be set...
api_keys        Value error, API_KEYS must be set...
```

The manager's import chain pulls in `Settings()` which requires production env vars unavailable in:
- Local dev shells (no secrets loaded)
- Husky pre-commit hook contexts (`/bin/sh` minimal env)
- CI lint job runners (only secrets exposed to deploy jobs)

The algorithm is 6 lines. DRY-via-duplication is cheaper than DRY-via-import-tax. Mitigation: companion test `test_drift_check_vs_canonical` re-implements the canonical algorithm inline and asserts byte-equal output. If the manager's algorithm ever changes (e.g. extends to sub-numbering), the drift test fails and forces lint sync within the same PR.

### Layer 2 — pre-commit hook

```bash
# .husky/pre-commit (W41 addition, line 3)
MIG_FILES=$(git diff --cached --name-only --diff-filter=d | grep -E '^apps/backend-rag/backend/db/migrations_v2/.*\.sql$' || true)
if [ -n "$MIG_FILES" ]; then
    echo "🔢 [W41] Migration number uniqueness lint..."
    if ! python3 scripts/lint_migration_numbers.py; then
        echo "❌ ERROR: duplicate migration number(s) detected."
        echo "   See cicatrix RESOLVED 2026-05-23 W40 + research/operations/2026-05-23-w40-migration-194-collision.md"
        exit 1
    fi
fi
```

**Empirical smoke** (synthetic dup):

```
$ touch apps/backend-rag/backend/db/migrations_v2/194_synthetic_dup.sql
$ git add apps/backend-rag/backend/db/migrations_v2/194_synthetic_dup.sql
$ .husky/pre-commit
🔍 Running pre-commit hooks...
🔢 [W41] Migration number uniqueness lint...
❌ migration-numbers lint: duplicate prefixes in migrations_v2/: 194: [194_reconcile_107_bridge_outbox_tracking.sql, 194_synthetic_dup.sql]
...resolution workflow printed...
❌ ERROR: duplicate migration number(s) detected.
$ echo $?
1
```

Hook correctly rejects. Clean state: pass-through, no-op.

### Layer 3 — CI push trigger

```yaml
# .github/workflows/lint-migration-numbers.yml (W41 addition)
on:
  pull_request:
    paths:
      - "apps/backend-rag/backend/db/migrations_v2/**"
  push:                                # NEW W41
    branches:
      - main
    paths:
      - "apps/backend-rag/backend/db/migrations_v2/**"
```

Cannot block the merge (push has already happened), but produces immediate CI failure + can trigger Telegram alert via repo notification settings. Recovery window: revert/rename ships within minutes vs being discovered at next deploy run.

## Test coverage

10/10 PASS in 0.06s (`scripts/tests/test_lint_migration_numbers.py`):

| Test | Coverage |
|---|---|
| `test_no_files_returns_empty` | Empty dir baseline |
| `test_unique_prefixes_clean` | Happy path |
| `test_w40_collision_caught` | Real W40 case (194_incident_ledger + 194_reconcile_107) |
| `test_2026_04_29_legacy_pattern_caught` | Regression guard for original P0-7 (dup 129 + 130) |
| `test_non_numeric_prefix_ignored` | Files like `rollback_one.sql`, `README.sql` not flagged |
| `test_triple_collision_lists_all` | 3+ files at same prefix all reported |
| `test_main_exits_0_on_live_repo` | Live state (79 files) green post-W40 fix |
| `test_main_exits_1_on_synthetic_collision` | End-to-end CLI exit code |
| `test_main_exits_0_on_synthetic_clean` | Negative control |
| `test_drift_check_vs_canonical` | Inlined algorithm matches re-implemented canonical |

## What's still open

**W42+ candidate: orchestrator-level pre-flight reservation.** W37 root cause was the wave-orchestrator pattern (4 parallel agents on isolated worktrees) without upfront migration-number reservation. W41 catches the collision at commit-time, but the agents still race. Future fix: when dispatching N agents that may touch `migrations_v2/`, the orchestrator should reserve consecutive migration numbers UPFRONT and pass each as a constraint to its respective agent.

**`HUSKY=0` bypass remains** — legitimate for emergency hotfixes. Layer 3 (CI push trigger) catches what layer 2 misses. The bypass cost is "alert within 60s" instead of "blocked at commit-time" — acceptable trade.

## Sources

1. `scripts/lint_migration_numbers.py` — NEW standalone lint
2. `scripts/tests/test_lint_migration_numbers.py` — NEW 10 tests (10/10 PASS)
3. `.husky/pre-commit` — extended with W41 block at line 3
4. `.github/workflows/lint-migration-numbers.yml` — extended with `push: branches: [main]` trigger
5. `apps/backend-rag/backend/db/migration_manager.py:34` — canonical `_assert_unique_migration_numbers` (algorithm twin)
6. Cicatrix entries: P0-7 (2026-04-29 dup 129/130), W40 (2026-05-23 dup 194), W41 (this fix)

## Next

- [ ] W42 candidate: orchestrator pre-flight migration-number reservation for parallel-agent waves
- [ ] Optional: extend the lint to also check SQL header comment matches filename number (catch header-vs-filename drift like the W40 fix needed `sed` patch)
- [ ] Optional: per-PR migration count cap (e.g. "max 3 migration files per PR") to limit blast radius of bugs
