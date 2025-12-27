import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryConversationCache:
    """
    Fallback cache for storing conversations and entities when the database is unavailable.
    This is ephemeral storage and will be cleared on server restart.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(InMemoryConversationCache, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, ttl_minutes: int = 60):
        if getattr(self, "_initialized", False):
            return

        self._cache: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._entities: dict[str, dict[str, Any]] = defaultdict(dict)
        self._timestamps: dict[str, datetime] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._initialized = True
        logger.info("✅ InMemoryConversationCache initialized")

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """Add a message to the in-memory cache."""
        self._cache[conversation_id].append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        self._timestamps[conversation_id] = datetime.now()

        # Extract entities from user messages
        if role == "user":
            self.extract_and_save_entities(conversation_id, content)

        self._cleanup_old()

    def get_messages(self, conversation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve messages from cache."""
        messages = self._cache.get(conversation_id, [])
        return messages[-limit:]

    def extract_and_save_entities(self, conversation_id: str, content: str) -> None:
        """Extract basic entities (name, city, budget) from message content."""
        content_lower = content.lower()
        entities = self._entities[conversation_id]

        # Name extraction (Simple heuristics)
        # "Mi chiamo [Name]", "Sono [Name]"
        # Use case-insensitive flag for the prefix, but capture the name as is
        name_match = re.search(r"(?i)(?:mi chiamo|sono|i am|my name is)\s+([A-Z][a-z]+)", content)
        if name_match:
            name = name_match.group(1)
            # Filter out common false positives
            if name.lower() not in ["zantara", "bali", "jakarta", "indonesia", "qui", "un", "una"]:
                entities["user_name"] = name
                logger.debug(f"🧠 Extracted name: {name}")

        # City extraction
        cities = [
            "milano",
            "roma",
            "napoli",
            "torino",
            "firenze",
            "bologna",
            "venezia",
            "genova",
            "palermo",
            "jakarta",
            "bali",
            "surabaya",
            "bandung",
            "medan",
            "london",
            "paris",
            "new york",
            "singapore",
            "sydney",
            "melbourne",
        ]
        for city in cities:
            if f" {city} " in f" {content_lower} " or content_lower.endswith(f" {city}"):
                entities["user_city"] = city.title()
                logger.debug(f"🧠 Extracted city: {city.title()}")
                break

        # Budget extraction
        # Matches: "50 milioni", "100 juta", "2000 usd", "5000 euro"
        budget_match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(milioni?|miliardi?|juta|milyar|k|mila|thousand|million|billion|euro|eur|usd|idr|rp)",
            content_lower,
        )
        if budget_match:
            full_match = content[budget_match.start() : budget_match.end()]
            entities["budget"] = full_match
            logger.debug(f"🧠 Extracted budget: {full_match}")

    def get_entities(self, conversation_id: str) -> dict[str, Any]:
        """Get extracted entities for a conversation."""
        return self._entities.get(conversation_id, {})

    def _cleanup_old(self) -> None:
        """Remove expired conversations to prevent memory leaks."""
        now = datetime.now()
        expired = [cid for cid, ts in self._timestamps.items() if now - ts > self._ttl]

        for cid in expired:
            if cid in self._cache:
                del self._cache[cid]
            if cid in self._timestamps:
                del self._timestamps[cid]
            if cid in self._entities:
                del self._entities[cid]

        if expired:
            logger.debug(f"🧹 Cleaned up {len(expired)} expired conversations from cache")


# Singleton accessor
_memory_cache = None


def get_memory_cache() -> InMemoryConversationCache:
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = InMemoryConversationCache()
    return _memory_cache
