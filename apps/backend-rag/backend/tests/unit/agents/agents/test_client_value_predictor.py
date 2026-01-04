"""
Unit tests for ClientValuePredictor
Target: >95% coverage
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.agents.client_value_predictor import ClientValuePredictor


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()

    @asynccontextmanager
    async def acquire():
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetch = AsyncMock(return_value=[])
        yield conn

    pool.acquire = acquire
    return pool


@pytest.fixture
def client_value_predictor(mock_db_pool):
    """Create ClientValuePredictor instance"""
    with (
        patch("agents.agents.client_value_predictor.ClientScoringService"),
        patch("agents.agents.client_value_predictor.ClientSegmentationService"),
        patch("agents.agents.client_value_predictor.NurturingMessageService"),
        patch("agents.agents.client_value_predictor.WhatsAppNotificationService"),
        patch("app.core.config.settings") as mock_settings,
    ):
        mock_settings.twilio_account_sid = "test_sid"
        mock_settings.twilio_auth_token = "test_token"
        mock_settings.twilio_whatsapp_number = "+1234567890"

        return ClientValuePredictor(db_pool=mock_db_pool)


class TestClientValuePredictor:
    """Tests for ClientValuePredictor"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        with (
            patch("agents.agents.client_value_predictor.ClientScoringService"),
            patch("agents.agents.client_value_predictor.ClientSegmentationService"),
            patch("agents.agents.client_value_predictor.NurturingMessageService"),
            patch("agents.agents.client_value_predictor.WhatsAppNotificationService"),
            patch("app.core.config.settings") as mock_settings,
        ):
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            predictor = ClientValuePredictor(db_pool=mock_db_pool)
            assert predictor.db_pool == mock_db_pool
            assert predictor.scoring_service is not None
            assert predictor.segmentation_service is not None
            assert predictor.message_service is not None
            assert predictor.whatsapp_service is not None

    def test_init_no_db_pool(self):
        """Test initialization without db_pool"""
        with patch("agents.agents.client_value_predictor.app", create=True) as mock_app:
            mock_app.state = MagicMock()
            mock_app.state.db_pool = None

            with pytest.raises(RuntimeError, match="Database pool not available"):
                ClientValuePredictor(db_pool=None)

    def test_init_from_app_state(self):
        """Test initialization from app.state"""
        mock_pool = MagicMock()

        # Create a mock app module with state
        mock_app_module = MagicMock()
        mock_app_module.state = MagicMock()
        mock_app_module.state.db_pool = mock_pool

        with (
            patch("app.main_cloud.app", mock_app_module),
            patch("agents.agents.client_value_predictor.ClientScoringService"),
            patch("agents.agents.client_value_predictor.ClientSegmentationService"),
            patch("agents.agents.client_value_predictor.NurturingMessageService"),
            patch("agents.agents.client_value_predictor.WhatsAppNotificationService"),
            patch("app.core.config.settings") as mock_settings,
        ):
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            predictor = ClientValuePredictor(db_pool=None)
            assert predictor.db_pool == mock_pool

    @pytest.mark.asyncio
    async def test_calculate_client_score(self, client_value_predictor):
        """Test calculating client score"""
        mock_score = {"client_id": "123", "ltv_score": 75.0, "interaction_count": 10}
        enriched_score = {**mock_score, "segment": "HIGH_VALUE", "risk_level": "LOW_RISK"}
        client_value_predictor.scoring_service.calculate_client_score = AsyncMock(
            return_value=mock_score
        )
        client_value_predictor.segmentation_service.enrich_client_data = MagicMock(
            return_value=enriched_score
        )

        result = await client_value_predictor.calculate_client_score("123")
        assert result == enriched_score
        client_value_predictor.scoring_service.calculate_client_score.assert_called_once_with("123")
        client_value_predictor.segmentation_service.enrich_client_data.assert_called_once_with(
            mock_score
        )

    @pytest.mark.asyncio
    async def test_calculate_client_score_none(self, client_value_predictor):
        """Test calculating client score when client not found"""
        client_value_predictor.scoring_service.calculate_client_score = AsyncMock(return_value=None)

        result = await client_value_predictor.calculate_client_score("999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_db_pool(self, client_value_predictor):
        """Test getting database pool"""
        pool = await client_value_predictor._get_db_pool()
        assert pool == client_value_predictor.db_pool
