# P0-2 Brainstorm — EventBus PG LISTEN/NOTIFY → Outbox pattern

**Goal:** Eliminate silent event loss when PG listener disconnects. Persist every event to durable storage BEFORE notify; replay missed events on reconnect.
**Effort:** 1-3 days (migration + helper + refactor of all NOTIFY callsites)
**Dependencies:** None directly (but P0-0 makes monitoring visible).

---

## Strategy options

### Option A: Outbox pattern (recommended by NB-1, DeepSeek)

Universal Outbox table. Every publisher writes to `events_outbox` BEFORE `pg_notify`. Recovery daemon replays unconsumed events on reconnect.

**Pros:**
- Standard pattern (Microsoft, AWS docs)
- Already has reference impl in codebase: `apps/backend-rag/backend/services/bridge/outbox.py`
- Survives PG outage (events queued in same DB, atomic INSERT+NOTIFY)
- No new infrastructure (no Redis, no Kafka)

**Cons:**
- Touches every NOTIFY callsite — need to find them all
- Outbox table grows; needs pruning policy
- Replay semantics need consumer cooperation (idempotency guards)

**Effort:** 1-3 days.

### Option B: Migrate to Redis Streams (align with Symbiosis Law 4 docs)

Replace PG LISTEN/NOTIFY with Redis Streams. This is what Symbiosis.md says we DO use. Reality vs docs alignment by changing reality.

**Pros:**
- Aligns with documented architecture
- Redis Streams have built-in consumer groups + ack
- Better scalability than PG NOTIFY (Redis can handle 100K+/sec)

**Cons:**
- Major architectural change
- Redis becomes new SPOF (currently Redis is just cache, not bus)
- Needs consumer migration for every event handler
- Higher risk for an audit fix

**Effort:** 1-2 weeks.

### Option C: Hybrid — keep PG NOTIFY for low-volume events + Outbox for high-volume

**Pros:**
- Preserves current architecture
- Adds durability where it matters most

**Cons:**
- Two patterns to maintain
- Hard to define "high-volume" cleanly

**Effort:** 2-3 days but inconsistent.

**Recommendation:** **Option A — Outbox pattern.** Aligns with existing bridge/outbox.py reference. Low risk, high impact.

---

## Implementation plan (Option A)

### Step 1: New migration `141_events_outbox.sql`

```sql
-- File: apps/backend-rag/backend/db/migrations_v2/141_events_outbox.sql

CREATE TABLE events_outbox (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed_at TIMESTAMPTZ NULL,
    last_consumer TEXT NULL
);

-- Pending events index (most queries filter by this)
CREATE INDEX events_outbox_pending ON events_outbox (channel, published_at)
    WHERE consumed_at IS NULL;

-- Time-based pruning index
CREATE INDEX events_outbox_published_at ON events_outbox (published_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS events_outbox_pending;
DROP INDEX IF EXISTS events_outbox_published_at;
DROP TABLE IF EXISTS events_outbox;
```

### Step 2: Universal outbox helper

