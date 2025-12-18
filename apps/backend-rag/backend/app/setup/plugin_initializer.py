"""
Plugin Initialization Module

Handles initialization of plugin system by discovering and registering all plugins.

Plugins are auto-discovered from the plugins/ directory and registered
in the global PluginRegistry.
"""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger("zantara.backend")


async def initialize_plugins(app: FastAPI) -> None:
    """
    Initialize plugin system by discovering and registering all plugins.

    Plugins are auto-discovered from the plugins/ directory and registered
    in the global PluginRegistry.

    Args:
        app: FastAPI application instance
    """
    try:
        from core.plugins import registry

        # Get plugins directory relative to backend root
        backend_root = Path(__file__).parent.parent.parent
        plugins_dir = backend_root / "plugins"

        # Ensure backend parent is in path for plugin imports
        backend_parent = backend_root.parent
        if str(backend_parent) not in sys.path:
            sys.path.insert(0, str(backend_parent))

        logger.info(f"Discovering plugins in {plugins_dir}...")
        # Use 'plugins' prefix since backend parent is now in path
        await registry.discover_plugins(plugins_dir, package_prefix="plugins")

        stats = registry.get_statistics()
        logger.info(
            f"Plugin System: Discovered {stats['total_plugins']} plugins in {stats['categories']} categories"
        )

        # Store registry in app state for health endpoints
        app.state.plugin_registry = registry

    except Exception as e:
        logger.error(f"Failed to initialize plugin system: {e}", exc_info=True)
        # Don't fail startup - plugins are non-critical
        app.state.plugin_registry = None

