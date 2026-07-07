"""FastAPI entrypoint for the Nuzantara V6 graph engine."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nuzantara_graph.api.middleware import RequestTracingMiddleware
from nuzantara_graph.api.routes import health_router, router
from nuzantara_graph.config import settings
from nuzantara_graph.dependencies import close_services, get_services
from nuzantara_graph.graph.builder import build_graph
from nuzantara_graph.observability import setup_structlog

# Configure structured JSON logs for Fly.io log drain at startup
setup_structlog(log_level=settings.log_level)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "starting",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # Startup: initialize services + compile graph
    services = await get_services()
    app.state.services = services

    # Ensure semantic cache Qdrant collection exists
    await services.cache.ensure_collection(services.vector_store.client)

    graph = build_graph(services=services)
    app.state.compiled_graph = graph.compile()

    logger.info("graph_compiled", nodes=len(graph.nodes))

    yield

    # Shutdown: close all connections
    await close_services()
    logger.info("shutting_down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health_router)
app.include_router(router)
