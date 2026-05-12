"""Bali Zero Event Bus (Redis Streams over Tailscale).

Mini-Pro2 Redis at 100.93.236.6:6379. Bus prefix `bz:`. Schema doc: EVENT_SCHEMA.md.
"""
from .publisher import publish, REDIS_HOST, REDIS_PORT
from .subscriber import EventSubscriber, EventEnvelope
from .schema import EVENT_TYPES, validate_payload, generate_event_id, RETENTION
from .heartbeat import beat, is_alive, list_all_heartbeats, start_background_beater

__all__ = [
    "publish",
    "EventSubscriber",
    "EventEnvelope",
    "EVENT_TYPES",
    "RETENTION",
    "validate_payload",
    "generate_event_id",
    "REDIS_HOST",
    "REDIS_PORT",
    "beat",
    "is_alive",
    "list_all_heartbeats",
    "start_background_beater",
]
