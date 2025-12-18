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

from app.setup.app_factory import create_app
from app.setup.cors_config import get_allowed_origins, register_cors_middleware
from app.setup.middleware_config import register_middleware
from app.setup.observability import setup_observability
from app.setup.plugin_initializer import initialize_plugins
from app.setup.router_registration import include_routers
from app.setup.service_initializer import initialize_services
from app.setup.sentry_config import init_sentry

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
