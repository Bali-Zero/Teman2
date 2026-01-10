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

from backend.services.rag.verification_service import (
    VerificationResult,
    VerificationService,
    VerificationStatus,
)


@pytest.fixture
def verification_service():
    """Create VerificationService instance"""
    with (
        patch("backend.services.rag.verification_service.GENAI_AVAILABLE", True),
        patch("backend.services.rag.verification_service.GenAIClient") as mock_client_class,
        patch("backend.app.core.config.settings") as mock_settings,
    ):
        mock_settings.google_api_key = "test_key"
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client_class.return_value = mock_client
        return VerificationService()


@pytest.fixture
def verification_service_no_genai():
    """Create VerificationService instance without GenAI"""
    with (
        patch("backend.services.rag.verification_service.GENAI_AVAILABLE", False),
        patch("backend.app.core.config.settings") as mock_settings,
    ):
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
            query="Test query", draft_answer="Test answer", context_chunks=["Context 1"]
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.VERIFIED
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_verify_response_no_context(self, verification_service):
        """Test verifying response with no context"""
        result = await verification_service.verify_response(
            query="Test query", draft_answer="Test answer", context_chunks=[]
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
            "missing_citations": [],
        }

        verification_service._genai_client.generate_text = AsyncMock(
            return_value='{"is_valid": true, "status": "verified", "score": 0.9, "reasoning": "Answer is supported", "corrected_answer": null, "missing_citations": []}'
        )

        result = await verification_service.verify_response(
            query="Test query",
            draft_answer="Test answer",
            context_chunks=["Context 1", "Context 2"],
        )
        assert isinstance(result, VerificationResult)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_verify_response_json_error(self, verification_service):
        """Test verifying response with JSON error"""
        verification_service._genai_client.generate_content = AsyncMock(
            return_value={"text": "Invalid JSON"}
        )

        result = await verification_service.verify_response(
            query="Test query", draft_answer="Test answer", context_chunks=["Context 1"]
        )
        assert isinstance(result, VerificationResult)
        # Error case returns partially verified
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_verify_response_successful(self, verification_service):
        """Test verifying response with valid JSON - covers lines 130-140"""
        mock_json = '{"status": "verified", "score": 0.9, "reasoning": "Fully supported", "corrections": null, "missing_citations": []}'
        verification_service._genai_client.generate_content = AsyncMock(
            return_value={"text": mock_json}
        )

        result = await verification_service.verify_response(
            query="What are KITAS requirements?",
            draft_answer="KITAS requires documentation.",
            context_chunks=["Source 1: KITAS requires documentation."],
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.VERIFIED
        assert result.score == 0.9
        assert result.reasoning == "Fully supported"

    @pytest.mark.asyncio
    async def test_verify_response_partial(self, verification_service):
        """Test partial verification with low score"""
        mock_json = '{"status": "partial", "score": 0.5, "reasoning": "Some claims unsupported", "corrections": "Fix claim X", "missing_citations": ["claim X"]}'
        verification_service._genai_client.generate_content = AsyncMock(
            return_value={"text": mock_json}
        )

        result = await verification_service.verify_response(
            query="Test", draft_answer="Answer", context_chunks=["Context"]
        )
        assert result.is_valid is False  # score < 0.7
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5
        assert result.corrected_answer == "Fix claim X"
        assert result.missing_citations == ["claim X"]

    @pytest.mark.asyncio
    async def test_verify_response_hallucination(self, verification_service):
        """Test hallucination detection"""
        mock_json = '{"status": "hallucination", "score": 0.1, "reasoning": "Invented facts", "corrections": null, "missing_citations": ["fake law"]}'
        verification_service._genai_client.generate_content = AsyncMock(
            return_value={"text": mock_json}
        )

        result = await verification_service.verify_response(
            query="Test", draft_answer="Answer", context_chunks=["Context"]
        )
        assert result.is_valid is False
        assert result.status == VerificationStatus.HALLUCINATION
        assert result.score == 0.1

    @pytest.mark.asyncio
    async def test_verify_response_unverified(self, verification_service):
        """Test unverified status"""
        mock_json = '{"status": "unverified", "score": 0.3, "reasoning": "Not in context"}'
        verification_service._genai_client.generate_content = AsyncMock(
            return_value={"text": mock_json}
        )

        result = await verification_service.verify_response(
            query="Test", draft_answer="Answer", context_chunks=["Context"]
        )
        assert result.is_valid is False
        assert result.status == VerificationStatus.UNVERIFIED

    @pytest.mark.asyncio
    async def test_verify_response_empty_text(self, verification_service):
        """Test with empty text response"""
        verification_service._genai_client.generate_content = AsyncMock(return_value={"text": "{}"})

        result = await verification_service.verify_response(
            query="Test", draft_answer="Answer", context_chunks=["Context"]
        )
        # Empty JSON defaults to unverified
        assert result.status == VerificationStatus.UNVERIFIED
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_verify_response_exception(self, verification_service):
        """Test exception during generation - covers lines 130-140 exception"""
        verification_service._genai_client.generate_content = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await verification_service.verify_response(
            query="Test", draft_answer="Answer", context_chunks=["Context"]
        )
        assert result.is_valid is True  # Fail safe
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5
        assert "API Error" in result.reasoning


class TestVerificationServiceInit:
    """Tests for VerificationService initialization"""

    def test_init_exception(self):
        """Test initialization with exception - covers lines 55-56"""
        with (
            patch("backend.services.rag.verification_service.GENAI_AVAILABLE", True),
            patch("backend.services.rag.verification_service.GenAIClient") as mock_client_class,
            patch("backend.app.core.config.settings") as mock_settings,
        ):
            mock_settings.google_api_key = "test_key"
            mock_client_class.side_effect = Exception("Connection failed")

            service = VerificationService()
            assert service._available is False
            assert service._genai_client is None

    def test_init_client_not_available(self):
        """Test initialization when client is not available"""
        with (
            patch("backend.services.rag.verification_service.GENAI_AVAILABLE", True),
            patch("backend.services.rag.verification_service.GenAIClient") as mock_client_class,
            patch("backend.app.core.config.settings") as mock_settings,
        ):
            mock_settings.google_api_key = "test_key"
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_client_class.return_value = mock_client

            service = VerificationService()
            assert service._available is False

    def test_init_no_api_key(self):
        """Test initialization without API key"""
        with (
            patch("backend.services.rag.verification_service.GENAI_AVAILABLE", True),
            patch("backend.services.rag.verification_service.settings") as mock_settings,
        ):
            mock_settings.google_api_key = None

            service = VerificationService()
            assert service._available is False
            assert service._genai_client is None


class TestVerificationStatusEnum:
    """Tests for VerificationStatus enum"""

    def test_verified_value(self):
        """Test VERIFIED value"""
        assert VerificationStatus.VERIFIED.value == "verified"

    def test_partial_value(self):
        """Test PARTIALLY_VERIFIED value"""
        assert VerificationStatus.PARTIALLY_VERIFIED.value == "partial"

    def test_unverified_value(self):
        """Test UNVERIFIED value"""
        assert VerificationStatus.UNVERIFIED.value == "unverified"

    def test_hallucination_value(self):
        """Test HALLUCINATION value"""
        assert VerificationStatus.HALLUCINATION.value == "hallucination"


class TestVerificationResult:
    """Tests for VerificationResult model"""

    def test_create_result(self):
        """Test creating result"""
        result = VerificationResult(
            is_valid=True, status=VerificationStatus.VERIFIED, score=0.9, reasoning="Test"
        )
        assert result.is_valid is True
        assert result.score == 0.9

    def test_create_result_with_all_fields(self):
        """Test creating result with all fields"""
        result = VerificationResult(
            is_valid=False,
            status=VerificationStatus.HALLUCINATION,
            score=0.1,
            reasoning="Invented",
            corrected_answer="Correct answer",
            missing_citations=["Claim 1", "Claim 2"],
        )
        assert result.corrected_answer == "Correct answer"
        assert len(result.missing_citations) == 2

    def test_result_defaults(self):
        """Test result default values"""
        result = VerificationResult(
            is_valid=True, status=VerificationStatus.VERIFIED, score=1.0, reasoning="OK"
        )
        assert result.corrected_answer is None
        assert result.missing_citations == []
