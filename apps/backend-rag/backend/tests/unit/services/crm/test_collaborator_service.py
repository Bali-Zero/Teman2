"""
Tests for CollaboratorService
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from services.crm.collaborator_service import CollaboratorService, CollaboratorProfile


@pytest.fixture
def sample_team_data():
    """Sample team data for testing"""
    return [
        {
            "id": "user1",
            "email": "john@example.com",
            "name": "John Doe",
            "role": "Developer",
            "department": "Engineering",
            "team": "Backend",
            "language": "en",
            "languages": ["en", "it"],
            "expertise_level": "senior",
            "traits": ["analytical", "detail-oriented"],
        },
        {
            "id": "user2",
            "email": "jane@example.com",
            "name": "Jane Smith",
            "role": "Designer",
            "department": "Design",
            "team": "Frontend",
            "language": "it",
            "languages": ["it", "en"],
            "expertise_level": "intermediate",
            "traits": ["creative", "collaborative"],
        },
    ]


@pytest.fixture
def temp_team_file(sample_team_data):
    """Create temporary team data file"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_team_data, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def collaborator_service(temp_team_file, sample_team_data):
    """Create CollaboratorService instance with temp data"""
    with patch("services.crm.collaborator_service.DATA_PATH", temp_team_file):
        service = CollaboratorService()
        yield service


class TestCollaboratorProfile:
    """Tests for CollaboratorProfile dataclass"""

    def test_to_dict(self):
        """Test profile serialization"""
        profile = CollaboratorProfile(
            id="user1",
            email="john@example.com",
            name="John Doe",
            role="Developer",
            department="Engineering",
            team="Backend",
            language="en",
        )

        result = profile.to_dict()

        assert result["id"] == "user1"
        assert result["email"] == "john@example.com"
        assert result["name"] == "John Doe"
        assert result["role"] == "Developer"

    def test_matches_name(self):
        """Test profile matching by name"""
        profile = CollaboratorProfile(
            id="user1",
            email="john@example.com",
            name="John Doe",
            role="Developer",
            department="Engineering",
            team="Backend",
            language="en",
        )

        assert profile.matches("John") is True
        assert profile.matches("john") is True
        assert profile.matches("DOE") is True
        assert profile.matches("Alice") is False

    def test_matches_email(self):
        """Test profile matching by email"""
        profile = CollaboratorProfile(
            id="user1",
            email="john@example.com",
            name="John Doe",
            role="Developer",
            department="Engineering",
            team="Backend",
            language="en",
        )

        assert profile.matches("john@example.com") is True
        assert profile.matches("example.com") is True

    def test_matches_role(self):
        """Test profile matching by role"""
        profile = CollaboratorProfile(
            id="user1",
            email="john@example.com",
            name="John Doe",
            role="Developer",
            department="Engineering",
            team="Backend",
            language="en",
        )

        assert profile.matches("Developer") is True
        assert profile.matches("developer") is True

    def test_matches_traits(self):
        """Test profile matching by traits"""
        profile = CollaboratorProfile(
            id="user1",
            email="john@example.com",
            name="John Doe",
            role="Developer",
            department="Engineering",
            team="Backend",
            language="en",
            traits=["analytical", "detail-oriented"],
        )

        assert profile.matches("analytical") is True
        assert profile.matches("detail-oriented") is True


class TestCollaboratorService:
    """Tests for CollaboratorService"""

    def test_init_success(self, temp_team_file):
        """Test successful service initialization"""
        with patch("services.crm.collaborator_service.DATA_PATH", temp_team_file):
            service = CollaboratorService()

            assert len(service.members) == 2
            assert service.members[0].name == "John Doe"
            assert service.members[1].name == "Jane Smith"

    def test_init_file_not_found(self):
        """Test initialization with missing file"""
        with patch("services.crm.collaborator_service.DATA_PATH", Path("/nonexistent.json")):
            with pytest.raises(FileNotFoundError):
                CollaboratorService()

    def test_get_member_success(self, collaborator_service):
        """Test getting collaborator by email"""
        profile = collaborator_service.get_member("john@example.com")

        assert profile is not None
        assert profile.email == "john@example.com"
        assert profile.name == "John Doe"

    def test_get_member_not_found(self, collaborator_service):
        """Test getting collaborator by non-existent email"""
        profile = collaborator_service.get_member("nonexistent@example.com")

        assert profile is None

    def test_get_member_case_insensitive(self, collaborator_service):
        """Test email lookup is case-insensitive"""
        profile = collaborator_service.get_member("JOHN@EXAMPLE.COM")

        assert profile is not None
        assert profile.email == "john@example.com"

    def test_search_members_by_name(self, collaborator_service):
        """Test searching collaborators by name"""
        results = collaborator_service.search_members("John")

        assert len(results) == 1
        assert results[0].name == "John Doe"

    def test_search_members_by_email(self, collaborator_service):
        """Test searching collaborators by email"""
        results = collaborator_service.search_members("john@example.com")

        assert len(results) == 1
        assert results[0].email == "john@example.com"

    def test_search_members_by_role(self, collaborator_service):
        """Test searching collaborators by role"""
        results = collaborator_service.search_members("Developer")

        assert len(results) == 1
        assert results[0].role == "Developer"

    def test_search_members_multiple_results(self, collaborator_service):
        """Test search returns multiple results"""
        results = collaborator_service.search_members("example.com")

        assert len(results) == 2

    def test_search_members_no_results(self, collaborator_service):
        """Test search with no matches"""
        results = collaborator_service.search_members("nonexistent")

        assert len(results) == 0

    def test_list_members_all(self, collaborator_service):
        """Test listing all collaborators"""
        all_members = collaborator_service.list_members()

        assert len(all_members) == 2
        assert all_members[0].name == "John Doe"
        assert all_members[1].name == "Jane Smith"

    def test_list_members_by_department(self, collaborator_service):
        """Test listing collaborators by department"""
        results = collaborator_service.list_members("Engineering")

        assert len(results) == 1
        assert results[0].department == "Engineering"

    def test_get_team_stats(self, collaborator_service):
        """Test getting service statistics"""
        stats = collaborator_service.get_team_stats()

        assert stats["total"] == 2
        assert "departments" in stats
        assert "languages" in stats

    @pytest.mark.asyncio
    async def test_identify_by_email(self, collaborator_service):
        """Test identify method by email"""
        result = await collaborator_service.identify("john@example.com")

        assert result is not None
        assert result.email == "john@example.com"
        assert result.name == "John Doe"

    @pytest.mark.asyncio
    async def test_identify_not_found(self, collaborator_service):
        """Test identify with non-existent collaborator"""
        result = await collaborator_service.identify("nonexistent@example.com")

        assert result is not None
        assert result.id == "anonymous"  # Returns anonymous profile

    @pytest.mark.asyncio
    async def test_identify_none(self, collaborator_service):
        """Test identify with None"""
        result = await collaborator_service.identify(None)

        assert result is not None
        assert result.id == "anonymous"

