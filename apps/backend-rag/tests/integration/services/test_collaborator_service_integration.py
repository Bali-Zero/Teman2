"""
Integration Tests for CollaboratorService
Tests team member identification and search
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCollaboratorServiceIntegration:
    """Comprehensive integration tests for CollaboratorService"""

    @pytest.fixture
    def mock_team_data(self, tmp_path):
        """Create mock team data file"""
        import json

        team_data = [
            {
                "id": "user-1",
                "email": "test1@example.com",
                "name": "Test User 1",
                "role": "Developer",
                "department": "technology",
                "team": "backend",
                "preferred_language": "en",
                "expertise_level": "senior",
                "traits": ["technical", "analytical"],
            },
            {
                "id": "user-2",
                "email": "test2@example.com",
                "name": "Test User 2",
                "role": "Designer",
                "department": "creative",
                "team": "frontend",
                "preferred_language": "it",
                "expertise_level": "mid",
                "traits": ["creative", "visual"],
            },
        ]

        data_file = tmp_path / "team_members.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(team_data, f)

        return data_file

    @pytest.fixture
    def service(self, mock_team_data):
        """Create CollaboratorService instance"""
        with patch("services.collaborator_service.DATA_PATH", mock_team_data):
            from services.collaborator_service import CollaboratorService

            return CollaboratorService()

    def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert len(service.members) == 2

    @pytest.mark.asyncio
    async def test_identify_by_email(self, service):
        """Test identifying collaborator by email"""
        profile = await service.identify("test1@example.com")

        assert profile is not None
        assert profile.email == "test1@example.com"
        assert profile.name == "Test User 1"

    @pytest.mark.asyncio
    async def test_identify_anonymous(self, service):
        """Test identifying anonymous user"""
        profile = await service.identify(None)

        assert profile is not None
        assert profile.id == "anonymous"

    @pytest.mark.asyncio
    async def test_identify_not_found(self, service):
        """Test identifying non-existent user"""
        profile = await service.identify("nonexistent@example.com")

        assert profile is not None
        assert profile.id == "anonymous"

    def test_get_member(self, service):
        """Test getting member by email"""
        member = service.get_member("test1@example.com")

        assert member is not None
        assert member.email == "test1@example.com"

    def test_list_members_all(self, service):
        """Test listing all members"""
        members = service.list_members()

        assert len(members) == 2

    def test_list_members_by_department(self, service):
        """Test listing members by department"""
        members = service.list_members(department="technology")

        assert len(members) == 1
        assert members[0].department == "technology"

    def test_search_members(self, service):
        """Test searching members"""
        results = service.search_members("Test User 1")

        assert len(results) == 1
        assert results[0].name == "Test User 1"

    def test_search_members_by_role(self, service):
        """Test searching members by role"""
        results = service.search_members("Developer")

        assert len(results) == 1
        assert results[0].role == "Developer"

    def test_get_team_stats(self, service):
        """Test getting team statistics"""
        stats = service.get_team_stats()

        assert stats is not None
        assert stats["total"] == 2
        assert "departments" in stats
        assert "languages" in stats

    def test_collaborator_profile_matches(self, service):
        """Test profile matching"""
        profile = service.members[0]

        assert profile.matches("Test User 1") is True
        assert profile.matches("Developer") is True
        assert profile.matches("nonexistent") is False

    def test_collaborator_profile_to_dict(self, service):
        """Test profile serialization"""
        profile = service.members[0]
        profile_dict = profile.to_dict()

        assert profile_dict is not None
        assert "id" in profile_dict
        assert "email" in profile_dict
        assert "name" in profile_dict
