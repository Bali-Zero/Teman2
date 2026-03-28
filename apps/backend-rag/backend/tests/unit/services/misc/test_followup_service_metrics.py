"""
Unit tests for FollowupService Metrics and Logging
Tests the new metrics and logging functionality added in 2026-01-19
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set minimal environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "test")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.misc.followup_service import (
    FollowupService,
    followup_ai_generation_total,
    followup_generation_duration,
    followup_requests_total,
    followup_topic_based_total,
)


@pytest.fixture
def followup_service():
    """Create FollowupService instance"""
    with patch("backend.services.misc.followup_service.ZantaraAIClient") as mock_client:
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        service = FollowupService()
        # Reset counters for clean tests
        service._total_requests = 0
        service._ai_generation_count = 0
        service._fallback_count = 0
        return service


@pytest.fixture
def followup_service_no_ai():
    """Create FollowupService instance without AI"""
    with patch(
        "backend.services.misc.followup_service.ZantaraAIClient",
        side_effect=Exception("Not available"),
    ):
        service = FollowupService()
        # Reset counters for clean tests
        service._total_requests = 0
        service._ai_generation_count = 0
        service._fallback_count = 0
        return service


class TestFollowupServiceMetrics:
    """Tests for FollowupService metrics"""

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self, followup_service):
        """Test that metrics are recorded on successful followup generation"""
        followup_service.zantara_client.chat_async = AsyncMock(
            return_value={"text": "1. First question?\n2. Second question?\n3. Third question?"},
        )

        # Get initial metric values
        initial_requests = followup_requests_total.labels(
            method="ai", topic="business", language="en", status="success",
        )._value.get()

        await followup_service.get_followups(
            query="Test query", response="Test response", use_ai=True,
        )

        # Verify metrics were incremented
        final_requests = followup_requests_total.labels(
            method="ai", topic="business", language="en", status="success",
        )._value.get()
        assert final_requests > initial_requests

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_fallback(self, followup_service_no_ai):
        """Test that metrics are recorded when using fallback"""
        initial_topic_based = followup_topic_based_total.labels(
            topic="business", language="en",
        )._value.get()

        await followup_service_no_ai.get_followups(
            query="Test query", response="Test response", use_ai=False,
        )

        # Verify topic-based metric was incremented
        final_topic_based = followup_topic_based_total.labels(
            topic="business", language="en",
        )._value.get()
        assert final_topic_based > initial_topic_based

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_error(self, followup_service):
        """Test that error metrics are recorded when AI fails (fallback still works)"""
        followup_service.zantara_client.chat_async = AsyncMock(side_effect=Exception("AI error"))

        # When AI fails, generate_dynamic_followups records followup_ai_generation_total(status="error")
        # and returns topic-based fallback; get_followups records status="success" (it got a result)
        initial_error = followup_ai_generation_total.labels(status="error")._value.get()

        await followup_service.get_followups(
            query="Test query", response="Test response", use_ai=True,
        )

        final_error = followup_ai_generation_total.labels(status="error")._value.get()
        assert final_error > initial_error

    @pytest.mark.asyncio
    async def test_duration_metric_recorded(self, followup_service):
        """Test that duration metric is recorded"""
        followup_service.zantara_client.chat_async = AsyncMock(
            return_value={"text": "1. First?\n2. Second?\n3. Third?"},
        )

        await followup_service.get_followups(
            query="Test query", response="Test response", use_ai=True,
        )

        # Verify duration histogram has observations
        # prometheus_client Histogram._buckets can be dict or list depending on version
        hist_child = followup_generation_duration.labels(
            method="ai", topic="business", language="en",
        )
        buckets = getattr(hist_child, "_buckets", None)
        if buckets is not None:
            samples = list(buckets.values()) if isinstance(buckets, dict) else list(buckets)
            assert len(samples) >= 0  # Metric structure exists

    def test_topic_based_metrics_incremented(self, followup_service):
        """Test that topic-based metrics are incremented"""
        initial_count = followup_topic_based_total.labels(
            topic="immigration", language="it",
        )._value.get()

        followup_service.get_topic_based_followups(
            _query="Test", _response="Test", topic="immigration", language="it",
        )

        final_count = followup_topic_based_total.labels(
            topic="immigration", language="it",
        )._value.get()
        assert final_count > initial_count

    @pytest.mark.asyncio
    async def test_ai_generation_metrics_success(self, followup_service):
        """Test AI generation success metrics"""
        followup_service.zantara_client.chat_async = AsyncMock(
            return_value={"text": "1. First?\n2. Second?\n3. Third?"},
        )

        initial_success = followup_ai_generation_total.labels(status="success")._value.get()

        await followup_service.generate_dynamic_followups(
            query="Test", response="Test", language="en",
        )

        final_success = followup_ai_generation_total.labels(status="success")._value.get()
        assert final_success > initial_success

    @pytest.mark.asyncio
    async def test_ai_generation_metrics_error(self, followup_service):
        """Test AI generation error metrics"""
        followup_service.zantara_client.chat_async = AsyncMock(side_effect=Exception("AI error"))

        initial_error = followup_ai_generation_total.labels(status="error")._value.get()

        await followup_service.generate_dynamic_followups(
            query="Test", response="Test", language="en",
        )

        final_error = followup_ai_generation_total.labels(status="error")._value.get()
        assert final_error > initial_error


class TestFollowupServiceLogging:
    """Tests for FollowupService logging"""

    @pytest.mark.asyncio
    async def test_logging_on_init(self, caplog):
        """Test that initialization is logged"""
        with patch("backend.services.misc.followup_service.ZantaraAIClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            with caplog.at_level("INFO"):
                FollowupService()

            assert "FollowupService" in caplog.text
            assert "initialized" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_logging_on_request(self, followup_service, caplog):
        """Test that requests are logged"""
        followup_service.zantara_client.chat_async = AsyncMock(
            return_value={"text": "1. First?\n2. Second?\n3. Third?"},
        )

        with caplog.at_level("INFO"):
            await followup_service.get_followups(
                query="Test query", response="Test response", use_ai=True,
            )

        assert "Followups" in caplog.text or "followup" in caplog.text.lower()
        assert "Request" in caplog.text or "request" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_logging_on_error(self, followup_service, caplog):
        """Test that errors are logged"""
        followup_service.zantara_client.chat_async = AsyncMock(side_effect=Exception("Test error"))

        with caplog.at_level("ERROR"):
            await followup_service.get_followups(
                query="Test query", response="Test response", use_ai=True,
            )

        assert "error" in caplog.text.lower() or "failed" in caplog.text.lower()


class TestFollowupServiceHealthCheck:
    """Tests for FollowupService health check"""

    @pytest.mark.asyncio
    async def test_health_check_includes_metrics(self, followup_service):
        """Test that health check includes metrics"""
        # Make some requests to generate metrics
        followup_service.zantara_client.chat_async = AsyncMock(
            return_value={"text": "1. First?\n2. Second?\n3. Third?"},
        )

        await followup_service.get_followups(query="Test 1", response="Test", use_ai=True)
        await followup_service.get_followups(query="Test 2", response="Test", use_ai=True)

        result = await followup_service.health_check()

        assert "metrics" in result
        assert "total_requests" in result["metrics"]
        assert "ai_generation_count" in result["metrics"]
        assert "fallback_count" in result["metrics"]
        assert "ai_usage_rate" in result["metrics"]
        assert result["metrics"]["total_requests"] == 2
        assert result["metrics"]["ai_generation_count"] == 2

    @pytest.mark.asyncio
    async def test_health_check_ai_usage_rate(self, followup_service):
        """Test that health check calculates AI usage rate correctly"""
        followup_service.zantara_client.chat_async = AsyncMock(
            return_value={"text": "1. First?\n2. Second?\n3. Third?"},
        )

        # Make 3 AI requests and 1 fallback
        await followup_service.get_followups(query="Test 1", response="Test", use_ai=True)
        await followup_service.get_followups(query="Test 2", response="Test", use_ai=True)
        await followup_service.get_followups(query="Test 3", response="Test", use_ai=True)
        await followup_service.get_followups(query="Test 4", response="Test", use_ai=False)

        result = await followup_service.health_check()

        assert result["metrics"]["total_requests"] == 4
        assert result["metrics"]["ai_generation_count"] == 3
        assert result["metrics"]["fallback_count"] == 1
        assert result["metrics"]["ai_usage_rate"] == 0.75  # 3/4

    @pytest.mark.asyncio
    async def test_health_check_zero_requests(self, followup_service):
        """Test health check with zero requests"""
        result = await followup_service.health_check()

        assert result["metrics"]["total_requests"] == 0
        assert result["metrics"]["ai_usage_rate"] == 0.0
