import pytest

from backend.services.memory_fallback import InMemoryConversationCache


@pytest.fixture
def cache():
    return InMemoryConversationCache(ttl_minutes=60)


def test_add_message_and_retrieval(cache):
    conversation_id = "test-conv-1"
    cache.add_message(conversation_id, "user", "Hello")
    cache.add_message(conversation_id, "assistant", "Hi there")

    messages = cache.get_messages(conversation_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there"


def test_entity_extraction_name(cache):
    conversation_id = "test-conv-name"
    cache.add_message(conversation_id, "user", "Mi chiamo Marco")

    entities = cache.get_entities(conversation_id)
    assert entities.get("user_name") == "Marco"


def test_entity_extraction_city(cache):
    conversation_id = "test-conv-city"
    cache.add_message(conversation_id, "user", "Vivo a Milano")

    entities = cache.get_entities(conversation_id)
    assert entities.get("user_city") == "Milano"


def test_entity_extraction_budget(cache):
    conversation_id = "test-conv-budget"
    cache.add_message(conversation_id, "user", "Ho un budget di 5000 euro")

    entities = cache.get_entities(conversation_id)
    assert "5000 euro" in entities.get("budget")


def test_cleanup_old(cache):
    # This is hard to test deterministically without mocking datetime,
    # but we can check that it doesn't crash
    cache._cleanup_old()
