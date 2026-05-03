"""
FastAPI entrypoint for the ZANTARA RAG backend.

This module serves as the minimal entry point for uvicorn.
All application setup is delegated to app.setup.app_factory.create_app().

Run via: uvicorn app.main_cloud:app --host 0.0.0.0 --port 8080

BACKWARD COMPATIBILITY:
- Exports app, initialize_services, initialize_plugins, on_startup, on_shutdown
- Exports utility functions: _parse_history, _allowed_origins, _safe_endpoint_label
- All exports maintain backward compatibility with existing tests and code
"""

import json
import logging
from typing import Any
from urllib.parse import urlparse

from backend.app.setup.sentry_config import init_sentry

logger = logging.getLogger("zantara.backend")

# Initialize Sentry before creating app (must be first)
init_sentry()

# Create FastAPI application instance (lazy imports inside app_factory)
from backend.app.setup.app_factory import create_app

app = create_app()

# Backward compatibility: Export functions for tests and other modules
# These are used by tests and some agent code that imports directly from main_cloud

# Re-export initialization functions
__all__ = [
    "app",
    "initialize_services",
    "initialize_plugins",
    "on_startup",
    "on_shutdown",
    "_parse_history",
    "_allowed_origins",
    "_safe_endpoint_label",
]


# Backward compatibility: Import and re-export initialization functions
# These are used by tests and other modules that import from main or main_cloud
from backend.app.setup.plugin_initializer import initialize_plugins
from backend.app.setup.service_initializer import initialize_services


# Backward compatibility: Export startup/shutdown handlers
# These functions can be called directly by tests and maintain the same interface
async def on_startup() -> None:
    """
    Startup handler - backward compatibility export.

    This function replicates the original startup behavior for tests.
    It initializes AlertService and calls initialize_services/initialize_plugins.

    NOTE: In production, startup is handled by the lifespan context manager
    in app_factory.py. This function exists only for backward compatibility
    with tests that call on_startup() directly.
    """
    from backend.app.setup.plugin_initializer import initialize_plugins
    from backend.app.setup.service_initializer import initialize_services
    from backend.services.monitoring.alert_service import AlertService

    # Initialize AlertService at startup (avoid import-time instantiation)
    try:
        app.state.alert_service = AlertService()
    except Exception as e:
        logger.error(f"Failed to initialize AlertService: {e}")

    await initialize_services(app)
    await initialize_plugins(app)


async def on_shutdown() -> None:
    """
    Shutdown handler - backward compatibility export.

    This function replicates the original shutdown behavior for tests.
    Note: Actual shutdown handlers are registered via register_shutdown_handlers()
    in app_factory.py, but this function exists for backward compatibility.
    """
    logger.info("🛑 Shutting down ZANTARA services...")

    import asyncio
    import inspect
    from contextlib import suppress

    # Shutdown WebSocket Redis Listener
    redis_task = getattr(app.state, "redis_listener_task", None)
    if redis_task:
        cancel = getattr(redis_task, "cancel", None)
        if callable(cancel):
            cancel()

        if inspect.isawaitable(redis_task):
            with suppress(asyncio.CancelledError):
                await redis_task
        logger.info("✅ WebSocket Redis Listener stopped")

    # Shutdown Health Monitor
    health_monitor = getattr(app.state, "health_monitor", None)
    if health_monitor:
        await health_monitor.stop()
        logger.info("✅ Health Monitor stopped")

    # Shutdown Compliance Monitor
    compliance_monitor = getattr(app.state, "compliance_monitor", None)
    if compliance_monitor:
        await compliance_monitor.stop()
        logger.info("✅ Compliance Monitor stopped")

    # Shutdown Autonomous Scheduler (all agents)
    autonomous_scheduler = getattr(app.state, "autonomous_scheduler", None)
    if autonomous_scheduler:
        await autonomous_scheduler.stop()
        logger.info("✅ Autonomous Scheduler stopped (all agents terminated)")

    logger.info("✅ HTTP clients closed")
    logger.info("✅ ZANTARA shutdown complete")


# Backward compatibility: Export utility functions
def _parse_history(history_raw: str | None) -> list[dict[str, Any]]:
    """
    Parse conversation history from raw string.

    Args:
        history_raw: JSON string containing conversation history

    Returns:
        List of conversation dictionaries, empty list if invalid/empty
    """
    if not history_raw:
        return []
    try:
        parsed = json.loads(history_raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        import logging

        logger = logging.getLogger("zantara.backend")
        logger.warning("Invalid conversation_history payload received")
    return []


def _allowed_origins() -> list[str]:
    """Get allowed CORS origins - backward compatibility wrapper."""
    from backend.app.setup.cors_config import get_allowed_origins

    return get_allowed_origins()


def _safe_endpoint_label(url: str | None) -> str:
    """Return a minimal identifier for logging without leaking credentials."""
    if not url:
        return "unknown"
    parsed = urlparse(url)
    return parsed.netloc or parsed.path or "unknown"
