---
name: wr3-supervisor-runbook
description: Runbook for scripts/wr3_supervisor.py (S7.5). Step-by-step operational procedures for starting/stopping/recovering the WR3 episode pipeline.
status: PLACEHOLDER (S7.5 implements supervisor; this runbook expands then)
---

# WR3 Supervisor Runbook

> **Status: PLACEHOLDER.** `scripts/wr3_supervisor.py` does not exist yet — implementation lands at S7.5. This runbook is seeded with operational structure so it can be expanded inline with implementation.

## Start

```bash
# (S7.5 will implement)
cd ~/Desktop/nuzantara
source apps/backend-rag/.venv/bin/activate
PYTHONPATH=apps/backend-rag/backend python scripts/wr3_supervisor.py
```

Expected stdout:

```
[wr3-supervisor] Loaded router from docs/wr3/contracts/_router.yaml (6 channels)
[wr3-supervisor] Loaded precedence from docs/wr3/symbiosis-precedence.md
[wr3-supervisor] Connected to PG (LISTEN on 6 channels)
[wr3-supervisor] Outbox replay on reconnect: 0 unconsumed events
[wr3-supervisor] Ready.
```

## Stop

`Ctrl+C` or `kill -SIGTERM <pid>`. Supervisor flushes outbox state on shutdown.

## Recover from stuck episode

1. Identify episode slug: `ls apps/war-room/output/episode/`
2. Check current state via manifest: `cat apps/war-room/output/episode/<slug>/episode_manifest.json | jq .stage`
3. Manual retry: `python scripts/wr3_supervisor.py --retry <slug> --from-stage <stage>`

## Telegram P0 channel

Failures emit to chat_id 1125336968 (Zero) via `~/scripts/telegram-notify.sh`.
Includes: episode slug, agent, failure reason, retry attempt count.

## LaunchAgents (installed 2026-05-21)

| Plist                                            | Status                                                      | Trigger                  | Wrapper                                                                                  |
| ------------------------------------------------ | ----------------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------- |
| `com.balizero.wr3.supervisor.plist`              | LIVE (KeepAlive=true, RunAtLoad=true, ThrottleInterval=30s) | Event-driven (PG LISTEN) | `~/.openclaw/bin/wr3/wr3-supervisor-wrapper.sh`                                          |
| `com.balizero.wr3.reflexion.weekly.plist`        | LIVE                                                        | Sun 02:30 WITA           | `~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py` (PLACEHOLDER stub exit 0) |
| `com.balizero.wr3.yt-metrics.weekly.plist`       | LIVE                                                        | Mon 06:07 WITA           | `~/.openclaw/bin/wr3/wr3-yt-metrics-run.sh` (fail-safe gate ≥3 episodi)                  |
| `com.balizero.wr3.editorial-bench.monthly.plist` | LIVE                                                        | Day 1 07:00 WITA         | `~/.openclaw/bin/wr3/wr3-editorial-bench-run.sh` (fail-safe gate ≥1 lessons.md)          |

### Thundering herd risk (deferred — panel DeepSeek 2026-05-22 P3 finding)

Quattro LaunchAgent condividono lo stesso pg-proxy upstream (`com.balizero.wr2.pg-proxy` su porta 15432). Tutti usano `EX_TEMPFAIL=75` + `ThrottleInterval=30s`. Se pg-proxy va down per >30s, i 4 agent failureranno simultaneamente e ripartiranno tutti dopo 30s precisi → connessioni concorrenti su Fly proxy appena risuscitato.

Mitigation deferred (richiede design):

- Opzione A: `ThrottleInterval` distinti per plist (30s, 47s, 73s, 113s — primes per anti-sync)
- Opzione B: wrapper aggiunge `sleep $(($RANDOM % 30))` prima di nc check (jitter)
- Opzione C: exponential backoff in wrapper con counter su `/tmp/wr3-<label>-fail-count`

In pratica: supervisor è l'unico critico H24. Gli altri 3 sono scheduled (no concurrent failure window). Risk teorico, basso impatto reale finché yt-metrics+editorial-bench restano fail-safe stub.

## See also

- `research/wr3/06-architecture-skeleton.md` — full architecture
- `docs/wr3/contracts/_schema.yaml` — contract meta-schema
- `docs/wr3/contracts/_router.yaml` — channel → agent map
- `docs/wr3/symbiosis-precedence.md` — inter-law conflict resolution
