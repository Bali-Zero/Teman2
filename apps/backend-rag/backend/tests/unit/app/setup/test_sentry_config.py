"""
Unit tests for app/setup/sentry_config.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.sentry_config import init_sentry


class TestSentryConfig:
    """Tests for Sentry configuration"""

    def test_init_sentry_skip(self):
        """Test skipping Sentry initialization"""
        with patch.dict("os.environ", {"SKIP_SENTRY_INIT": "1"}):
            init_sentry()
            # Should not raise exception

    def test_init_sentry_no_dsn(self):
        """Test Sentry initialization without DSN"""
        with patch.dict("os.environ", {"SKIP_SENTRY_INIT": "", "SENTRY_DSN": ""}):
            init_sentry()
            # Should not raise exception

    def test_init_sentry_with_dsn(self):
        """Test Sentry initialization with DSN"""
        with patch.dict("os.environ", {
            "SKIP_SENTRY_INIT": "",
            "SENTRY_DSN": "https://test@sentry.io/123",
            "ENVIRONMENT": "development"
        }), patch("app.setup.sentry_config.sentry_sdk") as mock_sentry:
            init_sentry()
            mock_sentry.init.assert_called_once()

    def test_init_sentry_production(self):
        """Test Sentry initialization in production"""
        with patch.dict("os.environ", {
            "SKIP_SENTRY_INIT": "",
            "SENTRY_DSN": "https://test@sentry.io/123",
            "ENVIRONMENT": "production",
            "SENTRY_TRACES_SAMPLE_RATE": "0.5"
        }), patch("app.setup.sentry_config.sentry_sdk") as mock_sentry:
            init_sentry()
            mock_sentry.init.assert_called_once()

