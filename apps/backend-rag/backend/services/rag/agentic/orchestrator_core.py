"""
Orchestrator Core - Main Query Processing Coordination

Responsabilità singola: Coordinamento del flusso principale di query processing.
Include:
- Orchestrazione dei moduli specializzati (context, routing, metrics, response)
- Coordinamento ReAct loop execution
- Cache checking
- Entity extraction e KG retrieval
- System prompt building

Questo modulo è il "conductor" che coordina tutti i moduli specializzati.
Mantiene il flusso principale pulito e leggibile (target: 300-400 righe).
"""

import asyncio
import logging
import time
import uuid
from typing import Any

from langsmith import traceable

from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.db.repositories.query_analytics_repository import QueryAnalyticsRepository
from backend.db.repositories.workflow_analytics_repository import WorkflowAnalyticsRepository
from backend.prompts.channel_overlays import build_channel_context
from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.agentic.llm_gateway import LLMGateway
from backend.services.rag.agentic.memory_handler import MemoryHandler
from backend.services.rag.agentic.orchestrator_context import OrchestratorContextManager
from backend.services.rag.agentic.orchestrator_metrics import OrchestratorMetricsManager
from backend.services.rag.agentic.orchestrator_response import OrchestratorResponseBuilder
from backend.services.rag.agentic.orchestrator_routing import OrchestratorRoutingManager
from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder
from backend.services.rag.agentic.query_gates import QueryGates
from backend.services.rag.agentic.query_helpers import wrap_query_with_language_instruction
from backend.services.rag.agentic.reasoning import ReasoningEngine
from backend.services.rag.agentic.schema import CoreResult
from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval
from backend.services.rag.multi_agent_coordinator import MultiAgentCoordinator, requires_multi_agent
from backend.services.search.semantic_cache import SemanticCache
from backend.services.tools.definitions import AgentState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Info level for core orchestration


