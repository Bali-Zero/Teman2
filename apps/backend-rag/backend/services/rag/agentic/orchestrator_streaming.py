"""
Orchestrator Streaming Manager

Responsabilità singola: SSE event generation e streaming logic.
Include:
- Event validation e schema checking
- Error event generation
- Stream event formatting
- Event error counting e abort logic

Questo modulo è testabile in isolamento mockando event sources.
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel, ValidationError

from backend.app.metrics import metrics_collector

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Info level for streaming operations (verbose)


class StreamEvent(BaseModel):
    """Schema per eventi stream."""

    type: str
    data: Any
    timestamp: float | None = None
    correlation_id: str | None = None

    class Config:
        arbitrary_types_allowed = True


class OrchestratorStreamingManager:
    """
    Gestisce SSE event generation e streaming logic.

    Responsabilità:
    - Valida event structure
    - Genera error events standardizzati
    - Gestisce event error counting
    - Formatta events per SSE
    """

    def __init__(self, max_event_errors: int = 10, event_validation_enabled: bool = True) -> None:
        """
        Inizializza il streaming manager.

        Args:
            max_event_errors: Max errori prima di abortire stream
            event_validation_enabled: Se abilitare validazione schema eventi
        """
        self._max_event_errors = max_event_errors
        self._event_validation_enabled = event_validation_enabled

    def create_error_event(
        self,
        error_type: str,
        message: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """
        Crea standardized error event.

        Args:
            error_type: Tipo di errore
            message: Messaggio errore
            correlation_id: Correlation ID per tracing

        Returns:
            Dict con error event structure
        """
        return {
            "type": "error",
            "data": {
                "error_type": error_type,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": time.time(),
            },
            "timestamp": time.time(),
        }

    def validate_event(self, raw_event: Any, correlation_id: str) -> dict[str, Any] | None:
        """
        Valida event structure secondo StreamEvent schema.

        Args:
            raw_event: Event raw da validare
            correlation_id: Correlation ID per error reporting

        Returns:
            Event validato come dict, o None se validation failed
        """
        if raw_event is None:
            logger.warning(
                "⚠️ [Stream] None event received",
                extra={"correlation_id": correlation_id},
            )
            metrics_collector.stream_event_none_total.inc()
            return None

        if not isinstance(raw_event, dict):
            logger.error(
                f"❌ [Stream] Invalid event type: {type(raw_event)}",
                extra={
                    "correlation_id": correlation_id,
                    "event_type": str(type(raw_event)),
                },
            )
            metrics_collector.stream_event_invalid_type_total.inc()
            return None

        # Validate event schema
        if self._event_validation_enabled:
            try:
                validated_event = StreamEvent(**raw_event)
                return validated_event.model_dump(exclude_none=True)
            except ValidationError as e:
                logger.error(
                    f"❌ [Stream] Event validation failed: {e}",
                    extra={
                        "correlation_id": correlation_id,
                        "validation_errors": str(e.errors()),
                        "raw_event": str(raw_event)[:200],
                    },
                )
                metrics_collector.stream_event_validation_failed_total.inc()
                return None
        else:
            # Skip validation but return as-is
            return raw_event

    async def process_event_stream(
        self,
        event_generator: AsyncGenerator[dict, None],
        correlation_id: str,
        user_id: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Processa stream di events con validazione e error handling.

        Args:
            event_generator: AsyncGenerator che produce raw events
            correlation_id: Correlation ID per tracing
            user_id: User ID per logging

        Yields:
            Events validati e formattati
        """
        event_error_count = 0

        async for raw_event in event_generator:
            try:
                # Validate event
                event = self.validate_event(raw_event, correlation_id)

                if event is None:
                    event_error_count += 1
                    if event_error_count >= self._max_event_errors:
                        yield self.create_error_event(
                            "too_many_errors",
                            "Stream aborted due to too many malformed events",
                            correlation_id,
                        )
                        break
                    continue

                # Yield validated event
                yield event

            except Exception as e:
                event_error_count += 1
                # Use error classification for better error handling
                from backend.app.core.error_classification import (
                    ErrorClassifier,
                    get_error_context,
                )

                error_category, error_severity = ErrorClassifier.classify_error(e)
                error_context = get_error_context(
                    e,
                    correlation_id=correlation_id,
                    user_id=user_id,
                    event_error_count=event_error_count,
                )

                logger.exception(
                    "❌ [Stream] Unexpected error processing event", extra=error_context,
                )
                metrics_collector.stream_event_processing_error_total.inc()

                if event_error_count >= self._max_event_errors:
                    yield self.create_error_event(
                        "processing_error", f"Stream aborted: {str(e)}", correlation_id,
                    )
                    break

    def create_initial_status_event(self, correlation_id: str) -> dict[str, Any]:
        """
        Crea initial status event per stream start.

        Args:
            correlation_id: Correlation ID

        Returns:
            Status event dict
        """
        return {
            "type": "status",
            "data": {"status": "processing", "correlation_id": correlation_id},
            "timestamp": time.time(),
        }

    def create_done_event(
        self,
        execution_time: float,
        route_used: str,
        evidence_score: float | None = None,
        confidence_zone: str | None = None,
    ) -> dict[str, Any]:
        """
        Crea done event per stream completion.

        Args:
            execution_time: Durata esecuzione
            route_used: Route usata per processing
            evidence_score: Optional evidence score from RAG pipeline
            confidence_zone: Optional confidence zone (ABSTAIN/CAUTIOUS/NORMAL)

        Returns:
            Done event dict
        """
        data: dict[str, Any] = {
            "execution_time": round(execution_time, 2),
            "route_used": route_used,
        }
        if evidence_score is not None:
            data["evidence_score"] = round(evidence_score, 3)
        if confidence_zone is not None:
            data["confidence_zone"] = confidence_zone
        return {"type": "done", "data": data}

    def create_metadata_event(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Crea metadata event.

        Args:
            metadata: Dict con metadata da includere

        Returns:
            Metadata event dict
        """
        return {
            "type": "metadata",
            "data": metadata,
            "timestamp": time.time(),
        }

    async def stream_text_response(
        self,
        text: str,
        status: str = "success",
        route: str = "direct",
        delay: float = 0.01,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream semplice text response token-by-token.

        Utile per gate responses (greeting, identity, etc.).

        Args:
            text: Testo da streamare
            status: Status metadata
            route: Route metadata
            delay: Delay tra token (secondi)

        Yields:
            Stream events
        """
        import re

        yield self.create_metadata_event({"status": status, "route": route})

        tokens = re.findall(r"\S+|\s+", text)
        for token in tokens:
            yield {"type": "token", "data": token}
            await asyncio.sleep(delay)

        yield {"type": "done", "data": None}
