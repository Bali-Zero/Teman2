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

## Cron LaunchAgents

S7.5 will install:

- `com.balizero.wr3.supervisor.plist` (KeepAlive=true, RunAtLoad=true)
- `com.balizero.wr3.reflexion.weekly.plist` (Sun 02:30 WITA)
- `com.balizero.wr3.yt-metrics.weekly.plist` (Mon 06:00 WITA)
- `com.balizero.wr3.editorial-bench.monthly.plist` (1st Mon 07:00 WITA)

## See also

- `research/wr3/06-architecture-skeleton.md` — full architecture
- `docs/wr3/contracts/_schema.yaml` — contract meta-schema
- `docs/wr3/contracts/_router.yaml` — channel → agent map
- `docs/wr3/symbiosis-precedence.md` — inter-law conflict resolution
