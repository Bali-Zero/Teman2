---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W24 audit v2 (recency-weighted) + daily cron + Telegram delta alert
sources: 5
---

# W24: audit script v2 — recency-weighted + daily Telegram-alert cron

## Context

Loop iteration 24, building on W22 launchd inventory audit. Two
parallel improvements:

### Problem 1: W22 audit over-counted historical errors as current breakage

W22 flagged 61/115 plists unhealthy, but W23 forensics revealed
many had errors only in HISTORICAL logs (pre-fix, pre-redeploy,
pre-dep-install). Example: `bridge.adaptive` showed 1372 "real_errors"
but ALL were from 2-week-old DNS issues that have resolved. Audit
couldn't distinguish "currently broken" from "broken in past, recovered".

### Problem 2: Audit existed but no scheduled run

Panel suggestion (Gemini W11→W21 review):

> "Serve script di audit programmatico schedulato come cron su
> garuda:alerts (audit_launchd_crons.py)."

W22 shipped the audit script + JSON snapshot but no cron. Same scar
family as W5/W10/W16/W17 ("diagnostic exists but no operator sees it").

## Fix shipped

### Layer 1: audit v2 — recency window (24h)

`analyze_log()` now parses each line's leading `YYYY-MM-DD HH:MM:SS`
timestamp and counts only errors within `recency_window_s` (default
86400 = 24h). For lines without timestamps (bare `Traceback`
continuations), falls back to the most-recent prior timestamped line.

New return field: `real_recent` (count within window) alongside
`real` (total).

Health verdict (`audit_plist`):

```python
# Before W24:
if err_analysis.get("real", 0) > 0:
    diagnosis.append(f"REAL_ERRORS={...}")
    healthy = False

# After W24:
if recent_real > 0:
    diagnosis.append(f"REAL_ERRORS_RECENT={recent_real} (total={total_real})")
    healthy = False
elif total_real > 0:
    diagnosis.append(f"HISTORICAL_ERRORS={total_real}")
    # NOT marked unhealthy — historical only
```

New summary fields:

- `with_real_errors_recent_24h`
- `with_historical_only`
- (retained) `with_real_errors_total`

### Layer 2: daily cron with Telegram delta alert

`~/scripts/audit-launchd-daily.sh` (50 lines, TCC-safe pattern):

- Runs audit, writes JSON snapshot to `~/logs/audit-launchd-daily-snapshots/<date>.json`
- Compares summary vs `~/.agent/decisions/audit-launchd-last-summary.json`
  - Emits delta on `unhealthy`, `with_real_errors_recent_24h`,
    `with_real_errors_total` (positive AND negative deltas)
- Telegram alert when: delta non-empty OR any plist has recent errors
- Saves new summary as next baseline

Plist `com.balizero.audit-launchd.daily.plist`:

- `StartCalendarInterval`: Hour=2, Minute=0 (02:00 WITA daily)
- No `*sh -l` antipattern — direct wrapper invocation (W21 pattern)

### Layer 3: defensive Python heredoc encoding

First wrapper version used `python3 -c "$AUDIT_OUTPUT_PIPE" | json.loads(stdin)`.
Failed with `JSONDecodeError: Invalid \escape` because some plists'
ProgramArguments contained embedded shell scripts with `\\\'` quoting
that, when passed through bash variable expansion + echo + stdin pipe,
got partially-unescaped to invalid JSON.

Fix: pipe audit output DIRECTLY to archive file (`python3 audit.py >
archive.json`), then process via temp-file-based Python helper that
reads the archive file from disk. No bash variable round-tripping.

## Empirical results

```bash
$ ~/scripts/audit-launchd-daily.sh
[audit-launchd-daily] 2026-05-23 unhealthy=36/115 | recent24h=4 | historical_only=30 | lc_antipattern=16
[audit-launchd-daily] delta=no_change
[audit-launchd-daily] snapshot=/Users/nuzantara/logs/audit-launchd-daily-snapshots/2026-05-23.json
```

