"""
Unit tests for CollaboratorService
Tests collaborator service functionality
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestCollaboratorService:
    """Unit tests for CollaboratorService"""

    def test_collaborator_service_init(self):
        """Test CollaboratorService initialization"""
        from backend.services.collaborator_service import CollaboratorService

        service = CollaboratorService()
        assert service is not None

    def test_list_members(self):
        """Test listing members"""
        from backend.services.collaborator_service import CollaboratorService

        service = CollaboratorService()
        members = service.list_members()

        assert isinstance(members, list)

    def test_search_members(self):
        """Test searching members"""
        from backend.services.collaborator_service import CollaboratorService

        service = CollaboratorService()
        members = service.search_members("test")

        assert isinstance(members, list)

    def test_search_members_empty_query(self):
        """Test searching members with empty query"""
        from backend.services.collaborator_service import CollaboratorService

        service = CollaboratorService()
        members = service.search_members("")

        assert isinstance(members, list)
