"""
CORS Configuration Module

Handles CORS middleware configuration for FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings


def get_allowed_origins() -> list[str]:
    """Get allowed CORS origins from settings"""
    origins = []

    # Production origins from settings
    if settings.zantara_allowed_origins:
        origins.extend(
            [
                origin.strip()
                for origin in settings.zantara_allowed_origins.split(",")
                if origin.strip()
            ],
        )

    # Development origins from settings (if configured)
    if hasattr(settings, "dev_origins") and settings.dev_origins:
        origins.extend(
            [origin.strip() for origin in settings.dev_origins.split(",") if origin.strip()],
        )

    # Default production origins
    default_origins = [
        "https://balizero.com",  # Primary production domain
        "https://www.balizero.com",  # Primary production domain (www)
        "https://kita.balizero.com",  # Admin dashboard
        "https://www.kita.balizero.com",
        "https://my.balizero.com",  # Portal clienti
        "https://www.my.balizero.com",
        "https://mail.balizero.com",  # Mail subdomain
        "https://calendar.balizero.com",  # Calendar subdomain
        "https://drive.balizero.com",  # Drive subdomain
        "https://knowledge.balizero.com",  # Knowledge subdomain
        "https://visa.balizero.com",  # Visa Oracle product
        "https://nuzantara-mouth.vercel.app",  # Frontend Vercel deployment
        "http://localhost:3000",  # Local development
    ]

    # Always include defaults
    for origin in default_origins:
        if origin not in origins:
            origins.append(origin)

    return origins


def register_cors_middleware(app: FastAPI) -> None:
    """
    Register CORS middleware on FastAPI application.

    CORS middleware is added first so it wraps all downstream middleware and responses.
    Starlette wraps middleware in reverse order; the first added user-middleware is the outermost.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Correlation-ID",
            "X-CSRF-Token",
            "Cookie",
            "Accept",
            "Accept-Language",
        ],
    )
