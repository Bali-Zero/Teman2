"""
Unit tests for VerificationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.verification_service import (
    VerificationService,
    VerificationStatus,
    VerificationResult
)


@pytest.fixture
def verification_service():
    """Create VerificationService instance"""
    with patch("services.rag.verification_service.GENAI_AVAILABLE", True), \
         patch("services.rag.verification_service.GenAIClient") as mock_client_class, \
         patch("app.core.config.settings") as mock_settings:
        mock_settings.google_api_key = "test_key"
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client_class.return_value = mock_client
        return VerificationService()


@pytest.fixture
def verification_service_no_genai():
    """Create VerificationService instance without GenAI"""
    with patch("services.rag.verification_service.GENAI_AVAILABLE", False), \
         patch("app.core.config.settings") as mock_settings:
        mock_settings.google_api_key = None
        return VerificationService()


class TestVerificationService:
    """Tests for VerificationService"""

    def test_init(self, verification_service):
        """Test initialization"""
        assert verification_service._available is True
        assert verification_service._genai_client is not None

    def test_init_no_genai(self, verification_service_no_genai):
        """Test initialization without GenAI"""
        assert verification_service_no_genai._available is False
        assert verification_service_no_genai._genai_client is None

    @pytest.mark.asyncio
    async def test_verify_response_no_genai(self, verification_service_no_genai):
        """Test verifying response without GenAI"""
        result = await verification_service_no_genai.verify_response(
            query="Test query",
            draft_answer="Test answer",
            context_chunks=["Context 1"]
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.VERIFIED
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_verify_response_no_context(self, verification_service):
        """Test verifying response with no context"""
        result = await verification_service.verify_response(
            query="Test query",
            draft_answer="Test answer",
            context_chunks=[]
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_verify_response_with_context(self, verification_service):
        """Test verifying response with context"""
        mock_response = {
            "is_valid": True,
            "status": "verified",
            "score": 0.9,
            "reasoning": "Answer is supported",
            "corrected_answer": None,
            "missing_citations": []
        }
        
        verification_service._genai_client.generate_text = AsyncMock(
            return_value='{"is_valid": true, "status": "verified", "score": 0.9, "reasoning": "Answer is supported", "corrected_answer": null, "missing_citations": []}'
        )
        
        result = await verification_service.verify_response(
            query="Test query",
            draft_answer="Test answer",
            context_chunks=["Context 1", "Context 2"]
        )
        assert isinstance(result, VerificationResult)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_verify_response_json_error(self, verification_service):
        """Test verifying response with JSON error"""
        verification_service._genai_client.generate_text = AsyncMock(
            return_value="Invalid JSON"
        )
        
        result = await verification_service.verify_response(
            query="Test query",
            draft_answer="Test answer",
            context_chunks=["Context 1"]
        )
        assert isinstance(result, VerificationResult)

