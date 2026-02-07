"""
FastAPI main application with graceful shutdown.

Handles:
- Application lifecycle
- Dependency initialization
- Graceful shutdown on SIGTERM
- Middleware setup
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from brotli_asgi import BrotliMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings
from backend.core.logger import get_logger, LogAction, set_component
from backend.db.connection import init_db, close_db
from backend.core.cache import init_cache, close_cache
from backend.core.task_queue import init_task_queue, stop_task_queue

# Import routers
from backend.app.routers import health
from backend.core.api_cache import APICacheMiddleware

logger = get_logger(__name__, component="main")

# Track shutdown event
_shutdown_event = asyncio.Event()


async def _handle_sigterm() -> None:
    """Handle SIGTERM signal for graceful shutdown."""
    logger.info(
        "SIGTERM received, initiating graceful shutdown",
        action=LogAction.START
    )
    _shutdown_event.set()


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""
    try:
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_handle_sigterm()))
            
        logger.info(
            "Signal handlers registered",
            action=LogAction.CONNECT
        )
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        logger.warning(
            "Signal handlers not supported on this platform",
            action=LogAction.SKIP
        )


async def initialize_services() -> None:
    """Initialize all required services."""
    logger.info(
        "Initializing services",
        action=LogAction.START
    )
    
    init_tasks = []
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized", action=LogAction.END)
    except Exception as e:
        logger.error(
            "Database initialization failed",
            action=LogAction.ERROR,
            metadata={"error": str(e)}
        )
        raise
    
    # Initialize cache
    try:
        await init_cache()
        logger.info("Cache initialized", action=LogAction.END)
    except Exception as e:
        logger.error(
            "Cache initialization failed",
            action=LogAction.ERROR,
            metadata={"error": str(e)}
        )
        # Non-critical, continue
    
    # Initialize task queue
    try:
        await init_task_queue()
        logger.info("Task queue initialized", action=LogAction.END)
    except Exception as e:
        logger.error(
            "Task queue initialization failed",
            action=LogAction.ERROR,
            metadata={"error": str(e)}
        )
        # Non-critical, continue
    
    logger.info(
        "All services initialized",
        action=LogAction.END
    )


async def shutdown_services() -> None:
    """Gracefully shutdown all services."""
    logger.info(
        "Shutting down services",
        action=LogAction.START
    )
    
    shutdown_order = [
        ("task_queue", stop_task_queue),
        ("cache", close_cache),
        ("database", close_db),
    ]
    
    for name, shutdown_func in shutdown_order:
        try:
            logger.info(
                f"Shutting down {name}",
                action=LogAction.START,
                metadata={"service": name}
            )
            await shutdown_func()
            logger.info(
                f"{name} shut down successfully",
                action=LogAction.END
            )
        except Exception as e:
            logger.error(
                f"Error shutting down {name}",
                action=LogAction.ERROR,
                metadata={"service": name, "error": str(e)}
            )
    
    logger.info(
        "Shutdown complete",
        action=LogAction.END
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan context manager.
    
    Handles startup and shutdown sequences.
    """
    # Startup
    set_component("main")
    
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version}",
        action=LogAction.START,
        metadata={
            "environment": settings.env.value,
            "debug": settings.debug
        }
    )
    
    setup_signal_handlers()
    await initialize_services()
    
    yield
    
    # Shutdown
    await shutdown_services()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Bali Intel Scraper - News processing pipeline",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add Brotli compression (better than gzip)
    app.add_middleware(
        BrotliMiddleware,
        minimum_size=1000,
        quality=4,  # Balance between compression and speed
    )
    
    # Add rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=100,
        excluded_paths=["/health", "/metrics", "/docs", "/redoc", "/openapi.json"],
        whitelisted_ips=["127.0.0.1", "::1"],
    )
    
    # Add API response caching middleware
    app.add_middleware(
        APICacheMiddleware,
        ttl=300,  # 5 minutes default
        exclude_paths=["/health", "/metrics", "/docs", "/redoc", "/openapi.json"],
    )
    
    # Add health tracking middleware
    from backend.app.routers.health import HealthTrackingMiddleware
    app.add_middleware(HealthTrackingMiddleware)
    
    # Include routers
    app.include_router(health.router)
    
    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.exception(
            "Unhandled exception",
            action=LogAction.ERROR,
            metadata={
                "path": request.url.path,
                "method": request.method
            }
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "request_id": get_logger(__name__).logger.handlers[0].request_id if hasattr(get_logger(__name__).logger.handlers[0], 'request_id') else None
            }
        )
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.env.value,
            "docs": "/docs" if not settings.is_production else None
        }
    
    # Version endpoint
    @app.get("/version")
    async def version():
        return {
            "version": settings.app_version,
            "build": os.getenv("BUILD_SHA", "unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return app


# Create the application instance
import os
from datetime import datetime
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=settings.debug,
        workers=1 if settings.debug else int(os.getenv("WORKERS", "4"))
    )
