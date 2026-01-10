"""
Unit tests for ClientJourneyOrchestrator
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.misc.client_journey_orchestrator import ClientJourneyOrchestrator


@pytest.fixture
def mock_journey_builder():
    """Mock journey builder service"""
    service = MagicMock()
    service.build_journey_from_template = AsyncMock(return_value=MagicMock())
    return service


@pytest.fixture
def mock_progress_tracker():
    """Mock progress tracker service"""
    service = MagicMock()
    service.get_progress = AsyncMock(return_value={"completed": 0, "total": 5})
    return service


@pytest.fixture
def mock_step_manager():
    """Mock step manager service"""
    service = MagicMock()
    service.start_step = AsyncMock(return_value={"status": "success"})
    service.complete_step = AsyncMock(return_value={"status": "success"})
    return service


@pytest.fixture
def mock_prerequisites_checker():
    """Mock prerequisites checker service"""
    service = MagicMock()
    service.check_prerequisites = AsyncMock(return_value=(True, []))
    return service


@pytest.fixture
def mock_journey_templates():
    """Mock journey templates service"""
    service = MagicMock()
    service.get_template = MagicMock(return_value={"steps": []})
    return service


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=conn)
    return pool


@pytest.fixture
def client_journey_orchestrator():
    """Create ClientJourneyOrchestrator instance"""
    with (
        patch("backend.services.misc.client_journey_orchestrator.JourneyTemplatesService"),
        patch("backend.services.misc.client_journey_orchestrator.JourneyBuilderService"),
        patch("backend.services.misc.client_journey_orchestrator.PrerequisitesCheckerService"),
        patch("backend.services.misc.client_journey_orchestrator.StepManagerService"),
        patch("backend.services.misc.client_journey_orchestrator.ProgressTrackerService"),
    ):
        return ClientJourneyOrchestrator()


class TestClientJourneyOrchestrator:
    """Tests for ClientJourneyOrchestrator"""

    def test_init(self, client_journey_orchestrator):
        """Test initialization"""
        assert client_journey_orchestrator.builder_service is not None
        assert client_journey_orchestrator.progress_tracker is not None

    def test_create_journey(self, client_journey_orchestrator):
        """Test creating journey"""
        with patch.object(
            client_journey_orchestrator.builder_service,
            "build_journey_from_template",
            return_value=MagicMock(),
        ) as mock_build:
            mock_journey = MagicMock()
            mock_journey.journey_id = "journey1"
            mock_journey.journey_type = "pt_pma_setup"
            mock_journey.steps = []
            mock_build.return_value = mock_journey
            result = client_journey_orchestrator.create_journey(
                client_id="client1", journey_type="pt_pma_setup"
            )
            assert result is not None

    def test_get_progress(self, client_journey_orchestrator):
        """Test getting journey progress"""
        mock_journey = MagicMock()
        mock_journey.steps = []
        mock_journey.status = "in_progress"
        mock_journey.started_at = None
        mock_journey.estimated_completion = None
        with patch.object(client_journey_orchestrator, "get_journey", return_value=mock_journey):
            with patch.object(
                client_journey_orchestrator.progress_tracker,
                "get_progress",
                return_value={
                    "progress_percent": 0,
                    "completed": 0,
                    "in_progress": 0,
                    "blocked": 0,
                    "total_steps": 5,
                },
            ):
                with patch.object(client_journey_orchestrator, "get_next_steps", return_value=[]):
                    progress = client_journey_orchestrator.get_progress("journey1")
                    assert isinstance(progress, dict)

    def test_start_step(self, client_journey_orchestrator):
        """Test starting a step"""
        mock_journey = MagicMock()
        mock_journey.steps = []
        with patch.object(client_journey_orchestrator, "get_journey", return_value=mock_journey):
            with patch.object(
                client_journey_orchestrator, "check_prerequisites", return_value=(True, [])
            ):
                with patch.object(
                    client_journey_orchestrator.step_manager, "start_step", return_value=True
                ):
                    result = client_journey_orchestrator.start_step("journey1", "step1")
                    assert result is True

    def test_complete_step(self, client_journey_orchestrator):
        """Test completing a step"""
        mock_journey = MagicMock()
        mock_journey.steps = []
        mock_journey.started_at = None
        with patch.object(client_journey_orchestrator, "get_journey", return_value=mock_journey):
            with patch.object(
                client_journey_orchestrator.step_manager, "complete_step", return_value=True
            ):
                result = client_journey_orchestrator.complete_step(
                    "journey1", "step1", notes="Done"
                )
                assert result is True
