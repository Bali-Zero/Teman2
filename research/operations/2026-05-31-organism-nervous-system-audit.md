---
date: 2026-05-31
domain: operations
client_case: none
sources:
  - launchctl print gui/501/<label> (158/167 introspectable)
  - launchctl list (Status + PID, 167/167)
  - plistlib / plutil -extract (KeepAlive, schedule, EnvironmentVariables, perms, ProgramArguments)
  - log file mtime + tail
  - ps / pgrep (live PID confirmation)
  - research/operations/2026-05-31-organism-truth-FROZEN.json
  - prior run research/operations/2026-05-31-system-audit.md (escalations/DLQ/disk/Fly — NOT re-done)
---

# S1 — "Il sistema nervoso mente": empirical organism / LaunchAgent audit (2026-05-31)

Covers ONLY what the prior `2026-05-31-system-audit.md` did not: the **167 `com.{nuzantara,balizero,cell}.*`
LaunchAgents one-by-one**, reboot-bombs, the `launchagent-state-bridge` W61 SPOF. Escalations (~4519
historic), DLQ (all TERMINAL), disk, worktrees, Fly health, events_outbox gate-off were the prior run —
**not re-counted here**. This run re-confirmed the W61 `repairer.py` `autopilot_attempts` patch is present.

Frozen truth: [`2026-05-31-organism-truth-FROZEN.json`](./2026-05-31-organism-truth-FROZEN.json) (167 records, `2026-05-31T00:37:40Z`).

## 0. Method honesty — false positives rejected

| Intermediate claim                             | Reality (tool-verified)                                                                                                                                                                                                      |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **"23 dead-but-alive"** (log-mtime>1h)         | **0.** `launchctl print` shows all `state=running active count = 1 last exit = (never exited)`; `ps` confirms each alive. "Log stale" ≠ death for a persistent daemon. True dead-but-alive = `running`+`active_count=0` = 0. |
| **"secret bomb on every TOKEN-keyword plist"** | Per-plist perms+value: **2 world-readable WITH a real value** (RED); **3 value behind `0400`** (hardened, YELLOW); rest source `~/.nuzantara-secrets.env` or `${VAR}`/empty.                                                 |

Also learned the hard way: a sibling `git checkout` + `/tmp` cleanup wiped an earlier branch + uncommitted
report mid-session; this build was redone from the surviving frozen dataset and verified against the git
object store, not intermediate tool output.

## 1. Verde / Giallo / Rosso REALE (BEFORE)

**167 plist — 🟢 GREEN 120 · 🟡 YELLOW 40 · 🔴 RED 7.** (60 nuzantara, 105 balizero, 2 cell.)

| Color     |   Count | Definition                                                                                                                                     |
| --------- | ------: | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 🟢 GREEN  | **120** | running `active_count>=1`, or cron `last_exit=0`.                                                                                              |
| 🟡 YELLOW |  **40** | nonzero retry exit (33), log `/tmp` (5), one-shot RunAtLoad+no-sched+no-KeepAlive (4), inline secret `0400` (3), critical-daemon-no-KeepAlive. |
| 🔴 RED    |   **7** | 5 `binary_missing` + 2 world-readable plist with a real secret value.                                                                          |

`launchctl print` states: {'not running': 121, 'running': 30, 'spawn scheduled': 7, None: 9}. Perms: **11 owner-only, 156 world-readable**.

## 2. The 7 RED

### 5 binary-missing (re-checked MISSING on disk this audit)

| Job (LOADED)                                               | Missing target                                                                           |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `com.balizero.wr2.canva-renderer` (status=78)              | `/Users/nuzantara/.openclaw/bin/wr2/wr2-canva-renderer-wrapper.sh`                       |
| `com.balizero.wr3.editorial-bench.monthly` (status=0)      | `/Users/nuzantara/.openclaw/bin/wr3/wr3-editorial-bench-run.sh`                          |
| `com.balizero.wr3.supervisor` (status=78)                  | `/Users/nuzantara/.openclaw/bin/wr3/wr3-supervisor-wrapper.sh`                           |
| `com.balizero.wr3.yt-metrics.weekly` (status=0)            | `/Users/nuzantara/.openclaw/bin/wr3/wr3-yt-metrics-run.sh`                               |
| `com.nuzantara.cleanup-2026-05-16-ttl-sentinel` (status=0) | `/Users/nuzantara/.automation-cleanup-2026-05-16/state/restore-federation-alert-mode.sh` |

All still `LOADED`; fail on next trigger (`No such file`). Wrappers under `~/.openclaw/bin/` (gitignored
HOME); `cleanup-2026-05-16-ttl-sentinel`'s state dir `~/.automation-cleanup-2026-05-16/` is gone.
`wr3.supervisor`+`wr2.canva-renderer` already show `launchctl list` Status=78 (EX_CONFIG, failing).
Decommission vs restore = **NEEDS-ANTONELLO**.

