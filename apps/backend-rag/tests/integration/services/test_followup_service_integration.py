"""
Integration Tests for FollowupService
Tests follow-up question generation
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestFollowupServiceIntegration:
    """Comprehensive integration tests for FollowupService"""

    @pytest.fixture
    def service(self):
        """Create FollowupService instance"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client:
            from services.followup_service import FollowupService

            service = FollowupService()
            service.zantara_client = None  # Disable AI for tests
            return service

    def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None

    def test_generate_followups_business(self, service):
        """Test generating business follow-ups"""
        followups = service.generate_followups(
            query="How to set up PT PMA?",
            response="PT PMA is a foreign investment company...",
            topic="business",
            language="en",
        )

        assert followups is not None
        assert len(followups) > 0
        assert all(isinstance(f, str) for f in followups)

    def test_generate_followups_immigration(self, service):
        """Test generating immigration follow-ups"""
        followups = service.generate_followups(
            query="How to get KITAS?",
            response="KITAS is a stay permit...",
            topic="immigration",
            language="it",
        )

        assert followups is not None
        assert len(followups) > 0

    def test_generate_followups_tax(self, service):
        """Test generating tax follow-ups"""
        followups = service.generate_followups(
            query="How to register for tax?",
            response="Tax registration requires...",
            topic="tax",
            language="id",
        )

        assert followups is not None
        assert len(followups) > 0

    def test_get_topic_based_followups(self, service):
        """Test getting topic-based follow-ups"""
        followups = service.get_topic_based_followups(
            _query="test", _response="test", topic="business", language="en"
        )

        assert followups is not None
        assert len(followups) >= 3

    def test_detect_language_from_query(self, service):
        """Test detecting language from query"""
        assert service.detect_language_from_query("Ciao, come stai?") == "it"
        assert service.detect_language_from_query("Hello, how are you?") == "en"
        assert service.detect_language_from_query("Apa kabar?") == "id"

    def test_detect_topic_from_query(self, service):
        """Test detecting topic from query"""
        assert service.detect_topic_from_query("How to set up PT PMA?") == "business"
        assert service.detect_topic_from_query("How to get KITAS?") == "immigration"
        assert service.detect_topic_from_query("How to register for tax?") == "tax"
