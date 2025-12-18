"""
Unit Tests for services/memory_fallback.py - 95% Coverage Target
Tests the InMemoryConversationCache class
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test"""
    from services import memory_fallback

    # Reset both the singleton instance and the module-level cache
    memory_fallback.InMemoryConversationCache._instance = None
    memory_fallback._memory_cache = None
    yield
    # Clean up after test
    memory_fallback.InMemoryConversationCache._instance = None
    memory_fallback._memory_cache = None


# ============================================================================
# Test Singleton Pattern
# ============================================================================


class TestSingletonPattern:
    """Test suite for singleton pattern"""

    def test_singleton_same_instance(self):
        """Test that multiple instantiations return same instance"""
        from services.memory_fallback import InMemoryConversationCache

        cache1 = InMemoryConversationCache()
        cache2 = InMemoryConversationCache()

        assert cache1 is cache2

    def test_singleton_init_once(self):
        """Test that initialization only happens once"""
        from services.memory_fallback import InMemoryConversationCache

        cache1 = InMemoryConversationCache(ttl_minutes=30)
        # Add a message to first instance
        cache1.add_message("test_conv", "user", "Hello")

        # Create second instance
        cache2 = InMemoryConversationCache(ttl_minutes=60)

        # Second instance should have the message from first
        messages = cache2.get_messages("test_conv")
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"


# ============================================================================
# Test add_message
# ============================================================================


class TestAddMessage:
    """Test suite for add_message method"""

    def test_add_user_message(self):
        """Test adding a user message"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Hello Zantara")

        messages = cache.get_messages("conv1")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello Zantara"
        assert "timestamp" in messages[0]

    def test_add_assistant_message(self):
        """Test adding an assistant message"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.add_message("conv1", "assistant", "How can I help you?")

        messages = cache.get_messages("conv1")
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"

    def test_add_multiple_messages(self):
        """Test adding multiple messages to same conversation"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Question 1")
        cache.add_message("conv1", "assistant", "Answer 1")
        cache.add_message("conv1", "user", "Question 2")

        messages = cache.get_messages("conv1")
        assert len(messages) == 3

    def test_add_messages_different_conversations(self):
        """Test adding messages to different conversations"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Message for conv1")
        cache.add_message("conv2", "user", "Message for conv2")

        messages1 = cache.get_messages("conv1")
        messages2 = cache.get_messages("conv2")

        assert len(messages1) == 1
        assert len(messages2) == 1
        assert messages1[0]["content"] == "Message for conv1"
        assert messages2[0]["content"] == "Message for conv2"


# ============================================================================
# Test get_messages
# ============================================================================


class TestGetMessages:
    """Test suite for get_messages method"""

    def test_get_messages_empty_conversation(self):
        """Test getting messages from non-existent conversation"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        messages = cache.get_messages("nonexistent")

        assert messages == []

    def test_get_messages_with_limit(self):
        """Test getting messages with limit"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        for i in range(30):
            cache.add_message("conv1", "user", f"Message {i}")

        messages = cache.get_messages("conv1", limit=10)
        assert len(messages) == 10
        # Should get the last 10 messages
        assert messages[0]["content"] == "Message 20"
        assert messages[9]["content"] == "Message 29"

    def test_get_messages_default_limit(self):
        """Test default limit is 20"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        for i in range(50):
            cache.add_message("conv1", "user", f"Message {i}")

        messages = cache.get_messages("conv1")
        assert len(messages) == 20


# ============================================================================
# Test extract_and_save_entities
# ============================================================================


class TestExtractAndSaveEntities:
    """Test suite for extract_and_save_entities method"""

    def test_extract_name_italian_mi_chiamo(self):
        """Test extracting name from 'Mi chiamo [Name]'"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "Mi chiamo Marco e voglio aprire un business")

        entities = cache.get_entities("conv1")
        assert entities.get("user_name") == "Marco"

    def test_extract_name_italian_sono(self):
        """Test extracting name from 'Sono [Name]'"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "Sono Giovanni, ho bisogno di aiuto")

        entities = cache.get_entities("conv1")
        assert entities.get("user_name") == "Giovanni"

    def test_extract_name_english_i_am(self):
        """Test extracting name from 'I am [Name]'"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "I am John and I need help with visas")

        entities = cache.get_entities("conv1")
        assert entities.get("user_name") == "John"

    def test_extract_name_english_my_name_is(self):
        """Test extracting name from 'My name is [Name]'"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "My name is Sarah")

        entities = cache.get_entities("conv1")
        assert entities.get("user_name") == "Sarah"

    def test_extract_name_filters_false_positives(self):
        """Test that false positive names are filtered"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        # These should NOT be extracted as names
        cache.extract_and_save_entities("conv1", "Mi chiamo Zantara")
        assert cache.get_entities("conv1").get("user_name") is None

        cache.extract_and_save_entities("conv2", "Sono Bali")
        assert cache.get_entities("conv2").get("user_name") is None

        cache.extract_and_save_entities("conv3", "I am Indonesia")
        assert cache.get_entities("conv3").get("user_name") is None

    def test_extract_city_italian(self):
        """Test extracting Italian cities"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "Vengo da Milano e voglio trasferirmi")

        entities = cache.get_entities("conv1")
        assert entities.get("user_city") == "Milano"

    def test_extract_city_ends_with(self):
        """Test extracting city at end of sentence"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "Vivo a Roma")

        entities = cache.get_entities("conv1")
        assert entities.get("user_city") == "Roma"

    def test_extract_city_international(self):
        """Test extracting international cities"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "I'm from Singapore originally")

        entities = cache.get_entities("conv1")
        assert entities.get("user_city") == "Singapore"

    def test_extract_budget_milioni(self):
        """Test extracting budget with 'milioni'"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "Ho un budget di 50 milioni IDR")

        entities = cache.get_entities("conv1")
        assert "50 milioni" in entities.get("budget", "")

    def test_extract_budget_juta(self):
        """Test extracting budget with 'juta' (Indonesian)"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "Saya punya budget 100 juta")

        entities = cache.get_entities("conv1")
        assert "100 juta" in entities.get("budget", "")

    def test_extract_budget_usd(self):
        """Test extracting budget with USD"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "My budget is 5000 usd")

        entities = cache.get_entities("conv1")
        assert "5000 usd" in entities.get("budget", "")

    def test_extract_budget_euro(self):
        """Test extracting budget with euro"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "I have around 10000 euro")

        entities = cache.get_entities("conv1")
        assert "10000 euro" in entities.get("budget", "")

    def test_extract_budget_thousand(self):
        """Test extracting budget with thousand"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "About 50 thousand dollars")

        entities = cache.get_entities("conv1")
        assert "50 thousand" in entities.get("budget", "")

    def test_extract_multiple_entities(self):
        """Test extracting multiple entities from one message"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities(
            "conv1", "Mi chiamo Paolo, vengo da Roma e ho un budget di 100 mila euro"
        )

        entities = cache.get_entities("conv1")
        assert entities.get("user_name") == "Paolo"
        assert entities.get("user_city") == "Roma"
        assert "100 mila" in entities.get("budget", "")

    def test_no_entities_extracted(self):
        """Test message with no extractable entities"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.extract_and_save_entities("conv1", "What are the visa requirements?")

        entities = cache.get_entities("conv1")
        assert entities == {}


