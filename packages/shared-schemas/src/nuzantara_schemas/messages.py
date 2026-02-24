"""Inter-service message schemas for Redis Streams communication."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    # Graph engine -> CRM
    CLIENT_QUERY = "client_query"
    CLIENT_ACTIVITY = "client_activity"

    # Graph engine -> Notifications
    ALERT_TRIGGER = "alert_trigger"

    # Ingestion -> Graph engine
    CACHE_INVALIDATION = "cache_invalidation"
    COLLECTION_UPDATED = "collection_updated"


class MessageEnvelope(BaseModel):
    """Standard envelope for all inter-service messages via Redis Streams."""

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str
    event_type: EventType
    payload: dict[str, Any]
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
