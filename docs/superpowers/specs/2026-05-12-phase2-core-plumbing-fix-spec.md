# Phase 2 — Core Plumbing Fix (Spec)

**Date**: 2026-05-12 18:35 WITA
**Owner**: Antonello (Zero)
**Predecessor**: Phase 1 (Visibility & Stability) merged via PR #614 + PR #615 corrections
**Mode**: Mixed (script writing + cron install + runtime mutation on Pro)
**Estimated effort**: ~5h (per Plan v2 4-panel consensus 2026-05-12)
**Review status**: PENDING 4-panel brainstorm before execution

## Goal

Drain the 2126 unconsumed events in `events_outbox`, install a prune cron to prevent indefinite growth, and seed the empty `cell:skills` Redis stream so Phase 3 HGT execution has a non-zero substrate to operate on.

## Prerequisites (from Phase 1 corrections)

Per CORR 4 + 4-panel review BEFORE Phase 2 starts:

1. **Verify outbox completeness during drop windows** — for each of 4 bridge drop clusters (2026-05-11 22:37–22:39, 2026-05-12 01:00–01:01, 11:09–11:12, 16:55), query `events_outbox` to confirm events were captured (INSERT happens BEFORE pg_notify, so should always be in outbox even if NOTIFY fails on the wire).
2. **Test patched plists at runtime** — `launchctl kickstart -k gui/$UID/com.balizero.seo-cell.daily` then tail log + verify observatory.db row for `seo-guardian` post-execution. Confirms env var sourcing works post CORR-1.
3. **Phase 0.5a UUID SSOT decision** — operator decides if Gap 7 spec PR #609 execution comes BEFORE or PARALLEL to Phase 2.

## The 5 steps

### Step 2.1 — Outbox completeness verification (30 min, P0)

For each drop cluster timestamp range:

```bash
psql via flyctl proxy → SELECT channel, COUNT(*), MIN(created_at), MAX(created_at)
FROM events_outbox
WHERE created_at BETWEEN '<drop_start>' AND '<drop_end>'
GROUP BY channel
ORDER BY 2 DESC;
```

Expected outcome: ≥1 events per channel per drop window. If zero events for some windows, that means producers ALSO experienced bridge connection issues simultaneously (not just bridge consumer), revealing a worse coupling that needs investigation BEFORE replay.

### Step 2.2 — Throttled replay script (1.5h, P0)

Write `scripts/replay_outbox_throttled.py`:

```python
"""Throttled outbox replay — sends unconsumed events to NOTIFY without
risking flood-induced consumer OOM. Per 4-panel consensus, NEVER blindly
extend the 60min replay_window of EventBus; use this one-shot drain instead.

Pattern: SELECT unconsumed, pg_notify in batches of 100 with 2s sleep between
batches → effective rate 50 events/sec → 2126 events drained in ~45s.

Args:
  --since <ISO timestamp> : only events after this time (default: all unconsumed)
  --channel <name>        : single channel only (default: all)
  --dry-run               : count what would be replayed, don't NOTIFY
  --batch 100             : events per batch
  --sleep 2               : seconds between batches
"""
```

**Safety**:
- Idempotent on `_outbox_id` (consumers check duplicates via `INSERT OR IGNORE` on `outbox_id` SQLite PK in `cell-observatory-collector`)
- Marks `consumed_at` only after successful pg_notify
- Stops gracefully on KeyboardInterrupt + summary report

**Test scope**:
- `tests/unit/test_replay_outbox_throttled.py` (new) — mock pg pool + verify batch logic + ack idempotency
- Dry-run smoke before any production execution

### Step 2.3 — Dry-run + full replay (45 min, P0)

1. `python scripts/replay_outbox_throttled.py --dry-run` → outputs "would replay N events"
2. `python scripts/replay_outbox_throttled.py --batch 50 --sleep 3` → conservative live replay
3. Monitor:
   - `redis-cli XLEN organism:events` stays bounded (consumer keeps up)
   - `bridge consumer-group lag` stays 0
   - `events_outbox unconsumed` decreases from 2126 → 0
4. Post-replay: re-run `events_outbox unconsumed by channel` to verify drain complete

**Refusal**: NO blind window extension. NO replay without dry-run first.

### Step 2.4 — Outbox prune cron (1h, P1)

Create `~/Library/LaunchAgents/com.nuzantara.outbox-prune.weekly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.nuzantara.outbox-prune.weekly</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/nuzantara</string>
        <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/.venv/bin/python /Users/nuzantara/Desktop/nuzantara/scripts/outbox_prune.py --older-than-days 30</string>
    </array>
    <key>WorkingDirectory</key><string>/Users/nuzantara/Desktop/nuzantara</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>0</integer>
        <key>Hour</key><integer>4</integer>
        <key>Minute</key><integer>30</integer>
    </dict>
    <key>RunAtLoad</key><false/>
    <key>KeepAlive</key><false/>
    <key>StandardOutPath</key><string>/Users/nuzantara/logs/outbox-prune.log</string>
    <key>StandardErrorPath</key><string>/Users/nuzantara/logs/outbox-prune.error.log</string>
</dict>
</plist>
```

Plus new `scripts/outbox_prune.py`:

```python
"""Weekly prune of events_outbox.consumed rows older than 30 days.

Uses backend.services.events.outbox.prune_consumed() to safely remove
fully-acked rows. Idempotent. Reports count + table size before/after.
"""
```

Install procedure (operator runs manually post-PR-merge):
- chmod 0444 plist
- launchctl bootstrap

