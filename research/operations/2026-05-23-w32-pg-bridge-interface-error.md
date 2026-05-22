---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W32 pg-bridge asyncpg.InterfaceError silent-death fix (W27 panel deferred item)
sources: 5
---

# W32 — pg-bridge asyncpg.InterfaceError fix (W27 silent-NOTIFY-drop)

## Trauma

During W27 live production test 2026-05-23 04:42-05:25 WITA, the pg-bridge daemon process kept running with healthy heartbeat ticks (`~/.organism/last_seen/pro.pg_organism_bridge.json` updated every 60s) but had ZERO open TCP connections to PG for ~50min:

```
PID 2409 state=running heartbeat=fresh
lsof -p 2409 | grep 15432  → empty
```

Empirical signature identical to W29 watchdog burn: `asyncpg.InterfaceError` is a SIBLING of `PostgresError` (not subclass), so the except tuple in `_run_listener`:

```python
except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
```

did NOT catch it. When the keep-alive `SELECT 1` raised `InterfaceError` on a stale conn (pg-proxy briefly disconnected, possibly Fly DNS hiccup per W26 pattern), the exception escaped → `_run_listener` task crashed → outer daemon kept the heartbeat loop alive (separate task) creating the false-positive "healthy" signal.

Impact: 50min of NOTIFY events dropped silently. Any W27 sustained-red events emitted during that window would have been invisible to Organism — auto-heal blind during the very outage class it was built for.

## Root cause analysis

`asyncpg` exception hierarchy (verified via `python -c "import asyncpg; help(asyncpg.InterfaceError.__mro__)"`):

```
Exception
├── asyncpg.exceptions._base.PostgresError      (DB errors: query, auth, etc.)
└── asyncpg.exceptions._base.InterfaceError     (connection state errors)
```

`InterfaceError` covers: "connection is closed", "cannot perform operation: another operation is in progress", "stale connection". `PostgresError` covers wire-protocol DB errors. They are siblings.

The intuition trap: developers see `PostgresError` in the except tuple and assume it's the base class (it isn't). Lint/typecheck won't catch this — both are valid `Exception` subclasses, the except runs at runtime, and the only signal is silent-death under specific timing.

## Fix shipped (commit `630f1bd1d`)

### 1. `scripts/pg-to-organism-bridge.py` (line 246)

```python
except (
    asyncpg.PostgresError,
    asyncpg.InterfaceError,  # W32: sibling of PostgresError, NOT subclass
    OSError,
    asyncio.TimeoutError,
) as exc:
```

Inline comment is load-bearing: a future refactor reformatting the tuple alphabetically could strip the entry without realizing the W29/W32 rationale.

### 2. `scripts/tests/test_pg_to_organism_bridge_interface_error.py` (5 tests, 5/5 PASS)

- `test_script_exists` — base file presence
- `test_except_tuple_includes_interface_error` — regression guard on the fix
- `test_w29_sibling_reasoning_comment_present` — guards the comment so a refactor pass can't silently strip it
- `test_channels_includes_cell_pulse_sustained_red` — W27 path A channel regression
- `test_warning_channels_classifies_sustained_red` — W27 severity classification regression

Source-textual tests rather than runtime tests because the script uses hyphenated filename (`pg-to-organism-bridge.py`) which can't be imported as a Python module without `importlib.util` workaround. Textual tests are sufficient for the structural guard.

### 3. Live restart verification

```
$ launchctl kickstart -k gui/$(id -u)/com.nuzantara.pg-organism-bridge
$ launchctl print gui/$(id -u)/com.nuzantara.pg-organism-bridge | grep state
        state = running
        pid = 67325

$ tail -3 ~/logs/pg-organism-bridge.error.log
2026-05-23 06:08:20,277 connecting to PG: 127.0.0.1:15432/nuzantara_rag
2026-05-23 06:08:21,667 LISTEN on 15 channels active
```

15 channels = 14 baseline + `cell_pulse_sustained_red` (W27 path A). All re-armed.

## Same pattern coverage audit (defense-in-depth)

Other places in the codebase that catch `asyncpg.PostgresError`:

```bash
$ grep -rn "asyncpg.PostgresError" apps/ scripts/ packages/ 2>/dev/null
scripts/wr2_supervisor_watchdog.py:399,407 (W29 already fixed)
scripts/pg-to-organism-bridge.py:246 (W32 just fixed)
```

Two known instances. Both now patched. Future audit candidate (W33+): broader sweep with `grep -rn "except.*PostgresError" --include="*.py"` to catch any other untracked occurrences before they bite.

## Open W27-panel items remaining (deferred to W33+)

| Item                                             | Status                           | Priority    |
| ------------------------------------------------ | -------------------------------- | ----------- |
| Kill switch `CELL_AUTOREMEDIATION_ENABLED=false` | not implemented                  | P2          |
| Durable incident ledger table                    | partial (decisions.jsonl exists) | P3          |
| Stale-event TTL guard on bridge replay           | not implemented                  | P2          |
| `backend_rag_v2` rolsuper=t demotion             | open                             | P1 SECURITY |
| 8 dependabot vulns (3 high, 5 moderate)          | open                             | P2 SECURITY |

## Sources

1. `~/logs/pg-organism-bridge.error.log` — pre/post-fix live evidence
2. `~/.organism/events/pg-bridge.jsonl` — historic NOTIFY trail (50min gap visible during W27)
3. asyncpg source — exception class hierarchy verification
4. W27 cicatrix entry + research doc (this is the deferred-item follow-up)
5. `scripts/tests/test_pg_to_organism_bridge_interface_error.py` — 5/5 PASS evidence
