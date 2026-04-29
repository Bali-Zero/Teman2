# P0-6 Brainstorm — Channels webhook ack-first + Twitter CRC

**Goal:** Convert webhook routers to "ack first, process async" pattern. Restore Twitter CRC handshake.
**Effort:** 2-3 days
**Dependencies:** P0-0 (visibility), P0-2 (Outbox pattern reusable for inbound queue)

---

## Strategy options

### Option A: Inbound webhook table + background worker

Webhook router persists payload to `inbound_webhooks` table within 200ms, returns 200 OK. Background `webhook_processor` worker polls (or LISTEN) and processes.

**Pros:**
- Standard pattern — mirrors `failed_messages` outbound DLQ
- Decouples Meta/Twitter timeout from processing time
- Survives Fly machine crash mid-processing (table persists)
- Reuse same Outbox infra from P0-2

**Cons:**
- Adds processing latency (queue → poll cycle)
- Worker loop needs heartbeat for monitoring

**Effort:** 2 days for table + router refactor + worker.

### Option B: BackgroundTasks (FastAPI built-in)

Use `BackgroundTasks` in router. Returns 200 OK immediately, processes in background.

**Pros:**
- Simplest — FastAPI native
- No new table

**Cons:**
- Lost on Fly machine crash (no persistence)
- Still single-process — high traffic can saturate
- Doesn't survive deploy (rolling)

**Effort:** 1 day. But low resilience.

### Option C: Async queue (Celery/RQ/Arq)

Heavy queue infrastructure.

**Pros:**
- Industry standard

**Cons:**
- New infra (Redis already present but new pattern)
- Complexity disproportionate to need

**Effort:** 1 week.

**Recommendation:** **Option A** — table-based. Aligns with existing pattern (`failed_messages`), uses durable storage we already have, low operational cost.

---

## Implementation plan (Option A)

### Step 1: Migration

```sql
-- File: apps/backend-rag/backend/db/migrations_v2/142_inbound_webhooks.sql

CREATE TABLE inbound_webhooks (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NULL,
    error_message TEXT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ NULL
);

CREATE INDEX inbound_webhooks_pending ON inbound_webhooks (channel, received_at)
    WHERE processed_at IS NULL AND (next_retry_at IS NULL OR next_retry_at < NOW());

CREATE INDEX inbound_webhooks_received_at ON inbound_webhooks (received_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS inbound_webhooks_pending;
DROP INDEX IF EXISTS inbound_webhooks_received_at;
DROP TABLE IF EXISTS inbound_webhooks;
```

### Step 2: Router refactor

```python
# apps/backend-rag/backend/app/routers/webhooks.py (or per-channel router)

@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    payload: dict,
    request: Request,
    db_pool=Depends(get_database_pool)
) -> dict:
    """ACK first, process async. <200ms response guarantee.

    Pattern: persist payload, return 200 OK. Background worker picks up.
    """
    # Verify Meta signature (synchronous, fast)
    if not verify_meta_signature(request):
        raise HTTPException(401, "invalid signature")

    # Persist (atomic, fast)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO inbound_webhooks (channel, payload)
               VALUES ($1, $2::jsonb)""",
            "whatsapp", json.dumps(payload)
        )
        # Trigger worker via NOTIFY (worker uses LISTEN to wake up immediately)
        await conn.execute("NOTIFY inbound_webhook_queued, 'whatsapp'")

    return {"status": "queued"}
```

### Step 3: Background worker

```python
# apps/backend-rag/backend/services/channels/webhook_processor.py

import asyncio
import asyncpg
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

CHANNEL_HANDLERS: dict[str, Callable[[dict], Awaitable[None]]] = {
    "whatsapp": process_whatsapp_message,
    "instagram": process_instagram_message,
    "telegram": process_telegram_message,
    "twitter": process_twitter_message,
}


class WebhookProcessor:
    """LISTEN-based worker for inbound_webhooks queue.

    Uses PG LISTEN/NOTIFY for low-latency wake-up + falls back to polling
    every 5s in case NOTIFY missed.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self._stopped = False

    async def run(self):
        async with self.db_pool.acquire() as listen_conn:
            await listen_conn.add_listener("inbound_webhook_queued", self._on_notify)
            while not self._stopped:
                await self._process_pending()
                # Fallback poll
                try:
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break

    async def _process_pending(self):
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, channel, payload FROM inbound_webhooks
                   WHERE processed_at IS NULL
                     AND (next_retry_at IS NULL OR next_retry_at < NOW())
                   ORDER BY received_at
                   LIMIT 50
                   FOR UPDATE SKIP LOCKED"""
            )
            for r in rows:
                await self._process_one(conn, r)

    async def _process_one(self, conn, row):
        handler = CHANNEL_HANDLERS.get(row["channel"])
        if not handler:
            await conn.execute(
                """UPDATE inbound_webhooks
                   SET processed_at = NOW(), error_message = 'no handler'
                   WHERE id = $1""",
                row["id"]
            )
            return

        try:
            await handler(row["payload"])
            await conn.execute(
                "UPDATE inbound_webhooks SET processed_at = NOW() WHERE id = $1",
                row["id"]
            )
        except Exception as e:
            logger.exception(f"Webhook processing failed for id={row['id']}")
            attempts = await conn.fetchval(
                "UPDATE inbound_webhooks SET attempts = attempts + 1, error_message = $1, next_retry_at = NOW() + INTERVAL '5 minutes' * (attempts+1) WHERE id = $2 RETURNING attempts",
                str(e)[:500], row["id"]
            )
            if attempts >= 5:
                # Move to terminal: mark processed with error
                await conn.execute(
                    "UPDATE inbound_webhooks SET processed_at = NOW(), error_message = $1 WHERE id = $2",
                    f"GIVING UP after 5 attempts: {e}",
                    row["id"]
                )

    def _on_notify(self, conn, pid, channel, payload):
        # Trigger immediate process_pending (don't wait for poll)
        asyncio.create_task(self._process_pending())

    async def stop(self):
        self._stopped = True
```

