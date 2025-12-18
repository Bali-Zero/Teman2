"""
Unit tests for Context Window Manager
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.context_window_manager import ContextWindowManager

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_zantara_client():
    """Mock ZantaraAIClient"""
    client = MagicMock()
    client.generate_text = AsyncMock(return_value="Test summary")
    return client


@pytest.fixture
def context_manager(mock_zantara_client):
    """Create ContextWindowManager with mocked client"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", return_value=mock_zantara_client):
        return ContextWindowManager(max_messages=15, summary_threshold=20), mock_zantara_client


@pytest.fixture
def context_manager_no_ai():
    """Create ContextWindowManager without AI client"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", side_effect=Exception("No AI")):
        return ContextWindowManager()


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_with_ai(mock_zantara_client):
    """Test initialization with AI client"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", return_value=mock_zantara_client):
        manager = ContextWindowManager(max_messages=10, summary_threshold=15)

        assert manager.max_messages == 10
        assert manager.summary_threshold == 15
        assert manager.zantara_client == mock_zantara_client


def test_init_without_ai():
    """Test initialization without AI client"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", side_effect=Exception("No AI")):
        manager = ContextWindowManager()

        assert manager.zantara_client is None


def test_init_defaults():
    """Test initialization with defaults"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", side_effect=Exception("No AI")):
        manager = ContextWindowManager()

        assert manager.max_messages == 10
        assert manager.summary_threshold == 15


# ============================================================================
# Tests for trim_conversation_history
# ============================================================================


def test_trim_conversation_history_empty(context_manager):
    """Test trim_conversation_history with empty history"""
    manager, mock_client = context_manager

    result = manager.trim_conversation_history([])

    assert result["trimmed_messages"] == []
    assert result["needs_summarization"] is False
    assert result["messages_to_summarize"] == []
    assert result["context_summary"] == ""


def test_trim_conversation_history_empty_with_summary(context_manager):
    """Test trim_conversation_history with empty history and existing summary"""
    manager, mock_client = context_manager

    result = manager.trim_conversation_history([], current_summary="Previous summary")

    assert result["context_summary"] == "Previous summary"


def test_trim_conversation_history_short(context_manager):
    """Test trim_conversation_history with short conversation"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]

    result = manager.trim_conversation_history(messages)

    assert len(result["trimmed_messages"]) == 10
    assert result["needs_summarization"] is False
    assert result["messages_to_summarize"] == []


def test_trim_conversation_history_medium(context_manager):
    """Test trim_conversation_history with medium conversation"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": f"Message {i}"} for i in range(18)]

    result = manager.trim_conversation_history(messages)

    assert len(result["trimmed_messages"]) == 15  # max_messages
    assert result["needs_summarization"] is False


def test_trim_conversation_history_long(context_manager):
    """Test trim_conversation_history with long conversation"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": f"Message {i}"} for i in range(30)]

    result = manager.trim_conversation_history(messages)

    assert len(result["trimmed_messages"]) == 15  # max_messages
    assert result["needs_summarization"] is True
    assert len(result["messages_to_summarize"]) == 15  # 30 - 15


def test_trim_conversation_history_exact_threshold(context_manager):
    """Test trim_conversation_history at exact threshold"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"} for _ in range(20)]

    result = manager.trim_conversation_history(messages)

    assert result["needs_summarization"] is False


# ============================================================================
# Tests for build_summarization_prompt
# ============================================================================


def test_build_summarization_prompt(context_manager):
    """Test build_summarization_prompt"""
    manager, mock_client = context_manager
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    prompt = manager.build_summarization_prompt(messages)

    assert "Summarize" in prompt
    assert "Hello" in prompt
    assert "Hi there" in prompt


def test_build_summarization_prompt_truncates_long_messages(context_manager):
    """Test build_summarization_prompt truncates long messages"""
    manager, mock_client = context_manager
    long_content = "x" * 500
    messages = [{"role": "user", "content": long_content}]

    prompt = manager.build_summarization_prompt(messages)

    assert len(prompt) < len(long_content) + 200  # Should be truncated


def test_build_summarization_prompt_missing_fields(context_manager):
    """Test build_summarization_prompt handles missing fields"""
    manager, mock_client = context_manager
    messages = [{"role": "user"}, {}]

    prompt = manager.build_summarization_prompt(messages)

    assert isinstance(prompt, str)


# ============================================================================
# Tests for get_context_status
# ============================================================================


def test_get_context_status_healthy(context_manager):
    """Test get_context_status with healthy status"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"} for _ in range(10)]

    result = manager.get_context_status(messages)

    assert result["status"] == "healthy"
    assert result["color"] == "green"
    assert result["total_messages"] == 10


def test_get_context_status_approaching_limit(context_manager):
    """Test get_context_status with approaching limit"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"} for _ in range(18)]

    result = manager.get_context_status(messages)

    assert result["status"] == "approaching_limit"
    assert result["color"] == "yellow"


