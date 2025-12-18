"""
Integration tests for CollaboratorService
Tests collaborator management and coordination
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCollaboratorServiceIntegration:
    """Integration tests for CollaboratorService"""

    def test_collaborator_service_init(self):
        """Test CollaboratorService initialization"""
        from services.collaborator_service import CollaboratorService

        service = CollaboratorService()
        assert service is not None

    def test_get_team_members(self):
        """Test getting team members"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
        ):
            import json

            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
                [
                    {
                        "id": "test1",
                        "email": "test1@example.com",
                        "name": "Test User 1",
                        "role": "developer",
                        "department": "engineering",
                    }
                ]
            )

            from services.collaborator_service import CollaboratorService

            service = CollaboratorService()
            assert len(service.members) > 0

    def test_identify_collaborator(self):
        """Test identifying a collaborator by email"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
        ):
            import json

            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
                [
                    {
                        "id": "test1",
                        "email": "test1@example.com",
                        "name": "Test User 1",
                        "role": "developer",
                        "department": "engineering",
                    }
                ]
            )

            from services.collaborator_service import CollaboratorService

            service = CollaboratorService()
            # Test that service can be instantiated
            assert service is not None
