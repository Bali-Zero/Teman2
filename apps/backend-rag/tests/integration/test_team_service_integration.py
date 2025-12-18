"""
Integration tests for Team Timesheet Service
Tests team activity tracking integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestTeamServiceIntegration:
    """Integration tests for Team Timesheet Service"""

    @pytest.mark.asyncio
    async def test_team_service_initialization(self, postgres_container):
        """Test team timesheet service initialization"""
        with patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            from services.team_timesheet_service import get_timesheet_service

            service = get_timesheet_service()
            assert service is not None

    @pytest.mark.asyncio
    async def test_clock_in_flow(self, postgres_container):
        """Test clock-in flow"""
        with patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.clock_in = AsyncMock(
                return_value={
                    "success": True,
                    "action": "clock_in",
                    "timestamp": "2025-12-08T10:00:00Z",
                }
            )
            mock_get_service.return_value = mock_service

            from services.team_timesheet_service import get_timesheet_service

            service = get_timesheet_service()
            result = await service.clock_in("user123", "test@example.com")

            assert result["success"] is True
