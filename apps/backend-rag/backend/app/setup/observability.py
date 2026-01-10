"""
Observability Configuration Module

Handles Prometheus metrics and OpenTelemetry tracing setup.
Supports both local Jaeger (gRPC) and Grafana Cloud (HTTP with auth).
"""

import logging

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from backend.app.core.config import settings

logger = logging.getLogger("zantara.backend")

# --- OpenTelemetry (optional - only when enabled via OTEL_ENABLED=true) ---
OTEL_AVAILABLE = False
OTEL_HTTP_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OTEL_AVAILABLE = True

    # Check for HTTP exporter (needed for Grafana Cloud)
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as OTLPHttpSpanExporter,
        )

        OTEL_HTTP_AVAILABLE = True
    except ImportError:
        pass

    # Check for gRPC exporter (needed for local Jaeger)
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as OTLPGrpcSpanExporter,
        )
    except ImportError:
        pass

except ImportError:
    pass  # OpenTelemetry not installed - skip tracing


def setup_observability(app: FastAPI) -> None:
    """
    Setup observability stack: Prometheus metrics and OpenTelemetry tracing.

    Supports two modes:
    - Local Jaeger: gRPC exporter without auth (when OTEL_EXPORTER_HEADERS is not set)
    - Grafana Cloud: HTTP exporter with Basic auth (when OTEL_EXPORTER_HEADERS is set)

    Args:
        app: FastAPI application instance
    """
    # --- Observability: Metrics (Prometheus) ---
    Instrumentator().instrument(app).expose(app)

    # --- Observability: Tracing (Jaeger/OpenTelemetry/Grafana Cloud) ---
    if OTEL_AVAILABLE and settings.otel_enabled:
        try:
            resource = Resource.create(
                attributes={
                    "service.name": settings.otel_service_name,
                    "service.namespace": "nuzantara",
                    "deployment.environment": settings.environment,
                }
            )
            trace.set_tracer_provider(TracerProvider(resource=resource))

            # Choose exporter based on whether auth headers are provided
            if settings.otel_exporter_headers:
                # Grafana Cloud mode: HTTP with authentication
                if not OTEL_HTTP_AVAILABLE:
                    logger.warning(
                        "⚠️ OTEL_EXPORTER_HEADERS set but HTTP exporter not available. "
                        "Install: pip install opentelemetry-exporter-otlp-proto-http"
                    )
                else:
                    # Parse headers (format: "Key=Value" or "Key=Value,Key2=Value2")
                    headers = {}
                    for header in settings.otel_exporter_headers.split(","):
                        if "=" in header:
                            key, value = header.split("=", 1)
                            headers[key.strip()] = value.strip()

                    otlp_exporter = OTLPHttpSpanExporter(
                        endpoint=f"{settings.otel_exporter_endpoint}/v1/traces",
                        headers=headers,
                    )
                    trace.get_tracer_provider().add_span_processor(
                        BatchSpanProcessor(otlp_exporter)
                    )
                    # Skip FastAPIInstrumentor to avoid conflicts with @app.on_event handlers
                    # The instrumentation can cause infinite loops when combined with event handlers
                    # Tracing will still work for manual spans, but automatic FastAPI instrumentation is disabled
                    logger.warning(
                        "⚠️ Skipping FastAPIInstrumentor.instrument_app() to avoid conflicts with @app.on_event handlers"
                    )
                    logger.info(
                        f"✅ OpenTelemetry tracing enabled (Grafana Cloud) → {settings.otel_exporter_endpoint} (manual spans only)"
                    )
            else:
                # Local Jaeger mode: gRPC without authentication
                otlp_exporter = OTLPGrpcSpanExporter(
                    endpoint=settings.otel_exporter_endpoint,
                    insecure=True,  # Required for local Jaeger without TLS
                )
                trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
                # Skip FastAPIInstrumentor to avoid conflicts with @app.on_event handlers
                # The instrumentation can cause infinite loops when combined with event handlers
                # Tracing will still work for manual spans, but automatic FastAPI instrumentation is disabled
                logger.warning(
                    "⚠️ Skipping FastAPIInstrumentor.instrument_app() to avoid conflicts with @app.on_event handlers"
                )
                logger.info(
                    f"✅ OpenTelemetry tracing enabled (Jaeger) → {settings.otel_exporter_endpoint} (manual spans only)"
                )

        except Exception as e:
            logger.warning(f"⚠️ Failed to setup OpenTelemetry tracing: {e}")

    elif settings.otel_enabled and not OTEL_AVAILABLE:
        logger.warning(
            "⚠️ OTEL_ENABLED=true but OpenTelemetry packages not installed. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp-proto-grpc "
            "opentelemetry-exporter-otlp-proto-http"
        )

    logger.info(
        "✅ Observability: Prometheus metrics enabled"
        + (" + OpenTelemetry tracing" if (OTEL_AVAILABLE and settings.otel_enabled) else "")
    )
