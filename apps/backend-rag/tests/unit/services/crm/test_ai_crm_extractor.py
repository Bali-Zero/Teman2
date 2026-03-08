"""
Unit tests for AI CRM Extractor Service
Tests for AsyncpgJSONEncoder UUID/datetime serialization fix
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.crm.ai_crm_extractor import (
    AICRMExtractor,
    AsyncpgJSONEncoder,
    get_extractor,
)

# ============================================================================
# Tests for AsyncpgJSONEncoder (UUID serialization fix)
# ============================================================================


class TestAsyncpgJSONEncoder:
    """Tests for the custom JSON encoder that handles asyncpg types"""

    def test_encode_uuid(self):
        """Test that UUID objects are serialized to strings"""
        test_uuid = UUID("12345678-1234-5678-1234-567812345678")
        data = {"id": test_uuid}

        result = json.dumps(data, cls=AsyncpgJSONEncoder)

        assert '"12345678-1234-5678-1234-567812345678"' in result
        # Verify it's valid JSON that can be decoded
        decoded = json.loads(result)
        assert decoded["id"] == "12345678-1234-5678-1234-567812345678"

    def test_encode_datetime(self):
        """Test that datetime objects are serialized to ISO format"""
        test_dt = datetime(2026, 1, 14, 12, 30, 45)
        data = {"created_at": test_dt}

        result = json.dumps(data, cls=AsyncpgJSONEncoder)

        assert "2026-01-14T12:30:45" in result
        decoded = json.loads(result)
        assert decoded["created_at"] == "2026-01-14T12:30:45"

    def test_encode_date(self):
        """Test that date objects are serialized to ISO format"""
        test_date = date(2026, 1, 14)
        data = {"birth_date": test_date}

        result = json.dumps(data, cls=AsyncpgJSONEncoder)

        assert "2026-01-14" in result
        decoded = json.loads(result)
        assert decoded["birth_date"] == "2026-01-14"

    def test_encode_nested_uuids(self):
        """Test that nested UUID objects in complex structures are serialized"""
        client_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        practice_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        data = {
            "client": {
                "id": client_id,
                "practices": [{"id": practice_id, "name": "PT PMA"}],
            }
        }

        result = json.dumps(data, cls=AsyncpgJSONEncoder)
        decoded = json.loads(result)

        assert decoded["client"]["id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert decoded["client"]["practices"][0]["id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def test_encode_mixed_types(self):
        """Test encoding of mixed types (UUID, datetime, date, strings, numbers)"""
        data = {
            "id": UUID("12345678-1234-5678-1234-567812345678"),
            "created_at": datetime(2026, 1, 14, 12, 30, 45),
            "birth_date": date(1990, 5, 15),
            "name": "Test Client",
            "age": 35,
            "is_active": True,
            "notes": None,
        }

        result = json.dumps(data, cls=AsyncpgJSONEncoder)
        decoded = json.loads(result)

        assert decoded["id"] == "12345678-1234-5678-1234-567812345678"
        assert decoded["created_at"] == "2026-01-14T12:30:45"
        assert decoded["birth_date"] == "1990-05-15"
        assert decoded["name"] == "Test Client"
        assert decoded["age"] == 35
        assert decoded["is_active"] is True
        assert decoded["notes"] is None

    def test_encode_list_of_uuids(self):
        """Test encoding a list of UUIDs"""
        uuids = [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
            UUID("33333333-3333-3333-3333-333333333333"),
        ]
        data = {"user_ids": uuids}

        result = json.dumps(data, cls=AsyncpgJSONEncoder)
        decoded = json.loads(result)

        assert len(decoded["user_ids"]) == 3
        assert decoded["user_ids"][0] == "11111111-1111-1111-1111-111111111111"

    def test_encode_unsupported_type_raises_error(self):
        """Test that unsupported types raise TypeError"""

        class CustomObject:
            pass

        data = {"custom": CustomObject()}

        with pytest.raises(TypeError):
            json.dumps(data, cls=AsyncpgJSONEncoder)


# ============================================================================
# Tests for AICRMExtractor
# ============================================================================


@pytest.fixture
def mock_ai_client():
    """Mock ZANTARA AI client"""
    mock = MagicMock()
    mock.conversational = AsyncMock()
    return mock


@pytest.fixture
def extractor(mock_ai_client):
    """Create extractor with mocked AI client"""
    with patch(
        "backend.services.crm.ai_crm_extractor.ZantaraAIClient", return_value=mock_ai_client
    ):
        return AICRMExtractor(ai_client=mock_ai_client)


class TestAICRMExtractor:
    """Tests for the AI CRM Extractor"""

    @pytest.mark.asyncio
    async def test_extract_from_conversation_success(self, extractor, mock_ai_client):
        """Test successful extraction from conversation"""
        mock_ai_client.conversational.return_value = {
            "text": json.dumps(
                {
                    "client": {
                        "full_name": "John Doe",
                        "email": "john@example.com",
                        "phone": "+62812345678",
                        "whatsapp": "+62812345678",
                        "nationality": "Australian",
                        "confidence": 0.85,
                    },
                    "practice_intent": {
                        "detected": True,
                        "practice_type_code": "PT_PMA",
                        "confidence": 0.9,
                        "details": "Setting up PT PMA",
                    },
                    "sentiment": "positive",
                    "urgency": "normal",
                    "summary": "Client interested in PT PMA setup",
                    "action_items": ["Send quote", "Schedule call"],
                    "topics_discussed": ["PT PMA", "KBLI codes"],
                    "extracted_entities": {
                        "dates": [],
                        "amounts": ["USD 50,000"],
                        "locations": ["Bali"],
                        "documents_mentioned": ["KTP", "Passport"],
                    },
                }
            )
        }

        messages = [
            {"role": "user", "content": "Hi, I want to set up a PT PMA in Bali"},
            {"role": "assistant", "content": "Sure, I can help with that."},
        ]

        result = await extractor.extract_from_conversation(messages)

        assert result["client"]["full_name"] == "John Doe"
        assert result["client"]["confidence"] == 0.85
        assert result["practice_intent"]["detected"] is True
        assert result["practice_intent"]["practice_type_code"] == "PT_PMA"

    @pytest.mark.asyncio
    async def test_extract_from_conversation_with_existing_client_uuid(
        self, extractor, mock_ai_client
    ):
        """Test extraction with existing client data containing UUID (the fix)"""
        mock_ai_client.conversational.return_value = {
            "text": json.dumps(
                {
                    "client": {
                        "full_name": "John Doe",
                        "email": "john@example.com",
                        "phone": None,
                        "whatsapp": None,
                        "nationality": None,
                        "confidence": 0.7,
                    },
                    "practice_intent": {"detected": False},
                    "sentiment": "neutral",
                    "urgency": "normal",
                    "summary": "General inquiry",
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

        messages = [{"role": "user", "content": "Hello"}]

        # Existing client data with UUID (as returned by asyncpg)
        existing_client = {
            "id": UUID("12345678-1234-5678-1234-567812345678"),
            "full_name": "John Doe",
            "email": "john@example.com",
            "created_at": datetime(2026, 1, 1, 10, 0, 0),
        }

        # This should NOT raise TypeError anymore after the fix
        result = await extractor.extract_from_conversation(
            messages, existing_client_data=existing_client
        )

        assert result["client"]["full_name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_extract_from_conversation_handles_markdown_json(self, extractor, mock_ai_client):
        """Test extraction handles JSON wrapped in markdown code blocks"""
        mock_ai_client.conversational.return_value = {
            "text": '```json\n{"client": {"confidence": 0.5}, "practice_intent": {"detected": false}, "sentiment": "neutral", "urgency": "normal", "summary": "", "action_items": [], "topics_discussed": [], "extracted_entities": {"dates": [], "amounts": [], "locations": [], "documents_mentioned": []}}\n```'
        }

        result = await extractor.extract_from_conversation([{"role": "user", "content": "Test"}])

        assert result["client"]["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_extract_from_conversation_json_error_returns_empty(
        self, extractor, mock_ai_client
    ):
        """Test extraction returns empty structure on JSON parse error"""
        mock_ai_client.conversational.return_value = {"text": "This is not valid JSON"}

        result = await extractor.extract_from_conversation([{"role": "user", "content": "Test"}])

        # Should return empty structure
        assert result["client"]["confidence"] == 0.0
        assert result["client"]["full_name"] is None
        assert result["practice_intent"]["detected"] is False

    @pytest.mark.asyncio
    async def test_extract_from_conversation_exception_returns_empty(
        self, extractor, mock_ai_client
    ):
        """Test extraction returns empty structure on exception"""
        mock_ai_client.conversational.side_effect = Exception("API error")

        result = await extractor.extract_from_conversation([{"role": "user", "content": "Test"}])

        assert result["client"]["confidence"] == 0.0

    def test_get_empty_extraction(self, extractor):
        """Test _get_empty_extraction returns correct structure"""
        result = extractor._get_empty_extraction()

        assert result["client"]["full_name"] is None
        assert result["client"]["email"] is None
        assert result["client"]["confidence"] == 0.0
        assert result["practice_intent"]["detected"] is False
        assert result["sentiment"] == "neutral"
        assert result["urgency"] == "normal"
        assert result["summary"] == ""
        assert result["action_items"] == []
        assert result["topics_discussed"] == []
        assert "dates" in result["extracted_entities"]

    @pytest.mark.asyncio
    async def test_enrich_client_data_no_existing(self, extractor):
        """Test enrich_client_data with no existing client"""
        extracted = {
            "client": {
                "full_name": "New User",
                "email": "new@example.com",
                "phone": None,
                "whatsapp": None,
                "nationality": None,
                "confidence": 0.8,
            }
        }

        result = await extractor.enrich_client_data(extracted)

        assert result["full_name"] == "New User"
        assert result["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_enrich_client_data_merges_with_existing(self, extractor):
        """Test enrich_client_data merges extracted with existing data"""
        extracted = {
            "client": {
                "full_name": None,
                "email": "test@example.com",
                "phone": "+62812345678",
                "whatsapp": None,
                "nationality": "Indonesian",
                "confidence": 0.8,
            }
        }

        existing = {
            "full_name": "Existing Name",
            "email": "test@example.com",
            "phone": None,
            "nationality": None,
        }

        result = await extractor.enrich_client_data(extracted, existing)

        # Existing non-null values should be kept
        assert result["full_name"] == "Existing Name"
        # New values should be added where existing is null
        assert result["phone"] == "+62812345678"
        assert result["nationality"] == "Indonesian"

    @pytest.mark.asyncio
    async def test_enrich_client_data_low_confidence_no_merge(self, extractor):
        """Test enrich_client_data doesn't merge with low confidence"""
        extracted = {
            "client": {
                "full_name": "Wrong Name",
                "email": "wrong@example.com",
                "phone": "+62999999999",
                "whatsapp": None,
                "nationality": None,
                "confidence": 0.3,  # Below 0.6 threshold
            }
        }

        existing = {
            "full_name": "Correct Name",
            "email": "correct@example.com",
            "phone": None,
        }

        result = await extractor.enrich_client_data(extracted, existing)

        # Existing values should remain unchanged
        assert result["full_name"] == "Correct Name"
        assert result["phone"] is None  # Not updated due to low confidence

    @pytest.mark.asyncio
    async def test_should_create_practice_true(self, extractor):
        """Test should_create_practice returns True when conditions met"""
        extracted = {
            "practice_intent": {
                "detected": True,
                "practice_type_code": "PT_PMA",
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
                "practice_type_code": "PT_PMA",
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
                "practice_type_code": "PT_PMA",
                "confidence": 0.5,  # Below 0.7 threshold
            }
        }

        result = await extractor.should_create_practice(extracted)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_create_practice_false_no_type_code(self, extractor):
        """Test should_create_practice returns False with no type code"""
        extracted = {
            "practice_intent": {
                "detected": True,
                "practice_type_code": None,
                "confidence": 0.8,
            }
        }

        result = await extractor.should_create_practice(extracted)

        assert result is False


# ============================================================================
# Tests for get_extractor singleton
# ============================================================================


class TestGetExtractor:
    """Tests for the singleton extractor factory"""

    def test_get_extractor_returns_instance(self):
        """Test get_extractor returns an extractor instance"""
        with patch("backend.services.crm.ai_crm_extractor._extractor_instance", None):
            with patch("backend.services.crm.ai_crm_extractor.ZantaraAIClient") as mock_client:
                mock_client.return_value = MagicMock()

                result = get_extractor()

                assert isinstance(result, AICRMExtractor)

    def test_get_extractor_singleton_behavior(self):
        """Test get_extractor returns same instance"""
        with patch("backend.services.crm.ai_crm_extractor._extractor_instance", None):
            with patch("backend.services.crm.ai_crm_extractor.ZantaraAIClient") as mock_client:
                mock_client.return_value = MagicMock()

                result1 = get_extractor()
                result2 = get_extractor()

                assert result1 is result2
                # Should only create client once
                assert mock_client.call_count == 1
