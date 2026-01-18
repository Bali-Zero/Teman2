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

import logging
import time
from typing import Any

from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.agentic.memory_handler import MemoryHandler
from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder
from backend.services.rag.agentic.query_gates import QueryGates
from backend.services.rag.agentic.reasoning import ReasoningEngine
from backend.services.search.semantic_cache import SemanticCache
from backend.services.tools.definitions import AgentState

from .llm_gateway import LLMGateway
from .orchestrator_context import OrchestratorContextManager
from .orchestrator_metrics import OrchestratorMetricsManager
from .orchestrator_response import OrchestratorResponseBuilder
from .orchestrator_routing import OrchestratorRoutingManager
from .query_helpers import wrap_query_with_language_instruction
from .schema import CoreResult

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
        db_pool: Any = None,
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
            kg_retrieval: Optional KGEnhancedRetrieval per KG context
            semantic_cache: Optional SemanticCache per caching
            db_pool: Optional database pool
        """
        self.llm_gateway = llm_gateway
        self.reasoning_engine = reasoning_engine
        self.prompt_builder = prompt_builder
        self.query_gates = query_gates
        self.entity_extractor = entity_extractor
        self.kg_retrieval = kg_retrieval
        self.semantic_cache = semantic_cache

        # Initialize specialized managers
        self.context_manager = OrchestratorContextManager(
            memory_handler=memory_handler,
            context_window_manager=context_window_manager,
            db_pool=db_pool,
        )
        self.routing_manager = OrchestratorRoutingManager()
        self.metrics_manager = OrchestratorMetricsManager()
        self.response_builder = OrchestratorResponseBuilder(entity_extractor=entity_extractor)

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
    ) -> tuple[dict[str, Any], str]:
        """
        Estrae entities e KG context per query.

        Args:
            query: Query string

        Returns:
            Tuple di (extracted_entities, system_context_for_prompt)
        """
        # Entity extraction
        with trace_span("entity.extraction", {"query_length": len(query)}):
            extracted_entities = await self.entity_extractor.extract_entities(query)
            if any(extracted_entities.values()):
                logger.info(f"🔍 [Entity Extraction] Extracted entities: {extracted_entities}")
                set_span_attribute("entities_found", str(extracted_entities))
            set_span_status("ok")

        # Build system context with entities
        system_context_for_prompt = ""
        if any(extracted_entities.values()):
            system_context_for_prompt = (
                f"\nKNOWN ENTITIES (Use strict filtering if possible): {extracted_entities}"
            )

        # KG-Enhanced Retrieval
        if self.kg_retrieval:
            try:
                kg_context = await self.kg_retrieval.get_context_for_query(query, max_depth=1)
                if kg_context and kg_context.graph_summary:
                    system_context_for_prompt += "\n" + kg_context.graph_summary
                    logger.info(
                        f"🔗 [KG] Added {len(kg_context.entities_found)} entities, "
                        f"{len(kg_context.relationships)} relationships to context"
                    )
            except Exception as e:
                logger.warning(f"⚠️ [KG] Failed to get graph context: {e}")

        return extracted_entities, system_context_for_prompt

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
            except Exception as react_error:
                logger.error(f"❌ ReAct loop failed: {react_error}", exc_info=True)
                set_span_status("error", str(react_error))
                raise

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
        1. Load context
        2. Check gates
        3. Check cache
        4. Extract entities/KG
        5. Route query
        6. Execute ReAct loop
        7. Build response
        8. Record metrics

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

        # 1. Load context
        user_context, optimized_history = await self.context_manager.get_full_context(
            user_id=user_id,
            query=query,
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
            return self.query_gates.gate_result_to_core_result(gate_result, start_time)

        # 3. Extract entities and KG context
        extracted_entities, system_context_for_prompt = await self.extract_entities_and_kg_context(
            query
        )

        # 4. Check semantic cache
        cached_result = await self.check_semantic_cache(
            query=query,
            extracted_entities=extracted_entities,
            start_time=start_time,
        )
        if cached_result:
            return cached_result

        # 5. Route query (intent classification + tier selection)
        model_tier, deep_think_mode, state = await self.routing_manager.route_query(query)

        # 6. Build system prompt
        system_prompt = self.prompt_builder.build_system_prompt(
            user_id=user_id or "anonymous",
            context=user_context,
            query=query,
            additional_context=system_context_for_prompt,
            conversation_history=optimized_history,
        )

        # 7. Create chat session
        chat = self.llm_gateway.create_chat_with_history(
            history_to_use=optimized_history,
            model_tier=model_tier,
            system_instruction=system_prompt,
        )

        # 8. Execute ReAct loop
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

        # 9. Extract metrics data
        timings = self.metrics_manager.extract_timings_from_state(
            state=state,
            reasoning_duration=reasoning_duration,
            start_time=start_time,
        )
        collections_used = self.metrics_manager.extract_collections_from_state(state)
        sources = self.metrics_manager.extract_sources_from_state(state)
        context_used = self.metrics_manager.calculate_context_used(state)

        # 10. Record metrics
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

        # 11. Build and return response
        return self.response_builder.build_core_result(
            state=state,
            sources=sources,
            extracted_entities=extracted_entities,
            model_used=model_used_name,
            token_usage=token_usage,
            timings=timings,
            start_time=start_time,
        )

    # ========== COMMON METHODS FOR STREAMING AND NON-STREAMING ==========

    async def prepare_query_context(
        self,
        query: str,
        user_id: str | None,
        conversation_history: list[dict] | None,
        session_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict], dict[str, Any]]:
        """
        Common context preparation for both streaming and non-streaming.

        Returns:
            Tuple of (user_context, optimized_history, extracted_entities)
        """
        # Load user context and optimize history
        user_context, optimized_history = await self.context_manager.get_full_context(
            user_id=user_id,
            query=query,
            conversation_history=conversation_history,
            session_id=session_id,
        )

        # Extract entities
        extracted_entities = await self.entity_extractor.extract_entities(query)

        return user_context, optimized_history, extracted_entities

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
        extracted_entities: dict[str, Any],  # TODO: Remove if not needed (legacy parameter)
        deep_think_mode: bool = False,
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

        # Extract KG context
        system_context_for_prompt, _ = await self.extract_entities_and_kg_context(query)

        # Build system prompt
        system_prompt = self.prompt_builder.build_system_prompt(
            user_id=user_context.get("profile", {}).get("id") or "anonymous",
            context=user_context,
            query=query,
            deep_think_mode=deep_think_mode,
            additional_context=system_context_for_prompt,
            conversation_history=history,
        )

        return model_tier, deep_think_mode, state, system_prompt
