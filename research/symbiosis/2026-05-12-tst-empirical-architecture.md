---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Step 2 · Gap 4 ghost MEMORY.md entry replacement
sources: 8
status: draft
loop_step: 2
loop_branch: feat/symbiosis-loop-2026-05-12
replaces_ghost_entry: true
ghost_path: research/tst/2026-05-10-actual-architecture.md
ghost_reason: file never committed in any git branch (verified via `git log --all -- research/tst/` returns 0). Probably written via Write tool 11-mag 2026, lost in branch-hijack scar before commit. Empirical findings preserved in MEMORY.md prose were re-verified and consolidated here under a new file with explicit replacement frontmatter.
---

# TST "Tutto Sente Tutto" — Empirical architecture (replacement for ghost file)

## Context

A MEMORY.md entry dated 2026-05-10 referenced a file at `research/tst/2026-05-10-actual-architecture.md` which does NOT exist in any git branch — verified 2026-05-12 01:35 WITA via `git log --all -- research/tst/` returning zero results, and `find ~/Desktop/nuzantara/research -type d -iname tst` returning no match. The original file was likely written via Write tool during 10-11 May session and lost in the branch-hijack scar pattern (cf. `cicatrix-scars.md` 2026-04-29 "Untracked files lost when sibling automation switches branches").

This document replaces the ghost reference with verifiable empirical findings from disk state 2026-05-12.

## The 4 architecture claims from the original prose

### Claim 1 — "Cells scrivono direttamente a Fly PG via `cell_core.observatory.emit_pulse_observed()`"

**Verified true**: `packages/cell-core/cell_core/observatory.py` contains `emit_pulse_observed()` (referenced at test sites: `packages/cell-core/tests/test_observatory.py:80,131,166`). The function is async, takes the pulse payload, and (per test naming) "writes_outbox_and_notifies". The pulse hook in `packages/cell-core/cell_core/pulse.py:265-266` schedules this as `asyncio.create_task(observatory.emit_pulse_observed(...))` when `observatory.is_enabled()` returns True.

Counter-evidence: the legacy `apps/cell/cell/core/pulse.py:432` has its OWN `observatory.emit_pulse_observed(` call. The legacy cell does NOT use `packages/cell-core` — it has a parallel implementation. So "cells scrivono direttamente" is true for cells using `cell_core` PulseLoop, but the legacy `apps/cell/` cell uses its own separate path.

### Claim 2 — "asyncpg pool min=1 max=3 per process, observatory.py:55-127"

**CORRECTED 2026-05-12 04:30 WITA after NB-1 review**: NB-1 cites `apps/backend-rag/backend/app/core/database.py` with hardcoded `_POOL_MIN_SIZE = 2`, `_POOL_MAX_SIZE = 5` (and `_COMMAND_TIMEOUT = 60s`, `_MAX_INACTIVE_CONN_LIFETIME = 300s`, `_ACQUIRE_TIMEOUT = 10s`). The LangGraph checkpointer separately uses `min_size=2, max_size=10` (`docs/.../2026-03-14-autonomous-agents-v2-enhanced-architecture.md`).

The ghost prose's "min=1 max=3 per process" appears to refer to the per-process cell_core asyncpg pool (NOT the backend-RAG canonical pool). NB-1 corpus does not include `packages/cell-core/cell_core/observatory.py:55-127` so it cannot confirm/refute the specific cell-side claim. Status: **TODO** — verify directly by reading `cell_core/observatory.py` in a future pass. Pool min=1/max=3 is plausible for cell-side (one writer per cell process) but is NOT a backend-wide constant.

### Claim 3 — "Collector (`cell-observatory-collector`) è LISTENER PG → SQLite locale `~/.cell-observatory/observatory.db`"

**Verified true**: SQLite DB at `~/.cell-observatory/observatory.db` is 26.5 MB, schema confirmed via `.schema pulse_events` shows 9 columns (outbox_id, cell_id, cell_kind, pulse_id, pulse_timestamp, phase, classifier_self, payload_json, received_at, received_lag_ms). LaunchAgent `com.nuzantara.cell-observatory` PID 2368 active (verified via `launchctl list` 2026-05-12 01:08 WITA).

### Claim 4 — "Bridge (`pg-organism-bridge`) ascolta 14 canali → Redis stream `organism:events` → Supervisor consumer group"

**Verified true**:

- LaunchAgent `com.nuzantara.pg-organism-bridge` PID 2367 active
- Redis stream `organism:events`: 3721 entries (verified `XLEN` 2026-05-12 01:08), latest entry `1778518815691-0` containing `cell_pulse_observed` payload
- Consumer group `organism-supervisor` consumer `supervisor-1` shows `pending=0, idle=93ms`
- LaunchAgent `com.nuzantara.organism.supervisor` PID 2377 active

