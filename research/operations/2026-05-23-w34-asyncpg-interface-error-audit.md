---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W34 broader asyncpg.PostgresError audit + lint guard (W32 follow-up)
sources: 4
---

# W34 — broader asyncpg audit + lint guard (W32 follow-up)

## Why

W32 fixed pg-bridge silent-death from `asyncpg.InterfaceError` escaping `except (asyncpg.PostgresError, ...)`. W32 closure mentioned "pattern coverage 2/2 known instances". W34 verifies via grep and finds **more silent-death traps** in long-running daemons.

## Audit method

```bash
grep -rn "except.*asyncpg\.PostgresError" --include="*.py" -l
```

31 file matches. Triage by daemon-class:

- **Long-running daemons / reconnect loops** (critical — W29/W32 family): wr2_supervisor.py (3 sites), pg-to-organism-bridge.py (W32 already fixed), wr2_supervisor_watchdog.py (W29 already fixed)
- **Cron one-shots** (medium — cron failure is visible via exit code, but adding InterfaceError is cheap): lead_intent_matcher.py, crm_automation_engine.py
- **HTTP routers / agents / base_repository / test fixtures** (low — request-scoped, no daemon loop, caller handles): ~25 files exempt by policy

## Fixes shipped (commit `cb32f8214`)

### Daemon patches

| File | Sites | Class |
|---|---|---|
| `scripts/wr2_supervisor.py` | 3 (lines 292, 479, 651) | Long-running daemon with LISTEN + heartbeat + outer reconnect loop |
| `scripts/lead_intent_matcher.py` | 1 (line 166) | Cron one-shot fallback path |
| `apps/backend-rag/scripts/crm_automation_engine.py` | 1 (line 532) | Pool creation retry loop |

All patched with the canonical pattern:

```python
except (
    asyncpg.PostgresError,
    asyncpg.InterfaceError,  # W34: sibling of PostgresError, NOT subclass
    OSError,
    asyncio.TimeoutError,
) as exc:
```

Inline comment is load-bearing — prevents future refactor from stripping the entry.

### Lint guard

**`scripts/lint_asyncpg_except_completeness.py`** (164 lines): scans every `except` clause across `scripts/`, `apps/`, `packages/` (excluding `.venv`, `node_modules`, `tests/`, HTTP routers, agents, base_repository per ALLOW_PREFIXES). For each clause that mentions `asyncpg.PostgresError` without `asyncpg.InterfaceError`, emits diff-style violation + remediation template + exit 1.

Live codebase post-W34 fixes: **0 violations, exit 0**.

```
✅ asyncpg-lint: no violations — all `except asyncpg.PostgresError` clauses
   also catch InterfaceError
```

### Lint tests

**`scripts/tests/test_lint_asyncpg_except_completeness.py`** (131 lines, 11/11 PASS in 6.33s):

- `test_bare_postgres_error_is_violation`
- `test_tuple_with_postgres_no_interface_is_violation`
- `test_tuple_with_both_is_clean`
- `test_venv_path_out_of_scope` — vendored asyncpg in .venv legitimately uses bare pattern
- `test_node_modules_out_of_scope`
- `test_tests_dir_out_of_scope`
- `test_allow_prefix_routers_out_of_scope`
- `test_scripts_in_scope`
- `test_cell_in_scope`
- `test_no_postgres_at_all_returns_empty`
- `test_main_exit_0_on_clean` — live codebase regression guard (fails if any future commit re-introduces the anti-pattern)

## Scope policy (allow-list)

Exempt paths and rationale:

| Path | Why exempt |
|---|---|
| `apps/backend-rag/backend/app/routers/` | HTTP handlers — request-scoped, no daemon loop. Connection failure returns 500 to client, no silent-death class. |
| `apps/backend-rag/backend/agents/` | Per-call agents, no long-running connection state. |
| `apps/backend-rag/backend/db/base_repository.py` | Per-query retry helper; caller responsible for reconnect at higher layer. |
| `apps/backend-rag/backend/db/migration_base.py` | One-shot migration runner. |
| `apps/backend-rag/backend/services/portal/_mixins/billing.py` | One-shot billing operation. |
| `*/tests/*` | Test fixtures legitimately catch PostgresError only (testing the happy path). |

Adding a new exempt path: add prefix to `ALLOW_PREFIXES` in `scripts/lint_asyncpg_except_completeness.py` with comment explaining why.

## CI integration (deferred to W35)

The lint script can be invoked manually:

```bash
python3 scripts/lint_asyncpg_except_completeness.py
```

Future W35 candidate: add `.github/workflows/asyncpg-lint.yml` triggering on push/PR touching any `.py` under `scripts/` or `apps/`. Same pattern as `scripts/lint_symbiosis_promises.py` + `.github/workflows/symbiosis-lint.yml`.

## Sources

1. `grep -rn "except.*asyncpg\.PostgresError"` — 31 file matches across repo
2. `scripts/wr2_supervisor.py:285-302, 470-482, 645-660` — fixed reconnect loops
3. `scripts/lint_asyncpg_except_completeness.py` — programmatic linter
4. `scripts/tests/test_lint_asyncpg_except_completeness.py` — 11/11 PASS
