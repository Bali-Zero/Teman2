"""
Unit tests for AI CRM Extractor Service
100% coverage target with comprehensive mocking
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.ai_crm_extractor import AICRMExtractor, get_extractor

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_ai_client():
    """Mock ZantaraAIClient"""
    client = AsyncMock()
    client.conversational = AsyncMock()
    return client


@pytest.fixture
def extractor(mock_ai_client):
    """Create AICRMExtractor instance"""
    return AICRMExtractor(ai_client=mock_ai_client)


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_with_client(mock_ai_client):
    """Test initialization with AI client"""
    extractor = AICRMExtractor(ai_client=mock_ai_client)

    assert extractor.client == mock_ai_client


def test_init_without_client():
    """Test initialization without AI client"""
    with patch("services.ai_crm_extractor.ZantaraAIClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        extractor = AICRMExtractor()

        assert extractor.client == mock_client


def test_init_exception():
    """Test initialization with exception"""
    with patch("services.ai_crm_extractor.ZantaraAIClient", side_effect=Exception("Init error")):
        with pytest.raises(Exception):
            AICRMExtractor()


# ============================================================================
# Tests for extract_from_conversation
# ============================================================================


@pytest.mark.asyncio
async def test_extract_from_conversation_success(extractor, mock_ai_client):
    """Test extract_from_conversation successful"""
    messages = [
        {"role": "user", "content": "Hi, I'm John Doe, email john@example.com"},
        {"role": "assistant", "content": "Hello John!"},
    ]

    mock_response = {
        "text": json.dumps(
            {
                "client": {
                    "full_name": "John Doe",
                    "email": "john@example.com",
                    "phone": None,
                    "whatsapp": None,
                    "nationality": None,
                    "confidence": 0.9,
                },
                "practice_intent": {
                    "detected": True,
                    "practice_type_code": "KITAS",
                    "confidence": 0.8,
                    "details": "Wants KITAS",
                },
                "sentiment": "positive",
                "urgency": "normal",
                "summary": "Client wants KITAS",
                "action_items": ["Follow up"],
                "topics_discussed": ["KITAS"],
                "extracted_entities": {
                    "dates": [],
                    "amounts": [],
                    "locations": [],
                    "documents_mentioned": [],
                },
            }
        )
    }
    mock_ai_client.conversational.return_value = mock_response

    result = await extractor.extract_from_conversation(messages)

    assert result["client"]["full_name"] == "John Doe"
    assert result["client"]["email"] == "john@example.com"
    assert result["practice_intent"]["detected"] is True
    mock_ai_client.conversational.assert_called_once()


@pytest.mark.asyncio
async def test_extract_from_conversation_with_existing_data(extractor, mock_ai_client):
    """Test extract_from_conversation with existing client data"""
    messages = [{"role": "user", "content": "Hello"}]
    existing_data = {"email": "existing@example.com", "phone": "+1234567890"}

    mock_response = {
        "text": json.dumps(
            {
                "client": {
                    "full_name": "John Doe",
                    "email": "john@example.com",
                    "phone": None,
                    "whatsapp": None,
                    "nationality": None,
                    "confidence": 0.9,
                },
                "practice_intent": {
                    "detected": False,
                    "practice_type_code": None,
                    "confidence": 0.0,
                    "details": "",
                },
                "sentiment": "neutral",
                "urgency": "normal",
                "summary": "",
                "action_items": [],
                "topics_discussed": [],
                "extracted_entities": {
                    "dates": [],
                    "amounts": [],
                    "locations": [],
                    "documents_mentioned": [],
                },
            }
        )
    }
    mock_ai_client.conversational.return_value = mock_response

    result = await extractor.extract_from_conversation(messages, existing_client_data=existing_data)

    assert result is not None
    # Should include existing data in prompt
    mock_ai_client.conversational.assert_called_once()


@pytest.mark.asyncio
async def test_extract_from_conversation_markdown_code_block(extractor, mock_ai_client):
    """Test extract_from_conversation with markdown code block"""
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = {
        "text": "```json\n"
        + json.dumps(
            {
                "client": {
                    "full_name": None,
                    "email": None,
                    "phone": None,
                    "whatsapp": None,
                    "nationality": None,
                    "confidence": 0.0,
                },
                "practice_intent": {
                    "detected": False,
                    "practice_type_code": None,
                    "confidence": 0.0,
                    "details": "",
                },
                "sentiment": "neutral",
                "urgency": "normal",
                "summary": "",
                "action_items": [],
                "topics_discussed": [],
                "extracted_entities": {
                    "dates": [],
                    "amounts": [],
                    "locations": [],
                    "documents_mentioned": [],
                },
            }
        )
        + "\n```"
    }
    mock_ai_client.conversational.return_value = mock_response

    result = await extractor.extract_from_conversation(messages)

    assert result is not None
    assert result["client"]["confidence"] == 0.0


@pytest.mark.asyncio
async def test_extract_from_conversation_json_error(extractor, mock_ai_client):
    """Test extract_from_conversation with JSON decode error"""
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = {"text": "Invalid JSON"}
    mock_ai_client.conversational.return_value = mock_response

    result = await extractor.extract_from_conversation(messages)

    # Should return empty extraction
    assert result["client"]["confidence"] == 0.0
    assert result["practice_intent"]["detected"] is False


@pytest.mark.asyncio
async def test_extract_from_conversation_exception(extractor, mock_ai_client):
    """Test extract_from_conversation with exception"""
    messages = [{"role": "user", "content": "Hello"}]
    mock_ai_client.conversational.side_effect = Exception("AI error")

    result = await extractor.extract_from_conversation(messages)

    # Should return empty extraction
    assert result["client"]["confidence"] == 0.0


# ============================================================================
# Tests for _get_empty_extraction
# ============================================================================


def test_get_empty_extraction(extractor):
    """Test _get_empty_extraction"""
    result = extractor._get_empty_extraction()

    assert result["client"]["confidence"] == 0.0
    assert result["practice_intent"]["detected"] is False
    assert result["sentiment"] == "neutral"
    assert result["urgency"] == "normal"
    assert isinstance(result["action_items"], list)
    assert isinstance(result["topics_discussed"], list)


# ============================================================================
# Tests for enrich_client_data
# ============================================================================


@pytest.mark.asyncio
async def test_enrich_client_data_no_existing(extractor):
    """Test enrich_client_data without existing client"""
    extracted = {
        "client": {
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": None,
            "whatsapp": None,
            "nationality": "US",
            "confidence": 0.9,
        }
    }

    result = await extractor.enrich_client_data(extracted)

    assert result == extracted["client"]


@pytest.mark.asyncio
async def test_enrich_client_data_with_existing(extractor):
    """Test enrich_client_data with existing client"""
    extracted = {
        "client": {
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": None,
            "whatsapp": None,
            "nationality": "US",
            "confidence": 0.9,
        }
    }
    existing = {"email": "existing@example.com", "phone": "+1234567890"}

    result = await extractor.enrich_client_data(extracted, existing_client=existing)

    # Should merge data
    assert result["email"] == "existing@example.com"  # Existing takes precedence if present
    assert result["phone"] == "+1234567890"


@pytest.mark.asyncio
async def test_enrich_client_data_low_confidence(extractor):
    """Test enrich_client_data with low confidence"""
    extracted = {
        "client": {
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": None,
            "whatsapp": None,
            "nationality": None,
            "confidence": 0.5,  # Below threshold
        }
    }
    existing = {"email": "existing@example.com"}

    result = await extractor.enrich_client_data(extracted, existing_client=existing)

    # Should not update with low confidence
    assert result["email"] == "existing@example.com"


# ============================================================================
# Tests for should_create_practice
# ============================================================================


@pytest.mark.asyncio
async def test_should_create_practice_true(extractor):
    """Test should_create_practice returns True"""
    extracted = {
        "practice_intent": {
            "detected": True,
            "practice_type_code": "KITAS",
            "confidence": 0.8,
            "details": "Wants KITAS",
        }
    }

    result = await extractor.should_create_practice(extracted)

    assert result is True


@pytest.mark.asyncio
async def test_should_create_practice_false_not_detected(extractor):
    """Test should_create_practice returns False when not detected"""
    extracted = {
        "practice_intent": {
            "detected": False,
            "practice_type_code": None,
            "confidence": 0.0,
            "details": "",
        }
    }

    result = await extractor.should_create_practice(extracted)

    assert result is False


@pytest.mark.asyncio
async def test_should_create_practice_false_low_confidence(extractor):
    """Test should_create_practice returns False with low confidence"""
    extracted = {
        "practice_intent": {
            "detected": True,
            "practice_type_code": "KITAS",
            "confidence": 0.6,  # Below threshold
            "details": "Wants KITAS",
        }
    }

    result = await extractor.should_create_practice(extracted)

    assert result is False


@pytest.mark.asyncio
async def test_should_create_practice_false_no_code(extractor):
    """Test should_create_practice returns False without practice type code"""
    extracted = {
        "practice_intent": {
            "detected": True,
            "practice_type_code": None,
            "confidence": 0.8,
            "details": "Wants something",
        }
    }

    result = await extractor.should_create_practice(extracted)

    assert result is False


# ============================================================================
# Tests for get_extractor
# ============================================================================


def test_get_extractor_singleton(mock_ai_client):
    """Test get_extractor returns singleton"""
    with patch("services.ai_crm_extractor._extractor_instance", None):
        extractor1 = get_extractor(ai_client=mock_ai_client)
        extractor2 = get_extractor(ai_client=mock_ai_client)

        assert extractor1 == extractor2


def test_get_extractor_exception():
    """Test get_extractor with exception"""
    with patch("services.ai_crm_extractor._extractor_instance", None):
        with patch("services.ai_crm_extractor.AICRMExtractor", side_effect=Exception("Init error")):
            with pytest.raises(Exception):
                get_extractor()