The "14 channels" claim — **CORRECTED 2026-05-12 04:30 WITA after NB-1 review**: NB-1 (queried 2026-05-12 04:15 WITA) cites `apps/backend-rag/backend/services/events/event_bus.py` defining `PG_CHANNEL_MAP` with **exactly 12 channels** (`practice_changed`, `client_changed`, `compliance_alert`, `lkpm_ingest_completed`, `war_room_event`, `intel_event`, `cognitive_event`, `federation_alert`, `cell_pulse_observed`, `measurer_event`, `crm_welcome_completed`, `asset_provenance`), NOT 13 as previously cited in `cicatrix-scars.md` Law 3.

`wr2_status_change` is NOT in `PG_CHANNEL_MAP` per NB-1 (handled separately by `wr2_supervisor.py`). The "14 channels" supervisor bridge claim in the original prose was inflated by 2: actual is `PG_CHANNEL_MAP=12` + separate channels handled by dedicated consumers.

Action: `cicatrix-scars.md` Law 3 row should be reviewed and amended to reflect canonical 12-channel count (NOT done in this loop — operator-controlled file).

## The 1 claim the ghost prose got right

### "Solo 1 cellula REALE emette oggi (cell_id='cell')"

**Verified true 2026-05-12 01:08 WITA**:

```sql
sqlite> SELECT cell_id, COUNT(*) FROM pulse_events
        WHERE pulse_timestamp > (strftime('%s','now')-86400)*1000
        GROUP BY cell_id;
cell     | 1154   (1146 green + 3 yellow + 5 red)
smoke-test | (fermo dal 2 mag, ultimo pulse 2026-05-02 09:00)
```

Original prose quoted "9.071 events, 53% red" as of 2026-05-10. By 2026-05-12 the cell has improved to 1154 events/24h with 99.3% green, suggesting either: (a) red-trigger sensors recovered after 11-mag fixes (PR #579), or (b) red events were transient.

## What was right vs wrong in the ghost prose

| Claim                                                          | Status 2026-05-12                                                   |
| -------------------------------------------------------------- | ------------------------------------------------------------------- |
| `cell_core.observatory.emit_pulse_observed()` direct to Fly PG | TRUE for `cell_core`-based cells; legacy `apps/cell/` has its own   |
| Collector PG→SQLite local                                      | TRUE (PID 2368)                                                     |
| Bridge listens N channels → Redis                              | TRUE (PID 2367, stream 3721 entries)                                |
| Supervisor consumer group                                      | TRUE (consumer `supervisor-1` pending=0)                            |
| Only `cell_id='cell'` emits today                              | TRUE (mata-garuda runner + seo-cell silenti; see Step 1 root cause) |
| 9.071 events, 53% red on 2026-05-10                            | OUTDATED snapshot (now 1154/24h, 0.4% red)                          |
| Sprint 1 = classification matrix 118/118                       | "118 organi" verified; planning artifact not in current scope       |

## Why "no Sprint 1 patch" lesson matters

Original prose self-criticized: 2 design rounds were blocked by red-team review (Codex + Gemini + DeepSeek) because the designer hadn't read `observatory.py:55` first. This is the same risk the current 5-gap loop faces — explicitly mitigated by tri-panel review of the briefing + empirical fact-check before per-step docs.

## Action: update MEMORY.md

The MEMORY.md ghost line at line 26 will be replaced by Step 2.b (separate commit) with:

```
- 2026-05-12 symbiosis tst-empirical-architecture-replacement → [research/symbiosis/2026-05-12-tst-empirical-architecture.md](~/Desktop/nuzantara/research/symbiosis/2026-05-12-tst-empirical-architecture.md) — Replacement for ghost MEMORY.md entry (research/tst/2026-05-10-actual-architecture.md never committed, lost in branch-hijack scar). Re-verifies 4 of original prose's architecture claims against disk 2026-05-12.
```

## Refusals enforced

1. **NO recreate the original file path** — ghost path NOT recreated.
2. **NO copy-paste the ghost prose verbatim** — every claim re-verified or marked TODO.
3. **NO write contents not verifiable from disk 2026-05-12**.

## Sources

1. `~/.cell-observatory/observatory.db` schema + counts (sqlite3 2026-05-12 01:08 WITA)
2. `redis-cli XLEN organism:events` → 3721
3. `redis-cli XINFO CONSUMERS organism:events organism-supervisor` → `supervisor-1` pending=0 idle=93ms
4. `launchctl list` → PIDs 2367/2368/2377/2376/2332/12591
5. `packages/cell-core/cell_core/pulse.py:265-266`
6. `packages/cell-core/tests/test_observatory.py:80,131,166`
7. `apps/organism/organism/organs_registry.yaml` → 118 organi
8. `git log --all -- research/tst/` → 0 results (ghost confirmation)