### Step 4: Twitter CRC restoration

```python
# apps/backend-rag/backend/channels/twitter/webhook_router.py

import hmac
import hashlib
import base64
import os

@router.get("/webhook/twitter")
async def twitter_crc(crc_token: str) -> dict:
    """Twitter CRC handshake per https://developer.twitter.com/en/docs/twitter-api/premium/account-activity-api/guides/securing-webhooks"""
    secret = os.getenv("TWITTER_CONSUMER_SECRET")
    if not secret:
        raise HTTPException(500, "TWITTER_CONSUMER_SECRET not configured")

    signature = hmac.new(
        secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256
    ).digest()

    return {
        "response_token": "sha256=" + base64.b64encode(signature).decode("utf-8")
    }


@router.post("/webhook/twitter")
async def twitter_webhook(
    payload: dict,
    request: Request,
    db_pool=Depends(get_database_pool)
):
    """POST handler — ACK first."""
    # Verify x-twitter-webhooks-signature header
    if not verify_twitter_signature(request):
        raise HTTPException(401, "invalid signature")

    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO inbound_webhooks (channel, payload) VALUES ($1, $2::jsonb)",
            "twitter", json.dumps(payload)
        )
        await conn.execute("NOTIFY inbound_webhook_queued, 'twitter'")

    return {}  # Twitter expects empty 200
```

Re-enable in `logging_config.py` (remove the disabled line for twitter.webhook_router).

Re-register webhook with Twitter API:
```bash
# (one-time, post-deploy)
curl -X POST "https://api.twitter.com/1.1/account_activity/all/$ENV_NAME/webhooks.json" \
  -H "Authorization: OAuth ..." \
  -d "url=https://nuzantara-rag.fly.dev/webhook/twitter"
```

### Step 5: Pruning

LaunchAgent or cron — daily prune of `inbound_webhooks` rows older than 30 days where processed_at IS NOT NULL.

### Step 6: ChannelSensor for Cell

```python
class ChannelSensor(Sensor):
    name = "channels_inbound"

    async def sense(self, conn) -> SensorResult:
        rows = await conn.fetch(
            """SELECT channel, COUNT(*) FILTER (WHERE processed_at IS NULL) AS pending
               FROM inbound_webhooks
               WHERE received_at > NOW() - INTERVAL '5 minutes'
               GROUP BY channel"""
        )
        max_pending = max((r['pending'] for r in rows), default=0)
        status = "red" if max_pending > 100 else ("yellow" if max_pending > 20 else "green")
        return SensorResult(name=self.name, status=status, value={r['channel']: r['pending'] for r in rows})
```

---

## Dependencies

- **Before:** P0-0 (visibility), P0-2 (Outbox infra)
- **After:** Ack-first pattern reusable for any new channel

## Rollback plan

Migration 142 has explicit ROLLBACK. Router changes revertable via git. Twitter CRC fix optional (don't enable webhook on Twitter side until ready).

## L2 autonomy decision

**Auto-implementable: PARTIAL.** 
- Migration + router + worker: YES  
- Twitter CRC re-enable + Twitter API call: requires verifying TWITTER_CONSUMER_SECRET in Fly secrets — Zero handoff for credential audit

## Verification

```bash
# Synthetic load: 100 concurrent webhooks
ab -n 100 -c 10 -p whatsapp_payload.json -T application/json \
   http://localhost:8001/webhook/whatsapp
# Expected: 100/100 200 OK, all under 200ms

# Pending count drains
sleep 30
psql ... -c "SELECT COUNT(*) FROM inbound_webhooks WHERE processed_at IS NULL"
# Expected: 0

# Twitter CRC
curl -s "http://localhost:8001/webhook/twitter?crc_token=test123"
# Expected: {"response_token": "sha256=..."}
```

Numbers:
- Before: webhook router processes synchronously, can take 3+ seconds → Meta disables webhook → 100% missed
- After: 200 OK in <200ms guaranteed → Meta keeps webhook active → 0% missed (processing latency moved to worker, no longer affects Meta SLA)
