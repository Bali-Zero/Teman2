"""
ZANTARA Unified Plugin Architecture

This module provides the core plugin system for ZANTARA, enabling:
- Standardized plugin interfaces
- Plugin discovery and registration
- Lifecycle management
- Performance monitoring
- Caching and rate limiting
"""

from .executor import PluginExecutor, executor
from .plugin import (
    Plugin,
    PluginCategory,
    PluginInput,
    PluginMetadata,
    PluginOutput,
)
from .registry import PluginRegistry, registry

__all__ = [
    "Plugin",
    "PluginMetadata",
    "PluginInput",
    "PluginOutput",
    "PluginCategory",
    "PluginRegistry",
    "registry",
    "PluginExecutor",
    "executor",
]
