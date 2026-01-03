"""
Unit tests for InMemoryConversationCache
Target: >95% coverage
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.memory.memory_fallback import InMemoryConversationCache, get_memory_cache


class TestInMemoryConversationCache:
    """Tests for InMemoryConversationCache"""

    def test_singleton_pattern(self):
        """Test that cache is a singleton"""
        cache1 = InMemoryConversationCache()
        cache2 = InMemoryConversationCache()
        assert cache1 is cache2

    def test_init(self):
        """Test initialization"""
        # Reset singleton for clean test
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache(ttl_minutes=30)
        assert cache._ttl == timedelta(minutes=30)
        assert len(cache._cache) == 0

    def test_add_message(self):
        """Test adding message"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Hello")
        assert len(cache._cache["conv1"]) == 1
        assert cache._cache["conv1"][0]["role"] == "user"
        assert cache._cache["conv1"][0]["content"] == "Hello"

    def test_get_messages(self):
        """Test getting messages"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Hello")
        cache.add_message("conv1", "assistant", "Hi")
        messages = cache.get_messages("conv1")
        assert len(messages) == 2

    def test_get_messages_limit(self):
        """Test getting messages with limit"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache()
        for i in range(30):
            cache.add_message("conv1", "user", f"Message {i}")
        messages = cache.get_messages("conv1", limit=10)
        assert len(messages) == 10

    def test_extract_entities_name(self):
        """Test extracting name entity"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Mi chiamo Mario")
        entities = cache.get_entities("conv1")
        assert entities["user_name"] == "Mario"

    def test_extract_entities_city(self):
        """Test extracting city entity"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Vivo a Milano")
        entities = cache.get_entities("conv1")
        assert entities["user_city"] == "Milano"

    def test_extract_entities_budget(self):
        """Test extracting budget entity"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Ho un budget di 50 milioni")
        entities = cache.get_entities("conv1")
        assert "budget" in entities

    def test_extract_entities_no_user_message(self):
        """Test that entities are not extracted from assistant messages"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache()
        cache.add_message("conv1", "assistant", "Mi chiamo Mario")
        entities = cache.get_entities("conv1")
        assert "user_name" not in entities

    def test_cleanup_old(self):
        """Test cleanup of old conversations"""
        InMemoryConversationCache._instance = None
        cache = InMemoryConversationCache(ttl_minutes=1)
        cache.add_message("conv1", "user", "Hello")

        # Set timestamp to old
        cache._timestamps["conv1"] = datetime.now() - timedelta(minutes=2)

        cache._cleanup_old()
        assert "conv1" not in cache._cache

    def test_get_memory_cache_singleton(self):
        """Test get_memory_cache returns singleton"""
        cache1 = get_memory_cache()
        cache2 = get_memory_cache()
        assert cache1 is cache2




