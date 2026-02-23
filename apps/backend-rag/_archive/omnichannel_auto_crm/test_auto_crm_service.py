"""
Tests for AutoCRMService
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.crm.auto_crm_service import AutoCRMService


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def mock_extractor():
    extractor = MagicMock()
    extractor.extract_crm_data = AsyncMock()
    return extractor


@pytest.fixture
def auto_crm_service(mock_pool, mock_extractor):
    service = AutoCRMService(db_pool=mock_pool)
    service.extractor = mock_extractor
    return service


@pytest.mark.asyncio
async def test_process_conversation_success(auto_crm_service, mock_pool, mock_extractor):
    # Mock data
    conversation_id = 123
    messages = [{"role": "user", "content": "Hello"}]

    mock_extractor.extract_crm_data.return_value = {
        "client": {"full_name": "Test Client", "confidence": 0.95},
        "practices": [],
    }

    # Mock DB responses
    mock_pool.fetchrow.return_value = {"id": 1, "uuid": "uuid-123"}

    result = await auto_crm_service.process_conversation(conversation_id, messages)

    assert result["success"] is True
    assert mock_extractor.extract_crm_data.called


@pytest.mark.asyncio
async def test_process_conversation_low_confidence(auto_crm_service, mock_pool, mock_extractor):
    conversation_id = 123
    messages = [{"role": "user", "content": "Hi"}]

    mock_extractor.extract_crm_data.return_value = {
        "client": {"full_name": "Test Client", "confidence": 0.1},  # Below threshold
        "practices": [],
    }

    result = await auto_crm_service.process_conversation(conversation_id, messages)

    assert result["success"] is False
    assert "Insufficient confidence" in result["message"]
