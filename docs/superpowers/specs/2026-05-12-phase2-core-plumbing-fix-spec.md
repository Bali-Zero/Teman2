# Phase 2 — Core Plumbing Fix (Spec v2 post 4-panel review)

**Date**: 2026-05-12 18:35 WITA · **Revised**: 19:00 WITA post-review
**Owner**: Antonello (Zero)
**Predecessor**: Phase 1 (Visibility & Stability) merged via PR #614 + PR #615 corrections
**Mode**: Mixed (script writing + cron install + runtime mutation on Pro)
**Estimated effort**: ~7h (revised up from 5h after 4-panel review)
**Review status**: APPROVED with 7 corrections (Gemini BLOCK → resolved; DeepSeek WEAK → resolved; NB-1 PROCEED CON CONDIZIONI → conditions applied)

## Goal

Drain the 2126 unconsumed events in `events_outbox`, install a prune cron to prevent indefinite growth, and seed the empty `cell:skills` Redis stream with high-quality hand-crafted skills so Phase 3 HGT execution has a non-polluted substrate to operate on.

## 4-panel review convergences applied (7 corrections)

| # | Original spec | 4-panel verdict | Correction |
|---|---|---|---|
| 1 | Replay rate 50 events/sec | UNANIMOUS too aggressive (Gemini/DeepSeek/NB-1) — OOM risk on Fly 2GB | **Rate 10/sec**, batch 10, sleep 1s. Hard cap in code. Auto-pause if Redis stream growing |
| 2 | Seed Option A (extract from observatory.db) | UNANIMOUS architectural pollution | **Option A REMOVED**. Only Option B (15-20 hand-crafted `StructuralPattern` schema-strict) |
| 3 | Replay SELECT without locks | Gemini caught: race condition with live producers | **`SELECT ... FOR UPDATE SKIP LOCKED`** for safe concurrent claim |
| 4 | Single-phase consumed_at mark | DeepSeek caught: abort leaves inconsistent state | **Two-phase mark**: `replay_in_progress` → `consumed_at` finalized only after pg_notify success |
| 5 | No poison pill handling | Gemini caught: 2126 events may be the ones that crashed bridge | **DLQ table** `events_outbox_dlq` for replay-failed events + payload schema pre-validation |
| 6 | Prune cron may delete unconsumed by age | DeepSeek caught: replay > 30d edge case | **Prune guard**: `WHERE consumed_at IS NOT NULL AND consumed_at < now()-30d` (NEVER prune unconsumed regardless of age) |
| 7 | UUID SSOT BLOCKING for Phase 2 | NB-1 ground-truth disagreement with Gemini/DeepSeek | NB-1 wins (has code access): idempotent `POST /record` upsert on `skill_id` already protects downstream. UUID SSOT remains Phase 3 prerequisite, NOT Phase 2 blocker. Phase 2 plumbing must run before/parallel Phase 0.5a. |

## Prerequisites (from Phase 1 corrections, unchanged)

1. **Verify outbox completeness during drop windows** — Step 2.1
2. **Test patched plists at runtime** — Step 2.0 (added)
3. **Phase 0.5a UUID SSOT** — NOT blocking Phase 2 per NB-1; remains Phase 3 prerequisite

## The 6 steps (revised)

### Step 2.0 — Test patched plists at runtime (15 min, P0 — NEW)

Per Phase 1 4-panel review: plist patches were NEVER kickstart-tested. Test now:

```bash
launchctl kickstart -k gui/$UID/com.balizero.seo-cell.daily
sleep 60  # cell does sensors + pulse
tail -10 ~/logs/seo-cell/pulse-*.log  # confirm 'awaiting fire-and-forget tasks' + no errors
sqlite3 ~/.cell-observatory/observatory.db \
  "SELECT COUNT(*) FROM pulse_events WHERE cell_id='seo-guardian' AND pulse_timestamp > (strftime('%s','now')-300)*1000"
```

Expected: ≥1 new `seo-guardian` pulse_event in last 5 min. Proves CORR-1 env-var sourcing from `~/.nuzantara-secrets.env` works correctly (vs prior plaintext-in-plist anti-pattern).

