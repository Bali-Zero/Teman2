"""Dependency injection container for the graph engine.

All service instances are created from Settings (Pydantic BaseSettings),
reading endpoints from environment variables. No hardcoded URLs.
"""

from __future__ import annotations

from functools import lru_cache

from nuzantara_graph.config import Settings, settings
from nuzantara_graph.services import Services


@lru_cache
def get_settings() -> Settings:
    return settings


_services: Services | None = None


async def get_services() -> Services:
    """Get or create the singleton Services container.

    Uses Settings to wire all real clients (Qdrant, PostgreSQL, Redis, Gemini).
    """
    global _services
    if _services is None:
        _services = Services.from_settings(get_settings())
    return _services


async def close_services() -> None:
    """Close all service connections (called on app shutdown)."""
    global _services
    if _services is not None:
        await _services.close()
        _services = None
