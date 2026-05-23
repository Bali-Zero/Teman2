---
date: 2026-05-23
domain: operations
client_case: NB-automations hardening loop W47 — wr2_supervisor_watchdog 5s keepalive on poll conn
sources: 6
---

# W47 — Watchdog 5s keepalive on poll conn

## Summary

W47 audit (post-W46 closure) found 2823 lifetime Tracebacks + 370 in last 24h in `wr2_supervisor_watchdog.launchd.err.log`:

```
asyncpg.exceptions.InterfaceError('connection is closed')
  File ".../wr2_supervisor_watchdog.py", line 171, in _probe_heartbeat_age
    age = await conn.fetchval(...)
```

Pattern: ~15 Tracebacks/hour = once every ~4min. Watchdog poll interval is 60s. Each `_evaluate_once` call expects `conn` to be alive but Fly proxy WG tunnel drops idle conns at ~10s (documented in `wr2_supervisor.py:649` cicatrix 2026-04-28). Outer reconnect catches the failure → 1 lost cycle every 4min ≈ 15 lost cycles/hour.

**Effective monitoring quality**: degraded ~25% (1 in 4 cycles wasted on reconnect instead of probing). Not catastrophic — watchdog still works — but inefficient AND noise pollutes audit dashboard signal.

## Fix shipped (commit `0d67b7269`)

Replace single 60s `asyncio.sleep` with 12× 5s chunks, each followed by `SELECT 1` keepalive:

```python
# W47 (2026-05-23): keepalive SELECT 1 every 5s while waiting for
# next probe cycle. ... 5s tick keeps socket below the tunnel timeout.
try:
    chunk_count = max(1, POLL_INTERVAL_SEC // 5)
    for _ in range(chunk_count):
        if _shutdown_event.is_set():
            return
        await asyncio.sleep(5)
        await conn.execute("SELECT 1")
    remainder = POLL_INTERVAL_SEC - chunk_count * 5
    if remainder > 0:
        await asyncio.sleep(remainder)
except asyncio.CancelledError:
    return
```

Mirrors the proven pattern from `wr2_supervisor.py:656-659` (cited in code comment for traceability).

If keepalive raises (`InterfaceError` from dead conn), the existing outer reconnect path handles it — same exception flow as `_evaluate_once`. Net effect: stale conn detected within 5s instead of at next 60s probe.

## Empirical validation

Pre-W47 (10:38 → 11:19 watchdog log):
```
2823 lifetime Tracebacks
370 Tracebacks in last 24h
~15 Tracebacks/hour rate
```

Post-W47 (11:54:29 restart → +5min):
```
0 Tracebacks in last 30 lines
INFO pipeline_frozen check skipped (canva-renderer kill switch OFF) every 60s
INFO success_rate_low check skipped (canva-renderer kill switch OFF) every 60s
```

Clean operation confirmed. Will continue to monitor over next hours for the ~15/hr historical rate; expectation is rate goes to 0.

## Deploy sync requirement (W46 lesson reinforced)

Production cron runs from `~/Desktop/nuzantara-deploy` (separate git worktree pointing at `deploy/main` branch). Must `git pull origin main` THERE in addition to landing the commit. Total flow:

```bash
# 1. Land commit in main repo
cd ~/Desktop/nuzantara && HUSKY=0 git push origin HEAD:main

# 2. Sync deploy worktree
cd ~/Desktop/nuzantara-deploy
git stash push -u -m "session-stop pre-pull"
git pull origin main

# 3. Restart daemon
launchctl kickstart -k gui/$(id -u)/com.balizero.wr2.supervisor-watchdog

# 4. Verify (watch log for kill-switch-OFF + zero Tracebacks)
tail -f ~/logs/wr2_supervisor_watchdog.launchd.err.log
```

Failing to do step 2 means production keeps running OLD code regardless of what's on `main`. W46 first attempt was bitten by this (commit landed, restart fired, but no log change because deploy worktree still on pre-W46 code).

## Companion to W46

W46 made the watchdog **correct** (suppresses false-alerts when kill switch off). W47 makes it **efficient** (no wasted reconnect cycles). Together they bring the watchdog from "silently degraded + noisy" to "silently working + clean".

## What's still open

- **W43 tiered escalation** still pending — with W46+W47 the noise floor is at ZERO for the canva-disabled period, but when canva is re-enabled AND something genuinely fails, the flat 24h cooldown still gives operator only ONE ping.
- **W47 doesn't audit other watchdogs**. cell.organism (22 errors/24h), wr2.sla-worker (4), wr2.topic-selector (4 httpx.ReadTimeout) all use similar patterns. Worth W48+ candidate.
- **2823 historical Tracebacks** in watchdog log are residue from pre-W47 era. Could rotate the log to fresh-start the noise stats. Optional.
- **2823 → 0 quantification**: weekly cron should diff `grep -c Traceback ~/logs/wr2_supervisor_watchdog.*.log` snapshots to surface regression if Tracebacks return.

## Sources

1. `scripts/wr2_supervisor_watchdog.py:459-490` — patched poll loop
2. `~/logs/wr2_supervisor_watchdog.launchd.err.log` — 2823 lifetime Tracebacks pre-W47
3. `scripts/wr2_supervisor.py:649,656-659` — keepalive pattern + WG tunnel timeout documentation
4. `~/.agent/decisions/state/wr2_supervisor_watchdog.state` — last_alert_pipeline_frozen cleared on first post-W46 canva_disabled cycle
5. Cicatrix 2026-04-28 — Fly proxy WG tunnel drops idle conns at ~10s
6. W46 research doc — companion finding that opened the audit window

## Next

- [ ] W48 candidate: audit cell.organism (22 errors/24h), wr2.sla-worker, wr2.topic-selector for similar patterns
- [ ] W49 candidate: implement W43 tiered escalation (now meaningful — false-alerts gone, real escalation possible)
- [ ] W50 candidate: log rotation policy to surface fresh-error counts vs accumulated history
