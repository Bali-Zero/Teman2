"""
Test Sentry initialization is conditional and doesn't run in tests.

Verifies that Sentry initialization:
- Can be skipped via SKIP_SENTRY_INIT env var
- Doesn't initialize when DSN is not set
- Only initializes when DSN is present and skip flag is not set
"""

import importlib
import os
from unittest.mock import patch


class TestSentryInitialization:
    """Test Sentry initialization behavior."""

    def test_sentry_not_initialized_when_skip_flag_set(self):
        """Test Sentry doesn't initialize when SKIP_SENTRY_INIT is set."""
        with patch.dict(os.environ, {"SKIP_SENTRY_INIT": "1", "SENTRY_DSN": "test-dsn"}):
            with patch("sentry_sdk.init") as mock_sentry_init:
                # Re-import to trigger initialization check
                import app.main_cloud
                importlib.reload(app.main_cloud)

                # Sentry should not be initialized
                mock_sentry_init.assert_not_called()

    def test_sentry_not_initialized_when_no_dsn(self):
        """Test Sentry doesn't initialize when DSN is not set."""
        # Remove SENTRY_DSN and SKIP_SENTRY_INIT
        env_vars = {k: v for k, v in os.environ.items() if k not in ["SENTRY_DSN", "SKIP_SENTRY_INIT"]}
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("sentry_sdk.init") as mock_sentry_init:
                import importlib
                import app.main_cloud
                importlib.reload(app.main_cloud)

                # Sentry should not be initialized without DSN
                mock_sentry_init.assert_not_called()

    def test_sentry_initialized_when_dsn_present(self):
        """Test Sentry initializes when DSN is configured."""
        with patch.dict(
            os.environ,
            {
                "SKIP_SENTRY_INIT": "",
                "SENTRY_DSN": "https://test@sentry.io/123",
                "ENVIRONMENT": "production",
            },
        ):
            with patch("sentry_sdk.init") as mock_sentry_init:
                import importlib
                import app.main_cloud
                importlib.reload(app.main_cloud)

                # Sentry should be initialized
                mock_sentry_init.assert_called_once()
                # Verify it was called with correct parameters
                call_kwargs = mock_sentry_init.call_args[1]
                assert call_kwargs["dsn"] == "https://test@sentry.io/123"
                assert call_kwargs["environment"] == "production"

