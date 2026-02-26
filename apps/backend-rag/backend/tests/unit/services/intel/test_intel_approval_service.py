"""
Unit tests for IntelApprovalService.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, mock_open, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.intel.intel_approval_service import IntelApprovalService


class TestIntelApprovalService:
    """Test suite for IntelApprovalService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        with patch("backend.services.intel.intel_approval_service.settings") as mock_settings:
            mock_settings.get_intel_pending_path = "/tmp/pending"
            service = IntelApprovalService()
            service.pending_intel_path = Path("/tmp/pending")
            service.pending_intel_path.mkdir(exist_ok=True)
            yield service

    @pytest.fixture
    def mock_team_config(self):
        """Mock team configuration."""
        return {
            "type": "visa",
            "required_votes": 2,
            "approvers": [{"name": "Test User", "chat_id": 123456, "email": "test@example.com"}],
        }

    @pytest.fixture
    def mock_item_data(self):
        """Mock item data."""
        return {
            "item_id": "test_item_123",
            "title": "Test Article",
            "content": "Test content here",
            "source_name": "Test Source",
            "source_url": "https://example.com",
            "detected_at": "2026-01-13T00:00:00",
        }

    @patch("backend.services.intel.intel_approval_service.get_chat_ids")
    @patch("backend.services.intel.intel_approval_service.get_team_config")
    @patch("backend.services.intel.intel_approval_service.telegram_bot")
    @patch("builtins.open", create=True)
    async def test_send_approval_notification_success(
        self,
        mock_open,
        mock_bot,
        mock_get_config,
        mock_get_chat_ids,
        service,
        mock_team_config,
        mock_item_data,
    ):
        """Test successful approval notification."""
        mock_get_config.return_value = mock_team_config
        mock_get_chat_ids.return_value = [123456]
        mock_bot.send_message = AsyncMock()
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = lambda s, *a: None
        mock_open.return_value.write = lambda s: None

        result = await service.send_approval_notification("visa", "test_item_123", mock_item_data)

        assert result is True
        mock_bot.send_message.assert_called_once()

    @patch("backend.services.intel.intel_approval_service.get_chat_ids")
    @patch("backend.services.intel.intel_approval_service.get_team_config")
    async def test_send_approval_notification_no_config(
        self, mock_get_config, mock_get_chat_ids, service, mock_item_data
    ):
        """Test notification fails when no team config."""
        mock_get_config.return_value = None

        result = await service.send_approval_notification("visa", "test_item_123", mock_item_data)

        assert result is False

    @patch("backend.services.intel.intel_approval_service.get_chat_ids")
    @patch("backend.services.intel.intel_approval_service.get_team_config")
    async def test_send_approval_notification_no_chat_ids(
        self, mock_get_config, mock_get_chat_ids, service, mock_team_config, mock_item_data
    ):
        """Test notification fails when no chat IDs."""
        mock_get_config.return_value = mock_team_config
        mock_get_chat_ids.return_value = []

        result = await service.send_approval_notification("visa", "test_item_123", mock_item_data)

        assert result is False

    @patch("backend.services.intel.intel_approval_service.get_chat_ids")
    @patch("backend.services.intel.intel_approval_service.get_team_config")
    @patch("backend.services.intel.intel_approval_service.telegram_bot")
    async def test_send_approval_notification_with_image(
        self,
        mock_bot,
        mock_get_config,
        mock_get_chat_ids,
        service,
        mock_team_config,
        mock_item_data,
    ):
        """Test approval notification with image."""
        mock_get_config.return_value = mock_team_config
        mock_get_chat_ids.return_value = [123456]
        mock_bot.send_photo = AsyncMock()

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=b"fake_image_data")):
                result = await service.send_approval_notification(
                    "visa", "test_item_123", mock_item_data, image_path="/tmp/image.jpg"
                )

        assert result is True
        mock_bot.send_photo.assert_called_once()

    @patch("backend.services.intel.intel_approval_service.get_chat_ids")
    @patch("backend.services.intel.intel_approval_service.get_team_config")
    @patch("backend.services.intel.intel_approval_service.telegram_bot")
    @patch("builtins.open", create=True)
    async def test_send_approval_notification_with_enriched_data(
        self,
        mock_open,
        mock_bot,
        mock_get_config,
        mock_get_chat_ids,
        service,
        mock_team_config,
        mock_item_data,
    ):
        """Test approval notification with enriched data."""
        mock_get_config.return_value = mock_team_config
        mock_get_chat_ids.return_value = [123456]
        mock_bot.send_message = AsyncMock()
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = lambda s, *a: None
        mock_open.return_value.write = lambda s: None

        enriched_data = {
            "enriched_title": "Enriched Title",
            "enriched_summary": "Enriched summary",
            "key_points": ["Point 1", "Point 2"],
            "seo_keywords": ["keyword1", "keyword2"],
        }

        result = await service.send_approval_notification(
            "visa", "test_item_123", mock_item_data, enriched_data=enriched_data
        )

        assert result is True
        # Verify caption contains enriched data
        call_args = mock_bot.send_message.call_args
        assert "Enriched Title" in call_args[1]["text"]

    def test_build_notification_caption(self, service, mock_team_config, mock_item_data):
        """Test building notification caption."""
        caption = service._build_notification_caption(
            "visa", "test_item_123", mock_item_data, None, mock_team_config
        )

        assert "BALI ZERO INTELLIGENCE" in caption
        assert "Test Article" in caption
        assert "test_item_123" in caption

    def test_build_approval_keyboard(self, service):
        """Test building approval keyboard."""
        keyboard = service._build_approval_keyboard("visa", "test_item_123")

        assert "inline_keyboard" in keyboard
        assert len(keyboard["inline_keyboard"]) == 1
        assert len(keyboard["inline_keyboard"][0]) == 2
        assert "APPROVE" in keyboard["inline_keyboard"][0][0]["text"]
        assert "REJECT" in keyboard["inline_keyboard"][0][1]["text"]
