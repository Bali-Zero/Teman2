"""
Light API process entrypoint — CRUD, auth, webhooks, admin.

Process group: 'api' (shared-cpu-1x, 1GB RAM)
Routers: light routers (no RAG/ML dependencies)
Startup: <5s (DB + Redis only, skips SearchService + ZantaraAIClient)

Run via: uvicorn backend.app.main_api:app --host 0.0.0.0 --port 8080
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.setup.sentry_config import init_sentry

init_sentry()

logger = logging.getLogger("zantara.backend")


def _make_wa_bot_generate(app: FastAPI):
    """Build the bot_generate_fn for the wa_outbox scheduler.

    v1.1 (Option B): wires the RAG orchestrator so the Meta-inbox bot actually
    auto-replies. Gated behind the WA_INBOX_BOT_AUTOREPLY flag inside
    generate_bot_reply — when off, it raises and the worker marks the row
    failed/retry (never a wrong send), preserving v1 behaviour by default.

    The pool is bound here via closure because process_outbox_once passes only
    the thread row to bot_generate_fn.
    """
    from backend.services.integrations.wa_inbox_bot import generate_bot_reply

    async def _bot_generate(thread: object) -> str:
        return await generate_bot_reply(app.state.db_pool, thread)

    return _bot_generate


async def _run_wa_outbox_scheduler(app: FastAPI) -> None:
    """Drain the wa_outbox send-queue by calling process_outbox_once in a loop.

    Hosted on the 'api' process group (always-on, single-worker) so exactly one
    scheduler runs. Tight-loops while draining (status == 'sent'), backs off to
    WA_OUTBOX_POLL_SECONDS when idle. Never crashes the app: per-tick exceptions
    are logged and the loop continues after a backoff.
    """
    from backend.services.integrations.wa_outbox_worker import process_outbox_once
    from backend.services.integrations.whatsapp_service import whatsapp_service

    interval = float(os.getenv("WA_OUTBOX_POLL_SECONDS", "3"))
    pool = app.state.db_pool
    bot_generate_fn = _make_wa_bot_generate(app)
    logger.info("✅ WA outbox scheduler started (poll=%ss)", interval)
    while True:
        try:
            status = await process_outbox_once(
                pool, whatsapp_service, bot_generate_fn
            )
            # Drain fast while sending, but always yield the loop (sleep(0)
            # would not starve asyncio, but a tiny throttle is safer under a
            # full queue per panel 2026-06-04). Back off fully when idle.
            await asyncio.sleep(0.1 if status == "sent" else interval)
        except asyncio.CancelledError:
            logger.info("🛑 WA outbox scheduler cancelled")
            raise
        except Exception:
            logger.exception("WA outbox scheduler tick failed; backing off")
            await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan_light(app: FastAPI):
    """
    Light lifespan: initializes DB + Redis only, skips RAG services.
    Background init so Fly.io health checks pass within grace period.
    """
    logger.info("🚀 [API PROCESS] Starting light init (DB + Redis)...")
    app.state.process_mode = "light"

    async def _background_light_init():
        from backend.app.setup.service_initializer import initialize_services_light

        try:
            await initialize_services_light(app)
        except Exception as e:
            logger.error("❌ [API PROCESS] DB init failed (degraded mode): %s", e)
            app.state.db_pool = None
            return

        # Background workers kill switch — see service_initializer.py note (2026-04-12 incident)
        if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
            logger.warning(
                "⚠️ DISABLE_BACKGROUND_WORKERS=1 — skipping Notification Scheduler "
                "+ WA outbox scheduler",
            )
            app.state.notification_scheduler = None
            app.state._wa_outbox_scheduler_task = None
        else:
            try:
                from backend.app.modules.notifications.scheduler import init_scheduler

                app.state.notification_scheduler = await init_scheduler(app.state.db_pool)
                logger.info("✅ Notification Scheduler initialized")
            except Exception as e:
                logger.warning("⚠️ Notification Scheduler failed: %s", e)

            # WA Meta inbox outbox scheduler — spawned HERE (not in the outer
            # lifespan) because app.state.db_pool is only set above, inside this
            # background init task; an outer-lifespan task could start with
            # db_pool=None (panel race-fix 2026-06-04). Guard on a real pool.
            if getattr(app.state, "db_pool", None) is not None:
                app.state._wa_outbox_scheduler_task = asyncio.create_task(
                    _run_wa_outbox_scheduler(app)
                )
            else:
                app.state._wa_outbox_scheduler_task = None
                logger.warning(
                    "⚠️ WA outbox scheduler NOT started — db_pool unavailable",
                )

    init_task = asyncio.create_task(_background_light_init())
    app.state._init_task = init_task

    yield

    # Shutdown: cancel the WA outbox scheduler BEFORE closing the pool it uses.
    logger.info("🛑 [API PROCESS] Shutting down...")
    wa_task = getattr(app.state, "_wa_outbox_scheduler_task", None)
    if wa_task is not None:
        wa_task.cancel()
        try:
            await wa_task
        except (asyncio.CancelledError, Exception):
            pass

    db_pool = getattr(app.state, "db_pool", None)
    if db_pool:
        await db_pool.close()
        logger.info("✅ DB pool closed")
    from backend.app.rag_proxy import close_proxy_client

    await close_proxy_client()
    from backend.services.integrations.wa_inbox_bot import close_rag_client

    await close_rag_client()


def create_api_app() -> FastAPI:
    from fastapi import HTTPException
    from fastapi.responses import ORJSONResponse
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
        docs_url="/docs"
        if getattr(settings, "ENVIRONMENT", "production") != "production"
        else None,
        redoc_url=None,
        default_response_class=ORJSONResponse,  # 3-10× faster JSON serialization (audit modernization 2026-05-18)
    )

    api.add_exception_handler(HTTPException, http_exception_handler)
    api.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    api.add_exception_handler(Exception, general_exception_handler)

    register_middleware(api)
    include_light_routers(api)

    # Proxy router: catches heavy routes and forwards to rag process
    # Must be added LAST (after all light routers)
    from backend.app.rag_proxy import create_proxy_router, is_proxy_enabled

    if is_proxy_enabled():
        api.include_router(create_proxy_router())
        logger.info("✅ RAG proxy router registered (forwarding to rag process)")
    else:
        logger.info("ℹ️ RAG proxy disabled (RAG_PROXY_ENABLED=false)")

    return api


app = create_api_app()