### 2 world-readable plist with a hardcoded secret value

- `com.balizero.wa-dashboard-m1` (`0o644`): `WA_DASHBOARD_DATABASE_URL` — real secret value in a group/other-readable plist.
- `com.nuzantara.skills-bridge-consumer` (`0o444`): `BRIDGE_SKILLS_API_KEY` — real secret value in a group/other-readable plist.

Residual of the 2026-04-29 "secrets in 0644 plist" scar (most plists were hardened to `0400`, §6).
Rotate value + `chmod 0400` touches auth = **NEEDS-ANTONELLO**. (`repomap.15min REPOMAP_MAX_TOKENS` is a
config number, excluded.)

## 3. dead-but-alive list

**Empty (0).** Every `running` daemon: `active_count=1` + live PID (`ps`):

```
com.balizero.nlm-bridge           active count = 1  state = running  pid = 997   last exit = (never exited)  ps=LIVE
com.nuzantara.organism.supervisor active count = 1  state = running  pid = 1016  last exit = (never exited)  ps=LIVE
com.balizero.qdrant.daemon        active count = 1  state = running  pid = 46562  curl :6333/healthz = HTTP 200
```

(qdrant `launchctl list` Status=-9 = prior SIGKILL/respawn, but print=running active_count=1, healthz HTTP 200 — alive.)

## 4. Reboot-bombs

**(a) RunAtLoad+no-schedule+no-KeepAlive: 4** — `com.balizero.post-publish-poller`, `com.balizero.wr2.supervisor-watchdog`, `com.nuzantara.automap-watchdog`, `com.nuzantara.sentinel`. `sentinel` is a clean-exit one-shot (`sys.exit`,
0 loop markers); `post-publish-poller` "runs every 5 minutes" but its plist has NO `StartInterval`;
`automap-watchdog` is a watcher (still RunAtLoad-without-KeepAlive). **Adding `KeepAlive=true` to a
clean-exiting one-shot = infinite respawn storm (W61 class)** — the WRONG fix; periodic jobs need
`StartInterval` (behavioral) = NEEDS-ANTONELLO.
**(b) binary-missing: 5** (§2). **(c) logs `/tmp`: 5** — `com.balizero.nlm-bridge`, `com.cell.metabolic-rollup`, `com.nuzantara.cost-advisor-daily-cap`, `com.nuzantara.cost-advisor-weekly`, `com.nuzantara.prime-tunnel`. Additive but each a live-daemon reload; deferred.

## 5. state-bridge (W61 SPOF)

🟢 **ALIVE.** `KeepAlive=true` (`plutil -extract KeepAlive raw`), `RunAtLoad=true`, perms `0444`, plist
mtime **2026-05-28** (W61 date). `launchctl print` idle between 5-min ticks; KeepAlive respawns; lint OK.
W61 `add_to_dlq autopilot_attempts` patch present in `scripts/sentinel_lib/repairer.py` (lines 136-157). Not recurring.

## 6. Fix SHIPPED vs NEEDS-ANTONELLO

**Shipped (`chore/audit-organism-2026-05-31`):** the audit artifacts — `2026-05-31-organism-truth-FROZEN.json`
(167 records) + this report. Additive, reversible, blast-radius 0 — the SYMBIOSIS Law 7 before-state baseline.
**NEEDS-ANTONELLO (not touched):** (1) decommission/restore the 5 binary-missing; (2) the 4
one-shot reboot-bombs — periodic vs run-once, **NO KeepAlive**; (3) rotate the 2 world-readable
secrets + chmod 0400; (4) mata_garuda active-active (out of glob, 2026-05-07 scar open); (5) 5 `/tmp` log moves.
No off-limits file touched; no plist/DLQ/escalations mutated (FASE A read-only).

## 7. Three structural recommendations (by future-incident reduction)

1. **Weekly liveness probe keyed on `active_count`** (not ps/log-mtime/`launchctl list` Status) — the
   23-FP trap + qdrant `Status=-9` confusion come from the wrong field; a probe on `running && active_count=0`
   or `binary_missing` catches the 5 RED with zero false alarms.
2. **Daily `lint-launchagents` failing on a non-existent `ProgramArguments` path** — all 5
   binary-missing are the 2026-04-29 P0-3 / W62 / W63 orphan-automation family; home it in the existing
   `com.balizero.audit-launchd.daily` (itself last-exited 1).
3. **`KeepAlive`-policy lint** refusing `KeepAlive=true` on a clean-exit one-shot (no `while True`/`asyncio.run`/
   `serve_forever`/`uvicorn`) — blocks the W61-class fix this audit nearly made on the 4 one-shots.

---

_Every count is from the frozen file or a tool run this audit: 167 plist, 120 green / 40 yellow / 7 red,
0 dead-but-alive, 4 one-shot reboot-bombs, 5 binary-missing, 2 world-readable secret
bombs, state-bridge KeepAlive=true._
