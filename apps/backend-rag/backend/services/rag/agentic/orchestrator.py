"""
Agentic RAG Orchestrator - Main Query Processing Logic

This is the core orchestrator that coordinates all agentic RAG operations:
- Query routing (Fast/Pro/DeepThink)
- Tool-based reasoning (ReAct pattern)
- Streaming and non-streaming query processing
- Model fallback cascade (Gemini Pro -> Flash -> Flash-Lite -> OpenRouter)
- Memory persistence
- Semantic caching
- Response verification

Architecture:
- Uses modular components for context, prompts, tools, and processing
- Implements quality routing based on intent classification
- Supports conversation history with context window management
- Provides backward compatibility with legacy interfaces
"""

import logging
import os
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.services.memory.orchestrator import MemoryOrchestrator

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.metrics import metrics_collector
from backend.app.utils.tracing import (
    trace_span,
)
from backend.services.classification.intent_classifier import IntentClassifier
from backend.services.misc.clarification_service import ClarificationService
from backend.services.misc.context_window_manager import ContextWindowManager
from backend.services.misc.emotional_attunement import EmotionalAttunementService
from backend.services.misc.followup_service import FollowupService
from backend.services.misc.golden_answer_service import GoldenAnswerService
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.agentic.llm_gateway import LLMGateway
from backend.services.rag.agentic.memory_handler import MemoryHandler
from backend.services.rag.agentic.pipeline import create_default_pipeline
from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder
from backend.services.rag.agentic.query_gates import QueryGates
from backend.services.rag.agentic.query_helpers import (
    is_conversation_recall_query,
    wrap_query_with_language_instruction,
)
from backend.services.rag.agentic.reasoning import ReasoningEngine
from backend.services.rag.agentic.schema import CoreResult
from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval
from backend.services.search.semantic_cache import SemanticCache
from backend.services.tools.definitions import BaseTool

logger = logging.getLogger(__name__)


class StreamEvent(BaseModel):
    """Schema per eventi stream."""

    type: str
    data: Any
    timestamp: float | None = None
    correlation_id: str | None = None

    class Config:
        arbitrary_types_allowed = True


# Alias for backward compatibility (used internally)
_wrap_query_with_language_instruction = wrap_query_with_language_instruction

# Re-export for backward compatibility (tests mock this path)
from backend.services.rag.agentic.context_manager import get_user_context  # noqa: F401, E402

_is_conversation_recall_query = is_conversation_recall_query


