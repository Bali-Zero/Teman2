"""
Agentic RAG Orchestrator - Refactored Thin Wrapper

Questo è il wrapper pubblico che mantiene backward compatibility.
Delega al OrchestratorCore per la logica principale.

Mantiene la stessa interfaccia pubblica dell'orchestrator originale:
- process_query() -> delega a OrchestratorCore
- stream_query() -> gestito qui (complessità streaming richiede refactoring separato)

Backward Compatibility: 100% - stessa interfaccia, stesso comportamento.
"""

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from backend.services.rag.agentic.kg_enhanced_retrieval import KGEnhancedRetrieval

from backend.app.utils.tracing import add_span_event
from backend.services.misc.clarification_service import ClarificationService
from backend.services.misc.context_window_manager import ContextWindowManager
from backend.services.misc.emotional_attunement import EmotionalAttunementService
from backend.services.misc.followup_service import FollowupService
from backend.services.misc.golden_answer_service import GoldenAnswerService
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.agentic.memory_handler import MemoryHandler
from backend.services.rag.agentic.pipeline import create_default_pipeline
from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder
from backend.services.rag.agentic.query_gates import QueryGates
from backend.services.rag.agentic.reasoning import ReasoningEngine
from backend.services.search.semantic_cache import SemanticCache
from backend.services.tools.definitions import BaseTool

from .llm_gateway import LLMGateway
from .orchestrator_core import OrchestratorCore
from .orchestrator_streaming import OrchestratorStreamingManager
from .schema import CoreResult

logger = logging.getLogger(__name__)


