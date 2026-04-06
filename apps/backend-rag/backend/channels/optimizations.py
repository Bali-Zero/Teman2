"""
Channel Optimizations.

Performance improvements for multi-channel architecture:
- Rate limiting per channel (Redis-backed + in-memory burst)
- Connection pooling
- Message deduplication
- Dead Letter Queue with Redis fallback
- Metrics collection

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import asyncio
import contextlib
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _get_redis_client() -> Any | None:
    """Get async Redis client from RedisManager. Returns None if unavailable."""
    try:
        from backend.core.redis_manager import RedisManager

        manager = RedisManager.get_instance()
        return manager.get_async_client()
    except Exception:
        return None


@dataclass
class RateLimitConfig:
    """Rate limit configuration per channel."""

    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    burst_size: int = 10  # Allow bursts


class ChannelRateLimiter:
    """
    Hybrid rate limiter per channel.

    - In-memory token bucket for sub-second burst limiting (resets on deploy, acceptable).
    - Redis INCR counters for per-minute and per-hour limits (persists across deploys).
    - Falls back to in-memory counters when Redis is unavailable.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        # In-memory burst tokens (intentionally ephemeral)
        self.tokens: dict[str, float] = defaultdict(lambda: config.burst_size)
        self.last_refill: dict[str, float] = defaultdict(time.time)
        # In-memory fallback counters (used only when Redis is down)
        self.minute_counts: dict[str, list[float]] = defaultdict(list)
        self.hour_counts: dict[str, list[float]] = defaultdict(list)

    async def acquire(self, channel_id: str) -> bool:
        """
        Acquire rate limit token.

        Returns:
            True if request allowed, False if rate limited.
        """
        now = time.time()

        # --- Burst check (always in-memory, sub-second) ---
        elapsed = now - self.last_refill[channel_id]
        self.tokens[channel_id] = min(
            self.config.burst_size,
            self.tokens[channel_id] + elapsed,
        )
        self.last_refill[channel_id] = now

        if self.tokens[channel_id] < 1:
            logger.warning(f"Rate limit (burst): {channel_id}")
            return False

        # --- Per-minute / per-hour: try Redis first ---
        redis_ok = await self._check_redis_limits(channel_id)
        if redis_ok is not None:
            # Redis answered definitively
            if not redis_ok:
                return False
            # Redis says OK — consume burst token and return
            self.tokens[channel_id] -= 1
            return True

        # --- Fallback: in-memory counters ---
        self._cleanup_old_counts(channel_id, now)
        if len(self.minute_counts[channel_id]) >= self.config.max_requests_per_minute:
            logger.warning(f"Rate limit (minute, in-memory): {channel_id}")
            return False
        if len(self.hour_counts[channel_id]) >= self.config.max_requests_per_hour:
            logger.warning(f"Rate limit (hour, in-memory): {channel_id}")
            return False

        # Consume
        self.tokens[channel_id] -= 1
        self.minute_counts[channel_id].append(now)
        self.hour_counts[channel_id].append(now)
        return True

    async def _check_redis_limits(self, channel_id: str) -> bool | None:
        """
        Check per-minute and per-hour limits via Redis INCR.

        Returns:
            True  — under limits (counters incremented)
            False — rate limited
            None  — Redis unavailable, caller should use in-memory fallback
        """
        redis = _get_redis_client()
        if redis is None:
            return None

        try:
            minute_key = f"channel_rate:{channel_id}:60"
            hour_key = f"channel_rate:{channel_id}:3600"

            # Atomic INCR + TTL for minute window
            minute_count = await redis.incr(minute_key)
            if minute_count == 1:
                await redis.expire(minute_key, 60)

            if minute_count > self.config.max_requests_per_minute:
                logger.warning(f"Rate limit (minute, Redis): {channel_id} count={minute_count}")
                # Decrement back since we're rejecting
                await redis.decr(minute_key)
                return False

            # Atomic INCR + TTL for hour window
            hour_count = await redis.incr(hour_key)
            if hour_count == 1:
                await redis.expire(hour_key, 3600)

            if hour_count > self.config.max_requests_per_hour:
                logger.warning(f"Rate limit (hour, Redis): {channel_id} count={hour_count}")
                await redis.decr(hour_key)
                # Also undo the minute increment
                await redis.decr(minute_key)
                return False

            return True

        except Exception as e:
            logger.debug(f"Redis rate limit check failed, falling back to in-memory: {e}")
            return None

    def _cleanup_old_counts(self, channel_id: str, now: float) -> None:
        """Remove counts older than time windows (in-memory fallback only)."""
        minute_ago = now - 60
        self.minute_counts[channel_id] = [
            t for t in self.minute_counts[channel_id] if t > minute_ago
        ]

        hour_ago = now - 3600
        self.hour_counts[channel_id] = [t for t in self.hour_counts[channel_id] if t > hour_ago]