```python
# File: apps/backend-rag/backend/services/events/outbox.py
"""
Universal Outbox pattern for EventBus.

Every NOTIFY publisher MUST go through this helper, NOT call conn.execute("NOTIFY ...") directly.

Design:
- Atomic INSERT to events_outbox + NOTIFY in same transaction
- Recovery daemon reads unconsumed entries on reconnect
- Consumers acknowledge by UPDATE consumed_at = NOW()
- Pruning cron deletes consumed >30 days old
"""

import json
import logging
from typing import Any
import asyncpg

logger = logging.getLogger(__name__)


async def publish(
    conn: asyncpg.Connection,
    channel: str,
    payload: dict[str, Any]
) -> int:
    """Publish event via Outbox. Returns outbox_id.

    Atomic INSERT + NOTIFY in same transaction. If notify fails, the row stays
    in events_outbox and the recovery daemon replays it.
    """
    async with conn.transaction():
        row = await conn.fetchrow(
            """INSERT INTO events_outbox (channel, payload)
               VALUES ($1, $2::jsonb)
               RETURNING id""",
            channel, json.dumps(payload)
        )
        outbox_id = row['id']

        # Add outbox_id to payload so consumers can ACK
        notify_payload = json.dumps({**payload, '_outbox_id': outbox_id})
        # asyncpg.Connection.execute passes through PG channel sanitization
        await conn.execute(f"NOTIFY {_quote_ident(channel)}, $1", notify_payload)

    return outbox_id


async def acknowledge(conn: asyncpg.Connection, outbox_id: int, consumer: str) -> bool:
    """Mark outbox entry as consumed. Idempotent — safe to call multiple times."""
    result = await conn.execute(
        """UPDATE events_outbox
           SET consumed_at = COALESCE(consumed_at, NOW()),
               last_consumer = COALESCE(last_consumer, $1)
           WHERE id = $2 AND consumed_at IS NULL""",
        consumer, outbox_id
    )
    return result.split()[1] == "1"  # asyncpg returns "UPDATE N"


async def replay_unconsumed(
    conn: asyncpg.Connection,
    max_age_minutes: int = 60,
    channel_filter: list[str] | None = None
) -> int:
    """Replay unconsumed events on listener reconnect.

    Returns count of events replayed. Called from EventBus reconnect handler.
    """
    where_clause = "consumed_at IS NULL AND published_at > NOW() - INTERVAL '$1 minutes'"
    params = [max_age_minutes]
    if channel_filter:
        where_clause += " AND channel = ANY($2)"
        params.append(channel_filter)

    rows = await conn.fetch(
        f"SELECT id, channel, payload FROM events_outbox WHERE {where_clause} ORDER BY published_at",
        *params
    )

    count = 0
    for r in rows:
        notify_payload = json.dumps({
            **json.loads(r['payload']),
            '_outbox_id': r['id'],
            '_replay': True
        })
        try:
            await conn.execute(f"NOTIFY {_quote_ident(r['channel'])}, $1", notify_payload)
            count += 1
        except Exception as e:
            logger.warning(f"Replay failed for outbox_id={r['id']}: {e}")

    logger.info(f"Outbox replay complete: {count}/{len(rows)} events emitted")
    return count


def _quote_ident(name: str) -> str:
    """PG identifier quoting. Safe for channel names which are static strings."""
    return '"' + name.replace('"', '""') + '"'
```

### Step 3: Refactor existing publishers

Find all callsites:

```bash
rg --type py "pg_notify|conn\.execute\(.*NOTIFY" apps/backend-rag/backend
```

Expected hits in:
- `services/events/handlers/__init__.py`
- `services/events/bridge/handlers.py`
- Database trigger functions (review SQL migrations 112, 113, 114)
- Any service that emits `practice_changed`, `client_changed`, etc.

For each callsite, replace:

```python
# Before
await conn.execute("NOTIFY practice_changed, $1", json.dumps(payload))

# After
from backend.services.events.outbox import publish
await publish(conn, "practice_changed", payload)
```

Database triggers need updating in a follow-up SQL migration:

```sql
-- File: 142_eventbus_triggers_use_outbox.sql

CREATE OR REPLACE FUNCTION trigger_publish_via_outbox() RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
    outbox_id BIGINT;
BEGIN
    payload := jsonb_build_object(
        'id', NEW.id,
        'event_type', TG_ARGV[0],
        'occurred_at', NOW()
    );

    INSERT INTO events_outbox (channel, payload)
    VALUES (TG_ARGV[1], payload)
    RETURNING id INTO outbox_id;

    PERFORM pg_notify(TG_ARGV[1], (payload || jsonb_build_object('_outbox_id', outbox_id))::TEXT);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate triggers using new function
DROP TRIGGER IF EXISTS practice_status_change_notify ON practices;
CREATE TRIGGER practice_status_change_notify
    AFTER UPDATE OF status ON practices
    FOR EACH ROW
    EXECUTE FUNCTION trigger_publish_via_outbox('status_changed', 'practice_changed');
-- ... similar for client_changed, war_room_event, intel_event, cognitive_event

-- === ROLLBACK ===
-- Restore old triggers (need to know previous function name — check before deploy)
```