If zero: abort Phase 2 + investigate (CORR-1 broke something).

### Step 2.1 — Outbox completeness verification (30 min, P0)

For each of 4 bridge drop clusters from Phase 1.3:

```python
# scripts/verify_outbox_during_drops.py
import asyncpg, asyncio
async def main():
    conn = await asyncpg.connect("postgresql://.../nuzantara_rag")
    drops = [
        ("2026-05-11T22:37:00+00:00", "2026-05-11T22:40:00+00:00"),
        ("2026-05-12T01:00:00+00:00", "2026-05-12T01:02:00+00:00"),
        ("2026-05-12T11:09:00+00:00", "2026-05-12T11:13:00+00:00"),
        ("2026-05-12T16:55:00+00:00", "2026-05-12T16:56:30+00:00"),
    ]
    for start, end in drops:
        rows = await conn.fetch(
            "SELECT channel, COUNT(*), MIN(created_at), MAX(created_at) "
            "FROM events_outbox WHERE created_at BETWEEN $1 AND $2 GROUP BY channel",
            start, end
        )
        print(f"Drop window {start}: {[(r['channel'], r['count']) for r in rows]}")
```

Expected outcome: ≥1 events per drop window per major channel. If zero events for some windows, producers were ALSO affected by the drop (not just bridge) — investigate before replay.

### Step 2.2 — Throttled replay script (2h, P0 — revised effort)

`scripts/replay_outbox_throttled.py`:

```python
"""Throttled outbox replay — drains unconsumed events safely.

Hard limits (4-panel consensus 2026-05-12):
- Rate: 10 events/sec default (hard cap 20/sec via --rate flag)
- Batch: 10 events per round (vs 100 in original spec)
- Sleep: 1s between batches
- Auto-pause: if Redis stream organism:events length grows >2× during replay
- Lock: SELECT ... FOR UPDATE SKIP LOCKED (avoid race with live producers)
- Two-phase mark: UPDATE consumed_at TO 'replay_in_progress_<pid>' first,
  then UPDATE to NOW() only after pg_notify confirms
- DLQ: failed events INSERT INTO events_outbox_dlq + log
- Poison pill check: validate payload JSON schema before notify

Args:
  --since <ISO>            : only events after this time (default: all unconsumed)
  --channel <name>         : single channel (default: all)
  --dry-run                : count + validate, no NOTIFY
  --rate <int>             : events/sec (default 10, hard max 20)
  --max-events <int>       : safety cap (default 5000)

Usage:
  python replay_outbox_throttled.py --dry-run
  python replay_outbox_throttled.py --rate 10 --max-events 2500
"""

import asyncpg, asyncio, json, signal, os, sys
from datetime import datetime

HARD_MAX_RATE = 20  # events/sec — never higher
DEFAULT_RATE = 10
DEFAULT_BATCH = 10
REDIS_GROWTH_THRESHOLD = 2.0  # auto-pause if length > 2× initial

# Two-phase mark via consumed_at value 'replay_in_progress' is unsafe
# (consumed_at is timestamptz). Use a separate column or a redis-side
# transaction marker. For Phase 2.2 minimal: use a sentinel timestamp
# 'epoch zero' (1970-01-01) as in-progress marker, then UPDATE to NOW()
# after pg_notify success.
IN_PROGRESS_MARKER = "1970-01-01T00:00:00+00:00"

# DLQ schema (auto-created on first failed event):
DLQ_SCHEMA = """
CREATE TABLE IF NOT EXISTS events_outbox_dlq (
    id BIGINT PRIMARY KEY,
    channel TEXT,
    payload JSONB,
    failed_at TIMESTAMPTZ DEFAULT NOW(),
    failure_reason TEXT,
    original_created_at TIMESTAMPTZ
)
"""
```

**Tests** `tests/unit/test_replay_outbox_throttled.py` (8 tests):
- rate enforcement (asserts ≤10/s under load)
- hard cap (rejects --rate 50)
- two-phase mark (in_progress before NOTIFY, NOW() after)
- DLQ on payload validation failure
- SKIP LOCKED prevents collision with live producer
- abort on Redis growth > 2×
- idempotent re-run (claimed-but-not-completed rows are recoverable)
- KeyboardInterrupt finalizes in_progress → reverts to NULL consumed_at