NOT autonomous (per Phase 1 lesson — plist install is operator territory).

### Step 2.5 — Seed cell:skills Redis stream (2h, P0 per DeepSeek catch)

DeepSeek 4-panel finding: HGT is no-op if `cell:skills` empty. We need ≥1 seed skill so consumers have something to subscribe/dedup against.

Sources for seeding:

**Option A** — Extract from existing genome SQLite KB (Pro-local `~/.agent/mata-garuda/kg.db` + apps/cell SQLite + observatory.db):

```python
"""Seed cell:skills from current cell genome state.

Extracts skills (or skill-like entries) from:
- ~/.agent/mata-garuda/kg.db `skills` table if exists
- ~/.cell-observatory/observatory.db `pulse_classifications` table (pulse outcomes treated as proto-skills)
- apps/cell/data/cell.db (legacy cell genome if reachable)

For each candidate, derives skill ID + procedure + confidence and writes to
Redis stream `cell:skills` via XADD with consumer-group friendly schema:
  {
    "skill_id": str,
    "procedure": str,
    "precondition": str,
    "success_criterion": str,
    "confidence": float,
    "scope": "Project" | "Personal",
    "cell_origin": str,
    "seeded_at": iso8601,
    "seed_source": "genome" | "observatory" | "manual"
  }
"""
```

**Option B** — Manual seed of 5-10 hand-crafted skills representing operational knowledge already established (e.g., "Brevo template T123 bounces 80%+ for segment X", "DJP RSS endpoint /api/v2/news stable", etc.).

**Decision**: try Option A first; if extraction yields <5 skills, fall back to Option B.

**Test scope**:
- Verify `redis-cli XLEN cell:skills` ≥1 post-seed
- Verify Redis consumer-group `cell:skills:sentinel-1` exists (XGROUP CREATE if absent)

### Step 2.6 — Doc + commit + PR (1h, P0)

Doc `research/symbiosis/2026-05-12-phase2-core-plumbing-complete.md`:
- Drop window completeness verification results (Step 2.1)
- Throttled replay script + tests committed
- Replay execution log: events drained, consumer lag, post-state metrics
- Outbox prune plist installed (or staged for operator install)
- Seed cell:skills: count, source, sample IDs

PR + auto-merge SQUASH.

## Refusals (4-panel consensus enforced)

1. **NO blind extension** of EventBus `_replay_outbox_on_reconnect` window (60min cap). Only one-shot throttled replay script.
2. **NO bulk emit-flag flip** on additional plists in Phase 2 (Phase 1 already covered the 4 PulseLoop plists; A2A daemons stay Phase 4 scope).
3. **NO UUID SSOT autonomous** (Gap 7 Phase 0.5a is BLOCKING per NB-1 for Phase 3, but it's operator-driven PR work).
4. **NO Consiglio cron install** until Step 2.5 seed completes (avoid empty deliberation).
5. **NO plist install** via `launchctl bootstrap` autonomously (per chmod 0444 plist scar — operator runs manually post-PR).

## Total effort

| Step | Effort | Risk |
|---|---:|---|
| 2.1 Outbox completeness verify | 30 min | low (read-only SQL) |
| 2.2 Throttled replay script + tests | 1.5h | medium (touches production replay logic) |
| 2.3 Dry-run + full replay execution | 45 min | medium (modifies events_outbox.consumed_at) |
| 2.4 Outbox prune cron | 1h | low (new script + new plist, doc-only autonomous) |
| 2.5 Seed cell:skills | 2h | medium (extracts from multiple genome sources, writes to Redis) |
| 2.6 Doc + commit + PR | 30 min | low |
| **Total Phase 2** | **~6h** | medium |

(Was 5h in plan v2; refined to 6h after Phase 1 lesson on under-estimates.)

## Success criteria

Phase 2 is complete when:

1. `events_outbox WHERE consumed_at IS NULL` count drops from 2126 to ≤50 (residual events from the replay window itself)
2. `~/Library/LaunchAgents/com.nuzantara.outbox-prune.weekly.plist` ready for operator install (file exists, plutil-lint OK)
3. `redis-cli XLEN cell:skills` ≥10 entries (seed minimum)
4. `redis-cli XINFO GROUPS cell:skills` shows ≥1 consumer group
5. No new bridge connection drop incident during the replay (proves replay throttle works)

## Hidden coupling notes (from Phase 1 retrospective)

- Phase 2.5 seed depends on Phase 1 having already corrected plist EMIT → if plists are emitting now, the cell:skills stream may auto-populate from cells doing their thing. Verify before seeding to avoid duplicates.
- Phase 2.3 replay assumes bridge stays stable. If a 5th drop cluster fires during replay, abort + investigate.
- Phase 2.4 prune cron interacts with Phase 2.2 replay: if replay marks rows as consumed_at, prune will remove them 30 days later (intended).

## 4-panel review checklist

Reviewers should answer:

1. Is the throttled replay rate (50/s) safe for the Redis consumer + Fly Postgres outbox table? Should it be more conservative?
2. Is the seed cell:skills procedure architecturally sound, or does it pollute the substrate with non-real skills?
3. Are the success criteria thresholds (≤50 residual, ≥10 skills) appropriate?
4. Hidden coupling not addressed?
5. What would you refuse to do autonomously in this Phase 2?
6. Is the Phase 0.5a UUID SSOT prerequisite (per NB-1 canonical 0.5→5→3) actually blocking Phase 2 or only Phase 3?
