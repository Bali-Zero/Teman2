"""
Channel Optimizations.

Performance improvements for multi-channel architecture:
- Rate limiting per channel
- Connection pooling
- Message deduplication
- Metrics collection

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration per channel."""

    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    burst_size: int = 10  # Allow bursts


class ChannelRateLimiter:
    """
    Token bucket rate limiter per channel.

    Prevents API abuse and ensures compliance with provider limits.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        self.tokens: dict[str, float] = defaultdict(lambda: config.burst_size)
        self.last_refill: dict[str, float] = defaultdict(time.time)
        self.minute_counts: dict[str, list[float]] = defaultdict(list)
        self.hour_counts: dict[str, list[float]] = defaultdict(list)

    async def acquire(self, channel_id: str) -> bool:
        """
        Acquire rate limit token.

        Returns:
            True if request allowed, False if rate limited
        """
        now = time.time()

        # Refill tokens (1 token per second)
        elapsed = now - self.last_refill[channel_id]
        self.tokens[channel_id] = min(
            self.config.burst_size,
            self.tokens[channel_id] + elapsed,
        )
        self.last_refill[channel_id] = now

        # Check burst capacity
        if self.tokens[channel_id] < 1:
            logger.warning(f"Rate limit (burst): {channel_id}")
            return False

        # Check per-minute limit
        self._cleanup_old_counts(channel_id, now)
        if len(self.minute_counts[channel_id]) >= self.config.max_requests_per_minute:
            logger.warning(f"Rate limit (minute): {channel_id}")
            return False

        # Check per-hour limit
        if len(self.hour_counts[channel_id]) >= self.config.max_requests_per_hour:
            logger.warning(f"Rate limit (hour): {channel_id}")
            return False

        # Consume token
        self.tokens[channel_id] -= 1
        self.minute_counts[channel_id].append(now)
        self.hour_counts[channel_id].append(now)

        return True

    def _cleanup_old_counts(self, channel_id: str, now: float):
        """Remove counts older than time windows."""
        # Remove minute-old counts
        minute_ago = now - 60
        self.minute_counts[channel_id] = [
            t for t in self.minute_counts[channel_id] if t > minute_ago
        ]

        # Remove hour-old counts
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

    def record_message_received(self, channel: str):
        """Record incoming message."""
        self.counters[f"{channel}.messages_received"] += 1

    def record_message_sent(self, channel: str, latency_ms: float):
        """Record outgoing message with latency."""
        self.counters[f"{channel}.messages_sent"] += 1
        self.latencies[channel].append(latency_ms)

        # Trim old samples
        if len(self.latencies[channel]) > self.max_latency_samples:
            self.latencies[channel] = self.latencies[channel][-self.max_latency_samples :]

    def record_error(self, channel: str, error_type: str):
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

    async def close_all(self):
        """Close all HTTP clients."""
        async with self._lock:
            for channel, client in self.clients.items():
                await client.aclose()
                logger.info(f"Closed HTTP client pool for {channel}")
            self.clients.clear()


# Global instances (initialized in service_initializer.py)
rate_limiter: ChannelRateLimiter | None = None
message_deduplicator: MessageDeduplicator | None = None
channel_metrics: ChannelMetrics | None = None
connection_pool: ConnectionPool | None = None


def initialize_optimizations():
    """Initialize global optimization instances."""
    global rate_limiter, message_deduplicator, channel_metrics, connection_pool

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

    logger.info("✅ Channel optimizations initialized")
