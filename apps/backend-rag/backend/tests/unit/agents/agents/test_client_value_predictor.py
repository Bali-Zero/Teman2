"""
Unit tests for ClientValuePredictor
Target: >95% coverage
"""

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.agents.client_value_predictor import ClientValuePredictor


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
        patch("backend.agents.agents.client_value_predictor.ClientScoringService"),
        patch("backend.agents.agents.client_value_predictor.ClientSegmentationService"),
        patch("backend.agents.agents.client_value_predictor.NurturingMessageService"),
        patch("backend.agents.agents.client_value_predictor.WhatsAppNotificationService"),
        patch("backend.app.core.config.settings") as mock_settings,
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
            patch("backend.agents.agents.client_value_predictor.ClientScoringService"),
            patch("backend.agents.agents.client_value_predictor.ClientSegmentationService"),
            patch("backend.agents.agents.client_value_predictor.NurturingMessageService"),
            patch("backend.agents.agents.client_value_predictor.WhatsAppNotificationService"),
            patch("backend.app.core.config.settings") as mock_settings,
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
        # __init__ does a *local* `from backend.app.main_cloud import app`, so patching
        # the `app` attribute on this test module (or on client_value_predictor's module
        # namespace) has no effect on that fresh import — it must go through sys.modules,
        # same technique as test_init_from_app_state below, to be order-independent.
        mock_app_module = MagicMock()
        mock_app_module.state = MagicMock()
        mock_app_module.state.db_pool = None

        mock_main_cloud_module = MagicMock()
        mock_main_cloud_module.app = mock_app_module

        with patch.dict(sys.modules, {"backend.app.main_cloud": mock_main_cloud_module}):
            with pytest.raises(RuntimeError, match="Database pool not available"):
                ClientValuePredictor(db_pool=None)

    def test_init_from_app_state(self):
        """Test initialization from backend.app.state"""
        mock_pool = MagicMock()

        # Create a mock app module with state
        mock_app_module = MagicMock()
        mock_app_module.state = MagicMock()
        mock_app_module.state.db_pool = mock_pool

        import sys

        mock_main_cloud_module = MagicMock()
        mock_main_cloud_module.app = mock_app_module

        with (
            patch.dict(sys.modules, {"backend.app.main_cloud": mock_main_cloud_module}),
            patch("backend.agents.agents.client_value_predictor.ClientScoringService"),
            patch("backend.agents.agents.client_value_predictor.ClientSegmentationService"),
            patch("backend.agents.agents.client_value_predictor.NurturingMessageService"),
            patch("backend.agents.agents.client_value_predictor.WhatsAppNotificationService"),
            patch("backend.app.core.config.settings") as mock_settings,
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
            return_value=mock_score,
        )
        client_value_predictor.segmentation_service.enrich_client_data = MagicMock(
            return_value=enriched_score,
        )

        result = await client_value_predictor.calculate_client_score("123")
        assert result == enriched_score
        client_value_predictor.scoring_service.calculate_client_score.assert_called_once_with("123")
        client_value_predictor.segmentation_service.enrich_client_data.assert_called_once_with(
            mock_score,
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

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_enriches_every_returned_score(
        self,
        client_value_predictor: ClientValuePredictor,
    ) -> None:
        """Batch scoring must enrich each returned client payload."""
        raw_scores = {
            "123": {"client_id": "123", "ltv_score": 91.0},
            "456": {"client_id": "456", "ltv_score": 34.0},
        }
        client_value_predictor.scoring_service.calculate_scores_batch = AsyncMock(
            return_value=raw_scores,
        )

        def enrich(score: dict[str, Any]) -> dict[str, Any]:
            return {
                **score,
                "segment": f"segment-{score['client_id']}",
                "risk_level": "LOW_RISK",
            }

        client_value_predictor.segmentation_service.enrich_client_data = MagicMock(
            side_effect=enrich,
        )

        result = await client_value_predictor.calculate_scores_batch(["123", "456"])

        assert result == {
            "123": {
                "client_id": "123",
                "ltv_score": 91.0,
                "segment": "segment-123",
                "risk_level": "LOW_RISK",
            },
            "456": {
                "client_id": "456",
                "ltv_score": 34.0,
                "segment": "segment-456",
                "risk_level": "LOW_RISK",
            },
        }
        client_value_predictor.scoring_service.calculate_scores_batch.assert_awaited_once_with(
            ["123", "456"],
        )

    @pytest.mark.asyncio
    async def test_generate_nurturing_message_passes_timeout_to_service(
        self,
        client_value_predictor: ClientValuePredictor,
    ) -> None:
        """Message generation must preserve the caller's timeout budget."""
        client_data = {"client_id": "123", "segment": "VIP", "risk_level": "LOW_RISK"}
        client_value_predictor.message_service.generate_message = AsyncMock(
            return_value="synthetic nurturing copy",
        )

        result = await client_value_predictor.generate_nurturing_message(
            client_data,
            timeout=1.5,
        )

        assert result == "synthetic nurturing copy"
        client_value_predictor.message_service.generate_message.assert_awaited_once_with(
            client_data,
            1.5,
        )

    @pytest.mark.asyncio
    async def test_send_whatsapp_message_returns_none_when_outbound_disabled(
        self,
        client_value_predictor: ClientValuePredictor,
    ) -> None:
        """Disabled outbound switch must fail closed before Twilio is touched."""
        client_value_predictor.whatsapp_service.send_message = AsyncMock(
            return_value="SM-should-not-send",
        )

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.client_nurturing_outbound_enabled = False
            result = await client_value_predictor.send_whatsapp_message(
                "+620000000",
                "synthetic message",
                max_retries=2,
            )

        assert result is None
        client_value_predictor.whatsapp_service.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_whatsapp_message_delegates_when_outbound_enabled(
        self,
        client_value_predictor: ClientValuePredictor,
    ) -> None:
        """Enabled outbound switch delegates to the notification service."""
        client_value_predictor.whatsapp_service.send_message = AsyncMock(return_value="SM123")

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.client_nurturing_outbound_enabled = True
            result = await client_value_predictor.send_whatsapp_message(
                "+620000000",
                "synthetic message",
                max_retries=2,
            )

        assert result == "SM123"
        client_value_predictor.whatsapp_service.send_message.assert_awaited_once_with(
            "+620000000",
            "synthetic message",
            2,
        )

    @pytest.mark.asyncio
    async def test_run_daily_nurturing_returns_zero_counts_without_active_clients(
        self,
        client_value_predictor: ClientValuePredictor,
    ) -> None:
        """No active clients should short-circuit before scoring or messaging."""
        client_value_predictor.calculate_scores_batch = AsyncMock()
        result = await client_value_predictor.run_daily_nurturing(timeout=1.0)

        assert result == {
            "vip_nurtured": 0,
            "high_risk_contacted": 0,
            "total_messages_sent": 0,
            "errors": [],
        }
        client_value_predictor.calculate_scores_batch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_daily_nurturing_reports_database_acquire_errors(
        self,
        client_value_predictor: ClientValuePredictor,
    ) -> None:
        """Initial database failures should return a database error payload."""

        @asynccontextmanager
        async def acquire() -> AsyncIterator[MagicMock]:
            raise asyncpg.InterfaceError("pool unavailable")
            yield MagicMock()

        failing_pool = MagicMock()
        failing_pool.acquire = acquire
        client_value_predictor.db_pool = failing_pool

        result = await client_value_predictor.run_daily_nurturing(timeout=1.0)

        assert result == {
            "vip_nurtured": 0,
            "high_risk_contacted": 0,
            "total_messages_sent": 0,
            "errors": ["Database error: pool unavailable"],
        }