**Unhealthy 61 → 36 (41% reduction in false-positives).** Of 34 plists
with real_errors, only 4 have recent (24h) errors — these are the
ACTUAL currently-broken crons:

| Plist                                        | Recent (24h) | Total                               |
| -------------------------------------------- | ------------ | ----------------------------------- |
| `com.balizero.wr2.supervisor-watchdog.plist` | **690**      | 2797 (asyncpg missing)              |
| `com.cell.organism.plist`                    | **22**       | 22 (cicatrix scar W22 still active) |
| `com.balizero.wr2.sla-worker.plist`          | 4            | 10                                  |
| `com.balizero.wr2.trend-hunter.plist`        | 2            | 6                                   |

The 30 historical-only plists include big surprise wins:

- `bridge.adaptive`: 1372 historical, **0 recent**
- `wa-mirror-auto-promote`: 79 historical, **0 recent**
- `guardrails-daemon`: 528 historical, **0 recent**
- `canva-lease-watchdog`: 265 historical, **0 recent**

All recovered without intervention from this loop.

## Plist + cron deployment

```bash
$ plutil -lint ~/Library/LaunchAgents/com.balizero.audit-launchd.daily.plist
OK
$ launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.balizero.audit-launchd.daily.plist
$ launchctl print "gui/$(id -u)/com.balizero.audit-launchd.daily" | grep state
        state = not running   # fires 02:00 WITA
```

Telegram alert format (when delta or recent errors present):

```
📊 Launchd audit daily report

unhealthy=36/115 | recent24h=4 | historical_only=30 | lc_antipattern=16

Delta vs yesterday: no change

Plists with recent (24h) errors:
- com.balizero.wr2.supervisor-watchdog.plist: 690 recent
- com.cell.organism.plist: 22 recent
- com.balizero.wr2.sla-worker.plist: 4 recent
- com.balizero.wr2.trend-hunter.plist: 2 recent

Snapshot: ~/logs/audit-launchd-daily-snapshots/2026-05-23.json
```

## W25 actionable backlog

Now that audit is recency-weighted + scheduled, the **4 currently-broken
crons** are the actual W25+ priority:

1. **`wr2.supervisor-watchdog`** — 690 recent / `ModuleNotFoundError: asyncpg`.
   `nuzantara-deploy/scripts/wr2_supervisor_watchdog.py:62`. Fix: install
   asyncpg in nuzantara-deploy venv OR migrate to httpx PG-REST.
2. **`cell.organism`** — 22 recent. Cell daemon scar from 2026-05-22
   resurfaced. Different from the `.env` quote-fix; need deeper
   investigation.
3. **`wr2.sla-worker`** — 4 recent.
4. **`wr2.trend-hunter`** — 2 recent.

## Open questions

- **wa-mirror family fully recovered?** W22 flagged 87+79+43 errors,
  W24 shows 0 recent. Likely sibling-agent ship resolved (`feat/wa-mirror-group-capture-2026-05-22`
  branch had recent commits per W23 discovery). Verify by spot-checking
  next 24h.
- **Telegram alert noise**: with 4 plists in recent-errors list, the
  daily Telegram will fire every day until those are fixed. Consider
  per-plist dedup window (4h pattern from W17 split-brain alerter).
  Defer to W25.
- **`bridge.adaptive` 1372 historical errors** — even though 0 recent,
  the log accumulation suggests a periodic transient failure pattern.
  Audit might want a "lifetime trend" metric (errors per week) to
  surface degrading-but-not-currently-broken crons. W26+ candidate.

## Sources

1. W22 cicatrix (commit `425059717`) — original audit baseline
2. W22 launchd snapshot — 61 unhealthy, 5 P0
3. W23 forensics revealed false-positive pattern (supervisor-watchdog
   recent INFO lines vs historical Tracebacks)
4. Panel review unanimous: schedule audit cron + delta tracking
5. Empirical W24 v2 run: 36 unhealthy (was 61), only 4 with recent errors