class AgenticRAGOrchestrator:
    """
    Orchestrator for Agentic RAG with Tool Use.
    Implements ReAct: Thought → Action → Observation → Repeat

    Supports:
    - Quality Routing: Fast (Flash) vs Pro (Pro) vs DeepThink (Reasoning)
    - Automatic fallback: Flash -> Flash-Lite -> OpenRouter
    - Memory persistence and context management
    - Streaming and non-streaming modes
    """

    def __init__(
        self,
        tools: list[BaseTool],
        db_pool: Any = None,
        model_name: str = "gemini-3-flash-preview",  # Zantara AI - Gemini 3 Flash Preview
        semantic_cache: SemanticCache = None,
        faq_cache: Any = None,  # NotebookLMCacheService
        retriever: Any = None,
        clarification_service: ClarificationService = None,
        entity_extractor: EntityExtractionService = None,
        llm_gateway: LLMGateway = None,
        nlm_enrichment_service: Any = None,
        cultural_insights_service: Any = None,
    ) -> None:
        """Initialize the AgenticRAGOrchestrator.

        Sets up model clients, dependencies, and configuration for multi-tier
        agentic reasoning with automatic fallback handling.

        Args:
            tools: List of tool definitions available for agent reasoning
            db_pool: Optional asyncpg connection pool for database operations
            model_name: Base model name (legacy, not actively used)
            semantic_cache: Optional semantic cache instance for query deduplication
            faq_cache: Optional FAQ cache for exact question matching (< 1ms)
            retriever: SearchService or KnowledgeService instance for embeddings
            clarification_service: Optional service for resolving ambiguous queries
            entity_extractor: Optional EntityExtractionService instance
            llm_gateway: Optional LLMGateway instance
            nlm_enrichment_service: Optional NLM enrichment service for CAUTIOUS-zone queries
        Note:
            - Initializes Gemini models (Pro, Flash, Flash-Lite) for cascade fallback
            - Lazy loads OpenRouter client and MemoryOrchestrator on first use
            - Configures intent classifier and emotional attunement services
            - Converts tools to Gemini function declarations for native calling
        """
        logger.debug(f"AgenticRAGOrchestrator.__init__ started. Model: {model_name}")
        self.tools = {tool.name: tool for tool in tools}  # Changed to dict for direct access
        self.db_pool = db_pool
        self.model_name = model_name
        self.semantic_cache = semantic_cache
        self.faq_cache = faq_cache  # FAQ cache (exact match, reduces API costs)
        self.retriever = retriever
        self.clarification_service = clarification_service
        self.nlm_enrichment_service = nlm_enrichment_service
        self.cultural_insights_service = cultural_insights_service
        self.llm_gateway = llm_gateway or LLMGateway()  # Initialize LLMGateway here

        # Convert tools to Gemini function declarations for native calling
        self.gemini_tools = [tool.to_gemini_function_declaration() for tool in tools]
        logger.debug(f"Converted {len(self.gemini_tools)} tools to Gemini function declarations")

        # Initialize IntentClassifier
        logger.debug("AgenticRAGOrchestrator: Initializing IntentClassifier...")
        self.intent_classifier = IntentClassifier()
        logger.debug("AgenticRAGOrchestrator: IntentClassifier initialized")

        # Initialize Emotional Attunement
        logger.debug("AgenticRAGOrchestrator: Initializing EmotionalAttunementService...")
        self.emotional_service = EmotionalAttunementService()
        logger.debug("AgenticRAGOrchestrator: EmotionalAttunementService initialized")

        # Initialize Prompt Builder
        self.prompt_builder = SystemPromptBuilder()

        # Initialize Response Processing Pipeline
        logger.debug("AgenticRAGOrchestrator: Initializing ResponsePipeline...")
        self.response_pipeline = create_default_pipeline()
        logger.debug("AgenticRAGOrchestrator: ResponsePipeline initialized")

        # Initialize LLM Gateway (manages all model interactions and fallbacks)
        logger.debug("AgenticRAGOrchestrator: Initializing LLMGateway...")
        # self.llm_gateway = LLMGateway(gemini_tools=self.gemini_tools) # Moved above
        self.llm_gateway.set_gemini_tools(
            self.gemini_tools,
        )  # Set tools after LLMGateway is initialized
        logger.debug("AgenticRAGOrchestrator: LLMGateway initialized")

        # BRIDGE: Inject LLM Gateway into tools that need semantic intelligence
        # This enables Knowledge Graph Builder to use LLM-based extraction instead of regex-only
        if "knowledge_graph_search" in self.tools:
            kg_tool = self.tools["knowledge_graph_search"]
            if hasattr(kg_tool, "kg_builder") and kg_tool.kg_builder:
                kg_tool.kg_builder.llm_gateway = self.llm_gateway
                logger.info("✅ LLM Gateway injected into KnowledgeGraphBuilder")

        # Initialize Reasoning Engine (manages ReAct loop)
        logger.debug("AgenticRAGOrchestrator: Initializing ReasoningEngine...")
        self.reasoning_engine = ReasoningEngine(
            tool_map=self.tools, response_pipeline=self.response_pipeline,
        )
        logger.debug("AgenticRAGOrchestrator: ReasoningEngine initialized")

        # Initialize Entity Extraction Service
        logger.debug("AgenticRAGOrchestrator: Initializing EntityExtractionService...")
        self.entity_extractor = entity_extractor or EntityExtractionService(
            llm_gateway=self.llm_gateway,
        )
        logger.debug("AgenticRAGOrchestrator: EntityExtractionService initialized")

        # Initialize KG-Enhanced Retrieval Service (legacy)
        self.kg_retrieval = KGEnhancedRetrieval(db_pool) if db_pool else None
        if self.kg_retrieval:
            logger.info("✅ KG-Enhanced Retrieval initialized (legacy)")

        # Initialize KG LangGraph Orchestrator (Phase 3)
        # Feature flag: Set to None to disable LangGraph workflow synthesis
        self.kg_langgraph_orchestrator = None
        kg_langgraph_enabled = os.getenv("ENABLE_KG_LANGGRAPH", "false").lower() in (
            "true",
            "1",
            "yes",
        )

        if db_pool and kg_langgraph_enabled:
            try:
                from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

                self.kg_langgraph_orchestrator = KGLangGraphOrchestrator(db_pool)
                logger.info(
                    "✅ KG LangGraph Orchestrator initialized (Phase 3 - ENABLE_KG_LANGGRAPH=true)",
                )
            except ImportError as e:
                logger.warning(f"⚠️ KG LangGraph Orchestrator not available: {e}")
            except Exception as e:
                logger.error(
                    f"❌ Failed to initialize KG LangGraph Orchestrator: {e}", exc_info=True,
                )
        else:
            if not db_pool:
                logger.warning("⚠️ KG LangGraph Orchestrator DISABLED: db_pool not available")
            elif not kg_langgraph_enabled:
                logger.warning(
                    "⚠️ KG LangGraph Orchestrator DISABLED: ENABLE_KG_LANGGRAPH not set to 'true'",
                )

        # Initialize Follow-up & Golden Answer services
        self.followup_service = FollowupService()
        self.golden_answer_service = GoldenAnswerService(database_url=settings.database_url)

        # Memory Handler - manages memory persistence with race condition protection
        self.memory_handler = MemoryHandler(db_pool=db_pool)

        # Query Gates - pre-processing gates that can bypass RAG pipeline
        self.query_gates = QueryGates(
            prompt_builder=self.prompt_builder,
            clarification_service=clarification_service,
        )

        # Stream event validation configuration
        self._event_validation_enabled = True
        self._max_event_errors = 10  # Max errori prima di abortire stream

        # Context Window Manager for conversation history summarization
        # Summarizes older messages to preserve key facts while managing token budget
        self.context_window_manager = ContextWindowManager(
            max_messages=20,  # Keep last 20 messages in full
            summary_threshold=30,  # Start summarizing when >30 messages
        )
        logger.debug("AgenticRAGOrchestrator: ContextWindowManager initialized")

        logger.debug("AgenticRAGOrchestrator.__init__ completed")

        # Initialize OrchestratorCore (delegates main logic)
        from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
        from backend.services.rag.agentic.orchestrator_streaming import OrchestratorStreamingManager
        from backend.services.rag.agentic.orchestrator_streaming_core import (
            OrchestratorStreamingCore,
        )

        self.core = OrchestratorCore(
            llm_gateway=self.llm_gateway,
            reasoning_engine=self.reasoning_engine,
            prompt_builder=self.prompt_builder,
            query_gates=self.query_gates,
            memory_handler=self.memory_handler,
            context_window_manager=self.context_window_manager,
            entity_extractor=self.entity_extractor,
            kg_retrieval=self.kg_retrieval,
            semantic_cache=self.semantic_cache,
            faq_cache=self.faq_cache,  # FAQ cache (exact match, < 1ms)
            db_pool=db_pool,
            kg_langgraph_orchestrator=self.kg_langgraph_orchestrator,
            nlm_enrichment_service=self.nlm_enrichment_service,
            cultural_insights_service=self.cultural_insights_service,
        )

        # Initialize streaming components
        streaming_manager = OrchestratorStreamingManager(
            max_event_errors=self._max_event_errors,
            event_validation_enabled=self._event_validation_enabled,
        )
        self.streaming_core = OrchestratorStreamingCore(
            core=self.core,
            streaming_manager=streaming_manager,
        )
        logger.info(
            "✅ OrchestratorCore and OrchestratorStreamingCore initialized (Refactored Architecture)",
        )

    async def process_query(
        self,
        query: str,
        user_id: str | None = None,
        conversation_history: list[dict] | None = None,
        start_time: float | None = None,
        session_id: str | None = None,
    ) -> CoreResult:
        """
        Process query with full RAG pipeline - Delegates to OrchestratorCore.

        Args:
            query: Query string
            user_id: Optional user ID
            conversation_history: Optional conversation history
            start_time: Optional start time (defaults to now)
            session_id: Optional session ID

        Returns:
            CoreResult with answer, sources, and metadata
        """
        start_time = start_time or time.time()

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # 🔍 TRACING: Parent span for entire query processing
        with trace_span(
            "orchestrator.process_query",
            {
                "user_id": user_id or "anonymous",
                "query_length": len(query),
                "session_id": session_id or "none",
                "has_history": bool(conversation_history),
            },
        ):
            # Delegate to OrchestratorCore
            logger.debug("Delegating process_query to OrchestratorCore")
            result = await self.core.process_query_core(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                start_time=start_time,
                session_id=session_id,
                tool_execution_counter=tool_execution_counter,
            )

            # 🧠 MEMORY PERSISTENCE: Save facts in background (Sync Path Fix)
            # This ensures parity with stream_query
            if user_id and user_id != "anonymous":
                try:
                    self.memory_handler.create_save_task(
                        user_id=user_id,
                        query=query,
                        answer=result.answer,
                        metrics_collector=metrics_collector,
                    )
                    logger.debug(f"🧠 [Sync] Dispatched memory save task for {user_id}")
                except Exception as mem_err:
                    logger.warning(f"⚠️ [Sync] Failed to dispatch memory save: {mem_err}")

            return result

    def _create_error_event(
        self,
        error_type: str,
        message: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Create standardized error event."""
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

    # ------------------------------------------------------------------
    # Backward-compatibility shims (delegate to memory_handler)
    # ------------------------------------------------------------------

    @property
    def _memory_locks(self) -> dict:
        """Backward-compat: delegate to memory_handler._memory_locks."""
        return self.memory_handler._memory_locks

    @property
    def _lock_timeout(self) -> float:
        """Backward-compat: delegate to memory_handler._lock_timeout."""
        return self.memory_handler._lock_timeout

    @_lock_timeout.setter
    def _lock_timeout(self, value: float) -> None:
        """Backward-compat: delegate to memory_handler._lock_timeout."""
        self.memory_handler._lock_timeout = value

    async def _get_memory_orchestrator(self) -> "MemoryOrchestrator | None":
        """Backward-compat shim: delegate to memory_handler.get_memory_orchestrator()."""
        return await self.memory_handler.get_memory_orchestrator()

    async def _save_conversation_memory(
        self,
        user_id: str,
        query: str,
        answer: str,
    ) -> None:
        """Backward-compat shim: delegate to memory_handler.save_conversation_memory()."""
        await self.memory_handler.save_conversation_memory(
            user_id=user_id,
            query=query,
            answer=answer,
            metrics_collector=metrics_collector,
        )

    async def stream_query(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
        images: list[dict] | None = None,
        channel: str | None = None,
    ):
        """Stream query with comprehensive error handling. Delegates to OrchestratorStreamingCore."""
        # Initialize required arguments for stream_query_core
        tool_execution_counter: dict[str, int] = {"count": 0}
        correlation_id: str = str(uuid.uuid4())

        # Forward to the refactored Streaming Core
        async for event in self.streaming_core.stream_query_core(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history,
            session_id=session_id,
            images=images,
            tool_execution_counter=tool_execution_counter,
            correlation_id=correlation_id,
            channel=channel,
        ):
            yield event
