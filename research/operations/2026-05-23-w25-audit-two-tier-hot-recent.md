---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W25 audit v3 two-tier hot+recent windows
sources: 5
---

# W25: audit v3 — two-tier hot (1h) + recent (24h) windows

## Context

Loop iteration 25, follow-up to W24 audit recency-weighting. W24's
24h window classified `wr2.supervisor-watchdog` as "currently broken"
(690 recent errors) when investigation revealed:

- Last Traceback in log: 2026-05-22 13:30:55 WITA (~13h ago)
- Tracebacks in last 1h: **0**
- Tracebacks in last 24h: 673 (all from a 30-min pg-proxy outage burst)
- pg-proxy: `state = running`, port 15432 LISTEN

Cron is **currently healthy**. The 13h-old outage already recovered.
But W24's binary "recent vs historical" classified it as unhealthy
because 24h is too wide for "currently broken" semantics.

This was W24's own open question: "lifetime trend vs current state".

## Fix shipped — two-tier window

`analyze_log()` now takes both `hot_window_s` (default 3600 = 1h)
and `recent_window_s` (default 86400 = 24h). Single-pass counts both:

```python
if effective_ts >= recent_cutoff:
    real_recent += 1
    if effective_ts >= hot_cutoff:
        real_hot += 1
```

Health verdict tier (highest priority first):

| Tier       | Condition                      | Diagnosis                                    | Healthy?        |
| ---------- | ------------------------------ | -------------------------------------------- | --------------- |
| HOT        | hot_real > 0                   | `REAL_ERRORS_HOT={N} (recent24h=X, total=Y)` | **NO**          |
| DEGRADING  | recent_real > 0, hot_real == 0 | `DEGRADING_RECENT={N} (recovered? total=Y)`  | yes (info only) |
| HISTORICAL | total > 0, recent_real == 0    | `HISTORICAL_ERRORS={N}`                      | yes (info only) |

## Empirical (2026-05-23 02:21 WITA)

```
unhealthy=33/116 | hot1h=0 | recent24h=4 | degrading_recovered=4 | historical_only=30 | lc_antipattern=16
delta=unhealthy: 36 -> 33 (-3)
```

| Metric                   | W22           | W24           | W25    |
| ------------------------ | ------------- | ------------- | ------ |
| Unhealthy                | 61            | 36            | **33** |
| With hot1h               | (not tracked) | (not tracked) | **0**  |
| With recent24h           | 35            | 4             | 4      |
| With degrading_recovered | (not tracked) | (not tracked) | 4      |
| With historical_only     | (not tracked) | 30            | 30     |

The 4 "DEGRADING" plists (recovered, no current breakage):

1. `wr2.supervisor-watchdog`: recent24h=671, total=2797 (30-min outage 13h ago)
2. `cell.organism`: recent24h=22 (cicatrix scar)
3. `wr2.sla-worker`: recent24h=4
4. `wr2.trend-hunter`: recent24h=2

**They're no longer marked unhealthy** because hot1h=0 = "currently healthy".

## Wrapper update

`~/scripts/audit-launchd-daily.sh`:

- Summary line: `hot1h={N} | recent24h={N} | degrading_recovered={N}`
- Delta tracks `with_real_errors_hot_1h` in addition to recent24h
- "Actionable list" is now HOT-only (1h window) — recovered plists
  don't appear in Telegram alert
- Telegram message body says "Plists currently broken (hot, last 1h)"

## Telegram alert behavior

- Fires on delta (unhealthy / hot1h / recent24h / total changed)
- Fires when hot1h > 0 (someone needs to look)
- Does NOT fire when only DEGRADING_RECOVERED — that's informational
  noise. Operator sees the count in the summary line but doesn't get
  paged.

## Open: where did the supervisor-watchdog 30-min outage come from?

The 13:00-13:30 yesterday burst shows `asyncpg.exceptions._base.InterfaceError:
connection is closed` for 690 attempts × 60s interval ≈ 30 min. Then
recovered. Need to correlate with `pg-proxy.error.log` to find what
made the proxy unreachable. W26+ candidate (not urgent — recovered
without intervention).

## W26+ candidates

1. **Investigate the 13:00-13:30 yesterday pg-proxy outage** — was
   it Fly-side hiccup? Network? Proxy restart? Look at
   `~/.openclaw/workspace/logs/war-room-v2/pg-proxy.error.log`.
2. **Add weekly-trend metric** to audit — count errors per day over
   last 7 days. Catches degrading-over-time patterns that current
   two-tier doesn't surface (e.g., `bridge.adaptive` 1372 historical
   could be 50/day for 28 days, or 1372 in one day with 27 days
   silence).
3. **Telegram alert dedup per-plist** (W17 split-brain pattern) so
   the same HOT plist doesn't re-alert every day until fix lands.
4. **5 P0 plists currently empty after W25** — when something new
   breaks (hot1h > 0), Telegram fires immediately. System is now
   reactive, not proactive.

## Sources

1. W22 cicatrix (audit baseline)
2. W24 cicatrix (recency-weighting)
3. Empirical 2026-05-23 02:18 investigation: supervisor-watchdog
   last Traceback 13:30:55 yesterday, currently 0 Tracebacks in 1h
4. pg-proxy state check: running, port 15432 LISTEN
5. W25 v3 empirical run: unhealthy 36→33, hot1h=0
