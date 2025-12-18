"""
ZANTARA MEDIA - FastAPI Application
Content Intelligence & Distribution Platform
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    content,
    distribution,
    intel,
    dashboard,
    ai_writer,
    media,
    automation,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize services
    # Initialize database pool (optional for now)
    try:
        from app.db.connection import get_db_pool

        if settings.database_url:
            pool = await get_db_pool()
            logger.info("Database connection pool initialized")
        else:
            logger.warning("DATABASE_URL not configured, running without database")
    except Exception as e:
        logger.warning(
            f"Database initialization failed: {e}. Running without database."
        )

    # Initialize scheduler for automated content generation (optional)
    try:
        from app.services.scheduler import scheduler_service

        await scheduler_service.start()
        logger.info("Automation scheduler started")
    except Exception as e:
        logger.warning(
            f"Scheduler initialization failed: {e}. Running without scheduler."
        )

    # TODO: Initialize Redis connection

    yield

    # Shutdown
    logger.info("Shutting down ZANTARA MEDIA...")

    # Cleanup connections
    # Stop scheduler
    try:
        from app.services.scheduler import scheduler_service

        await scheduler_service.stop()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")

    # Close database
    try:
        from app.db.connection import close_db_pool

        await close_db_pool()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning(f"Error closing database: {e}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Content Intelligence & Distribution Platform for Bali Zero",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


# Include Routers
app.include_router(
    dashboard.router,
    prefix=f"{settings.api_prefix}/dashboard",
    tags=["Dashboard"],
)

app.include_router(
    content.router,
    prefix=f"{settings.api_prefix}/content",
    tags=["Content"],
)

app.include_router(
    distribution.router,
    prefix=f"{settings.api_prefix}/distribution",
    tags=["Distribution"],
)

app.include_router(
    intel.router,
    prefix=f"{settings.api_prefix}/intel",
    tags=["Intel Signals"],
)

app.include_router(
    ai_writer.router,
    prefix=f"{settings.api_prefix}/ai",
    tags=["AI Writer"],
)

app.include_router(
    media.router,
    prefix=f"{settings.api_prefix}/media",
    tags=["Media Generation"],
)

app.include_router(
    automation.router,
    prefix=f"{settings.api_prefix}/automation",
    tags=["Automation"],
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "description": "Content Intelligence & Distribution Platform",
        "docs": "/docs" if settings.debug else "Disabled in production",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug,
    )
