"""
Observability Configuration Module

Handles Prometheus metrics and OpenTelemetry tracing setup.
"""

import logging

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings

logger = logging.getLogger("zantara.backend")

# --- OpenTelemetry (optional - only for local dev with Jaeger) ---
OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OTEL_AVAILABLE = True
except ImportError:
    pass  # OpenTelemetry not installed - skip tracing


def setup_observability(app: FastAPI) -> None:
    """
    Setup observability stack: Prometheus metrics and OpenTelemetry tracing.

    Args:
        app: FastAPI application instance
    """
    # --- Observability: Metrics (Prometheus) ---
    Instrumentator().instrument(app).expose(app)

    # --- Observability: Tracing (Jaeger/OpenTelemetry) ---
    # Only enable if OpenTelemetry is installed (for local dev with Jaeger)
    if OTEL_AVAILABLE:
        resource = Resource.create(attributes={"service.name": "nuzantara-backend"})
        trace.set_tracer_provider(TracerProvider(resource=resource))
        otlp_exporter = OTLPSpanExporter(
            endpoint="http://jaeger:4317",
            insecure=settings.log_level == "DEBUG",
        )
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
        FastAPIInstrumentor.instrument_app(app)

    logger.info(
        "✅ Full Stack Observability: Prometheus + OpenTelemetry + ErrorMonitoring + RateLimiting"
    )

