"""
Episodic Memory Service - Timeline of User Events

Manages user experiences and events over time, enabling:
- "When did I start the PT PMA process?"
- "What happened last week?"
- "Show me my milestones"

Features:
- Store events with temporal context (when, what, emotion)
- Extract events automatically from conversations
- Link events to Knowledge Graph entities
- Timeline queries with filtering
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that can be stored"""

    MILESTONE = "milestone"  # Achievement, completion
    PROBLEM = "problem"  # Issue, blocker
    RESOLUTION = "resolution"  # Problem solved
    DECISION = "decision"  # Choice made
    MEETING = "meeting"  # Consultation, call
    DEADLINE = "deadline"  # Due date, timeline
    DISCOVERY = "discovery"  # Learned something new
    GENERAL = "general"  # Other events


class Emotion(str, Enum):
    """Emotional context of events"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    URGENT = "urgent"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    WORRIED = "worried"


# Temporal patterns for extraction (Italian + English)
TEMPORAL_PATTERNS = {
    # Today/Yesterday
    r"\b(oggi|today)\b": lambda: datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    ),
    r"\b(ieri|yesterday)\b": lambda: (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    ),
    r"\b(domani|tomorrow)\b": lambda: (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    ),
    # Relative days
    r"\b(\d+)\s*(giorni? fa|days? ago)\b": lambda m: datetime.now(timezone.utc)
    - timedelta(days=int(m.group(1))),
    r"\b(la settimana scorsa|last week)\b": lambda: datetime.now(timezone.utc) - timedelta(weeks=1),
    r"\b(il mese scorso|last month)\b": lambda: datetime.now(timezone.utc) - timedelta(days=30),
    # Specific dates (DD/MM or DD/MM/YYYY)
    r"\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b": "_parse_date",
}

# Event type keywords
EVENT_KEYWORDS = {
    EventType.MILESTONE: [
        "completato",
        "finito",
        "concluso",
        "ottenuto",
        "approvato",
        "firmato",
        "completed",
        "finished",
        "achieved",
        "approved",
        "signed",
        "done",
    ],
    EventType.PROBLEM: [
        "problema",
        "errore",
        "bloccato",
        "rifiutato",
        "fallito",
        "difficoltà",
        "problem",
        "error",
        "blocked",
        "rejected",
        "failed",
        "issue",
        "stuck",
    ],
    EventType.RESOLUTION: [
        "risolto",
        "sistemato",
        "corretto",
        "funziona",
        "resolved",
        "fixed",
        "solved",
        "working now",
    ],
    EventType.DECISION: [
        "deciso",
        "scelto",
        "optato",
        "preferito",
        "decided",
        "chose",
        "opted",
        "selected",
    ],
    EventType.MEETING: [
        "incontro",
        "riunione",
        "chiamata",
        "meeting",
        "call",
        "consulenza",
        "appointment",
        "consultation",
    ],
    EventType.DEADLINE: ["scadenza", "entro", "deadline", "due date", "by", "before"],
}

# Emotion keywords
EMOTION_KEYWORDS = {
    Emotion.POSITIVE: [
        "felice",
        "contento",
        "ottimo",
        "perfetto",
        "happy",
        "great",
        "excellent",
        "perfect",
    ],
    Emotion.NEGATIVE: ["male", "purtroppo", "sfortunatamente", "bad", "unfortunately", "sadly"],
    Emotion.URGENT: ["urgente", "subito", "immediato", "urgent", "asap", "immediately"],
    Emotion.FRUSTRATED: ["frustrato", "arrabbiato", "stufo", "frustrated", "angry", "annoyed"],
    Emotion.EXCITED: ["entusiasta", "eccitato", "non vedo l'ora", "excited", "can't wait"],
    Emotion.WORRIED: ["preoccupato", "ansioso", "worried", "anxious", "concerned"],
}


class EpisodicMemoryService:
    """Service for managing episodic memories (timeline of events)"""

    def __init__(self, pool: asyncpg.Pool | None = None):
        self.pool = pool

    def _parse_date(self, match: re.Match) -> datetime:
        """Parse DD/MM or DD/MM/YYYY date format"""
        day = int(match.group(1))
        month = int(match.group(2))
        year_str = match.group(3)

        if year_str:
            year = int(year_str)
            if year < 100:
                year += 2000
        else:
            year = datetime.now().year

        try:
            return datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)

    def _extract_datetime(self, text: str) -> datetime | None:
        """Extract datetime from text using temporal patterns"""
        text_lower = text.lower()

        for pattern, resolver in TEMPORAL_PATTERNS.items():
            match = re.search(pattern, text_lower)
            if match:
                if resolver == "_parse_date":
                    return self._parse_date(match)
                elif callable(resolver):
                    try:
                        # Check if resolver needs the match object
                        import inspect

                        sig = inspect.signature(resolver)
                        if len(sig.parameters) > 0:
                            return resolver(match)
                        else:
                            return resolver()
                    except Exception:
                        continue

        return None

    def _detect_event_type(self, text: str) -> EventType:
        """Detect event type from text content"""
        text_lower = text.lower()

        for event_type, keywords in EVENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return event_type

        return EventType.GENERAL

    def _detect_emotion(self, text: str) -> Emotion:
        """Detect emotional context from text"""
        text_lower = text.lower()

        for emotion, keywords in EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return emotion

        return Emotion.NEUTRAL

    def _extract_title(self, text: str, max_length: int = 100) -> str:
        """Extract a concise title from text"""
        # Remove temporal expressions
        cleaned = text
        for pattern in TEMPORAL_PATTERNS.keys():
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Take first sentence or first N chars
        sentences = re.split(r"[.!?]", cleaned)
        title = sentences[0].strip() if sentences else cleaned

        if len(title) > max_length:
            title = title[: max_length - 3] + "..."

        return title or "Event"

    async def add_event(
        self,
        user_id: str,
        title: str,
        description: str | None = None,
        event_type: EventType | str = EventType.GENERAL,
        emotion: Emotion | str = Emotion.NEUTRAL,
        occurred_at: datetime | None = None,
        related_entities: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        Add a new event to user's timeline.

        Args:
            user_id: User identifier (email)
            title: Short event title
            description: Detailed description
            event_type: Type of event (milestone, problem, etc.)
            emotion: Emotional context
            occurred_at: When the event happened (defaults to now)
            related_entities: Links to KG entities
            metadata: Additional data

        Returns:
            Created event with ID
        """
        if not self.pool:
            logger.warning("No database pool, cannot add event")
            return {"status": "error", "message": "Database not available"}

        # Normalize enums
        if isinstance(event_type, EventType):
            event_type = event_type.value
        if isinstance(emotion, Emotion):
            emotion = emotion.value

        # Default to now if no date
        if occurred_at is None:
            occurred_at = datetime.now(timezone.utc)

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO episodic_memories
                    (user_id, title, description, event_type, emotion,
                     occurred_at, related_entities, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id, created_at
                    """,
                    user_id,
                    title,
                    description,
                    event_type,
                    emotion,
                    occurred_at,
                    related_entities or [],
                    metadata or {},
                )

                logger.info(f"Added episodic event for {user_id}: {title}")

                return {
                    "status": "created",
                    "id": row["id"],
                    "title": title,
                    "event_type": event_type,
                    "occurred_at": occurred_at.isoformat(),
                    "created_at": row["created_at"].isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to add event: {e}")
            return {"status": "error", "message": str(e)}

    async def get_timeline(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_type: str | None = None,
        emotion: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get user's event timeline with optional filters.

        Args:
            user_id: User identifier
            start_date: Filter events after this date
            end_date: Filter events before this date
            event_type: Filter by event type
            emotion: Filter by emotion
            limit: Max events to return
            offset: Pagination offset

        Returns:
            List of events ordered by occurred_at DESC
        """
        if not self.pool:
            return []

        try:
            # Build query dynamically
            conditions = ["user_id = $1"]
            params: list[Any] = [user_id]
            param_idx = 2

            if start_date:
                conditions.append(f"occurred_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1

            if end_date:
                conditions.append(f"occurred_at <= ${param_idx}")
                params.append(end_date)
                param_idx += 1

            if event_type:
                conditions.append(f"event_type = ${param_idx}")
                params.append(event_type)
                param_idx += 1

            if emotion:
                conditions.append(f"emotion = ${param_idx}")
                params.append(emotion)
                param_idx += 1

            where_clause = " AND ".join(conditions)

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT id, user_id, event_type, title, description,
                           emotion, occurred_at, related_entities, metadata,
                           created_at, updated_at
                    FROM episodic_memories
                    WHERE {where_clause}
                    ORDER BY occurred_at DESC
                    LIMIT ${param_idx} OFFSET ${param_idx + 1}
                    """,
                    *params,
                    limit,
                    offset,
                )

                return [
                    {
                        "id": row["id"],
                        "event_type": row["event_type"],
                        "title": row["title"],
                        "description": row["description"],
                        "emotion": row["emotion"],
                        "occurred_at": row["occurred_at"].isoformat()
                        if row["occurred_at"]
                        else None,
                        "related_entities": row["related_entities"],
                        "metadata": row["metadata"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get timeline: {e}")
            return []

    async def get_recent_events(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent events for user context"""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.get_timeline(
            user_id=user_id,
            start_date=start_date,
            limit=limit,
        )

    async def extract_and_save_event(
        self,
        user_id: str,
        message: str,
        ai_response: str | None = None,
        conversation_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Extract event from conversation and save if found.

        Args:
            user_id: User identifier
            message: User's message
            ai_response: Optional AI response for context
            conversation_id: Optional conversation ID

        Returns:
            Created event or None if no event detected
        """
        # Try to extract datetime
        occurred_at = self._extract_datetime(message)
        if ai_response:
            occurred_at = occurred_at or self._extract_datetime(ai_response)

        # Only save if we found a temporal reference
        if not occurred_at:
            return None

        # Detect event characteristics
        event_type = self._detect_event_type(message)
        emotion = self._detect_emotion(message)
        title = self._extract_title(message)

        # Create metadata
        metadata = {
            "source": "conversation",
            "ai_extracted": True,
            "original_message": message[:500],  # Truncate for storage
        }
        if conversation_id:
            metadata["conversation_id"] = conversation_id

        # Save event
        result = await self.add_event(
            user_id=user_id,
            title=title,
            description=message,
            event_type=event_type,
            emotion=emotion,
            occurred_at=occurred_at,
            metadata=metadata,
        )

        if result.get("status") == "created":
            logger.info(f"Extracted episodic event from conversation: {title}")
            return result

        return None

    async def get_context_summary(
        self,
        user_id: str,
        limit: int = 5,
    ) -> str:
        """
        Get a formatted summary of recent events for AI context.

        Returns a string suitable for including in system prompts.
        """
        events = await self.get_recent_events(user_id, days=30, limit=limit)

        if not events:
            return ""

        lines = ["### Recent Timeline"]
        for event in events:
            occurred = event.get("occurred_at", "")[:10]  # Just date
            title = event.get("title", "")
            event_type = event.get("event_type", "")
            emotion = event.get("emotion", "")

            emoji = {
                "milestone": "🎯",
                "problem": "⚠️",
                "resolution": "✅",
                "decision": "🔷",
                "meeting": "📅",
                "deadline": "⏰",
                "discovery": "💡",
            }.get(event_type, "📝")

            line = f"- {emoji} {occurred}: {title}"
            if emotion and emotion != "neutral":
                line += f" ({emotion})"
            lines.append(line)

        return "\n".join(lines)

    async def delete_event(self, event_id: int, user_id: str) -> bool:
        """Delete an event (only if owned by user)"""
        if not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM episodic_memories WHERE id = $1 AND user_id = $2",
                    event_id,
                    user_id,
                )
                return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False

    async def get_stats(self, user_id: str) -> dict[str, Any]:
        """Get statistics about user's episodic memory"""
        if not self.pool:
            return {}

        try:
            async with self.pool.acquire() as conn:
                stats = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(DISTINCT DATE(occurred_at)) as unique_days,
                        MIN(occurred_at) as first_event,
                        MAX(occurred_at) as last_event,
                        COUNT(*) FILTER (WHERE event_type = 'milestone') as milestones,
                        COUNT(*) FILTER (WHERE event_type = 'problem') as problems,
                        COUNT(*) FILTER (WHERE event_type = 'resolution') as resolutions
                    FROM episodic_memories
                    WHERE user_id = $1
                    """,
                    user_id,
                )

                return {
                    "total_events": stats["total_events"],
                    "unique_days": stats["unique_days"],
                    "first_event": stats["first_event"].isoformat()
                    if stats["first_event"]
                    else None,
                    "last_event": stats["last_event"].isoformat() if stats["last_event"] else None,
                    "milestones": stats["milestones"],
                    "problems": stats["problems"],
                    "resolutions": stats["resolutions"],
                }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
