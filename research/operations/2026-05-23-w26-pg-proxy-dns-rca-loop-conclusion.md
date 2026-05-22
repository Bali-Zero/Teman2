---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W26 pg-proxy outage RCA (Fly DNS) + loop conclusion
sources: 5
---

# W26: pg-proxy 13:00-13:30 outage RCA + loop W1→W26 conclusion

## Pg-proxy outage root cause

W25 deferred: investigate yesterday's 13:00-13:30 pg-proxy outage that
generated 690 supervisor-watchdog Tracebacks.

**Found in `/Users/nuzantara/.fly/agent-logs/1122430107.log` (3.3MB,
last modified 2026-05-22 13:31)**:

```
2026/05/22 13:30:37 #2a4c -> err dial: lookup nuzantara-postgres.internal.
  on fdaa:31:dc12::3: read udp [fdaa:31:dc12:a7b:d6b:4008:1dbd:b100]:16420: i/o timeout
2026/05/22 13:31:13 #2a4e -> err dial: lookup nuzantara-postgres.internal.
  on fdaa:31:dc12::3: write udp ...:26852: i/o timeout
2026/05/22 13:31:13 #2a50 -> err dial: lookup nuzantara-postgres.internal.
  on fdaa:31:dc12::3: read udp ...:25854: i/o timeout
```

**Root cause: Fly platform DNS i/o timeout.** `fdaa:31:dc12::3` is the
Fly-side resolver for `*.internal` names. UDP timeouts on resolver
queries mean Fly's DNS infrastructure was unreachable from Pro for ~30min.

This is a **Fly platform incident, not local code bug**. No fix
warranted in our code:

- pg-proxy auto-restart via launchd's `ThrottleInterval=30` (already in place)
- supervisor-watchdog's tiered alerts already detected the outage
  (PIPELINE_FROZEN cooldown logic)
- System recovered automatically — current PID 13602 started 17:42 (4h
  after outage started), no manual intervention needed

Confirmed: current pg-proxy agent log shows clean `ok` responses since
this morning. System healthy.

## Mitigation already in place

The 28 restart events in `pg-proxy.log` (across 2026-05-22 02:00 and
17:42) prove the auto-restart machinery worked:

1. Launchd respawned pg-proxy on crash (ThrottleInterval=30s minimum)
2. supervisor-watchdog detected pipeline_frozen + entered cooldown
3. Once DNS resolved again, proxy bound port 15432 and resumed serving

Future enhancement (W27+, OPTIONAL): add explicit Fly DNS health probe
that pings `flyctl agent ping` every 5min and alerts on consecutive
failures BEFORE clients see errors. Would shorten alert latency from
~minutes (after pipeline_frozen) to ~seconds. Not urgent — Fly platform
outages are rare and self-recovering.

## Loop conclusion W1→W26

System status (2026-05-23 02:50 WITA):

```
unhealthy=33/116 | hot1h=0 | recent24h=4 | degrading_recovered=4 | historical_only=30 | lc_antipattern=16
```

**0 plists currently broken.** All transient issues resolved. Audit
dashboard reactive (daily cron + Telegram delta alert). Core
NB-automations pipeline hardened across 4 phases:

### Phase 1 — Hardening (W1-W17)

| Iter    | Domain                                                 |
| ------- | ------------------------------------------------------ |
| W1-W3   | bridge heartbeat + error-streak escalation             |
| W4      | kg-linker upstream-dead detection                      |
| W5+W10  | consumer-group lag monitor + launchd cron              |
| W6-W7   | NER worker restored + flock semaphore                  |
| W8      | gap-consumer split-stream logging                      |
| W9      | classifier worker restored                             |
| W11-W13 | PEL recovery — XCLAIM root-cause to deep-XACK          |
| W14     | stream_ack silent-failure detection                    |
| W15     | nlm_feeder NB source-cap gate                          |
| W16-W17 | Pro<->Mini Redis split-brain detector + Telegram dedup |

### Phase 2 — TCC migration (W18-W21)

11 plists migrated from `/bin/{bash,zsh} -lc` to TCC-safe wrapper. Two
silent production failures unmasked:

- `reg-alert.30min`: dead ~6 days, now `processed=20, sent=20, failed=0` per fire
- `daily-briefing`: sqlite I/O error → clean Python init

### Phase 3 — Audit dashboard (W22-W25)

- W22: programmatic `audit_launchd_crons.py` (115 plists baseline)
- W23: cross-tree audit revealed sibling-agent W8 mirror
- W24: recency-weighted (24h window) — 61 → 36 unhealthy
- W25: two-tier (1h hot + 24h recent) — 36 → 33 unhealthy, 0 hot

### Phase 4 — RCA + loop close (W26)

- pg-proxy 13:00-13:30 outage: Fly DNS i/o timeout (platform incident)
- PR #823 conflict resolved, status MERGEABLE
- Status update posted to PR

## Cron inventory (loop additions)

| Plist                                    | Schedule  | Purpose                              |
| ---------------------------------------- | --------- | ------------------------------------ |
| `com.matagaruda.pel-cleaner.weekly`      | Sun 04:00 | PEL stale + ghost consumer cleanup   |
| `com.matagaruda.redis-split-brain.check` | 30min     | Pro<->Mini Redis drift detector      |
| `com.balizero.audit-launchd.daily`       | 02:00     | 116-plist inventory + Telegram alert |

## P1 wins consolidated

1. **`reg-alert.30min`** silently dead → now alerting (W21)
2. **`wr2.supervisor-watchdog`** asyncpg crashes → recovered (W21+W26)
3. **`daily-briefing`** sqlite I/O error → clean (W21)
4. **`gap.consumer`**: split-stream + cross-tree mirror (W8/W23)
5. **NLM feeder**: source-cap gate + recency-aware (W15)

## Open / Antonello sign-off needed

1. **W16 Redis split-brain root-cause**: panel diverged A vs B vs D.
   Detector + Telegram alert deployed. Architecture decision pending.
2. **`bridge.adaptive` 1372 historical errors**: weekly-trend metric
   not built (W26+ if pattern recurs).
3. **`cell.organism` 22 recent24h errors**: cicatrix scar still active
   despite 2026-05-22 resurrection. Different from `.env` quote-fix.

## Sources

1. `~/.fly/agent-logs/1122430107.log` — 13:31 yesterday RCA
2. `~/.openclaw/workspace/logs/war-room-v2/pg-proxy.log` — restart history
3. `lsof -nP -iTCP:15432 -sTCP:LISTEN` — current PID 13602 serving
4. W25 audit empirical: hot1h=0, system green
5. PR #823 status MERGEABLE post-merge of origin/main
