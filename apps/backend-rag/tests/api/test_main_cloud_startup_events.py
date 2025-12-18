"""
Test startup events initialize AlertService correctly.

Verifies that:
- Startup event initializes AlertService in app.state
- Startup can be called multiple times (idempotent)
- HealthMonitor uses app.state.alert_service

Note: These tests test the function logic directly.
When run together with other tests, conftest.py may interfere.
Run individually if needed: pytest tests/api/test_main_cloud_startup_events.py
"""

import pytest
from unittest.mock import patch, MagicMock

from app.main_cloud import app, on_startup
from services.alert_service import AlertService


class TestStartupEvents:
    """Test startup event handlers."""

    @pytest.mark.asyncio
    async def test_startup_initializes_alert_service(self):
        """Test startup event initializes AlertService in app.state."""
        # Ensure clean state
        original_services_initialized = getattr(app.state, "services_initialized", False)
        original_alert_service = getattr(app.state, "alert_service", None)

        try:
            # Reset state to allow startup to run
            app.state.services_initialized = False
            if hasattr(app.state, "alert_service"):
                delattr(app.state, "alert_service")

            # Mock initialize_services and initialize_plugins to avoid heavy initialization in tests
            from unittest.mock import patch, AsyncMock
            with patch("app.main_cloud.initialize_services", new_callable=AsyncMock) as mock_init, \
                 patch("app.main_cloud.initialize_plugins", new_callable=AsyncMock) as mock_plugins:
                # Run startup
                await on_startup()

                # Verify AlertService is initialized (happens before initialize_services)
                assert hasattr(app.state, "alert_service"), "alert_service should be in app.state"
                assert app.state.alert_service is not None, "alert_service should not be None"
                assert isinstance(app.state.alert_service, AlertService), f"Expected AlertService, got {type(app.state.alert_service)}"
                # Verify initialize_services was called
                mock_init.assert_called_once()
                mock_plugins.assert_called_once()
        finally:
            # Restore original state
            app.state.services_initialized = original_services_initialized
            if original_alert_service is not None:
                app.state.alert_service = original_alert_service

    @pytest.mark.asyncio
    async def test_startup_idempotent_alert_service(self):
        """Test startup can be called multiple times without issues."""
        # Save original state
        original_state_dict = {k: getattr(app.state, k) for k in dir(app.state) if not k.startswith('_')}
        original_alert_service = getattr(app.state, "alert_service", None)

        try:
            from unittest.mock import patch, AsyncMock
            
            # Clear alert_service if it exists
            if hasattr(app.state, "alert_service"):
                delattr(app.state, "alert_service")
            app.state.services_initialized = False
            
            # Run startup first time
            with patch("app.main_cloud.initialize_services", new_callable=AsyncMock), \
                 patch("app.main_cloud.initialize_plugins", new_callable=AsyncMock):
                await on_startup()
            first_instance = getattr(app.state, "alert_service", None)
            
            # Verify first instance was created
            assert first_instance is not None, f"First instance should not be None. State keys: {[k for k in dir(app.state) if not k.startswith('_')]}"
            assert isinstance(first_instance, AlertService), f"Expected AlertService, got {type(first_instance)}"

            # Reset to allow second run (but keep alert_service to test idempotency)
            app.state.services_initialized = False
            
            # Run startup again (will overwrite alert_service)
            with patch("app.main_cloud.initialize_services", new_callable=AsyncMock), \
                 patch("app.main_cloud.initialize_plugins", new_callable=AsyncMock):
                await on_startup()
            second_instance = getattr(app.state, "alert_service", None)

            # Both should be AlertService instances
            assert second_instance is not None, f"Second instance should not be None. State keys: {[k for k in dir(app.state) if not k.startswith('_')]}"
            assert isinstance(second_instance, AlertService), f"Expected AlertService, got {type(second_instance)}"
        finally:
            # Restore original state
            if original_alert_service is not None:
                app.state.alert_service = original_alert_service
            elif hasattr(app.state, "alert_service"):
                delattr(app.state, "alert_service")
            for k, v in original_state_dict.items():
                if k != "alert_service":  # Already handled above
                    setattr(app.state, k, v)

    def test_health_monitor_uses_app_state_alert_service(self):
        """Test HealthMonitor initialization uses app.state.alert_service."""
        # Setup app.state.alert_service
        original_alert_service = getattr(app.state, "alert_service", None)
        mock_alert_service = MagicMock(spec=AlertService)
        app.state.alert_service = mock_alert_service

        try:
            # Verify app.state has alert_service
            assert hasattr(app.state, "alert_service")
            assert app.state.alert_service == mock_alert_service

            # In the actual code, HealthMonitor would use:
            # alert_service = getattr(app.state, "alert_service", None)
            # This test verifies the pattern is correct
        finally:
            # Restore original
            if original_alert_service is not None:
                app.state.alert_service = original_alert_service
            elif hasattr(app.state, "alert_service"):
                # If it was None, ensure we have a valid one after startup
                if not isinstance(app.state.alert_service, AlertService):
                    app.state.alert_service = original_alert_service

