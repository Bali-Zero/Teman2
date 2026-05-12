"""Bali Zero event subscriber (Redis Streams consumer groups, redis-py).

Usage:
    from eventbus import EventSubscriber
    sub = EventSubscriber(agent_name="my-agent", event_types=["regulatory.delta.detected"])
    for env in sub.listen(block_ms=5000):
        process(env.payload)
        sub.ack(env)

REFACTORED 2026-05-09 per Gemini W1 review (P0):
- Replaced redis-cli subprocess with native redis-py
- Added PEL drain at boot (fixes at-least-once delivery violation)
"""
from __future__ import annotations
import os
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

import redis

from .publisher import REDIS_HOST, REDIS_PORT, STREAM_PREFIX, _client
from .schema import EVENT_TYPES

log = logging.getLogger("eventbus.subscriber")


@dataclass
class EventEnvelope:
    event_id: str
    event_type: str
    version: str
    emitted_at: str
    emitted_by: str
    trace_id: str
    payload: dict[str, Any]
    _stream: str = field(default="", repr=False)
    _redis_id: str = field(default="", repr=False)


def _envelope_from_fields(stream: str, redis_id: str, fields: dict[str, Any]) -> EventEnvelope:
    payload_raw = fields.get("payload", "{}")
    try:
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
    except (json.JSONDecodeError, TypeError):
        payload = {"_raw": str(payload_raw), "_parse_error": True}
    return EventEnvelope(
        event_id=str(fields.get("event_id", "")),
        event_type=str(fields.get("event_type", "")),
        version=str(fields.get("version", "1")),
        emitted_at=str(fields.get("emitted_at", "")),
        emitted_by=str(fields.get("emitted_by", "")),
        trace_id=str(fields.get("trace_id", "")),
        payload=payload,
        _stream=stream,
        _redis_id=redis_id,
    )