# ============================================================================
# Test get_entities
# ============================================================================


class TestGetEntities:
    """Test suite for get_entities method"""

    def test_get_entities_existing(self):
        """Test getting entities for existing conversation"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Mi chiamo Luigi")

        entities = cache.get_entities("conv1")
        assert "user_name" in entities

    def test_get_entities_nonexistent(self):
        """Test getting entities for non-existent conversation"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        entities = cache.get_entities("nonexistent")

        assert entities == {}


# ============================================================================
# Test _cleanup_old
# ============================================================================


class TestCleanupOld:
    """Test suite for _cleanup_old method"""

    def test_cleanup_removes_expired(self):
        """Test that expired conversations are removed"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache(ttl_minutes=1)

        # Add a message
        cache.add_message("conv1", "user", "Hello")

        # Manually set old timestamp
        cache._timestamps["conv1"] = datetime.now() - timedelta(minutes=10)

        # Add another message to trigger cleanup
        cache.add_message("conv2", "user", "New message")

        # conv1 should be cleaned up
        assert "conv1" not in cache._cache
        assert "conv1" not in cache._timestamps
        assert "conv1" not in cache._entities

    def test_cleanup_keeps_recent(self):
        """Test that recent conversations are kept"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache(ttl_minutes=60)

        cache.add_message("conv1", "user", "Recent message")
        cache.add_message("conv2", "user", "Another recent message")

        # Both should still exist
        assert len(cache.get_messages("conv1")) == 1
        assert len(cache.get_messages("conv2")) == 1


# ============================================================================
# Test get_memory_cache
# ============================================================================


class TestGetMemoryCache:
    """Test suite for get_memory_cache function"""

    def test_get_memory_cache_returns_instance(self):
        """Test get_memory_cache returns an instance"""
        from services.memory_fallback import get_memory_cache

        cache = get_memory_cache()

        assert cache is not None
        from services.memory_fallback import InMemoryConversationCache

        assert isinstance(cache, InMemoryConversationCache)

    def test_get_memory_cache_singleton(self):
        """Test get_memory_cache returns same instance"""
        from services.memory_fallback import get_memory_cache

        cache1 = get_memory_cache()
        cache2 = get_memory_cache()

        assert cache1 is cache2


# ============================================================================
# Test entity extraction via add_message
# ============================================================================


class TestEntityExtractionViaAddMessage:
    """Test that add_message triggers entity extraction for user messages"""

    def test_add_user_message_extracts_entities(self):
        """Test that user messages trigger entity extraction"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.add_message("conv1", "user", "Mi chiamo Roberto")

        entities = cache.get_entities("conv1")
        assert entities.get("user_name") == "Roberto"

    def test_add_assistant_message_no_extraction(self):
        """Test that assistant messages don't trigger entity extraction"""
        from services.memory_fallback import InMemoryConversationCache

        cache = InMemoryConversationCache()
        cache.add_message("conv1", "assistant", "Mi chiamo ZANTARA")

        entities = cache.get_entities("conv1")
        # No entities should be extracted from assistant messages
        assert entities.get("user_name") is None
