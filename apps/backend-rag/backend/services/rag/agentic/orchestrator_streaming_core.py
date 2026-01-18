"""
Orchestrator Streaming Core - Streaming Query Processing Coordination

Responsabilità singola: Coordinamento del flusso di streaming query processing.
Include:
- Coordinamento context loading, gates, cache usando OrchestratorCore
- Gestione event generation e validation usando OrchestratorStreamingManager
- Coordinamento ReAct loop streaming
- Gestione follow-up questions generation
- Memory persistence dopo stream

Questo modulo coordina lo streaming usando tutti i moduli specializzati.
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from backend.app.utils.tracing import add_span_event

from .orchestrator_core import OrchestratorCore
from .orchestrator_streaming import OrchestratorStreamingManager
from .query_helpers import wrap_query_with_language_instruction

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class OrchestratorStreamingCore:
    """
    Core orchestrator per streaming query processing.

    Coordina tutti i moduli specializzati per lo streaming.
    """

    def __init__(
        self,
        core: OrchestratorCore,
        streaming_manager: OrchestratorStreamingManager,
    ):
        """
        Inizializza OrchestratorStreamingCore.

        Args:
            core: OrchestratorCore instance per logica comune
            streaming_manager: OrchestratorStreamingManager per event handling
        """
        self.core = core
        self.streaming_manager = streaming_manager

    async def stream_query_core(
        self,
        query: str,
        user_id: str,
        conversation_history: list[dict] | None,
        session_id: str | None,
        images: list[dict] | None,
        tool_execution_counter: dict[str, int],
        correlation_id: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Core streaming query processing logic.

        Args:
            query: Query string
            user_id: User ID
            conversation_history: Optional conversation history
            session_id: Optional session ID
            images: Optional vision images
            tool_execution_counter: Tool execution counter dict
            correlation_id: Correlation ID for tracing

        Yields:
            Stream events (dict)
        """
        start_time = time.time()

        # Yield initial status
        yield self.streaming_manager.create_initial_status_event(correlation_id)

        # 1. Prepare context (common logic)
        user_context, optimized_history, extracted_entities = await self.core.prepare_query_context(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history,
            session_id=session_id,
        )

        # Yield metadata for extracted entities
        if any(extracted_entities.values()):
            yield {
                "type": "metadata",
                "data": {"extracted_entities": extracted_entities},
                "timestamp": time.time(),
            }

        # 2. Check gates and cache (common logic)
        gate_or_cache_result = await self.core.check_gates_and_cache(
            query=query,
            user_context=user_context,
            history=optimized_history,
            extracted_entities=extracted_entities,
            start_time=start_time,
        )

        if gate_or_cache_result:
            # Stream gate/cache response
            async for event in self._stream_core_result(
                result=gate_or_cache_result,
                route_used=gate_or_cache_result.model_used or "gate",
            ):
                yield event
            return

        # 3. Prepare ReAct execution (common logic)
        model_tier, deep_think_mode, state, system_prompt = await self.core.prepare_react_execution(
            query=query,
            user_context=user_context,
            history=optimized_history,
            extracted_entities=extracted_entities,
            deep_think_mode=False,  # Will be determined by routing
        )

        # 4. Create chat session
        chat = self.core.llm_gateway.create_chat_with_history(
            history_to_use=optimized_history,
            model_tier=model_tier,
            system_instruction=system_prompt,
        )

        # 5. Execute ReAct loop streaming
        logger.info(f"🧠 [Stream] Processing query with ReAct loop for user {user_id}")

        add_span_event(
            "react.stream.start",
            {
                "model_tier": model_tier,
                "user_id": user_id,
            },
        )

        try:
            # Stream ReAct loop events
            async for raw_event in self.core.reasoning_engine.execute_react_loop_stream(
                state=state,
                llm_gateway=self.core.llm_gateway,
                chat=chat,
                initial_prompt=wrap_query_with_language_instruction(query),
                system_prompt=system_prompt,
                query=query,
                user_id=user_id or "anonymous",
                model_tier=model_tier,
                tool_execution_counter=tool_execution_counter,
                images=images,
            ):
                # Process and validate events
                async for event in self.streaming_manager.process_event_stream(
                    event_generator=self._single_event_generator(raw_event),
                    correlation_id=correlation_id,
                    user_id=user_id,
                ):
                    yield event

            # 6. Yield done event with metrics
            execution_time = time.time() - start_time
            route_used = "agentic" if tool_execution_counter["count"] > 0 else "direct"

            yield self.streaming_manager.create_done_event(
                execution_time=execution_time,
                route_used=route_used,
            )

        except Exception as e:
            logger.error(f"❌ [Stream] ReAct loop failed: {e}", exc_info=True)
            yield self.streaming_manager.create_error_event(
                error_type="react_loop_error",
                message=str(e),
                correlation_id=correlation_id,
            )

    async def _stream_core_result(
        self,
        result: Any,  # CoreResult
        route_used: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream a CoreResult as SSE events.

        Args:
            result: CoreResult to stream
            route_used: Route identifier

        Yields:
            Stream events
        """
        # Yield metadata
        yield {
            "type": "metadata",
            "data": {
                "status": "success",
                "route": route_used,
                "model_used": getattr(result, "model_used", route_used),
            },
            "timestamp": time.time(),
        }

        # Stream answer tokens
        answer = getattr(result, "answer", "")
        if answer:
            tokens = answer.split()
            for token in tokens:
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)

        # Yield sources if available
        sources = getattr(result, "sources", [])
        if sources:
            yield {"type": "sources", "data": sources}

        # Yield done
        execution_time = getattr(result, "timings", {}).get("total", 0.0)
        yield self.streaming_manager.create_done_event(
            execution_time=execution_time,
            route_used=route_used,
        )

    async def _single_event_generator(
        self, event: dict | None
    ) -> AsyncGenerator[dict | None, None]:
        """
        Convert single event to async generator.

        Args:
            event: Single event dict or None

        Yields:
            Event or None
        """
        yield event