class MessageDeduplicator:
    """
    Deduplicates messages using content hash + time window.

    Prevents duplicate processing of same message (webhook retries, etc.).
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self.seen_hashes: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def is_duplicate(self, channel: str, user_id: str, text: str) -> bool:
        """
        Check if message is duplicate.

        Args:
            channel: Channel name
            user_id: User identifier
            text: Message text

        Returns:
            True if duplicate (seen recently), False if new
        """
        # Create content hash
        content = f"{channel}:{user_id}:{text}"
        message_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        async with self._lock:
            now = time.time()

            # Cleanup old hashes
            self.seen_hashes = {
                h: t for h, t in self.seen_hashes.items() if now - t < self.ttl_seconds
            }

            # Check if seen
            if message_hash in self.seen_hashes:
                logger.info(f"Duplicate message detected: {message_hash}")
                return True

            # Mark as seen
            self.seen_hashes[message_hash] = now
            return False


class ChannelMetrics:
    """
    Collect metrics per channel.

    Tracks success rate, latency, errors for monitoring.
    """

    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.latencies: dict[str, list[float]] = defaultdict(list)
        self.max_latency_samples = 1000  # Keep last 1000 samples

    def record_message_received(self, channel: str) -> None:
        """Record incoming message."""
        self.counters[f"{channel}.messages_received"] += 1

    def record_message_sent(self, channel: str, latency_ms: float) -> None:
        """Record outgoing message with latency."""
        self.counters[f"{channel}.messages_sent"] += 1
        self.latencies[channel].append(latency_ms)

        # Trim old samples
        if len(self.latencies[channel]) > self.max_latency_samples:
            self.latencies[channel] = self.latencies[channel][-self.max_latency_samples :]

    def record_error(self, channel: str, error_type: str) -> None:
        """Record error."""
        self.counters[f"{channel}.errors.{error_type}"] += 1

    def get_stats(self, channel: str) -> dict[str, Any]:
        """Get statistics for channel."""
        received = self.counters.get(f"{channel}.messages_received", 0)
        sent = self.counters.get(f"{channel}.messages_sent", 0)
        errors = sum(v for k, v in self.counters.items() if k.startswith(f"{channel}.errors."))

        latencies = self.latencies.get(channel, [])
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        success_rate = (sent / received * 100) if received > 0 else 0

        return {
            "messages_received": received,
            "messages_sent": sent,
            "errors": errors,
            "success_rate": f"{success_rate:.1f}%",
            "avg_latency_ms": f"{avg_latency:.1f}",
            "p95_latency_ms": f"{p95_latency:.1f}",
        }


class ConnectionPool:
    """
    HTTP connection pool for channel adapters.

    Reuses httpx.AsyncClient instances to reduce connection overhead.
    """

    def __init__(self, max_connections: int = 100, timeout: float = 30.0) -> None:
        self.max_connections = max_connections
        self.timeout = timeout
        self.clients: dict[str, Any] = {}  # channel -> AsyncClient
        self._lock = asyncio.Lock()

    async def get_client(self, channel: str):
        """Get or create HTTP client for channel."""
        async with self._lock:
            if channel not in self.clients:
                import httpx

                self.clients[channel] = httpx.AsyncClient(
                    timeout=self.timeout,
                    limits=httpx.Limits(max_connections=self.max_connections),
                )
                logger.info(f"Created HTTP client pool for {channel}")

            return self.clients[channel]

    async def close_all(self) -> None:
        """Close all HTTP clients."""
        async with self._lock:
            for channel, client in self.clients.items():
                await client.aclose()
                logger.info(f"Closed HTTP client pool for {channel}")
            self.clients.clear()


class DeliveryManager:
    """
    Dead Letter Queue manager for failed outbound messages.

    Persists failed messages to PostgreSQL for retry with exponential backoff.
    Falls back to Redis LPUSH if PG is unavailable, with a drain loop that
    moves items from Redis back to PG when the database recovers.
    """

    REDIS_DLQ_KEY = "channel_dlq:pending"
    MAX_ATTEMPTS = 3
    BASE_BACKOFF_SECONDS = 30  # 30s, 60s, 120s

    def __init__(self, db_pool: Any | None = None) -> None:
        self._db_pool = db_pool
        self._retry_task: asyncio.Task[None] | None = None

    async def persist_failed(
        self,
        channel: str,
        channel_id: str,
        content: str,
        error: str,
        *,
        sender_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Persist a failed message to the DLQ.

        Tries PostgreSQL first; if PG write fails, falls back to Redis list.
        """
        record = {
            "channel": channel,
            "channel_id": channel_id,
            "sender_id": sender_id or "",
            "content": content,
            "metadata": metadata or {},
            "error_message": error,
            "error_type": "send_failure",
        }

        if await self._persist_to_pg(record):
            return

        # PG failed — try Redis fallback
        await self._persist_to_redis(record)

    async def _persist_to_pg(self, record: dict[str, Any]) -> bool:
        """Write failed message to PostgreSQL. Returns True on success."""
        if self._db_pool is None:
            return False
        try:
            next_retry = datetime.now(timezone.utc) + timedelta(seconds=self.BASE_BACKOFF_SECONDS)
            await self._db_pool.execute(
                """
                INSERT INTO failed_messages
                    (channel, channel_id, sender_id, content, metadata,
                     error_message, error_type, attempt_count, max_attempts,
                     next_retry_at, status)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, 0, $8, $9, 'pending')
                """,
                record["channel"],
                record["channel_id"],
                record["sender_id"],
                record["content"],
                json.dumps(record["metadata"]),
                record["error_message"],
                record["error_type"],
                self.MAX_ATTEMPTS,
                next_retry,
            )
            logger.info(f"DLQ: persisted failed message to PG ({record['channel']}:{record['channel_id']})")
            return True
        except Exception as e:
            logger.warning(f"DLQ: PG write failed, trying Redis fallback: {e}")
            return False

    async def _persist_to_redis(self, record: dict[str, Any]) -> bool:
        """Push failed message to Redis list as JSON. Returns True on success."""
        redis = _get_redis_client()
        if redis is None:
            logger.error(f"DLQ: BOTH PG and Redis unavailable — message LOST: {record['channel']}:{record['channel_id']}")
            return False
        try:
            payload = json.dumps({**record, "queued_at": time.time()})
            await redis.lpush(self.REDIS_DLQ_KEY, payload)
            logger.info(f"DLQ: persisted to Redis fallback ({record['channel']}:{record['channel_id']})")
            return True
        except Exception as e:
            logger.error(f"DLQ: Redis LPUSH also failed — message LOST: {e}")
            return False

    async def _drain_redis_dlq(self) -> int:
        """
        Move items from Redis DLQ list back to PostgreSQL.

        Called at the start of each retry loop iteration so that messages
        buffered during a PG outage eventually land in the proper DLQ table.
        Returns count of items drained.
        """
        if self._db_pool is None:
            return 0

        redis = _get_redis_client()
        if redis is None:
            return 0

        drained = 0
        try:
            while True:
                raw = await redis.rpop(self.REDIS_DLQ_KEY)
                if raw is None:
                    break
                record = json.loads(raw)
                # Remove the queued_at timestamp used for diagnostics
                record.pop("queued_at", None)
                if await self._persist_to_pg(record):
                    drained += 1
                else:
                    # PG still down — push it back and stop draining
                    await redis.lpush(self.REDIS_DLQ_KEY, json.dumps(record))
                    logger.debug("DLQ drain: PG still unavailable, stopping drain")
                    break
        except Exception as e:
            logger.warning(f"DLQ drain error: {e}")

        if drained > 0:
            logger.info(f"DLQ: drained {drained} items from Redis to PG")
        return drained

    async def _process_dlq(self, adapters: dict[str, Any]) -> None:
        """Background loop that retries pending DLQ messages with exponential backoff."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Drain Redis buffer first
                await self._drain_redis_dlq()

                if self._db_pool is None:
                    continue

                now = datetime.now(timezone.utc)
                rows = await self._db_pool.fetch(
                    """
                    SELECT id, channel, channel_id, content, attempt_count, max_attempts
                    FROM failed_messages
                    WHERE status IN ('pending', 'retrying')
                      AND next_retry_at <= $1
                    ORDER BY next_retry_at ASC
                    LIMIT 10
                    """,
                    now,
                )

                for row in rows:
                    ch = row["channel"]
                    adapter = adapters.get(ch)
                    if adapter is None:
                        continue

                    attempt = row["attempt_count"] + 1
                    try:
                        from backend.channels.base import ChannelResponse

                        await adapter.send_response(
                            row["channel_id"],
                            ChannelResponse(text=row["content"], metadata={}),
                        )
                        # Success — mark delivered
                        await self._db_pool.execute(
                            "UPDATE failed_messages SET status='delivered', attempt_count=$1, updated_at=NOW() WHERE id=$2",
                            attempt, row["id"],
                        )
                        logger.info(f"DLQ: delivered message {row['id']} on attempt {attempt}")

                    except Exception as e:
                        if attempt >= row["max_attempts"]:
                            new_status = "exhausted"
                            next_retry = None
                        else:
                            new_status = "retrying"
                            backoff = self.BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                            next_retry = now + timedelta(seconds=backoff)

                        await self._db_pool.execute(
                            """
                            UPDATE failed_messages
                            SET status=$1, attempt_count=$2, next_retry_at=$3,
                                error_message=$4, updated_at=NOW()
                            WHERE id=$5
                            """,
                            new_status, attempt, next_retry, str(e), row["id"],
                        )
                        logger.debug(f"DLQ: retry {attempt} failed for {row['id']}: {e}")

            except asyncio.CancelledError:
                logger.info("DLQ retry loop cancelled")
                break
            except Exception as e:
                logger.error(f"DLQ retry loop error: {e}")
                await asyncio.sleep(60)

    async def start_retry_loop(self, adapters: dict[str, Any]) -> None:
        """Start the background DLQ retry loop."""
        if self._retry_task is not None:
            return
        self._retry_task = asyncio.create_task(self._process_dlq(adapters))
        logger.info("DLQ retry loop started")

    async def stop_retry_loop(self) -> None:
        """Stop the background DLQ retry loop."""
        if self._retry_task is not None:
            self._retry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._retry_task
            self._retry_task = None


# Global instances (initialized in service_initializer.py)
rate_limiter: ChannelRateLimiter | None = None
message_deduplicator: MessageDeduplicator | None = None
channel_metrics: ChannelMetrics | None = None
connection_pool: ConnectionPool | None = None
delivery_manager: DeliveryManager | None = None


def initialize_optimizations(db_pool: Any | None = None) -> None:
    """Initialize global optimization instances."""
    global rate_limiter, message_deduplicator, channel_metrics, connection_pool, delivery_manager

    rate_limiter = ChannelRateLimiter(
        RateLimitConfig(
            max_requests_per_minute=60,
            max_requests_per_hour=1000,
            burst_size=10,
        ),
    )

    message_deduplicator = MessageDeduplicator(ttl_seconds=300)
    channel_metrics = ChannelMetrics()
    connection_pool = ConnectionPool(max_connections=100, timeout=30.0)
    delivery_manager = DeliveryManager(db_pool=db_pool)

    logger.info("Channel optimizations initialized (rate_limiter, dedup, metrics, pool, DLQ)")