### Step 2.3 — Dry-run + full replay (1h, P0 — revised effort)

1. `python scripts/replay_outbox_throttled.py --dry-run --max-events 2500`
   Output: "would replay N events (channels: ...), 0 schema violations"
2. `python scripts/replay_outbox_throttled.py --rate 10 --max-events 2500`
   Expected duration: 2126 events / 10 per sec ≈ **3.5 min** (NOT 45 sec as in v1 spec)
3. Monitor every 30s during replay:
   - `XLEN organism:events` (must stay ≤2× initial)
   - bridge `consumer-group pending`
   - `events_outbox_dlq` count (should stay 0)
4. Post-replay verification:
   ```sql
   SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL;  -- target ≤20 (live traffic during replay)
   SELECT COUNT(*) FROM events_outbox_dlq;  -- target 0 (no poison pills)
   ```

**Abort triggers**:
- Redis stream growth > 2× initial
- DLQ count > 5 (indicates systemic payload issue)
- bridge connection drop during replay (5th cluster — investigate, do not retry blindly)

### Step 2.4 — Outbox prune cron (1.5h, P1 — revised effort)

`~/Library/LaunchAgents/com.nuzantara.outbox-prune.weekly.plist` invokes `scripts/outbox_prune.py`:

```python
"""Weekly prune of events_outbox.consumed rows older than 30 days.

GUARDS (per 4-panel review):
- NEVER prune rows where consumed_at IS NULL (regardless of age)
- NEVER prune rows where consumed_at == in_progress_marker (replay active)
- ONLY prune where consumed_at IS NOT NULL AND consumed_at < NOW() - INTERVAL '30 days'

Reports: count before, count pruned, count after, table size before/after.
"""
```

Plist schedule: Sunday 04:30 WITA (low traffic). Operator installs manually (per chmod 0444 scar).

### Step 2.5 — Seed cell:skills with 15-20 hand-crafted skills (2h, P0 — revised approach)

**Option A REMOVED entirely** per 4-panel unanimous verdict (polluting HGT substrate).

**Option B only**: write `scripts/seed_cell_skills_manual.py` that XADDs 15-20 hand-curated `StructuralPattern`-shaped skills to `cell:skills` Redis stream.

Schema (canonical from `apps/bali-intel-scraper/backend/cell/hgt_publisher.py`):

```python
SKILLS = [
    {
        "skill_id": "intel.scraper.djp_rss_v2_stable",
        "procedure": "DJP regulatory RSS at /api/v2/news endpoint is stable; poll every 6h, expect ≥3 new items/week",
        "precondition": "regulatory monitoring of Indonesian tax authority needed",
        "success_criterion": "≥3 new regulations harvested per 7-day window",
        "confidence": 0.9,
        "scope": "Project",
        "domain": "tax",
        "cell_origin": "intel-scraper-cell",
        "seeded_at": "<iso8601>",
        "seed_source": "manual_v1"
    },
    # ... 14-19 more entries covering: KBLI/tax/visa/property/CRM patterns ...
]
```

**15-20 skills coverage**: 4 tax + 4 visa + 3 property + 3 CRM + 2 KBLI + 2-4 cross-domain. All schema-validated before XADD.

**Smoke test** post-seed:
```bash
redis-cli XLEN cell:skills        # ≥15
redis-cli XRANGE cell:skills - + COUNT 1 | grep skill_id  # validates first entry
redis-cli XINFO STREAM cell:skills | grep length  # confirm
```

### Step 2.6 — Doc + commit + PR (1h, P0)

Closure doc `research/symbiosis/2026-05-12-phase2-core-plumbing-complete.md`:
- Step 2.0 plist runtime test result (kickstart log + observatory.db row)
- Step 2.1 drop-window outbox completeness numbers
- Step 2.2 script + tests committed
- Step 2.3 replay execution log: events drained, peak Redis stream length, DLQ count, duration
- Step 2.4 prune plist staged for operator install
- Step 2.5 seed: 15-20 skill IDs, schema-validation results

