"""
Light API process entrypoint — CRUD, auth, webhooks, admin.

Process group: 'api' (shared-cpu-1x, 1GB RAM)
Routers: light routers (no RAG/ML dependencies)
Startup: <5s (DB + Redis only, skips SearchService + ZantaraAIClient)

Run via: uvicorn backend.app.main_api:app --host 0.0.0.0 --port 8080
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.setup.sentry_config import init_sentry

init_sentry()

logger = logging.getLogger("zantara.backend")


@asynccontextmanager
async def lifespan_light(app: FastAPI):
    """
    Light lifespan: initializes DB + Redis only, skips RAG services.
    Background init so Fly.io health checks pass within grace period.
    """
    logger.info("🚀 [API PROCESS] Starting light init (DB + Redis)...")

    async def _background_light_init():
        from backend.app.setup.service_initializer import initialize_services_light
        await initialize_services_light(app)

        try:
            from backend.app.modules.notifications.scheduler import init_scheduler
            app.state.notification_scheduler = await init_scheduler(app.state.db_pool)
            logger.info("✅ Notification Scheduler initialized")
        except Exception as e:
            logger.warning(f"⚠️ Notification Scheduler failed: {e}")

    asyncio.create_task(_background_light_init())

    yield

    # Shutdown: close DB pool
    logger.info("🛑 [API PROCESS] Shutting down...")
    db_pool = getattr(app.state, "db_pool", None)
    if db_pool:
        await db_pool.close()
        logger.info("✅ DB pool closed")


def create_api_app() -> FastAPI:
    from fastapi import HTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from backend.app.core.config import settings
    from backend.app.setup.exception_handlers import (
        general_exception_handler,
        http_exception_handler,
        starlette_http_exception_handler,
    )
    from backend.app.setup.logging_config import configure_logging
    from backend.app.setup.middleware_config import register_middleware
    from backend.app.setup.router_registration import include_light_routers

    configure_logging()

    api = FastAPI(
        title="Zantara API Worker",
        description="Light CRUD/auth/webhook process — no RAG",
        version=getattr(settings, "VERSION", "5.2.0"),
        lifespan=lifespan_light,
        docs_url="/docs" if getattr(settings, "ENVIRONMENT", "production") != "production" else None,
        redoc_url=None,
    )

    api.add_exception_handler(HTTPException, http_exception_handler)
    api.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    api.add_exception_handler(Exception, general_exception_handler)

    register_middleware(api)
    include_light_routers(api)

    return api


app = create_api_app()