def test_get_context_status_needs_summarization(context_manager):
    """Test get_context_status needs summarization"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"} for _ in range(25)]

    result = manager.get_context_status(messages)

    assert result["status"] == "needs_summarization"
    assert result["color"] == "red"


def test_get_context_status_usage_percentage(context_manager):
    """Test get_context_status calculates usage percentage"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"} for _ in range(10)]

    result = manager.get_context_status(messages)

    assert "usage_percentage" in result
    assert result["usage_percentage"] == 50.0  # 10/20 * 100


def test_get_context_status_messages_until_summarization(context_manager):
    """Test get_context_status calculates messages until summarization"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"} for _ in range(15)]

    result = manager.get_context_status(messages)

    assert result["messages_until_summarization"] == 5  # 20 - 15


# ============================================================================
# Tests for inject_summary_into_history
# ============================================================================


def test_inject_summary_into_history_with_summary(context_manager):
    """Test inject_summary_into_history with summary"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"}]

    result = manager.inject_summary_into_history(messages, "Previous summary")

    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert "Previous summary" in result[0]["content"]


def test_inject_summary_into_history_no_summary(context_manager):
    """Test inject_summary_into_history without summary"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"}]

    result = manager.inject_summary_into_history(messages, "")

    assert result == messages


def test_inject_summary_into_history_none_summary(context_manager):
    """Test inject_summary_into_history with None summary"""
    manager, mock_client = context_manager
    messages = [{"role": "user", "content": "test"}]

    result = manager.inject_summary_into_history(messages, None)

    assert result == messages


# ============================================================================
# Tests for generate_summary
# ============================================================================


@pytest.mark.asyncio
async def test_generate_summary_success(context_manager):
    """Test generate_summary successful"""
    manager, mock_client = context_manager
    mock_client.generate_text.return_value = "Generated summary"
    messages = [{"role": "user", "content": "test"}]

    result = await manager.generate_summary(messages)

    assert result == "Generated summary"
    mock_client.generate_text.assert_called_once()


@pytest.mark.asyncio
async def test_generate_summary_with_existing_summary(context_manager):
    """Test generate_summary with existing summary"""
    manager, mock_client = context_manager
    mock_client.generate_text.return_value = "Updated summary"
    messages = [{"role": "user", "content": "test"}]

    result = await manager.generate_summary(messages, existing_summary="Previous summary")

    assert "Previous summary" in str(mock_client.generate_text.call_args)
    assert result == "Updated summary"


@pytest.mark.asyncio
async def test_generate_summary_no_ai(context_manager_no_ai):
    """Test generate_summary without AI client"""
    manager = context_manager_no_ai
    messages = [{"role": "user", "content": "test"}]

    result = await manager.generate_summary(messages)

    assert result == "Earlier conversation covered various topics."


@pytest.mark.asyncio
async def test_generate_summary_no_ai_with_existing(context_manager_no_ai):
    """Test generate_summary without AI client but with existing summary"""
    manager = context_manager_no_ai
    messages = [{"role": "user", "content": "test"}]

    result = await manager.generate_summary(messages, existing_summary="Previous summary")

    assert result == "Previous summary"


@pytest.mark.asyncio
async def test_generate_summary_exception(context_manager):
    """Test generate_summary handles exception"""
    manager, mock_client = context_manager
    mock_client.generate_text.side_effect = Exception("AI error")
    messages = [{"role": "user", "content": "test"}]

    result = await manager.generate_summary(messages)

    assert result == "Previous conversation context (summary generation unavailable)."


@pytest.mark.asyncio
async def test_generate_summary_exception_with_existing(context_manager):
    """Test generate_summary exception with existing summary"""
    manager, mock_client = context_manager
    mock_client.generate_text.side_effect = Exception("AI error")
    messages = [{"role": "user", "content": "test"}]

    result = await manager.generate_summary(messages, existing_summary="Previous summary")

    assert result == "Previous summary"


# ============================================================================
# Tests for format_summary_for_display
# ============================================================================


def test_format_summary_for_display(context_manager):
    """Test format_summary_for_display"""
    manager, mock_client = context_manager
    stats = {"total_messages": 30, "messages_in_context": 15}

    result = manager.format_summary_for_display("Test summary", stats)

    assert result["summary"] == "Test summary"
    assert result["stats"]["total_messages"] == 30
    assert result["stats"]["messages_in_context"] == 15
    assert result["stats"]["summary_active"] is True
    assert "timestamp" in result


def test_format_summary_for_display_empty_summary(context_manager):
    """Test format_summary_for_display with empty summary"""
    manager, mock_client = context_manager
    stats = {"total_messages": 10}

    result = manager.format_summary_for_display("", stats)

    assert result["stats"]["summary_active"] is False


def test_format_summary_for_display_missing_stats(context_manager):
    """Test format_summary_for_display with missing stats"""
    manager, mock_client = context_manager

    result = manager.format_summary_for_display("Test summary", {})

    assert result["stats"]["total_messages"] == 0
    assert result["stats"]["messages_in_context"] == 0
