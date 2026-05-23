---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W49
status: shipped (commit 120078999); active on next 10min cron tick
---

# W49 — `wr2_canva_lease_watchdog` 98 lifetime TimeoutError on PG connect

## TL;DR

10-min cron `wr2_canva_lease_watchdog.py` was crash-exiting on `asyncpg.connect(timeout=10)`
race against pg-proxy WG tunnel idle drop. **98 lifetime TimeoutError** events. Each crash =
lost tick = stale-lease window accumulates. Fix: retry-with-backoff (3 attempts, 1s/3s/7s) +
exit-0 on retry-exhaust (next tick recovers within tolerance).

## Empirical evidence pre-fix

```
$ grep -c "TimeoutError" ~/logs/wr2_canva_lease_watchdog.error.log
98

$ wc -l ~/logs/wr2_canva_lease_watchdog.error.log
6874

$ grep -v "getcwd\|shell-init\|job-working-directory\|chdir:" \
    ~/logs/wr2_canva_lease_watchdog.error.log | wc -l
4068
```

| Metric | Value |
|---|---|
| Total error log lines | 6874 |
| TCC `getcwd` shell noise | 2806 (~41%) |
| Real Python errors | 4068 |
| `TimeoutError` instances | 98 |

The 41% TCC noise is independent (macOS launchd zsh sandbox; W49 doesn't fix it — separate
W50+ candidate via wrapper script eliminating `zsh -lc` indirection).

Stack trace (truncated):

```
asyncio.exceptions.CancelledError
  File "scripts/wr2_canva_lease_watchdog.py", line 26, in main
    conn = await asyncpg.connect(dsn, timeout=10)
  File ".../asyncpg/connection.py", line 2442, in connect
    async with compat.timeout(timeout):
  File ".../asyncio/timeouts.py", line 115, in __aexit__
    raise TimeoutError from exc_val
TimeoutError
```

## Root cause

W47-family pattern: **pg-proxy WG tunnel drops idle conns at ~10s**. The watchdog's
single `asyncpg.connect(dsn, timeout=10)` races the drop:

- Cron fires every 10min (StartInterval=600).
- pg-proxy tunnel sits idle between ticks.
- New TCP handshake on next tick races the WG idle-timeout (~10s).
- Connect either succeeds (cached route) or times out at exactly 10s (the script's
  timeout matching the proxy's drop window — pathological alignment).

Local manual probe in W49 returned `OK in 0.01s` (cached route hot from prior bash
command), but cron-context timing differs (fresh process, fresh DNS, fresh tunnel).

## Fix shipped

`scripts/wr2_canva_lease_watchdog.py` (commit `120078999`):

```python
CONNECT_TIMEOUT_SEC = 10
MAX_RETRIES = 3
BACKOFF_SEC = (1, 3, 7)  # progressive backoff per retry

async def _connect_with_retry(dsn: str) -> asyncpg.Connection | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await asyncpg.connect(dsn, timeout=CONNECT_TIMEOUT_SEC)
        except (asyncio.TimeoutError, OSError, asyncpg.PostgresError) as e:
            if attempt == MAX_RETRIES:
                logger.warning(
                    "connect exhausted %d retries (last error: %s: %s); skipping tick",
                    MAX_RETRIES, type(e).__name__, e,
                )
                return None
            sleep_for = BACKOFF_SEC[attempt - 1]
            logger.info(
                "connect attempt %d/%d failed (%s: %s); retry in %ds",
                attempt, MAX_RETRIES, type(e).__name__, e, sleep_for,
            )
            await asyncio.sleep(sleep_for)
    return None
```

Caller:
```python
conn = await _connect_with_retry(dsn)
if conn is None:
    return 0  # next tick recovers within stale-lease tolerance
```

## Why exit 0 on retry-exhaust

This is a **recovery watchdog**, not a producer. Losing one tick is harmless if the next
tick still resets stale leases within the same business-tolerance window:

| Parameter | Value | Note |
|---|---|---|
| Cron interval | 10min | StartInterval=600 |
| Stale-lease threshold | 15min | `reset_stale_leases(stale_after_minutes=15)` |
| Margin | 5min | Single missed tick stays within tolerance |
| Two consecutive misses | 20min | EXCEEDS threshold (P2 alert candidate) |

Exit-0 prevents launchd retry-storm; if the proxy is hard-down (two consecutive misses),
the broader `wr2_supervisor_watchdog` (1min cadence) raises the alert.

## Verification plan

**Behavioral (next 1h)**:
- Check error log growth: `wc -l ~/logs/wr2_canva_lease_watchdog.error.log` at 14:50, 15:00,
  15:10. Expected: ZERO new `TimeoutError` entries (retry absorbs them).
- New log entries should be `INFO connect attempt N/3 failed (...) retry in Ns` if the race
  happens, OR clean silent success.

**Eventual (24h)**:
- `grep -c "TimeoutError" ~/logs/wr2_canva_lease_watchdog.error.log` post-rotate: 98 → frozen.
- `grep -c "connect attempt" ~/logs/wr2_canva_lease_watchdog.log`: any non-zero confirms
  retry pathway is actually executing in production.

## Deferred W50+ candidates

1. **TCC `getcwd` shell noise** (2806 lines, 41% of error log): root cause is launchd
   `zsh -lc` + macOS sandbox not granting cwd access to spawned shell. Fix via wrapper script
   (eliminates the `-l` interactive shell init) — same pattern as today's sibling W48
   canva-renderer-wrapper.sh fix.
2. **wr2_canva_pdf_apply.error.log 695KB**: same TCC noise pattern, less actionable (script
   itself exits clean via kill-switch — the noise is purely cosmetic).
3. **pg-organism-bridge.error.log 309KB** stopped 06:25: check if dead daemon or just quiet.

## Lessons

- **Watchdog scripts need retry-with-backoff** even when local probes show pg-proxy healthy.
  Production timing differs from interactive probe (cold connect vs cached route).
- **Exit-0 on retry-exhaust is the right posture for recovery scripts** (not producers).
  Lost ticks self-heal next interval if business tolerance permits.
- **Connect timeout == tunnel idle timeout is pathological**. Worth tuning either: increase
  `CONNECT_TIMEOUT_SEC` to 15s (forces handshake to finish before idle drop) OR add
  `tcp_keepalive=...` to DSN. W49 chose retry as orthogonal/robust; tuning is W50+ option.
- **Error log line counts hide structure**: 4068 real errors vs 98 TimeoutError = there's
  another error class in there. Sample-grep next iteration to enumerate.

## Reference

- Commit: `120078999`
- File: `scripts/wr2_canva_lease_watchdog.py`
- Pattern source: W47 `scripts/wr2_supervisor_watchdog.py` (keepalive variant)
- Sibling crontroller wrapper template: `~/.openclaw/bin/wr2/wr2-canva-renderer-wrapper.sh`
- Family: pg-proxy WG idle drop (W47 keepalive in long-running service; W49 retry-on-connect
  in one-shot cron — two faces of same root cause).