class OrchestratorCore:
    """
    Core orchestrator che coordina il flusso principale di query processing.

    Responsabilità:
    - Coordina context loading
    - Gestisce query gates
    - Coordina routing e ReAct loop
    - Gestisce metrics e response building
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        reasoning_engine: ReasoningEngine,
        prompt_builder: SystemPromptBuilder,
        query_gates: QueryGates,
        memory_handler: MemoryHandler,
        context_window_manager: Any,  # ContextWindowManager
        entity_extractor: EntityExtractionService,
        kg_retrieval: KGEnhancedRetrieval | None,
        semantic_cache: SemanticCache | None,
        faq_cache: Any = None,  # NotebookLMCacheService
        db_pool: Any = None,
        kg_langgraph_orchestrator: Any = None,  # KGLangGraphOrchestrator
        nlm_enrichment_service: Any = None,  # NLMEnrichmentService
    ):
        """
        Inizializza OrchestratorCore.

        Args:
            llm_gateway: LLM Gateway per model interactions
            reasoning_engine: ReasoningEngine per ReAct loop
            prompt_builder: SystemPromptBuilder per prompt construction
            query_gates: QueryGates per pre-processing gates
            memory_handler: MemoryHandler per memory operations
            context_window_manager: ContextWindowManager per history management
            entity_extractor: EntityExtractionService per entity extraction
            kg_retrieval: Optional KGEnhancedRetrieval per KG context (legacy)
            semantic_cache: Optional SemanticCache per caching
            faq_cache: Optional NotebookLMCacheService per FAQ caching (exact match)
            db_pool: Optional database pool
            kg_langgraph_orchestrator: Optional KGLangGraphOrchestrator (Phase 3)
            nlm_enrichment_service: Optional NLMEnrichmentService for CAUTIOUS-zone enrichment
        """
        self.llm_gateway = llm_gateway
        self.reasoning_engine = reasoning_engine
        self.prompt_builder = prompt_builder
        self.query_gates = query_gates
        self.entity_extractor = entity_extractor
        self.kg_retrieval = kg_retrieval
        self.semantic_cache = semantic_cache
        self.faq_cache = faq_cache  # FAQ cache (exact match, < 1ms)
        self.kg_langgraph_orchestrator = kg_langgraph_orchestrator  # Phase 3: LangGraph KG
        self.nlm_enrichment_service = nlm_enrichment_service  # NLM CAUTIOUS-zone enrichment
        self.db_pool = db_pool  # Store for later use

        # Initialize specialized managers
        self.context_manager = OrchestratorContextManager(
            memory_handler=memory_handler,
            context_window_manager=context_window_manager,
            db_pool=db_pool,
        )
        self.routing_manager = OrchestratorRoutingManager()
        self.metrics_manager = OrchestratorMetricsManager()
        self.response_builder = OrchestratorResponseBuilder(entity_extractor=entity_extractor)

        # Phase 6: Multi-Agent Coordinator (lazy-initialized)
        self._multi_agent_coordinator: MultiAgentCoordinator | None = None
        if db_pool or kg_retrieval:
            try:
                self._multi_agent_coordinator = MultiAgentCoordinator(
                    kg_retrieval=kg_retrieval,
                    db_pool=db_pool,
                )
                logger.info("✅ [Phase 6] MultiAgentCoordinator ready")
            except Exception as e:
                logger.warning(f"⚠️ [Phase 6] MultiAgentCoordinator init skipped: {e}")

    async def check_faq_cache(
        self,
        query: str,
        extracted_entities: dict[str, Any],
        start_time: float,
    ) -> CoreResult | None:
        """
        Check FAQ cache for exact question match (Redis hash lookup < 1ms).

        FAQ cache is faster than semantic cache (exact match vs vector similarity).
        Covers ~60-80% of common questions with pre-calculated answers.

        Args:
            query: Query string
            extracted_entities: Entities estratte
            start_time: Timestamp di inizio

        Returns:
            CoreResult se cache hit, None altrimenti
        """
        if not self.faq_cache:
            return None

        try:
            cached = await self.faq_cache.get(query)

            if cached:
                # Cache HIT! Return instant response
                logger.info(f"✅ FAQ Cache HIT: {query[:60]}... (< 1ms)")

                # Record metrics
                from backend.app.metrics import faq_cache_hits_total

                faq_cache_hits_total.labels(
                    domain=cached.get("metadata", {}).get("domain", "unknown")
                ).inc()

                return CoreResult(
                    answer=cached["answer"],
                    sources=[
                        {
                            "type": "faq_cache",
                            "source": cached.get("metadata", {}).get("source", "team_qa"),
                            "domain": cached.get("metadata", {}).get("domain", "unknown"),
                        }
                    ],
                    model_used="faq_cache",
                    entities=extracted_entities,
                    timings={"total": time.time() - start_time, "faq_cache_lookup": 0.001},
                    tools_called=[],
                )
            else:
                # Cache MISS - continue to semantic cache / full processing
                logger.debug(f"FAQ Cache MISS: {query[:60]}...")

                # Record metrics
                from backend.app.metrics import faq_cache_misses_total

                faq_cache_misses_total.inc()

                return None

        except Exception as e:
            logger.warning(f"⚠️ FAQ Cache error: {e}")

            # Record error metric
            try:
                from backend.app.metrics import faq_cache_errors_total

                faq_cache_errors_total.inc()
            except ImportError:
                pass

            return None  # Graceful degradation

    async def check_semantic_cache(
        self,
        query: str,
        extracted_entities: dict[str, Any],
        start_time: float,
    ) -> CoreResult | None:
        """
        Check semantic cache per query.

        Args:
            query: Query string
            extracted_entities: Entities estratte
            start_time: Timestamp di inizio

        Returns:
            CoreResult se cache hit, None altrimenti
        """
        if not self.semantic_cache:
            return None

        with trace_span("cache.semantic_check", {"cache_enabled": True}):
            try:
                cached = await self.semantic_cache.get_cached_result(query)
                if cached:
                    logger.info("✅ [Cache Hit] Returning cached result for query")
                    set_span_attribute("cache_hit", "true")
                    set_span_status("ok")

                    cached_result = cached.get("result", cached)
                    answer = cached_result.get("answer", "")
                    sources = cached_result.get("sources", [])

                    return CoreResult(
                        answer=answer,
                        sources=sources,
                        model_used="cache",
                        cache_hit=True,
                        timings={"total": time.time() - start_time},
                        entities=extracted_entities,
                        document_count=len(sources),
                    )
                else:
                    set_span_attribute("cache_hit", "false")
            except (KeyError, ValueError, RuntimeError) as e:
                logger.warning(f"Cache lookup failed: {e}", exc_info=True)
                set_span_status("error", str(e))

        return None

    async def extract_entities_and_kg_context(
        self,
        query: str,
        user_context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str, dict | None]:
        """
        Estrae entities e KG context per query.

        OPTIMIZED (Phase 1.2): Entity extraction e KG retrieval sono eseguiti in PARALLEL
        usando asyncio.gather per ~100-200ms latency reduction.

        Phase 3: Added KGLangGraphOrchestrator as optional third parallel task.

        Args:
            query: Query string
            user_context: Optional user context (for KGLangGraph)

        Returns:
            Tuple di (extracted_entities, system_context_for_prompt, langgraph_workflow_or_none)
        """
        start_time = time.time()

        # 🚀 PARALLEL EXECUTION: Entity Extraction + KG Retrieval + LangGraph (Phase 3)
        # These three operations are independent and can run concurrently
        async def _extract_entities_task() -> Any:
            """Entity extraction task"""
            with trace_span("entity.extraction", {"query_length": len(query)}):
                entities = await self.entity_extractor.extract_entities(query)
                if any(entities.values()):
                    logger.info(f"🔍 [Entity Extraction] Extracted entities: {entities}")
                    set_span_attribute("entities_found", str(entities))
                set_span_status("ok")
                return entities

        async def _fetch_kg_context_task() -> None:
            """KG retrieval task (legacy)"""
            if not self.kg_retrieval:
                return None

            try:
                kg_context = await self.kg_retrieval.get_context_for_query(query, max_depth=1)
                if kg_context and kg_context.graph_summary:
                    logger.info(
                        f"🔗 [KG Legacy] Added {len(kg_context.entities_found)} entities, "
                        f"{len(kg_context.relationships)} relationships to context"
                    )
                return kg_context
            except Exception as e:
                logger.warning(f"⚠️ [KG Legacy] Failed to get graph context: {e}")
                return None

        async def _fetch_langgraph_workflow_task() -> None:
            """KGLangGraphOrchestrator task (Phase 3)"""
            if not self.kg_langgraph_orchestrator:
                logger.warning(
                    "🔀 [KG LangGraph] DISABLED: Orchestrator not initialized (ENABLE_KG_LANGGRAPH=false or db_pool missing)"
                )
                return None
            logger.info("🔀 [KG LangGraph] ENABLED: Starting workflow synthesis...")

            try:
                with trace_span("kg.langgraph", {"query_length": len(query)}):
                    # Initialize orchestrator if needed
                    if (
                        not hasattr(self.kg_langgraph_orchestrator, "app")
                        or self.kg_langgraph_orchestrator.app is None
                    ):
                        await self.kg_langgraph_orchestrator.initialize()

                    # Execute LangGraph workflow
                    result = await self.kg_langgraph_orchestrator.query(
                        query=query,
                        user_context=user_context or {},
                    )

                    if result and result.get("workflow"):
                        workflow = result["workflow"]
                        logger.info(
                            f"🔀 [KG LangGraph] Synthesized workflow: {workflow['type']} "
                            f"({len(workflow.get('steps', []))} steps, source: {workflow.get('source', 'unknown')})"
                        )
                        set_span_attribute("workflow_type", workflow["type"])
                        set_span_attribute("workflow_steps", len(workflow.get("steps", [])))
                        set_span_status("ok")

                    return result
            except Exception as e:
                logger.warning(
                    f"⚠️ [KG LangGraph] Failed to synthesize workflow: {e}", exc_info=True
                )
                set_span_status("error", str(e))
                return None

        # Execute all three tasks in parallel
        entity_start = time.time()
        kg_start = time.time()
        langgraph_start = time.time()

        extracted_entities, kg_context, langgraph_result = await asyncio.gather(
            _extract_entities_task(),
            _fetch_kg_context_task(),
            _fetch_langgraph_workflow_task(),
            return_exceptions=True,  # Don't fail if one task fails
        )

        parallel_time = time.time() - start_time

        # Handle entity extraction result
        if isinstance(extracted_entities, Exception):
            logger.error(f"❌ Entity extraction failed: {extracted_entities}", exc_info=True)
            extracted_entities = {}
        else:
            entity_time = time.time() - entity_start
            logger.info(f"⏱️  [Orchestrator] Entity extraction: {entity_time:.3f}s")

        # Handle KG context result (legacy)
        if isinstance(kg_context, Exception):
            logger.error(f"❌ KG retrieval failed: {kg_context}", exc_info=True)
            kg_context = None
        elif kg_context:
            kg_time = time.time() - kg_start
            logger.info(f"⏱️  [Orchestrator] KG retrieval: {kg_time:.3f}s")

        # Handle LangGraph result (Phase 3)
        if isinstance(langgraph_result, Exception):
            logger.error(f"❌ KG LangGraph failed: {langgraph_result}", exc_info=True)
            langgraph_result = None
        elif langgraph_result:
            langgraph_time = time.time() - langgraph_start
            logger.info(f"⏱️  [Orchestrator] KG LangGraph: {langgraph_time:.3f}s")

        # Build system context with entities
        system_context_for_prompt = ""
        if any(extracted_entities.values()):
            system_context_for_prompt = (
                f"\nKNOWN ENTITIES (Use strict filtering if possible): {extracted_entities}"
            )

        # Add KG context if available (legacy)
        if kg_context and kg_context.graph_summary:
            system_context_for_prompt += "\n" + kg_context.graph_summary

        # Add LangGraph workflow if available (Phase 3)
        if langgraph_result and langgraph_result.get("workflow"):
            workflow = langgraph_result["workflow"]
            workflow_str = self._format_workflow_for_prompt(workflow)
            system_context_for_prompt += "\n" + workflow_str

            # Phase 4: Track workflow generation (fire-and-forget)
            asyncio.create_task(
                self._track_workflow(
                    query=query,
                    workflow=workflow,
                    execution_time_ms=int((time.time() - langgraph_start) * 1000),
                )
            )

        total_time = time.time() - start_time

        # Log parallel execution summary
        if (
            not isinstance(extracted_entities, Exception)
            and not isinstance(kg_context, Exception)
            and not isinstance(langgraph_result, Exception)
        ):
            entity_time_actual = time.time() - entity_start
            kg_time_actual = time.time() - kg_start if kg_context else 0.0
            langgraph_time_actual = time.time() - langgraph_start if langgraph_result else 0.0
            estimated_sequential_time = entity_time_actual + kg_time_actual + langgraph_time_actual
            speedup = max(0, estimated_sequential_time - parallel_time)
            logger.info(
                f"⚡ [Orchestrator] PARALLEL Entity+KG+LangGraph completed in {total_time:.3f}s "
                f"(Entity: {entity_time_actual:.3f}s, KG: {kg_time_actual:.3f}s, LangGraph: {langgraph_time_actual:.3f}s, "
                f"speedup: ~{speedup:.3f}s vs sequential ~{estimated_sequential_time:.3f}s)"
            )

        # Extract workflow dict for direct answer injection
        workflow_result = None
        if (
            langgraph_result
            and isinstance(langgraph_result, dict)
            and langgraph_result.get("workflow")
        ):
            workflow_result = langgraph_result["workflow"]

        return extracted_entities, system_context_for_prompt, workflow_result

    def _format_workflow_for_prompt(self, workflow: dict) -> str:
        """
        Format LangGraph workflow for system prompt.

        Includes confidence breakdown when available (Phase 2).

        Args:
            workflow: Workflow dict from KGLangGraphOrchestrator

        Returns:
            Formatted workflow string for prompt
        """
        workflow_type = workflow.get("type", "workflow")
        workflow_name = workflow.get("name", "Unknown Workflow")
        steps = workflow.get("steps", [])
        source = workflow.get("source", "unknown")
        confidence = workflow.get("confidence", 0.0)
        breakdown = workflow.get("confidence_breakdown")

        formatted = f"\n## SUGGESTED WORKFLOW (from {source}, confidence: {confidence:.0%})"
        formatted += f"\n**{workflow_name}** ({workflow_type}):\n"

        for step_data in steps:
            step_num = step_data.get("step", "?")
            action = step_data.get("action", "Unknown action")

            formatted += f"\n{step_num}. {action}"

            # Add details if available
            details = step_data.get("details")
            if details and isinstance(details, dict):
                if "requirement" in details:
                    formatted += f" ({details['requirement']})"
                elif "location" in details:
                    formatted += f" (Location: {details['location']})"
                elif "processing_time" in details:
                    formatted += f" (Processing: {details['processing_time']})"

        # Phase 2: Confidence breakdown
        if breakdown:
            warning_level = breakdown.get("warning_level", "unknown")
            warning_message = breakdown.get("warning_message", "")
            source_count = breakdown.get("unique_source_count", 0)
            rel_strength = breakdown.get("relationship_strength_avg", 0.0)

            formatted += f"\n\n**Confidence**: {warning_level} — {source_count} source(s), relationship strength {rel_strength:.0%}"

            if warning_level in ("low", "very_low"):
                formatted += f"\nWARNING: {warning_message}"

        formatted += "\n\nIMPORTANT: This is a suggested workflow. Always verify current requirements with the user."

        return formatted

    async def _track_workflow(
        self,
        query: str,
        workflow: dict,
        execution_time_ms: int | None = None,
        user_email: str | None = None,
    ) -> None:
        """
        Track workflow generation to workflow_analytics (fire-and-forget).

        Args:
            query: Original user query
            workflow: Workflow dict from KGLangGraphOrchestrator
            execution_time_ms: Time taken to generate workflow
            user_email: Optional user email
        """
        if not self.db_pool:
            return

        try:
            repo = WorkflowAnalyticsRepository(self.db_pool)
            steps = workflow.get("steps", [])
            workflow_id = f"wf-{uuid.uuid4().hex[:12]}"

            await repo.log_workflow(
                workflow_id=workflow_id,
                query=query,
                user_email=user_email,
                workflow_type=workflow.get("type"),
                workflow_name=workflow.get("name"),
                steps_count=len(steps),
                steps_json=steps,
                source=workflow.get("source", "kg_langgraph"),
                confidence=workflow.get("confidence", 0.0),
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.warning(f"Failed to track workflow analytics: {e}")

    @traceable(run_type="chain", name="ReAct Loop", tags=["nuzantara", "react"])
    async def execute_react_loop(
        self,
        state: AgentState,
        chat: Any,
        system_prompt: str,
        query: str,
        user_id: str,
        model_tier: str,
        tool_execution_counter: dict[str, int],
    ) -> tuple[AgentState, str, TokenUsage, float]:
        """
        Esegue ReAct loop per query processing.

        Args:
            state: AgentState inizializzato
            chat: Chat session
            system_prompt: System prompt completo
            query: Query originale
            user_id: User ID
            model_tier: Model tier selezionato
            tool_execution_counter: Counter per tool executions

        Returns:
            Tuple di (state, model_used_name, token_usage, reasoning_duration)
        """
        with trace_span(
            "react.loop",
            {
                "model_tier": model_tier,
                "user_id": user_id,
                "query_length": len(query),
            },
        ):
            try:
                loop_start = time.time()
                (
                    state,
                    model_used_name,
                    conversation_messages,
                    token_usage,
                ) = await self.reasoning_engine.execute_react_loop(
                    state=state,
                    llm_gateway=self.llm_gateway,
                    chat=chat,
                    initial_prompt=wrap_query_with_language_instruction(query),
                    system_prompt=system_prompt,
                    query=query,
                    user_id=user_id,
                    model_tier=model_tier,
                    tool_execution_counter=tool_execution_counter,
                )
                loop_duration = time.time() - loop_start

                set_span_attribute("model_used", model_used_name)
                set_span_attribute("steps_count", len(state.steps))
                set_span_attribute("tools_executed", tool_execution_counter["count"])
                set_span_status("ok")

                return state, model_used_name, token_usage, loop_duration
            except (RuntimeError, ValueError, TimeoutError) as react_error:
                # Specific error types from ReAct loop execution
                logger.error(f"❌ ReAct loop failed: {react_error}", exc_info=True)
                set_span_status("error", str(react_error))
                raise
            except Exception as unexpected_error:
                # Catch-all for unexpected errors with detailed logging
                logger.critical(
                    f"🚨 Unexpected error in ReAct loop: {unexpected_error}",
                    exc_info=True,
                    extra={"error_type": type(unexpected_error).__name__},
                )
                set_span_status("error", f"unexpected:{type(unexpected_error).__name__}")
                raise RuntimeError(f"ReAct loop failed: {unexpected_error}") from unexpected_error

    @traceable(run_type="chain", name="Agentic RAG Query", tags=["nuzantara", "rag", "production"])
    async def process_query_core(
        self,
        query: str,
        user_id: str | None,
        conversation_history: list[dict] | None,
        start_time: float,
        session_id: str | None = None,
        tool_execution_counter: dict[str, int] | None = None,
    ) -> CoreResult:
        """
        Core query processing logic coordinando tutti i moduli.

        Questo è il metodo principale che orchestra tutto il flusso:
        1. Load context + Extract Entities/KG (PARALLEL)
        2. Check gates
        3. Check cache
        4. Route query
        5. Execute ReAct loop
        6. Build response
        7. Record metrics

        Args:
            query: Query string
            user_id: User ID (può essere None)
            conversation_history: Optional conversation history
            start_time: Timestamp di inizio
            session_id: Optional session ID
            tool_execution_counter: Optional tool execution counter

        Returns:
            CoreResult completo
        """
        if tool_execution_counter is None:
            tool_execution_counter = {"count": 0}

        # 1. Load context and Extract Entities/KG in PARALLEL
        # This reduces TTFT by overlapping DB calls with NLP/Graph calls
        (
            user_context,
            optimized_history,
            extracted_entities,
            system_context_for_prompt,
            langgraph_workflow,
        ) = await self.prepare_query_context(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history,
            session_id=session_id,
        )

        # 2. Check gates (security, greeting, etc.)
        gate_result = self.query_gates.run_all_gates(
            query=query,
            user_context=user_context,
            conversation_history=optimized_history,
        )
        if gate_result.triggered:
            return self.query_gates.gate_result_to_core_result(
                gate_result, start_time, extracted_entities=extracted_entities
            )

        # 3. Check FAQ cache (exact match, < 1ms)
        faq_cached_result = await self.check_faq_cache(
            query=query,
            extracted_entities=extracted_entities,
            start_time=start_time,
        )
        if faq_cached_result:
            return faq_cached_result

        # 3b. Check semantic cache (vector similarity, ~50ms)
        # (Already have entities from parallel step 1)
        cached_result = await self.check_semantic_cache(
            query=query,
            extracted_entities=extracted_entities,
            start_time=start_time,
        )
        if cached_result:
            return cached_result

        # 3b. Phase 6: Check if multi-agent coordination is needed
        if self._multi_agent_coordinator and requires_multi_agent(query):
            try:
                logger.info("🔀 [Phase 6] Multi-agent query detected, delegating to coordinator")
                ma_result = await self._multi_agent_coordinator.process(
                    query=query,
                    user_context={"extracted_entities": extracted_entities},
                )
                if ma_result.get("final_answer"):
                    return CoreResult(
                        answer=ma_result["final_answer"],
                        sources=[],
                        model_used="multi-agent-coordinator",
                        entities=extracted_entities,
                        timings={"total": time.time() - start_time},
                        tools_called=["legal_agent", "financial_agent", "timeline_agent"],
                    )
            except Exception as e:
                logger.warning(f"⚠️ [Phase 6] Multi-agent failed, falling back to ReAct: {e}")

        # 4. Route query (intent classification + tier selection)
        model_tier, deep_think_mode, state = await self.routing_manager.route_query(query)

        # 5. Build system prompt
        system_prompt = self.prompt_builder.build_system_prompt(
            user_id=user_id or "anonymous",
            context=user_context,
            query=query,
            additional_context=system_context_for_prompt,
            conversation_history=optimized_history,
        )

        # 6. Create chat session
        chat = self.llm_gateway.create_chat_with_history(
            history_to_use=optimized_history,
            model_tier=model_tier,
            system_instruction=system_prompt,
        )

        # 7. Execute ReAct loop
        logger.info(f"🚀 [AgenticRAG] Processing query with ReAct loop (Model tier: {model_tier})")
        state, model_used_name, token_usage, reasoning_duration = await self.execute_react_loop(
            state=state,
            chat=chat,
            system_prompt=system_prompt,
            query=query,
            user_id=user_id or "anonymous",
            model_tier=model_tier,
            tool_execution_counter=tool_execution_counter,
        )

        # 8. Extract metrics data
        timings = self.metrics_manager.extract_timings_from_state(
            state=state,
            reasoning_duration=reasoning_duration,
            start_time=start_time,
        )
        collections_used = self.metrics_manager.extract_collections_from_state(state)
        sources = self.metrics_manager.extract_sources_from_state(state)
        context_used = self.metrics_manager.calculate_context_used(state)

        # Retrieval debug logging
        logger.info(f"\U0001f4da [Retrieval] Collections interrogated: {collections_used}")
        source_collections = (
            list(
                {
                    s.get("collection", s.get("source", "unknown"))
                    if isinstance(s, dict)
                    else str(s)
                    for s in sources
                }
            )
            if sources
            else []
        )
        logger.info(
            f"\U0001f4c4 [Retrieval] Chunks retrieved: {len(sources)} from {source_collections}"
        )

        # 9. Record metrics
        self.metrics_manager.record_rag_metrics(
            state=state,
            collections_used=collections_used,
            tool_execution_count=tool_execution_counter["count"],
            context_used=context_used,
            execution_time=timings["total"],
            sources=sources,
        )
        self.metrics_manager.record_token_usage(
            model_used=model_used_name,
            token_usage=token_usage,
        )
        self.metrics_manager.log_query_completion(
            user_id=user_id,
            query=query,
            model_used=model_used_name,
            execution_time=timings["total"],
            state=state,
            collections_used=collections_used,
            tool_execution_count=tool_execution_counter["count"],
            token_usage=token_usage,
        )

        # 10. Log to query_analytics (fire-and-forget, non-blocking)
        await self._log_query_analytics(
            query=query,
            user_id=user_id,
            session_id=session_id,
            collections_used=collections_used,
            sources=sources,
            model_used=model_used_name,
            token_usage=token_usage,
            timings=timings,
        )

        # 11. Build and return response (with KG LangGraph workflow if available)
        # Extract reasoning from langgraph_result if available
        langgraph_reasoning = None
        if langgraph_workflow and isinstance(langgraph_workflow, dict):
            # Try to get reasoning from the workflow or the original langgraph result
            langgraph_reasoning = langgraph_workflow.get("reasoning")

        result = self.response_builder.build_core_result(
            state=state,
            sources=sources,
            extracted_entities=extracted_entities,
            model_used=model_used_name,
            token_usage=token_usage,
            timings=timings,
            start_time=start_time,
            workflow=langgraph_workflow,
            reasoning=langgraph_reasoning,
        )

        # 12. Also append KG LangGraph workflow text to answer for visibility
        if langgraph_workflow:
            workflow_text = self._format_workflow_for_prompt(langgraph_workflow)
            result.answer = result.answer.rstrip() + "\n\n" + workflow_text
            logger.info(
                f"🔗 [KG LangGraph] Workflow included in response: {langgraph_workflow.get('type')}"
            )

        return result

    async def _log_query_analytics(
        self,
        query: str,
        user_id: str | None,
        session_id: str | None,
        collections_used: set[str],
        sources: list[Any],
        model_used: str,
        token_usage: TokenUsage,
        timings: dict[str, float],
        error_message: str | None = None,
    ) -> None:
        """
        Persist query execution data to query_analytics table.
        Fails silently to never block the main query flow.
        """
        if not self.db_pool:
            return

        try:
            repo = QueryAnalyticsRepository(self.db_pool)
            await repo.log_query(
                query_text=query,
                user_id=user_id,
                session_id=session_id,
                collections_queried=list(collections_used) if collections_used else [],
                chunks_retrieved_count=len(sources),
                response_generated=len(sources) > 0,
                model_used=model_used,
                execution_time_ms=int(timings.get("total", 0) * 1000),
                token_usage_total=token_usage.total_tokens,
                cost_usd=token_usage.cost_usd,
                error_message=error_message,
            )
        except Exception as e:
            logger.warning(f"Failed to log query analytics (non-critical): {e}")

    # ========== COMMON METHODS FOR STREAMING AND NON-STREAMING ==========

    async def prepare_query_context(
        self,
        query: str,
        user_id: str | None,
        conversation_history: list[dict] | None,
        session_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict], dict[str, Any], str, dict | None]:
        """
        Common context preparation for both streaming and non-streaming.
        Executes Context Loading and Entity/KG Extraction in PARALLEL.

        Returns:
            Tuple of (user_context, optimized_history, extracted_entities, kg_context_str, workflow)
        """

        # Definisci i task da eseguire in parallelo
        async def _load_context() -> Any:
            return await self.context_manager.get_full_context(
                user_id=user_id,
                query=query,
                conversation_history=conversation_history,
                session_id=session_id,
            )

        # First load context to get user_context for LangGraph
        try:
            user_context, optimized_history = await _load_context()
        except Exception as e:
            logger.error(f"❌ Context loading failed: {e}", exc_info=True)
            user_context = {}
            optimized_history = []

        # Then run entity/KG extraction with user_context
        async def _extract_entities_kg_with_context() -> Any:
            return await self.extract_entities_and_kg_context(query, user_context=user_context)

        workflow = None
        try:
            (
                extracted_entities,
                system_context_for_prompt,
                workflow,
            ) = await _extract_entities_kg_with_context()
        except Exception as e:
            logger.error(f"❌ KG extraction failed: {e}", exc_info=True)
            extracted_entities = {}
            system_context_for_prompt = ""

        return (
            user_context,
            optimized_history,
            extracted_entities,
            system_context_for_prompt,
            workflow,
        )

    async def check_gates_and_cache(
        self,
        query: str,
        user_context: dict[str, Any],
        history: list[dict],
        extracted_entities: dict[str, Any],
        start_time: float,
    ) -> CoreResult | None:
        """
        Common gate checking and cache lookup.

        Returns:
            CoreResult if gate triggered or cache hit, None otherwise
        """
        # Check gates
        gate_result = self.query_gates.run_all_gates(
            query=query,
            user_context=user_context,
            conversation_history=history,
        )
        if gate_result.triggered:
            logger.debug("Gate triggered, returning gate response")
            return self.query_gates.gate_result_to_core_result(
                gate_result=gate_result,
                extracted_entities=extracted_entities,
                start_time=start_time,
            )

        # Check semantic cache
        cached_result = await self.check_semantic_cache(
            query=query,
            extracted_entities=extracted_entities,
            start_time=start_time,
        )
        if cached_result:
            return cached_result

        return None

    async def _prepare_react_loop(
        self,
        query: str,
        user_context: dict[str, Any],
        history: list[dict],
        extracted_entities: dict[str, Any],  # noqa: ARG002 — kept for signature compatibility
        deep_think_mode: bool = False,
        kg_context_str: str = "",  # New argument to pass pre-fetched KG context
        channel: str | None = None,  # Channel overlay for response formatting
    ) -> tuple[str, bool, AgentState, str]:
        """
        Common ReAct loop preparation.

        Returns:
            Tuple of (model_tier, deep_think_mode, state, system_prompt)
        """
        # Route query (intent classification + tier selection)
        model_tier, deep_think_mode, state = await self.routing_manager.route_query(query)

        # Override deep_think_mode if explicitly provided
        if deep_think_mode:
            state.deep_think_mode = True

        # Use pre-fetched KG context if available, otherwise fetch it (fallback)
        system_context_for_prompt = kg_context_str
        if not system_context_for_prompt:
            _, system_context_for_prompt, _ = await self.extract_entities_and_kg_context(query)

        # Build system prompt - handle None user_context
        safe_user_context = user_context or {}
        user_id = (safe_user_context.get("profile") or {}).get("id") or "anonymous"

        system_prompt = self.prompt_builder.build_system_prompt(
            user_id=user_id,
            context=safe_user_context,
            query=query,
            deep_think_mode=deep_think_mode,
            additional_context=system_context_for_prompt,
            conversation_history=history,
        )

        # Inject channel overlay (website, webapp, whatsapp, etc.)
        channel_context = build_channel_context(channel or "webapp")
        if channel_context:
            system_prompt += f"\n\n{channel_context}"

        # 🔍 DEBUG: Log full context breakdown
        logger.debug("🔍 [ORCHESTRATOR DEBUG] ===== CONTEXT BREAKDOWN =====")
        logger.debug(f"🔍 Query: {query}")
        logger.debug(f"🔍 System prompt length: {len(system_prompt)} chars")
        logger.debug(f"🔍 KG context length: {len(system_context_for_prompt)} chars")
        logger.debug(f"🔍 User context facts: {len(safe_user_context.get('facts', []))} facts")
        logger.debug(f"🔍 Conversation history: {len(history)} messages")
        logger.debug(f"🔍 Deep think mode: {deep_think_mode}")
        logger.debug(f"🔍 First 1000 chars of KG context:\n{system_context_for_prompt[:1000]}...")
        logger.debug("🔍 ===== END CONTEXT BREAKDOWN =====")

        return model_tier, deep_think_mode, state, system_prompt

    async def prepare_react_execution(
        self,
        query: str,
        user_context: dict[str, Any],
        history: list[dict],
        extracted_entities: dict[str, Any],
        deep_think_mode: bool = False,
        kg_context_str: str = "",
        channel: str | None = None,
    ) -> tuple[str, bool, AgentState, str]:
        """
        Prepare ReAct execution (alias for _prepare_react_loop for streaming compatibility).

        Returns:
            Tuple of (model_tier, deep_think_mode, state, system_prompt)
        """
        return await self._prepare_react_loop(
            query=query,
            user_context=user_context,
            history=history,
            extracted_entities=extracted_entities,
            deep_think_mode=deep_think_mode,
            kg_context_str=kg_context_str,
            channel=channel,
        )