class AgenticRAGOrchestrator:
    """
    Orchestrator for Agentic RAG with Tool Use - Refactored Version.

    Thin wrapper che mantiene backward compatibility e delega al OrchestratorCore.
    Implementa ReAct: Thought → Action → Observation → Repeat

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
        model_name: str = "gemini-3-flash-preview",  # Zantara AI
        semantic_cache: SemanticCache = None,
        retriever: Any = None,
        clarification_service: ClarificationService = None,
        entity_extractor: EntityExtractionService = None,
        llm_gateway: LLMGateway = None,
    ):
        """
        Initialize the AgenticRAGOrchestrator.

        Args:
            tools: List of tool definitions available for agent reasoning
            db_pool: Optional asyncpg connection pool for database operations
            model_name: Base model name (legacy, not actively used)
            semantic_cache: Optional semantic cache instance for query deduplication
            retriever: SearchService or KnowledgeService instance for embeddings
            clarification_service: Optional service for resolving ambiguous queries
            entity_extractor: Optional EntityExtractionService instance
            llm_gateway: Optional LLMGateway instance
        """
        logger.debug(f"AgenticRAGOrchestrator.__init__ started. Model: {model_name}")

        # Store original attributes for backward compatibility
        self.tools = {tool.name: tool for tool in tools}
        self.db_pool = db_pool
        self.model_name = model_name
        self.semantic_cache = semantic_cache
        self.retriever = retriever
        self.clarification_service = clarification_service

        # Initialize LLM Gateway
        self.llm_gateway = llm_gateway or LLMGateway()
        self.gemini_tools = [tool.to_gemini_function_declaration() for tool in tools]
        self.llm_gateway.set_gemini_tools(self.gemini_tools)
        logger.debug(f"Converted {len(self.gemini_tools)} tools to Gemini function declarations")

        # Initialize services (same as original)
        from backend.services.classification.intent_classifier import IntentClassifier

        self.intent_classifier = IntentClassifier()
        self.emotional_service = EmotionalAttunementService()
        self.prompt_builder = SystemPromptBuilder()
        self.response_pipeline = create_default_pipeline()

        # Initialize Reasoning Engine
        self.reasoning_engine = ReasoningEngine(
            tool_map=self.tools, response_pipeline=self.response_pipeline
        )

        # Initialize Entity Extraction Service
        self.entity_extractor = entity_extractor or EntityExtractionService(
            llm_gateway=self.llm_gateway
        )

        # Initialize KG-Enhanced Retrieval Service
        self.kg_retrieval = KGEnhancedRetrieval(db_pool) if db_pool else None

        # Initialize Follow-up & Golden Answer services
        from backend.app.core.config import settings

        self.followup_service = FollowupService()
        self.golden_answer_service = GoldenAnswerService(database_url=settings.database_url)

        # Memory Handler
        self.memory_handler = MemoryHandler(db_pool=db_pool)

        # Query Gates
        self.query_gates = QueryGates(
            prompt_builder=self.prompt_builder,
            clarification_service=clarification_service,
        )

        # Context Window Manager
        self.context_window_manager = ContextWindowManager(
            max_messages=20,
            summary_threshold=30,
        )

        # Streaming Manager
        self.streaming_manager = OrchestratorStreamingManager(
            max_event_errors=10,
            event_validation_enabled=True,
        )

        # Initialize OrchestratorCore (delegates main logic)
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
            db_pool=db_pool,
        )

        # BRIDGE: Inject LLM Gateway into tools that need semantic intelligence
        if "knowledge_graph_search" in self.tools:
            kg_tool = self.tools["knowledge_graph_search"]
            if hasattr(kg_tool, "kg_builder") and kg_tool.kg_builder:
                kg_tool.kg_builder.llm_gateway = self.llm_gateway
                logger.info("✅ LLM Gateway injected into KnowledgeGraphBuilder")

        logger.debug("AgenticRAGOrchestrator.__init__ completed (Refactored)")

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
        tool_execution_counter = {"count": 0}

        # Delegate to core orchestrator
        return await self.core.process_query_core(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history,
            start_time=start_time,
            session_id=session_id,
            tool_execution_counter=tool_execution_counter,
        )

    async def stream_query(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
        images: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream query with comprehensive error handling.

        NOTE: Streaming logic è complesso e richiede refactoring separato.
        Per ora manteniamo la logica originale ma usiamo streaming_manager per event validation.

        Args:
            query: Query string
            user_id: User ID
            conversation_history: Optional conversation history
            session_id: Optional session ID
            images: Optional vision images

        Yields:
            Stream events (dict)
        """
        # TODO: Refactor streaming logic in orchestrator_streaming_core.py
        # Per ora manteniamo logica originale con streaming_manager per validation
        # Questo mantiene backward compatibility mentre prepariamo refactoring completo

        correlation_id = str(uuid.uuid4())

        # Security: Validate user_id format
        if user_id and user_id != "anonymous":
            if not isinstance(user_id, str) or len(user_id) < 1:
                raise ValueError("Invalid user_id format")

        tool_execution_counter = {"count": 0}

        # TRACING: Add span event for stream query start
        add_span_event(
            "stream_query.start",
            {
                "user_id": user_id,
                "query_length": len(query),
                "session_id": session_id or "none",
                "images_count": len(images) if images else 0,
            },
        )

        # Log vision mode if images are attached
        if images:
            logger.info(f"🖼️ Vision mode: {len(images)} images attached to query")

        # NOTE: Per ora manteniamo logica streaming originale
        # Refactoring completo di stream_query sarà fatto in fase 2
        # Questo wrapper mantiene backward compatibility

        # Import original stream_query logic (temporaneo fino a refactoring completo)
        from .orchestrator import AgenticRAGOrchestrator as OriginalOrchestrator

        # Create temporary orchestrator instance per streaming
        # TODO: Estrarre streaming logic in modulo separato
        original = OriginalOrchestrator(
            tools=list(self.tools.values()),
            db_pool=self.db_pool,
            semantic_cache=self.semantic_cache,
            retriever=self.retriever,
            clarification_service=self.clarification_service,
            entity_extractor=self.entity_extractor,
            llm_gateway=self.llm_gateway,
        )

        # Delegate to original stream_query (temporaneo)
        async for event in original.stream_query(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history,
            session_id=session_id,
            images=images,
        ):
            yield event
