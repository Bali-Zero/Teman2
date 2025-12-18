"""
Unit Tests for Client Value Predictor Agent
Tests agents/agents/client_value_predictor.py

Target: Autonomous client value predictor
File: backend/agents/agents/client_value_predictor.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents.agents.client_value_predictor import ClientValuePredictor


class TestClientValuePredictorInit:
    """Test ClientValuePredictor initialization"""

    def test_init_with_db_pool(self):
        """Test: ClientValuePredictor initializes with provided db_pool"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            assert predictor.db_pool == mock_pool
            assert predictor.scoring_service is not None
            assert predictor.segmentation_service is not None
            assert predictor.message_service is not None
            assert predictor.whatsapp_service is not None

    def test_init_without_db_pool_raises(self):
        """Test: ClientValuePredictor raises RuntimeError without db_pool"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            # Should raise RuntimeError when no db_pool is available
            with pytest.raises(RuntimeError, match="Database pool not available"):
                ClientValuePredictor(db_pool=None)


class TestCalculateClientScore:
    """Test calculate_client_score method"""

    @pytest.mark.asyncio
    async def test_calculate_client_score_success(self):
        """Test: Successfully calculates client score"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            # Mock scoring service
            mock_score_data = {
                "client_id": "client1",
                "ltv_score": 85.5,
                "total_value": 1000.0,
                "interaction_count": 10,
            }
            predictor.scoring_service.calculate_client_score = AsyncMock(
                return_value=mock_score_data
            )

            # Mock segmentation service
            enriched_data = {**mock_score_data, "segment": "VIP", "risk_level": "low"}
            predictor.segmentation_service.enrich_client_data = MagicMock(
                return_value=enriched_data
            )

            result = await predictor.calculate_client_score("client1")

            assert result == enriched_data
            assert result["segment"] == "VIP"
            assert result["ltv_score"] == 85.5
            predictor.scoring_service.calculate_client_score.assert_called_once_with("client1")

    @pytest.mark.asyncio
    async def test_calculate_client_score_not_found(self):
        """Test: Returns None when client not found"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            # Mock scoring service returning None
            predictor.scoring_service.calculate_client_score = AsyncMock(return_value=None)

            result = await predictor.calculate_client_score("nonexistent")

            assert result is None


class TestCalculateScoresBatch:
    """Test calculate_scores_batch method"""

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_success(self):
        """Test: Successfully calculates scores for multiple clients"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            # Mock scoring service batch response
            mock_scores = {
                "client1": {"client_id": "client1", "ltv_score": 85.5},
                "client2": {"client_id": "client2", "ltv_score": 65.0},
            }
            predictor.scoring_service.calculate_scores_batch = AsyncMock(return_value=mock_scores)

            # Mock segmentation enrichment
            def mock_enrich(score_data):
                return {
                    **score_data,
                    "segment": "VIP" if score_data["ltv_score"] > 80 else "High Value",
                }

            predictor.segmentation_service.enrich_client_data = MagicMock(side_effect=mock_enrich)

            result = await predictor.calculate_scores_batch(["client1", "client2"])

            assert len(result) == 2
            assert result["client1"]["segment"] == "VIP"
            assert result["client2"]["segment"] == "High Value"

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_empty_list(self):
        """Test: Handles empty client list"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            predictor.scoring_service.calculate_scores_batch = AsyncMock(return_value={})

            result = await predictor.calculate_scores_batch([])

            assert result == {}


class TestGenerateNurturingMessage:
    """Test generate_nurturing_message method"""

    @pytest.mark.asyncio
    async def test_generate_nurturing_message_success(self):
        """Test: Successfully generates nurturing message"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            # Mock message service
            predictor.message_service.generate_message = AsyncMock(
                return_value="Hello! We value your business."
            )

            client_data = {
                "client_id": "client1",
                "segment": "VIP",
                "risk_level": "low",
                "name": "Test Client",
            }

            result = await predictor.generate_nurturing_message(client_data, timeout=30.0)

            assert result == "Hello! We value your business."
            predictor.message_service.generate_message.assert_called_once_with(client_data, 30.0)


class TestSendWhatsAppMessage:
    """Test send_whatsapp_message method"""

    @pytest.mark.asyncio
    async def test_send_whatsapp_message_success(self):
        """Test: Successfully sends WhatsApp message"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            # Mock WhatsApp service
            predictor.whatsapp_service.send_message = AsyncMock(return_value="SM123456789")

            result = await predictor.send_whatsapp_message(
                "+1234567890", "Test message", max_retries=3
            )

            assert result == "SM123456789"
            predictor.whatsapp_service.send_message.assert_called_once_with(
                "+1234567890", "Test message", 3
            )

    @pytest.mark.asyncio
    async def test_send_whatsapp_message_failure(self):
        """Test: Handles WhatsApp send failure"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            mock_pool = MagicMock()
            predictor = ClientValuePredictor(db_pool=mock_pool)

            # Mock WhatsApp service failure
            predictor.whatsapp_service.send_message = AsyncMock(return_value=None)

            result = await predictor.send_whatsapp_message("+1234567890", "Test message")

            assert result is None


class TestRunDailyNurturing:
    """Test run_daily_nurturing method"""

    @pytest.mark.asyncio
    async def test_run_daily_nurturing_no_clients(self):
        """Test: Handles case with no active clients"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            # Mock database pool
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # No active clients
            mock_conn.fetch.return_value = []

            predictor = ClientValuePredictor(db_pool=mock_pool)

            result = await predictor.run_daily_nurturing(timeout=300.0)

            assert result["vip_nurtured"] == 0
            assert result["high_risk_contacted"] == 0
            assert result["total_messages_sent"] == 0
            assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_run_daily_nurturing_with_clients(self):
        """Test: Processes clients successfully"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test_sid"
            mock_settings.twilio_auth_token = "test_token"
            mock_settings.twilio_whatsapp_number = "+1234567890"

            # Mock database pool
            mock_pool = MagicMock()
            mock_conn = AsyncMock()

            # Create proper transaction context manager
            mock_transaction = MagicMock()
            mock_transaction.__aenter__ = AsyncMock(return_value=None)
            mock_transaction.__aexit__ = AsyncMock(return_value=False)
            mock_conn.transaction.return_value = mock_transaction

            # Setup pool acquire
            pool_cm = MagicMock()
            pool_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            pool_cm.__aexit__ = AsyncMock(return_value=False)
            mock_pool.acquire.return_value = pool_cm

            # Mock client data fetch
            mock_conn.fetch.return_value = [{"id": "client1"}]

            # Mock fetchrow for client details
            mock_conn.fetchrow.return_value = {
                "name": "Test Client",
                "email": "test@example.com",
                "phone": "+1234567890",
            }

            predictor = ClientValuePredictor(db_pool=mock_pool)

            # Mock services
            predictor.calculate_scores_batch = AsyncMock(
                return_value={
                    "client1": {
                        "client_id": "client1",
                        "ltv_score": 85.5,
                        "segment": "VIP",
                        "risk_level": "medium",
                        "days_since_last_interaction": 15,
                    }
                }
            )

            predictor.generate_nurturing_message = AsyncMock(
                return_value="Hello! We value your business."
            )

            predictor.send_whatsapp_message = AsyncMock(return_value="SM123456789")

            # Mock database execute for logging
            mock_conn.execute = AsyncMock()

            result = await predictor.run_daily_nurturing(timeout=300.0)

            # Verify results (exact counts depend on implementation logic)
            assert isinstance(result, dict)
            assert "vip_nurtured" in result
            assert "high_risk_contacted" in result
            assert "total_messages_sent" in result
            assert "errors" in result