PR + auto-merge SQUASH (lessons from Phase 1: doc carefully retracts claims, no over-stating).

## Refusals enforced (4-panel post-correction)

1. **NO blind extension** of EventBus `_replay_outbox_on_reconnect` 60min cap (4-panel unanimous)
2. **NO rate >20/sec** in replay script (hard cap in code)
3. **NO Option A seed** from observatory or genome SQLite (4-panel unanimous: polluting)
4. **NO bulk emit-flag flip** on additional plists (Phase 4 scope)
5. **NO Consiglio cron install** in Phase 2 (wait for Phase 4 after cell:skills seeded)
6. **NO `launchctl bootstrap` autonomously** on prune plist (operator manual)
7. **NO replay without --dry-run first** (4-panel mandatory)
8. **NO replay without DLQ + lock + two-phase mark** (poison pill + race + abort safety)

## Total effort (revised)

| Step | Effort | Risk |
|---|---:|---|
| 2.0 Runtime test patched plists | 15m | low |
| 2.1 Outbox completeness verify | 30m | low |
| 2.2 Throttled replay script + 8 tests | 2h | medium |
| 2.3 Dry-run + full replay execution | 1h | medium |
| 2.4 Outbox prune cron + script | 1.5h | low |
| 2.5 Seed cell:skills 15-20 manual | 2h | low |
| 2.6 Doc + commit + PR | 1h | low |
| **Total Phase 2** | **~8h** | medium |

(Was 5h plan-v2, then 6h spec-v1; now 8h spec-v2 post-4-panel.)

## Success criteria (revised)

Phase 2 complete when:

1. `events_outbox WHERE consumed_at IS NULL` count drops from 2126 → **≤20** (was ≤50; tightened per DeepSeek)
2. `events_outbox_dlq` count == **0** (or all entries have understood failure_reason)
3. `~/Library/LaunchAgents/com.nuzantara.outbox-prune.weekly.plist` ready for operator install + plutil-lint OK
4. `redis-cli XLEN cell:skills` ≥ **15** (was ≥10; raised per DeepSeek for HGT substrate viability)
5. `redis-cli XINFO STREAM cell:skills` confirms consumer-group friendly format
6. No new bridge connection drop incident during replay (5th cluster = automatic abort + investigation)
7. Step 2.0 confirms patched plists emit at runtime (proves Phase 1 CORR-1 works end-to-end)

## Hidden coupling notes (revised after 4-panel)

- Phase 2.5 manual seed does NOT depend on Phase 1 emit being live; the 15-20 hand-crafted skills are independent. If plists emit duplicates with same skill_id, the idempotent upsert at `apps/backend-rag/backend/app/routers/skill.py POST /record` handles dedup (NB-1 confirmed).
- Phase 2.3 replay can run before Phase 0.5a UUID SSOT (NB-1 ground-truth: idempotent `POST /record` upsert protects downstream).
- Phase 2.4 prune cron's 30-day window will reach the replay'd events on 2026-06-11 — by then Phase 3 HGT should be live and consuming, so the events are processed canonically before prune.

## What this loop produces (autonomous scope)

Doc-only artifacts + Pro-local script + new Python file. NO autonomous:
- launchctl bootstrap (operator runs)
- Live replay execution (operator triggers `--dry-run` first, then approves live run)
- Plist file install (operator copies to ~/Library/LaunchAgents/)

The replay execution itself (Step 2.3) is operator-gated despite the script being autonomous-ready — too high blast radius for autonomous trigger.

## Brainstorm artifacts archived

- `/tmp/symbiosis-phase2-spec-review-2026-05-12/00_spec.md` (v1 spec)
- `/tmp/symbiosis-phase2-spec-review-2026-05-12/02_gemini_review.md` (BLOCK)
- `/tmp/symbiosis-phase2-spec-review-2026-05-12/03_deepseek_review.md` (WEAK)
- `/tmp/symbiosis-phase2-spec-review-2026-05-12/04_nb1_review.md` (PROCEED CON CONDIZIONI)

Should be copied to `docs/audits/2026-05-12-phase2-spec-brainstorm/` for permanent archive.
