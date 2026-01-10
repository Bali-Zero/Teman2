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

from backend.app.setup.app_factory import create_app
from backend.app.setup.cors_config import get_allowed_origins, register_cors_middleware
from backend.app.setup.middleware_config import register_middleware
from backend.app.setup.observability import setup_observability
from backend.app.setup.plugin_initializer import initialize_plugins
from backend.app.setup.router_registration import include_routers
from backend.app.setup.sentry_config import init_sentry
from backend.app.setup.service_initializer import initialize_services

__all__ = [
    "create_app",
    "get_allowed_origins",
    "include_routers",
    "initialize_plugins",
    "initialize_services",
    "init_sentry",
    "register_cors_middleware",
    "register_middleware",
    "setup_observability",
]
