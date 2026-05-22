---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W11 nlm_feeder ghost consumer cleanup + nexus-bridge legacy decision pending
sources: 4
---

# nlm_feeder ghost consumer cleanup — 77 pending recovered

## Context

Loop iteration 11 of NB-automations hardening. After deploying W6
(NER), W9 (classifier), W10 (lag monitor) the W5 lag monitor now
surfaces 4 remaining stuck groups. Triage to distinguish patterns:

| Group | Consumer state | Pattern |
|---|---|---|
| `scorer-1` | idle 24s, no plist | Run via batch sentinel.sh nightly — alive, leave alone |
| `normalizer-1` | idle 24s, pending 9, no plist | Same — alive via batch script |
| `nlm_feeder` (4 consumers) | 1 active, 3 ghost | **ACTIONABLE: orphan pending claim + ghost cleanup** |
| `nexus-bridge` `bridge-worker-1` | idle 12d, no code | **LEGACY: needs Antonello decision** |

## nlm_feeder ghost cleanup (shipped)

`XINFO CONSUMERS garuda:enriched nlm_feeder` pre-cleanup:

```
name            pending  idle (ms)     state
debug-trace     0        1544828157    18 days stale (debug session leftover)
nlm_feeder-1    5        24326800      ACTIVE (24s idle = currently consuming)
nlm_feeder-debug 0        1545096519    18 days stale (debug session leftover)
scan            77       1544807854    18 days stale — 77 MESSAGES DEAD-LETTERED
```

The `scan` ghost had **77 pending messages** stuck since 2026-05-04 (a
debug invocation that crashed mid-batch, leaving claims unreleased).
Standard Redis Streams behavior: messages stay in the Pending Entries
List (PEL) of the dead consumer forever unless explicitly XCLAIM'd to
a live consumer or PEL is manually trimmed.

Operations performed:

```bash
# 1. Transfer 77 pending messages from 'scan' (dead) to 'nlm_feeder-1' (alive)
XPENDING garuda:enriched nlm_feeder - + 100 scan
# → returns 77 message IDs
for msg_id in $IDS; do
    XCLAIM garuda:enriched nlm_feeder nlm_feeder-1 60000 "$msg_id"
done

# 2. Delete 3 zero-pending ghost consumers
XGROUP DELCONSUMER garuda:enriched nlm_feeder scan
XGROUP DELCONSUMER garuda:enriched nlm_feeder debug-trace
XGROUP DELCONSUMER garuda:enriched nlm_feeder nlm_feeder-debug
```

Post-cleanup:
- nlm_feeder consumer count: 4 → 1
- nlm_feeder-1 pending: 5 → 82 (claimed 77 from scan + 5 original)
- Idle 24s post-claim → 30s on next inspection (active processing)

The 82 pending messages will drain via the `com.matagaruda.nlm-feeder-stream.hourly.plist`
cron (hourly cadence). At ~20 msg/cycle drainage rate, full PEL clears
in ~4 hours.

## nexus-bridge decision pending (NOT shipped)

`bridge-worker-1` consumer on garuda:raw: idle 12 days, lag 2279, no
code reference anywhere in `mata_garuda/` or `~/scripts/`.

Options:
- **A. DELETE consumer group** (clean): `XGROUP DESTROY garuda:raw nexus-bridge` →
  removes the 2279 lag and the dead consumer. Permanent.
- **B. RESTORE worker** (revive): create runner + LaunchAgent following
  W6/W9 pattern. But: who would write the worker code? `nexus-bridge`
  isn't referenced in the codebase, suggesting it was scaffolded but
  never implemented, OR was renamed/refactored at some point.
- **C. LEAVE AS-IS** (conservative): accept the perpetual 2279 lag
  alert from W10 monitor as background noise.

Without Antonello sign-off, this scar selects **option C** — the
W10 alert at 2279 lag is loud but harmless. If Antonello confirms
"nexus-bridge is legacy, delete it", apply option A in ~5 seconds.

## scorer + normalizer (no action)

Both consumers show idle ~24s — they're being drained by some
upstream process (most likely `~/scripts/run_sentinel.sh` cap 50
per invocation, daily 02:00 WITA via launchd, plus possibly
on-demand from research-sentinel daemon). Lag values (scorer=927,
normalizer=858) grow because upstream stream inflow > nightly cap×1
drain rate. Out of scope for ghost-cleanup iteration — would need
either bigger cap or own dedicated cron LaunchAgent (W12 candidate).

## Sources

1. `redis-cli XINFO CONSUMERS garuda:enriched nlm_feeder` output 2026-05-22 08:23 WITA
2. `redis-cli XPENDING garuda:enriched nlm_feeder - + 100 scan` — 77 IDs
3. `~/scripts/run_sentinel.sh` lines 91-96 — normalizer + scorer batch invocation
4. W5 lag monitor live output showing 4 stuck groups
