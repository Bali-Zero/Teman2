"""
CORS Configuration Module

Handles CORS middleware configuration for FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


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
            ]
        )

    # Development origins from settings (if configured)
    if hasattr(settings, "dev_origins") and settings.dev_origins:
        origins.extend(
            [origin.strip() for origin in settings.dev_origins.split(",") if origin.strip()]
        )

    # Default production origins
    default_origins = [
        "https://zantara.balizero.com",
        "https://www.zantara.balizero.com",
        "https://nuzantara-mouth.fly.dev",  # Frontend Fly.io deployment (mouth)
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
        allow_methods=["*"],
        allow_headers=["*"],
    )

