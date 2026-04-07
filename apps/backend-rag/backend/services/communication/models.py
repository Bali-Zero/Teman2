"""Omnichannel data models — enums, dataclasses, and filter types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class MessageIntent(str, Enum):
    """Classified intent of an incoming message."""

    QUESTION = "question"
    COMPLAINT = "complaint"
    LEAD = "lead"
    SUPPORT = "support"
    GREETING = "greeting"
    FOLLOWUP = "followup"
    SPAM = "spam"
    UNKNOWN = "unknown"


class Priority(str, Enum):
    """Thread priority level."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ThreadStatus(str, Enum):
    """Thread lifecycle status."""

    OPEN = "open"
    ASSIGNED = "assigned"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class RoutingDecision:
    """Result of the routing engine's classification."""

    intent: MessageIntent
    priority: Priority
    suggested_assignee: str | None = None
    thread_id: UUID | None = None
    client_id: int | None = None
    is_vip: bool = False
    reason: str = ""


@dataclass
class ThreadFilter:
    """Filter parameters for listing threads."""

    status: ThreadStatus | None = None
    assigned_to: str | None = None
    priority: Priority | None = None
    channel: str | None = None
    client_id: int | None = None
    search: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass
class ThreadMessage:
    """A single message within a thread (for API responses)."""

    id: int
    channel: str
    direction: str
    sender_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class ThreadDetail:
    """Full thread with messages (for API responses)."""

    id: UUID
    client_id: int | None
    status: ThreadStatus
    priority: Priority
    assigned_to: str | None
    subject: str | None
    channels: list[str]
    intent: str | None
    unread_count: int
    last_message_preview: str | None
    last_activity_at: str
    created_at: str
    messages: list[ThreadMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
