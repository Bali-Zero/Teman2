"""
Heavy RAG process entrypoint — RAG, KG, AI agents, embeddings.

Process group: 'rag' (shared-cpu-2x, 2GB RAM)
Routers: heavy routers (require SearchService + ZantaraAIClient)
Startup: ~30s (full service init with Qdrant + LLM warmup)

Run via: uvicorn backend.app.main_rag:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.app.setup.sentry_config import init_sentry

if TYPE_CHECKING:
    from fastapi import FastAPI

init_sentry()

logger = logging.getLogger("zantara.backend")


def create_rag_app() -> FastAPI:
    from fastapi import FastAPI, HTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from backend.app.core.config import settings
    from backend.app.setup.app_factory import lifespan as lifespan_full
    from backend.app.setup.exception_handlers import (
        general_exception_handler,
        http_exception_handler,
        starlette_http_exception_handler,
    )
    from backend.app.setup.logging_config import configure_logging
    from backend.app.setup.middleware_config import register_middleware
    from backend.app.setup.router_registration import include_heavy_routers

    configure_logging()

    rag = FastAPI(
        title="Zantara RAG Worker",
        description="Heavy RAG/KG/AI process — SearchService + ZantaraAIClient",
        version=getattr(settings, "VERSION", "5.2.0"),
        lifespan=lifespan_full,
        docs_url="/docs" if getattr(settings, "ENVIRONMENT", "production") != "production" else None,
        redoc_url=None,
    )

    rag.add_exception_handler(HTTPException, http_exception_handler)
    rag.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    rag.add_exception_handler(Exception, general_exception_handler)

    register_middleware(rag)
    include_heavy_routers(rag)

    return rag


app = create_rag_app()
