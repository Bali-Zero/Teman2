"""
Comprehensive tests for AICRMExtractor
Target: >95% coverage
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.crm.ai_crm_extractor import AICRMExtractor, get_extractor


@pytest.fixture
def mock_ai_client():
    """Mock AI client"""
    client = AsyncMock()
    client.conversational = AsyncMock(
        return_value={
            "text": json.dumps(
                {
                    "client": {
                        "full_name": "John Doe",
                        "email": "john@example.com",
                        "phone": "+1234567890",
                        "whatsapp": "+1234567890",
                        "nationality": "US",
                        "confidence": 0.9,
                    },
                    "practice_intent": {
                        "detected": True,
                        "practice_type_code": "KITAS",
                        "confidence": 0.8,
                        "details": "Work permit application",
                    },
                    "sentiment": "positive",
                    "urgency": "normal",
                    "summary": "Client interested in KITAS",
                    "action_items": ["Submit documents", "Schedule appointment"],
                    "topics_discussed": ["visa", "work permit"],
                    "extracted_entities": {
                        "dates": ["2025-01-01"],
                        "amounts": ["$1000"],
                        "locations": ["Bali"],
                        "documents_mentioned": ["passport"],
                    },
                }
            )
        }
    )
    return client


@pytest.fixture
def extractor(mock_ai_client):
    """Create AICRMExtractor instance"""
    return AICRMExtractor(ai_client=mock_ai_client)


class TestAICRMExtractor:
    """Tests for AICRMExtractor"""

    def test_init_with_client(self, mock_ai_client):
        """Test initialization with provided client"""
        extractor = AICRMExtractor(ai_client=mock_ai_client)
        assert extractor.client == mock_ai_client

    def test_init_without_client(self):
        """Test initialization without client (uses ZantaraAIClient)"""
        with patch("services.crm.ai_crm_extractor.ZantaraAIClient") as mock_zantara:
            mock_client = MagicMock()
            mock_zantara.return_value = mock_client

            extractor = AICRMExtractor()
            assert extractor.client == mock_client

    def test_init_error(self):
        """Test initialization error handling"""
        with (
            patch(
                "services.crm.ai_crm_extractor.ZantaraAIClient", side_effect=Exception("Init error")
            ),
            pytest.raises(Exception),
        ):
            AICRMExtractor()

    @pytest.mark.asyncio
    async def test_extract_from_conversation_success(self, extractor, mock_ai_client):
        """Test successful extraction from conversation"""
        messages = [
            {"role": "user", "content": "I need a KITAS"},
            {"role": "assistant", "content": "I can help with that"},
        ]

        result = await extractor.extract_from_conversation(messages)

        assert result["client"]["full_name"] == "John Doe"
        assert result["client"]["email"] == "john@example.com"
        assert result["practice_intent"]["detected"] is True
        assert result["practice_intent"]["practice_type_code"] == "KITAS"
        assert result["sentiment"] == "positive"
        assert len(result["action_items"]) == 2

    @pytest.mark.asyncio
    async def test_extract_from_conversation_with_existing_client(self, extractor, mock_ai_client):
        """Test extraction with existing client data"""
        messages = [{"role": "user", "content": "Update my info"}]
        existing_client = {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
        }

        result = await extractor.extract_from_conversation(
            messages,
            existing_client_data=existing_client,
        )

        assert result["client"]["full_name"] == "John Doe"
        mock_ai_client.conversational.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_from_conversation_json_error(self, extractor, mock_ai_client):
        """Test handling JSON decode error"""
        mock_ai_client.conversational = AsyncMock(return_value={"text": "Invalid JSON response"})

        messages = [{"role": "user", "content": "Test"}]
        result = await extractor.extract_from_conversation(messages)

        assert result["client"]["confidence"] == 0.0
        assert result["practice_intent"]["detected"] is False

    @pytest.mark.asyncio
    async def test_extract_from_conversation_markdown_wrapped(self, extractor, mock_ai_client):
        """Test extraction with markdown code blocks"""
        mock_ai_client.conversational = AsyncMock(
            return_value={
                "text": "```json\n"
                + json.dumps(
                    {
                        "client": {"full_name": "Test", "confidence": 0.5},
                        "practice_intent": {"detected": False},
                    }
                )
                + "\n```"
            }
        )

        messages = [{"role": "user", "content": "Test"}]
        result = await extractor.extract_from_conversation(messages)

        assert result["client"]["full_name"] == "Test"

    @pytest.mark.asyncio
    async def test_extract_from_conversation_general_error(self, extractor, mock_ai_client):
        """Test handling general extraction error"""
        mock_ai_client.conversational = AsyncMock(side_effect=Exception("AI error"))

        messages = [{"role": "user", "content": "Test"}]
        result = await extractor.extract_from_conversation(messages)

        assert result["client"]["confidence"] == 0.0
        assert result["practice_intent"]["detected"] is False

    def test_get_empty_extraction(self, extractor):
        """Test empty extraction structure"""
        result = extractor._get_empty_extraction()

        assert result["client"]["confidence"] == 0.0
        assert result["practice_intent"]["detected"] is False
        assert result["sentiment"] == "neutral"
        assert result["urgency"] == "normal"
        assert result["summary"] == ""
        assert result["action_items"] == []
        assert result["topics_discussed"] == []

    @pytest.mark.asyncio
    async def test_enrich_client_data_no_existing(self, extractor):
        """Test enriching client data without existing client"""
        extracted = {
            "client": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "confidence": 0.9,
            }
        }

        result = await extractor.enrich_client_data(extracted, existing_client=None)

        assert result == extracted["client"]

    @pytest.mark.asyncio
    async def test_enrich_client_data_low_confidence(self, extractor):
        """Test enriching with low confidence (should not update)"""
        extracted = {
            "client": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "confidence": 0.5,  # Below 0.6 threshold
            }
        }
        existing = {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
        }

        result = await extractor.enrich_client_data(extracted, existing_client=existing)

        assert result["full_name"] == "Jane Doe"
        assert result["email"] == "jane@example.com"

    @pytest.mark.asyncio
    async def test_enrich_client_data_high_confidence(self, extractor):
        """Test enriching with high confidence (should update)"""
        extracted = {
            "client": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "confidence": 0.8,  # Above 0.6 threshold
            }
        }
        existing = {
            "full_name": "Jane Doe",
            "email": None,  # Missing email
        }

        result = await extractor.enrich_client_data(extracted, existing_client=existing)

        assert result["full_name"] == "Jane Doe"  # Existing value kept
        assert result["email"] == "john@example.com"  # Extracted value fills gap

    @pytest.mark.asyncio
    async def test_enrich_client_data_partial_update(self, extractor):
        """Test partial update of client data"""
        extracted = {
            "client": {
                "full_name": None,
                "email": "john@example.com",
                "phone": "+1234567890",
                "confidence": 0.9,
            }
        }
        existing = {
            "full_name": "Jane Doe",
            "email": None,
        }

        result = await extractor.enrich_client_data(extracted, existing_client=existing)

        assert result["full_name"] == "Jane Doe"
        assert result["email"] == "john@example.com"
        assert result["phone"] == "+1234567890"

    @pytest.mark.asyncio
    async def test_should_create_practice_true(self, extractor):
        """Test should_create_practice returns True"""
        extracted = {
            "practice_intent": {
                "detected": True,
                "practice_type_code": "KITAS",
                "confidence": 0.8,
            }
        }

        result = await extractor.should_create_practice(extracted)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_create_practice_false_not_detected(self, extractor):
        """Test should_create_practice returns False when not detected"""
        extracted = {
            "practice_intent": {
                "detected": False,
                "practice_type_code": "KITAS",
                "confidence": 0.8,
            }
        }

        result = await extractor.should_create_practice(extracted)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_create_practice_false_low_confidence(self, extractor):
        """Test should_create_practice returns False with low confidence"""
        extracted = {
            "practice_intent": {
                "detected": True,
                "practice_type_code": "KITAS",
                "confidence": 0.5,  # Below 0.7 threshold
            }
        }

        result = await extractor.should_create_practice(extracted)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_create_practice_false_no_code(self, extractor):
        """Test should_create_practice returns False without practice type code"""
        extracted = {
            "practice_intent": {
                "detected": True,
                "practice_type_code": None,
                "confidence": 0.8,
            }
        }

        result = await extractor.should_create_practice(extracted)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_create_practice_missing_practice_intent(self, extractor):
        """Test should_create_practice with missing practice_intent"""
        extracted = {}

        result = await extractor.should_create_practice(extracted)

        assert result is False


class TestGetExtractor:
    """Tests for get_extractor singleton function"""

    def test_get_extractor_first_call(self):
        """Test first call creates instance"""
        # Reset singleton
        import services.crm.ai_crm_extractor as module

        module._extractor_instance = None

        with patch("services.crm.ai_crm_extractor.AICRMExtractor") as mock_extractor_class:
            mock_instance = MagicMock()
            mock_extractor_class.return_value = mock_instance

            result = get_extractor()

            assert result == mock_instance
            assert module._extractor_instance == mock_instance

    def test_get_extractor_subsequent_calls(self):
        """Test subsequent calls return same instance"""
        import services.crm.ai_crm_extractor as module

        mock_instance = MagicMock()
        module._extractor_instance = mock_instance

        result = get_extractor()

        assert result == mock_instance

    def test_get_extractor_with_client(self):
        """Test get_extractor with provided client"""
        import services.crm.ai_crm_extractor as module

        module._extractor_instance = None

        mock_client = MagicMock()

        with patch("services.crm.ai_crm_extractor.AICRMExtractor") as mock_extractor_class:
            mock_instance = MagicMock()
            mock_extractor_class.return_value = mock_instance

            result = get_extractor(ai_client=mock_client)

            mock_extractor_class.assert_called_once_with(ai_client=mock_client)
            assert result == mock_instance

    def test_get_extractor_init_error(self):
        """Test get_extractor handles initialization error"""
        import services.crm.ai_crm_extractor as module

        module._extractor_instance = None

        with (
            patch(
                "services.crm.ai_crm_extractor.AICRMExtractor", side_effect=Exception("Init error")
            ),
            pytest.raises(Exception),
        ):
            get_extractor()

