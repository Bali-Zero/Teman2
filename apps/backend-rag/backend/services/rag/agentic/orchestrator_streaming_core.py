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
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.rag.agentic.orchestrator_streaming import OrchestratorStreamingManager
from backend.services.rag.agentic.query_helpers import wrap_query_with_language_instruction
from backend.services.rag.agentic.thinking_indicators import ThinkingIndicatorService, ThinkingPhase

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
    ) -> None:
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
        initial_user_context: dict[str, Any] | None = None,
        channel: str | None = None,
        agent_role: Any | None = None,  # VASSAL Phase 2: AgentRole | None
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
            initial_user_context: Optional pre-loaded basic context (Profile/History)

        Yields:
            Stream events (dict)
        """
        start_time = time.time()

        # Initialize thinking service
        thinking_service = ThinkingIndicatorService()

        # Yield initial status
        yield self.streaming_manager.create_initial_status_event(correlation_id)

        # IMMEDIATE: Yield granular thinking indicator for user feedback
        yield thinking_service.create_thinking_event(
            ThinkingPhase.ANALYZING, message_override="🧠 Analyzing request & intent...",
        )

        # 1. Prepare context (TIERED LOADING)
        user_context = None
        optimized_history = []
        extracted_entities = {}
        kg_context_str = ""

        langgraph_workflow = None

        if initial_user_context:
            # FAST PATH: Using pre-loaded basic context
            # We need to enrich it with Memory + Entities + LangGraph (Heavy Lifting)
            user_context = initial_user_context
            optimized_history = conversation_history or user_context.get("history", [])

            # ENRICHMENT PHASE
            yield thinking_service.create_thinking_event(
                ThinkingPhase.SEARCHING, message_override="🔍 Retrieving memory & facts...",
            )

            # Parallel Enrichment: Memory + Entities + LangGraph
            async def _enrich_memory() -> Any:
                return await self.core.context_manager.enrich_user_context(
                    user_context, user_id, query,
                )

            async def _extract_entities_and_kg() -> Any:
                return await self.core.extract_entities_and_kg_context(
                    query, user_context=user_context,
                )

            enrich_results = await asyncio.gather(
                _enrich_memory(), _extract_entities_and_kg(), return_exceptions=True,
            )

            # Process Memory result
            if not isinstance(enrich_results[0], Exception):
                user_context = enrich_results[0]

            # Process Entity+KG result (now returns 3-tuple)
            if not isinstance(enrich_results[1], Exception):
                extracted_entities, kg_context_str, langgraph_workflow = enrich_results[1]

        else:
            # LEGACY / FULL LOAD PATH
            yield thinking_service.create_thinking_event(
                ThinkingPhase.SEARCHING,
                message_override="👤 Loading profile & extracting entities...",
            )

            (
                user_context,
                optimized_history,
                extracted_entities,
                kg_context_str,
                langgraph_workflow,
            ) = await self.core.prepare_query_context(
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

        # 2b. CRM Pre-call: if query is about clients/practices, call CRM tool
        # directly and inject results into context. This avoids Gemini wasting
        # 2-3 ReAct steps trying vector_search before discovering crm_query.
        crm_precall_context = ""
        _crm_keywords = {"clienti", "clients", "klien", "pratiche", "practices",
                         "quanti", "how many", "berapa", "attivi", "active",
                         "in corso", "in progress", "scadenza", "expiring",
                         "leads", "breakdown", "database", "cerca cliente", "find client"}
        query_lower = query.lower()
        if any(kw in query_lower for kw in _crm_keywords):
            crm_tool = self.core.tool_map.get("crm_query")
            if crm_tool:
                try:
                    # Determine best query_type
                    if any(w in query_lower for w in ("quanti", "how many", "berapa", "attivi", "active", "leads")):
                        crm_result = await crm_tool.execute(query_type="client_stats")
                    elif any(w in query_lower for w in ("pratiche", "practices", "in corso", "in progress", "breakdown")):
                        crm_result = await crm_tool.execute(query_type="practice_stats")
                    elif any(w in query_lower for w in ("scadenza", "expiring")):
                        crm_result = await crm_tool.execute(query_type="expiring_documents")
                    elif any(w in query_lower for w in ("cerca", "find", "search")):
                        # Extract search term (naive: everything after the keyword)
                        crm_result = await crm_tool.execute(query_type="search_clients", search_term=query)
                    else:
                        crm_result = await crm_tool.execute(query_type="client_stats")

                    if crm_result and len(crm_result) > 10:
                        crm_precall_context = f"\n\n[CRM DATABASE RESULTS — USE THESE NUMBERS IN YOUR ANSWER]\n{crm_result}\n"
                        logger.info(f"🚀 [CRM Pre-call] Injected {len(crm_result)} bytes of CRM data into context")
                except Exception as e:
                    logger.warning(f"[CRM Pre-call] Failed: {e}")

        # 3. Prepare ReAct execution (common logic)
        # If CRM pre-call returned data, mark as trusted (skip evidence check)
        # This is applied AFTER prepare_react_execution via state mutation below.
        _crm_precall_has_data = len(crm_precall_context) > 0

        model_tier, deep_think_mode, state, system_prompt = await self.core.prepare_react_execution(
            query=query,
            user_context=user_context,
            history=optimized_history,
            extracted_entities=extracted_entities,
            deep_think_mode=False,  # Will be determined by routing
            kg_context_str=kg_context_str,  # Pass pre-fetched KG context
            channel=channel,
            agent_role=agent_role,  # VASSAL Phase 2 — stamps state.agent_role
        )

        # If CRM pre-call has data, mark state so evidence check is skipped
        if _crm_precall_has_data:
            state.trusted_tools_used = True
            state.skip_rag = True
            state.context_gathered.append(crm_precall_context)

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

        # Show reasoning indicator before ReAct loop
        yield thinking_service.create_thinking_event(ThinkingPhase.REASONING)

        # R5 Phase 6: NLM Speculative Fire removed

        try:
            # Stream ReAct loop events
            async for raw_event in self.core.reasoning_engine.execute_react_loop_stream(
                state=state,
                llm_gateway=self.core.llm_gateway,
                chat=chat,
                initial_prompt=wrap_query_with_language_instruction(query) + crm_precall_context,
                system_prompt=system_prompt,
                query=query,
                user_id=user_id or "anonymous",
                model_tier=model_tier,
                tool_execution_counter=tool_execution_counter,
                images=images,
            ):
                # Skip non-dict events (defensive guard)
                if not isinstance(raw_event, dict):
                    continue

                # Check if this is a tool call event
                if raw_event and raw_event.get("type") == "tool_call":
                    tool_name = raw_event.get("data", {}).get("tool_name", "unknown tool")
                    yield thinking_service.create_thinking_event(
                        ThinkingPhase.TOOL_CALLING, tool_name=tool_name,
                    )

                # Process and validate events
                async for event in self.streaming_manager.process_event_stream(
                    event_generator=self._single_event_generator(raw_event),
                    correlation_id=correlation_id,
                    user_id=user_id,
                ):
                    yield event

            # Clear thinking state when done
            yield thinking_service.create_done_event()

            # 5b. Stream KG LangGraph workflow if available
            if langgraph_workflow:
                # First yield metadata with structured workflow for programmatic use
                yield {
                    "type": "metadata",
                    "data": {
                        "workflow": langgraph_workflow,
                        "detected_entities": extracted_entities
                        if any(extracted_entities.values())
                        else None,
                    },
                    "timestamp": time.time(),
                }
                logger.info(f"🔗 [Stream] Workflow metadata sent: {langgraph_workflow.get('type')}")

            # ==================== NLM LATE MERGE ====================
            # Decide whether to consume the speculative NLM result based
            # on evidence score and trusted-tool usage from the ReAct loop.
            # R5 Phase 6: NLM merge removed
            evidence_score = getattr(state, "evidence_score", None)
            trusted = getattr(state, "trusted_tools_used", True)

            # Determine confidence zone
            confidence_zone: str = "confident"
            if evidence_score is not None:
                if evidence_score < 0.15:
                    confidence_zone = "abstain"
                elif evidence_score <= 0.60 and not trusted:
                    confidence_zone = "cautious"

            # 6. Yield done event with metrics
            execution_time = time.time() - start_time
            route_used = "agentic" if tool_execution_counter["count"] > 0 else "direct"

            yield self.streaming_manager.create_done_event(
                execution_time=execution_time,
                route_used=route_used,
                evidence_score=evidence_score,
                confidence_zone=confidence_zone,
            )

            # 7. Log to query_analytics (fire-and-forget)
            collections_used = self.core.metrics_manager.extract_collections_from_state(state)
            sources = self.core.metrics_manager.extract_sources_from_state(state)
            try:
                from backend.db.repositories.query_analytics_repository import (
                    QueryAnalyticsRepository,
                )

                if self.core.db_pool:
                    repo = QueryAnalyticsRepository(self.core.db_pool)
                    await repo.log_query(
                        query_text=query,
                        user_id=user_id,
                        session_id=session_id,
                        collections_queried=list(collections_used) if collections_used else [],
                        chunks_retrieved_count=len(sources),
                        response_generated=len(sources) > 0,
                        model_used=model_tier,
                        execution_time_ms=int(execution_time * 1000),
                    )
            except Exception as analytics_err:
                logger.warning(
                    f"Failed to log streaming query analytics (non-critical): {analytics_err}",
                )

        except Exception as e:
            logger.error(f"❌ [Stream] ReAct loop failed: {e}", exc_info=True)
            yield self.streaming_manager.create_error_event(
                error_type="react_loop_error",
                message=str(e),
                correlation_id=correlation_id,
            )
        finally:
            pass  # R5 Phase 6: NLM task cleanup removed (no speculative NLM task)

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
        # Yield metadata — derive status from route_used (gate name) or verification_status
        # Gate routes have form "<gate_name>-gate" (e.g. "greeting-gate", "security-gate")
        # Map gate names to the status values expected by tests and clients
        _GATE_STATUS_MAP: dict[str, str] = {
            "security-gate": "blocked",
            "out_of_domain-gate": "out-of-domain",
            "clarification-gate": "clarification_needed",
            "greeting-gate": "greeting",
            "casual-gate": "casual",
            "identity-gate": "identity",
            "recall-gate": "recall",
            "team-gate": "team-query",
        }
        model_used = getattr(result, "model_used", route_used) or route_used
        if model_used in _GATE_STATUS_MAP:
            status = _GATE_STATUS_MAP[model_used]
        elif model_used and model_used.endswith("-gate"):
            # Fallback: strip "-gate" suffix for unknown gate types
            status = model_used[: -len("-gate")]
        else:
            verification_status = getattr(result, "verification_status", None)
            status = (
                verification_status
                if verification_status and verification_status != "passed"
                else "success"
            )
        yield {
            "type": "metadata",
            "data": {
                "status": status,
                "route": route_used,
                "model_used": model_used,
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
        self, event: dict | None,
    ) -> AsyncGenerator[dict | None, None]:
        """
        Convert single event to async generator.

        Args:
            event: Single event dict or None

        Yields:
            Event or None
        """
        yield event
