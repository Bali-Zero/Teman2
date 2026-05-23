"""
Application Setup Module

Centralizes all application setup logic including:
- Sentry configuration
- CORS configuration
- Observability setup (Prometheus, OpenTelemetry)
- Middleware registration
- Service initialization
- Plugin initialization
- Router registration
- Application factory
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "create_app": ("backend.app.setup.app_factory", "create_app"),
    "get_allowed_origins": ("backend.app.setup.cors_config", "get_allowed_origins"),
    "include_routers": ("backend.app.setup.router_registration", "include_routers"),
    "init_sentry": ("backend.app.setup.sentry_config", "init_sentry"),
    "initialize_plugins": ("backend.app.setup.plugin_initializer", "initialize_plugins"),
    "initialize_services": ("backend.app.setup.service_initializer", "initialize_services"),
    "register_cors_middleware": (
        "backend.app.setup.cors_config",
        "register_cors_middleware",
    ),
    "register_middleware": ("backend.app.setup.middleware_config", "register_middleware"),
    "setup_observability": ("backend.app.setup.observability", "setup_observability"),
}


def __getattr__(name: str) -> Any:
    """Resolve setup exports lazily so light API imports stay light."""
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value

__all__ = [
    "create_app",
    "get_allowed_origins",
    "include_routers",
    "init_sentry",
    "initialize_plugins",
    "initialize_services",
    "register_cors_middleware",
    "register_middleware",
    "setup_observability",
]
