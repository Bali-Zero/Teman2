"""
Tests for memory_fallback.py - In-memory conversation cache fallback.
"""

import pytest

from backend.services.memory.memory_fallback import InMemoryConversationCache


@pytest.fixture
def cache():
    """Create a fresh cache instance (bypass singleton)."""
    instance = object.__new__(InMemoryConversationCache)
    instance._initialized = False
    instance.__init__(ttl_minutes=60)
    return instance


class TestAddAndGetMessages:
    """Tests for add_message and get_messages methods."""

    def test_add_and_retrieve_message(self, cache):
        cache.add_message("conv_1", "user", "Hello!")
        messages = cache.get_messages("conv_1")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"
        assert "timestamp" in messages[0]

    def test_multiple_messages_ordered(self, cache):
        cache.add_message("conv_1", "user", "First")
        cache.add_message("conv_1", "assistant", "Second")
        cache.add_message("conv_1", "user", "Third")
        messages = cache.get_messages("conv_1")
        assert len(messages) == 3
        assert messages[0]["content"] == "First"
        assert messages[2]["content"] == "Third"

    def test_get_messages_limit(self, cache):
        for i in range(30):
            cache.add_message("conv_1", "user", f"Message {i}")
        messages = cache.get_messages("conv_1", limit=5)
        assert len(messages) == 5
        # Should return the last 5
        assert messages[0]["content"] == "Message 25"

    def test_get_messages_empty_conversation(self, cache):
        messages = cache.get_messages("nonexistent")
        assert messages == []

    def test_separate_conversations(self, cache):
        cache.add_message("conv_1", "user", "Hello conv 1")
        cache.add_message("conv_2", "user", "Hello conv 2")
        assert len(cache.get_messages("conv_1")) == 1
        assert len(cache.get_messages("conv_2")) == 1


class TestEntityExtraction:
    """Tests for extract_and_save_entities method."""

    def test_name_extraction_italian(self, cache):
        cache.add_message("conv_1", "user", "Mi chiamo Marco e sono italiano")
        entities = cache.get_entities("conv_1")
        assert entities.get("user_name") == "Marco"

    def test_name_extraction_english(self, cache):
        cache.add_message("conv_1", "user", "My name is John and I am from London")
        entities = cache.get_entities("conv_1")
        assert entities.get("user_name") == "John"

    def test_city_extraction(self, cache):
        cache.add_message("conv_1", "user", "I live in bali and work remotely")
        entities = cache.get_entities("conv_1")
        assert entities.get("user_city") == "Bali"

    def test_budget_extraction(self, cache):
        cache.add_message("conv_1", "user", "My budget is 50 milioni for the company setup")
        entities = cache.get_entities("conv_1")
        assert "budget" in entities
        assert "50 milioni" in entities["budget"]

    def test_budget_usd(self, cache):
        cache.add_message("conv_1", "user", "I have about 2000 usd for the visa")
        entities = cache.get_entities("conv_1")
        assert "budget" in entities

    def test_false_positive_names_filtered(self, cache):
        cache.add_message("conv_1", "user", "Sono Zantara, il tuo assistente")
        entities = cache.get_entities("conv_1")
        # "Zantara" should be filtered out as false positive
        assert entities.get("user_name") != "Zantara"

    def test_no_entities_for_generic_message(self, cache):
        cache.add_message("conv_1", "user", "what is the weather today?")
        entities = cache.get_entities("conv_1")
        assert len(entities) == 0

    def test_entities_accumulated(self, cache):
        cache.add_message("conv_1", "user", "Mi chiamo Marco")
        cache.add_message("conv_1", "user", "Vivo a Milano")
        entities = cache.get_entities("conv_1")
        assert entities.get("user_name") == "Marco"
        assert entities.get("user_city") == "Milano"

    def test_get_entities_empty_conversation(self, cache):
        entities = cache.get_entities("nonexistent")
        assert entities == {}


class TestCleanup:
    """Tests for _cleanup_old method."""

    def test_cleanup_removes_expired(self, cache):
        from datetime import datetime, timedelta, timezone

        cache.add_message("conv_1", "user", "Hello")
        # Manually expire the conversation
        cache._timestamps["conv_1"] = datetime.now(tz=timezone.utc) - timedelta(hours=2)
        cache._cleanup_old()
        assert "conv_1" not in cache._cache
        assert "conv_1" not in cache._timestamps

    def test_cleanup_keeps_fresh(self, cache):
        cache.add_message("conv_1", "user", "Hello")
        cache._cleanup_old()
        assert "conv_1" in cache._cache


class TestAssistantMessagesNoEntityExtraction:
    """Verify entity extraction only triggers for user messages."""

    def test_assistant_message_no_entities(self, cache):
        cache.add_message("conv_1", "assistant", "Mi chiamo Zantara, sono Marco")
        entities = cache.get_entities("conv_1")
        # extract_and_save_entities only called for role == "user"
        assert entities.get("user_name") is None
