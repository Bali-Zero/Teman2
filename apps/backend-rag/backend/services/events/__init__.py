"""Event system — PG LISTEN/NOTIFY + in-process pub/sub.

Includes a durability layer (``backend.services.events.outbox``) that lets
the EventBus replay events lost during listener-reconnect windows.
"""

from backend.services.events.event_bus import EventBus, EventHandler, EventTrace
from backend.services.events.outbox import (
    InvalidChannelError,
    acknowledge,
    get_unconsumed_count,
    prune_consumed,
    publish,
    replay_unconsumed,
    validate_channel,
)

__all__ = [
    "EventBus",
    "EventHandler",
    "EventTrace",
    # Outbox helper (P0-2 phase 1)
    "InvalidChannelError",
    "acknowledge",
    "get_unconsumed_count",
    "prune_consumed",
    "publish",
    "replay_unconsumed",
    "validate_channel",
]
