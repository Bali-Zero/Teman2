"""
API Tests for ClientValuePredictor - Coverage 95% Target
Tests ClientValuePredictor via API endpoints

Coverage:
- POST /api/autonomous-agents/client-value-predictor/run
- calculate_client_score method
- run_daily_nurturing method
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "test_twilio_sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_twilio_token")
os.environ.setdefault("TWILIO_WHATSAPP_NUMBER", "+1234567890")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestClientValuePredictorAPI:
    """Test ClientValuePredictor via API endpoints"""

    @pytest.mark.asyncio
    async def test_run_client_value_predictor_endpoint(self, authenticated_client):
        """Test POST /api/autonomous-agents/client-value-predictor/run endpoint"""
        response = authenticated_client.post("/api/autonomous-agents/client-value-predictor/run")

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "agent_name" in data
        assert data["agent_name"] == "client_value_predictor"
        assert "status" in data
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_calculate_client_score_success(self):
        """Test calculate_client_score with successful calculation"""
        from backend.agents.agents.client_value_predictor import ClientValuePredictor

        mock_pool = MagicMock()
        mock_scoring_service = MagicMock()
        mock_scoring_service.calculate_client_score = AsyncMock(
            return_value={"ltv_score": 85.5, "risk_level": "low"}
        )

        with patch(
            "backend.agents.agents.client_value_predictor.ClientScoringService"
        ) as mock_scoring:
            mock_scoring.return_value = mock_scoring_service

            predictor = ClientValuePredictor(db_pool=mock_pool)

            result = await predictor.calculate_client_score("client123")

            assert result is not None
            assert "ltv_score" in result

    @pytest.mark.asyncio
    async def test_calculate_client_score_no_client(self):
        """Test calculate_client_score with non-existent client"""
        from backend.agents.agents.client_value_predictor import ClientValuePredictor

        mock_pool = MagicMock()
        mock_scoring_service = MagicMock()
        mock_scoring_service.calculate_client_score = AsyncMock(return_value=None)

        with patch(
            "backend.agents.agents.client_value_predictor.ClientScoringService"
        ) as mock_scoring:
            mock_scoring.return_value = mock_scoring_service

            predictor = ClientValuePredictor(db_pool=mock_pool)

            result = await predictor.calculate_client_score("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_run_daily_nurturing_success(self):
        """Test run_daily_nurturing with successful execution"""
        from backend.agents.agents.client_value_predictor import ClientValuePredictor

        mock_pool = MagicMock()
        mock_scoring_service = MagicMock()
        mock_scoring_service.calculate_scores_batch = AsyncMock(
            return_value={"client123": {"ltv_score": 90, "risk_level": "low"}}
        )

        mock_segmentation_service = MagicMock()
        mock_segmentation_service.segment_clients = MagicMock(
            return_value={"vip": ["client123"], "high_risk": []}
        )

        mock_message_service = MagicMock()
        mock_message_service.generate_message = AsyncMock(return_value="Test message")

        mock_whatsapp_service = MagicMock()
        mock_whatsapp_service.send_message = AsyncMock(return_value=True)

        with patch(
            "backend.agents.agents.client_value_predictor.ClientScoringService"
        ) as mock_scoring:
            with patch(
                "backend.agents.agents.client_value_predictor.ClientSegmentationService"
            ) as mock_seg:
                with patch(
                    "backend.agents.agents.client_value_predictor.NurturingMessageService"
                ) as mock_msg:
                    with patch(
                        "backend.agents.agents.client_value_predictor.WhatsAppNotificationService"
                    ) as mock_wa:
                        mock_scoring.return_value = mock_scoring_service
                        mock_seg.return_value = mock_segmentation_service
                        mock_msg.return_value = mock_message_service
                        mock_wa.return_value = mock_whatsapp_service

                        predictor = ClientValuePredictor(db_pool=mock_pool)

                        result = await predictor.run_daily_nurturing()

                        assert "vip_nurtured" in result
                        assert "high_risk_contacted" in result
                        assert "total_messages_sent" in result

    @pytest.mark.asyncio
    async def test_run_daily_nurturing_no_clients(self):
        """Test run_daily_nurturing with no clients"""
        from backend.agents.agents.client_value_predictor import ClientValuePredictor

        mock_pool = MagicMock()
        mock_scoring_service = MagicMock()
        mock_scoring_service.calculate_scores_batch = AsyncMock(return_value={})

        mock_segmentation_service = MagicMock()
        mock_segmentation_service.segment_clients = MagicMock(
            return_value={"vip": [], "high_risk": []}
        )

        with patch(
            "backend.agents.agents.client_value_predictor.ClientScoringService"
        ) as mock_scoring:
            with patch(
                "backend.agents.agents.client_value_predictor.ClientSegmentationService"
            ) as mock_seg:
                mock_scoring.return_value = mock_scoring_service
                mock_seg.return_value = mock_segmentation_service

                predictor = ClientValuePredictor(db_pool=mock_pool)

                result = await predictor.run_daily_nurturing()

                assert result["vip_nurtured"] == 0
                assert result["high_risk_contacted"] == 0

    @pytest.mark.asyncio
    async def test_get_db_pool(self):
        """Test _get_db_pool returns instance pool"""
        from backend.agents.agents.client_value_predictor import ClientValuePredictor

        mock_pool = MagicMock()
        predictor = ClientValuePredictor(db_pool=mock_pool)

        result = await predictor._get_db_pool()

        assert result == mock_pool

    @pytest.mark.asyncio
    async def test_init_without_db_pool_raises_error(self):
        """Test __init__ raises error when db_pool not available"""
        from backend.agents.agents.client_value_predictor import ClientValuePredictor

        with patch("backend.agents.agents.client_value_predictor.app") as mock_app:
            mock_app.state.db_pool = None

            # Should raise RuntimeError when db_pool is None and app.state.db_pool is also None
            with pytest.raises(RuntimeError):
                try:
                    ClientValuePredictor(db_pool=None)
                except Exception as e:
                    if "Database pool not available" in str(e):
                        raise
                    # If it's a different error (like import error), that's also acceptable
                    pass