class EventSubscriber:
    """Consumer-group-backed reader over one or more bz:* streams.

    Implements at-least-once delivery: on boot, drains pending entries (PEL)
    before consuming new messages. Crashed-but-not-acked messages are recovered.
    """

    def __init__(
        self,
        agent_name: str,
        event_types: Iterable[str],
        *,
        consumer_id: str | None = None,
        start_from: str = "$",  # "$"=new only, "0"=full backlog
    ):
        self.agent_name = agent_name
        self.event_types = list(event_types)
        for et in self.event_types:
            if et not in EVENT_TYPES:
                raise ValueError(f"unknown event_type '{et}'")
        self.consumer_id = consumer_id or f"{agent_name}-{os.getpid()}"
        self.group = f"bz:cg:{agent_name}"
        self.streams = [f"{STREAM_PREFIX}{et}" for et in self.event_types]
        self.start_from = start_from
        self.r = _client()
        self._ensure_groups()
        self._pel_drained = False

    def _ensure_groups(self) -> None:
        for stream in self.streams:
            try:
                self.r.xgroup_create(stream, self.group, id=self.start_from, mkstream=True)
                log.info("created consumer group %s on %s", self.group, stream)
            except redis.exceptions.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    log.warning("group create on %s: %s", stream, e)

    def _drain_pel(self, count: int = 100) -> int:
        """Read pending-not-yet-acked messages on boot (recovery from crash).
        Returns number of pending entries yielded."""
        streams_pending = {s: "0" for s in self.streams}
        result = self.r.xreadgroup(
            self.group, self.consumer_id, streams_pending, count=count
        )
        if not result:
            return 0
        return sum(len(msgs) for _, msgs in result)

    def listen(self, block_ms: int = 5000, count: int = 10) -> Iterator[EventEnvelope]:
        """Generator. Yields EventEnvelope as they arrive.

        Phase 1 (one-time): drain PEL so crashed-but-not-acked messages are recovered.
        Phase 2: XREADGROUP with ">" to fetch only new messages.
        """
        # Phase 1: drain PEL on boot
        if not self._pel_drained:
            streams_pending = {s: "0" for s in self.streams}
            while True:
                result = self.r.xreadgroup(
                    self.group, self.consumer_id, streams_pending, count=count
                )
                if not result or all(not msgs for _, msgs in result):
                    break
                for stream, msgs in result:
                    for redis_id, fields in msgs:
                        log.info("PEL recovery: re-yielding %s from %s", redis_id, stream)
                        yield _envelope_from_fields(stream, redis_id, fields)
            self._pel_drained = True
            log.info("PEL drained, switching to new-message mode")

        # Phase 2: stream new messages
        streams_new = {s: ">" for s in self.streams}
        while True:
            try:
                result = self.r.xreadgroup(
                    self.group, self.consumer_id, streams_new,
                    count=count, block=block_ms,
                )
            except redis.RedisError as e:
                log.error("xreadgroup failed: %s", e)
                time.sleep(2)
                continue

            if not result:
                continue

            for stream, msgs in result:
                for redis_id, fields in msgs:
                    yield _envelope_from_fields(stream, redis_id, fields)

    def ack(self, env: EventEnvelope) -> None:
        try:
            self.r.xack(env._stream, self.group, env._redis_id)
        except redis.RedisError as e:
            log.warning("xack failed: %s", e)

    # -------- Poison-pill / DLQ handling (W1.5 Risk 1 fix) --------
    MAX_DELIVERY_ATTEMPTS = 3
    DLQ_STREAM = "bz:dlq"

    def get_delivery_count(self, env: EventEnvelope) -> int:
        """Return how many times this redis_id has been delivered to this consumer group.
        Uses XPENDING which returns delivery count per pending entry."""
        try:
            res = self.r.xpending_range(
                env._stream, self.group,
                min=env._redis_id, max=env._redis_id, count=1,
            )
            if res:
                # xpending_range returns list of dicts with 'times_delivered' (redis-py 5+)
                first = res[0]
                return int(first.get("times_delivered", 1))
        except redis.RedisError as e:
            log.warning("xpending check failed for %s: %s", env._redis_id, e)
        return 1  # assume first delivery if we can't check

    def park_to_dlq(self, env: EventEnvelope, failure_reason: str) -> None:
        """Move event to dead-letter queue, ack original to drain PEL."""
        dlq_envelope = {
            "event_id": env.event_id,
            "event_type": env.event_type,
            "version": env.version,
            "emitted_at": env.emitted_at,
            "emitted_by": env.emitted_by,
            "trace_id": env.trace_id,
            "payload": json.dumps(env.payload, default=str) if isinstance(env.payload, dict) else str(env.payload),
            "_dlq_reason": failure_reason[:500],
            "_dlq_original_stream": env._stream,
            "_dlq_consumer_group": self.group,
            "_dlq_parked_at": "{}".format(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()),
        }
        try:
            dlq_id = self.r.xadd(self.DLQ_STREAM, dlq_envelope, maxlen=10000, approximate=True)
            log.error(
                "POISON PILL parked event %s (stream=%s) to DLQ %s reason=%s",
                env.event_id, env._stream, dlq_id, failure_reason[:120],
            )
            # Ack original so it stops being redelivered
            self.r.xack(env._stream, self.group, env._redis_id)
        except redis.RedisError as e:
            log.warning("DLQ park failed for %s: %s", env._redis_id, e)

    def is_seen(self, event_id: str, ttl_seconds: int = 86400) -> bool:
        """Idempotency helper: returns True if event_id already processed.
        Uses Redis SET with TTL to track recent event_ids per consumer."""
        seen_key = f"bz:consumer:{self.agent_name}:seen"
        try:
            existed = self.r.sismember(seen_key, event_id)
            if existed:
                return True
            pipe = self.r.pipeline()
            pipe.sadd(seen_key, event_id)
            pipe.expire(seen_key, ttl_seconds)
            pipe.execute()
            return False
        except redis.RedisError as e:
            log.warning("is_seen check failed: %s", e)
            return False  # fail-open: process anyway


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("usage: python -m eventbus.subscriber <agent_name> <event_type1> [...]", file=sys.stderr)
        sys.exit(2)
    sub = EventSubscriber(agent_name=sys.argv[1], event_types=sys.argv[2:])
    print(f"listening on {sub.streams}", file=sys.stderr)
    for env in sub.listen(block_ms=10000):
        print(json.dumps({
            "event_id": env.event_id,
            "event_type": env.event_type,
            "emitted_by": env.emitted_by,
            "trace_id": env.trace_id,
            "payload": env.payload,
        }))
        sub.ack(env)
