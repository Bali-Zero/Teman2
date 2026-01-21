"""
Main application entry point (compatibility alias).

This module re-exports everything from main_cloud.py for backward compatibility
with tests and imports that reference 'backend.app.main'.

The actual application is defined in main_cloud.py.
"""

# Explicit imports instead of wildcard for better type checking and IDE support
from backend.app.main_cloud import (
    app,
    initialize_services,
    initialize_plugins,
    on_startup,
    on_shutdown,
    _parse_history,
    _allowed_origins,
    _safe_endpoint_label,
)

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