### Step 4: EventBus reconnect → replay

```python
# File: apps/backend-rag/backend/services/events/__init__.py (extend EventBus)

class EventBus:
    async def _start_listener(self):
        while not self._stopped:
            try:
                await self._connect()
                # NEW: replay missed events on (re)connect
                from backend.services.events.outbox import replay_unconsumed
                count = await replay_unconsumed(self._conn, max_age_minutes=60)
                if count > 0:
                    logger.info(f"Replayed {count} unconsumed events on reconnect")

                await self._listen_loop()
            except (asyncpg.exceptions.ConnectionDoesNotExistError, OSError) as e:
                logger.warning(f"EventBus listener disconnected: {e}; reconnecting in {_RECONNECT_DELAY_S}s")
                await asyncio.sleep(_RECONNECT_DELAY_S)
```

### Step 5: Consumer ACK

Each consumer must ACK after processing:

```python
# Example: review_handler
async def handle_war_room_event(payload: dict):
    outbox_id = payload.get('_outbox_id')
    is_replay = payload.get('_replay', False)

    # Idempotency check — handler must be safe to run again
    if is_replay:
        if await already_processed(payload['post_id']):
            await acknowledge(conn, outbox_id, 'review_handler')
            return

    # Normal processing
    await process_war_room_event(payload)
    await acknowledge(conn, outbox_id, 'review_handler')
```

### Step 6: Pruning cron

LaunchAgent `com.nuzantara.outbox-prune.plist`, daily 03:00:

```python
# scripts/outbox_prune.py
async def prune_consumed_old(conn, days: int = 30):
    result = await conn.execute(
        "DELETE FROM events_outbox WHERE consumed_at IS NOT NULL AND consumed_at < NOW() - INTERVAL '$1 days'",
        days
    )
    return int(result.split()[1])
```

---

## Dependencies & ordering

- **Before:** P0-4 (deploy ordering) — otherwise migration 141 won't apply on first deploy
- **After:** This unblocks reliable cognitive event delivery, war_room reviews, intel briefs

## Rollback plan

If Outbox causes issues:
1. Revert publishers to direct `pg_notify`
2. Migration 141 has explicit ROLLBACK section (drop table)
3. Trigger function migration 142 needs ROLLBACK to restore previous trigger function

**Risk:** Medium. Migration touches DB schema + triggers. Test on staging first if possible.

## L2 autonomy decision

**Auto-implementable: PARTIAL.**

Reasoning:
- Migration + helper + tests: L2 yes
- Refactor of all `pg_notify` callsites: mechanical, L2 yes (each callsite is similar pattern)
- Trigger function migration: requires verifying current trigger SQL — Zero handoff for review
- Consumer idempotency check additions: each handler needs review (L2 with care)

**Recommendation:** Implement in 2 phases. Phase 1 (helper + migration + replay) = L2. Phase 2 (refactor + consumers) = L2 with PR review.

## Verification

```bash
# 1. Run migration locally
PYTHONPATH=. python -m backend.db.migrate apply --target 141 --dry-run
PYTHONPATH=. python -m backend.db.migrate apply --target 141

# 2. Test publish + replay
psql ... <<SQL
-- Disconnect listener
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name LIKE '%listener%';
-- Insert events
INSERT INTO events_outbox (channel, payload) VALUES ('practice_changed', '{"id": 1}'::jsonb);
SELECT pg_notify('practice_changed', '{"id": 1, "_outbox_id": 1}');
SQL

# 3. Reconnect listener; verify replay log

# 4. Consumer integration test
pytest backend/tests/services/events/test_outbox.py -v
```

Numbers before/after:
- Before: 30s PG outage during war_room post = ~30 events lost (depending on disconnect timing)
- After: 30s PG outage = 0 events lost (all replayed on reconnect)
