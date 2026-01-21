"""
Main application entry point (compatibility alias).

This module re-exports everything from main_cloud.py for backward compatibility
with tests and imports that reference 'backend.app.main'.

The actual application is defined in main_cloud.py.
"""

from backend.app.main_cloud import *  # noqa: F401, F403

__all__ = ["app"]
