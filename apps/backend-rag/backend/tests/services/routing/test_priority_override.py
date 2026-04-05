"""
Tests for priority_override.py - Priority override detection for special query patterns.
"""

import pytest

from backend.services.routing.priority_override import PriorityOverrideService


@pytest.fixture
def service():
    return PriorityOverrideService()


class TestCheckPriorityOverrides:
    """Tests for check_priority_overrides method."""

    def test_identity_query_returns_none(self, service):
        """Identity queries return None to let Agentic RAG handle via TeamKnowledgeTool."""
        result = service.check_priority_overrides("Chi sono?")
        assert result is None

    def test_identity_query_english(self, service):
        result = service.check_priority_overrides("Who am I?")
        assert result is None

    def test_team_query_returns_none(self, service):
        result = service.check_priority_overrides("Mostrami i membri del team")
        assert result is None

    def test_founder_query_returns_none(self, service):
        result = service.check_priority_overrides("Chi è il fondatore?")
        assert result is None

    def test_founder_english(self, service):
        result = service.check_priority_overrides("Who is the founder of Bali Zero?")
        assert result is None

    def test_backend_services_query_returns_zantara_books(self, service):
        result = service.check_priority_overrides("What backend services are available?")
        assert result == "zantara_books"

    def test_api_endpoint_query(self, service):
        result = service.check_priority_overrides("Which endpoint should I call for CRM?")
        assert result == "zantara_books"

    def test_unrelated_query_returns_none(self, service):
        result = service.check_priority_overrides("How much does a PT PMA cost?")
        assert result is None

    def test_case_insensitive(self, service):
        result = service.check_priority_overrides("CHI SONO?")
        assert result is None  # Identity detected


class TestIsIdentityQuery:
    """Tests for is_identity_query method."""

    def test_italian_identity(self, service):
        assert service.is_identity_query("chi sono io?") is True
        assert service.is_identity_query("mi conosci?") is True
        assert service.is_identity_query("cosa sai di me?") is True

    def test_english_identity(self, service):
        assert service.is_identity_query("who am I?") is True
        assert service.is_identity_query("do you know me?") is True

    def test_indonesian_identity(self, service):
        assert service.is_identity_query("siapa saya?") is True

    def test_non_identity(self, service):
        assert service.is_identity_query("what is a visa?") is False
        assert service.is_identity_query("hello") is False


class TestIsTeamQuery:
    """Tests for is_team_query method."""

    def test_team_keywords(self, service):
        assert service.is_team_query("chi sono i membri del team?") is True
        assert service.is_team_query("who are the team members?") is True

    def test_department_query(self, service):
        assert service.is_team_query("quale dipartimento gestisce i visti?") is True

    def test_non_team_query(self, service):
        assert service.is_team_query("what is KBLI?") is False


class TestIsBackendServicesQuery:
    """Tests for is_backend_services_query method."""

    def test_backend_keyword(self, service):
        assert service.is_backend_services_query("how does the backend work?") is True

    def test_api_keyword(self, service):
        assert service.is_backend_services_query("api endpoint for pricing") is True

    def test_crm_keyword(self, service):
        assert service.is_backend_services_query("come funziona il crm service?") is True

    def test_non_backend_query(self, service):
        assert service.is_backend_services_query("quanto costa una villa a Bali?") is False
