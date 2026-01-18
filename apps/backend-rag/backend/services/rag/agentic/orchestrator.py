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

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.metrics import metrics_collector
from backend.app.utils.tracing import (
    add_span_event,
    trace_span,
)
from backend.services.classification.intent_classifier import IntentClassifier
from backend.services.misc.clarification_service import ClarificationService
from backend.services.misc.context_window_manager import ContextWindowManager
from backend.services.misc.emotional_attunement import EmotionalAttunementService
from backend.services.misc.followup_service import FollowupService
from backend.services.misc.golden_answer_service import GoldenAnswerService
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval
from backend.services.response.cleaner import OUT_OF_DOMAIN_RESPONSES, is_out_of_domain
from backend.services.search.semantic_cache import SemanticCache
from backend.services.tools.definitions import BaseTool

from .llm_gateway import LLMGateway
from .memory_handler import MemoryHandler
from .pipeline import create_default_pipeline
from .prompt_builder import SystemPromptBuilder
from .query_gates import QueryGates
from .query_helpers import (
    TIER_FLASH,
    is_conversation_recall_query,
    wrap_query_with_language_instruction,
)
from .reasoning import ReasoningEngine, detect_team_query
from .schema import CoreResult
from .tool_executor import execute_tool

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
        model_name: str = "gemini-3-flash-preview",  # Zantara AI
        semantic_cache: SemanticCache = None,
        retriever: Any = None,
        clarification_service: ClarificationService = None,
        entity_extractor: EntityExtractionService = None,
        llm_gateway: LLMGateway = None,
    ):
        """Initialize the AgenticRAGOrchestrator.

        Sets up model clients, dependencies, and configuration for multi-tier
        agentic reasoning with automatic fallback handling.

        Args:
            tools: List of tool definitions available for agent reasoning
            db_pool: Optional asyncpg connection pool for database operations
            model_name: Base model name (legacy, not actively used)
            semantic_cache: Optional semantic cache instance for query deduplication
            retriever: SearchService or KnowledgeService instance for embeddings
            clarification_service: Optional service for resolving ambiguous queries
            entity_extractor: Optional EntityExtractionService instance
            llm_gateway: Optional LLMGateway instance
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
        self.retriever = retriever
        self.clarification_service = clarification_service
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
            self.gemini_tools
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
            tool_map=self.tools, response_pipeline=self.response_pipeline
        )
        logger.debug("AgenticRAGOrchestrator: ReasoningEngine initialized")

        # Initialize Entity Extraction Service
        logger.debug("AgenticRAGOrchestrator: Initializing EntityExtractionService...")
        self.entity_extractor = entity_extractor or EntityExtractionService(
            llm_gateway=self.llm_gateway
        )
        logger.debug("AgenticRAGOrchestrator: EntityExtractionService initialized")

        # Initialize KG-Enhanced Retrieval Service
        self.kg_retrieval = KGEnhancedRetrieval(db_pool) if db_pool else None
        if self.kg_retrieval:
            logger.info("✅ KG-Enhanced Retrieval initialized")

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
        from .orchestrator_core import OrchestratorCore
        from .orchestrator_streaming import OrchestratorStreamingManager
        from .orchestrator_streaming_core import OrchestratorStreamingCore

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
            "✅ OrchestratorCore and OrchestratorStreamingCore initialized (Refactored Architecture)"
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
            return await self.core.process_query_core(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                start_time=start_time,
                session_id=session_id,
                tool_execution_counter=tool_execution_counter,
            )

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

    async def stream_query(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
        images: list[dict] | None = None,  # Vision images: [{"base64": ..., "name": ...}]
    ) -> AsyncGenerator[dict, None]:
        """Stream query with comprehensive error handling. Supports vision with images."""
        correlation_id = str(uuid.uuid4())

        # Security: Validate user_id format
        if user_id and user_id != "anonymous":
            if not isinstance(user_id, str) or len(user_id) < 1:
                raise ValueError("Invalid user_id format")

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # 🔍 TRACING: Add span event for stream query start
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

        # Prepare context using common logic (for early gates)
        user_context, history_to_use, _ = await self.core.prepare_query_context(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history,
            session_id=session_id,
        )

        logger.info(
            f"🧠 [Stream Context] Loaded context for {user_id or 'anonymous'} (History: {len(history_to_use)} msgs)"
        )

        # -1. SECURITY GATE: Prompt Injection Detection (MUST BE FIRST!)
        is_injection, injection_response = self.prompt_builder.detect_prompt_injection(query)
        if is_injection:
            logger.warning("🛡️ [Security Stream] Blocked prompt injection/off-topic request")
            yield {"type": "metadata", "data": {"status": "blocked", "route": "security-gate"}}
            for token in injection_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # Check Greetings first (skip RAG for simple greetings)
        # INJECT CONTEXT
        greeting_response = self.prompt_builder.check_greetings(query, context=user_context)
        if greeting_response:
            logger.info("👋 [Greeting Stream] Returning direct greeting response (skipping RAG)")
            yield {"type": "metadata", "data": {"status": "greeting", "route": "greeting-pattern"}}
            for token in greeting_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # 0.05 Check Casual Conversation (skip RAG for "come stai", "how are you", etc.)
        casual_response = self.prompt_builder.get_casual_response(query, context=user_context)
        if casual_response:
            logger.info("💬 [Casual Stream] Returning direct casual response (skipping RAG)")
            yield {"type": "metadata", "data": {"status": "casual", "route": "casual-pattern"}}
            for token in casual_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.02)  # Slightly slower for natural feel
            yield {"type": "done", "data": None}
            return

        # 0.5 Check Identity / Hardcoded Patterns
        identity_response = self.prompt_builder.check_identity_questions(
            query, context=user_context
        )
        if identity_response:
            logger.info("🤖 [Identity Stream] Returning hardcoded identity response")
            yield {"type": "metadata", "data": {"status": "identity", "route": "identity-pattern"}}
            for token in identity_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # 0.1 CLARIFICATION GATE (Ambiguity Detection - Stream)
        if self.clarification_service:
            ambiguity_info = self.clarification_service.detect_ambiguity(
                query, conversation_history or user_context.get("history", [])
            )
            if (
                ambiguity_info["is_ambiguous"]
                and ambiguity_info["confidence"] > 0.6
                and ambiguity_info["clarification_needed"]
            ):
                logger.info(
                    f"🛑 [Clarification Gate Stream] Stopped ambiguous query: {ambiguity_info['reasons']}"
                )
                clarification_msg = self.clarification_service.generate_clarification_request(
                    query, ambiguity_info
                )

                yield {
                    "type": "metadata",
                    "data": {
                        "status": "clarification_needed",
                        "confidence": ambiguity_info["confidence"],
                        "reasons": ambiguity_info["reasons"],
                    },
                }

                # Stream the clarification question
                tokens = clarification_msg.split()
                for token in tokens:
                    yield {"type": "token", "data": token + " "}
                    await asyncio.sleep(0.01)

                yield {"type": "done", "data": None}
                return

        # EARLY TEAM QUERY CHECK - handle team questions immediately
        is_team_query, team_query_type, team_search_term = detect_team_query(query)
        if is_team_query and "team_knowledge" in self.tools:  # Changed self.tool_map to self.tools
            logger.info(
                f"🎯 [Early Team Route] Forcing team_knowledge for: {team_query_type}={team_search_term}"
            )
            yield {"type": "metadata", "data": {"status": "team-query", "route": "team-knowledge"}}
            yield {"type": "status", "data": "Fetching team data..."}
            try:
                team_result = await execute_tool(
                    self.tools,  # Changed self.tool_map to self.tools
                    "team_knowledge",
                    {"query_type": team_query_type, "search_term": team_search_term},
                    user_id,
                    tool_execution_counter,
                )
                if team_result and len(team_result) > 20:
                    # Build simple prompt with team context
                    # Language handling: model will match user's language automatically
                    team_prompt = f"""You are ZANTARA. Answer this question using the team data below.
Be direct and factual. IMPORTANT: Respond in the SAME language the user is writing in.

TEAM DATA:
{team_result}

USER QUESTION: {query}

Answer directly. Example: "Zainal Abidin è il CEO di {settings.COMPANY_NAME}."
"""
                    team_chat = self.llm_gateway.create_chat_with_history(
                        history_to_use=history_to_use, model_tier=TIER_FLASH
                    )
                    team_response, model_used, _ = await self.llm_gateway.send_message(
                        team_chat,
                        team_prompt,
                        system_prompt="",
                        tier=TIER_FLASH,
                        enable_function_calling=False,
                    )
                    import re

                    tokens = re.findall(r"\S+|\s+", team_response)
                    for token in tokens:
                        yield {"type": "token", "data": token}
                        await asyncio.sleep(0.01)
                    yield {"type": "done", "data": None}
                    return
            except Exception as e:
                logger.warning(f"⚠️ [Early Team Route] Failed: {e}, falling back to RAG")

        # 🧠 CONVERSATION RECALL GATE - bypass RAG for recall questions
        # This fixes the "lost in the middle" problem where LLM searches Qdrant
        # for information that's actually in the conversation history
        if _is_conversation_recall_query(query) and len(history_to_use) > 0:
            logger.info("🧠 [Recall Gate] Detected conversation recall query - bypassing RAG")
            yield {
                "type": "metadata",
                "data": {"status": "recall", "route": "conversation-history"},
            }
            yield {"type": "status", "data": "Ricordando la conversazione..."}

            # Format conversation history for the prompt
            history_text = "\n".join(
                [
                    f"{'USER' if msg.get('role') == 'user' else 'ASSISTANT'}: {msg.get('content', '')}"
                    for msg in history_to_use[-20:]  # Last 20 messages
                ]
            )

            recall_prompt = f"""You are ZANTARA. The user is asking you to recall something from THIS conversation.

CRITICAL: The answer is in the CONVERSATION HISTORY below. Do NOT say you don't have information - read the history!

CONVERSATION HISTORY:
{history_text}

USER QUESTION: {query}

Answer directly using information from the conversation above. Be specific with names, details, and facts the user mentioned.
Respond in the SAME language the user is using."""

            try:
                recall_chat = self.llm_gateway.create_chat_with_history(
                    history_to_use=[],
                    model_tier=TIER_FLASH,  # Empty history - we put it in prompt
                )
                recall_response, model_used, _, _ = await self.llm_gateway.send_message(
                    recall_chat,
                    recall_prompt,
                    system_prompt="",
                    tier=TIER_FLASH,
                    enable_function_calling=False,
                )
                import re

                tokens = re.findall(r"\S+|\s+", recall_response)
                for token in tokens:
                    yield {"type": "token", "data": token}
                    await asyncio.sleep(0.01)
                yield {"type": "done", "data": {"route": "recall-gate"}}
                return
            except Exception as e:
                logger.warning(f"⚠️ [Recall Gate] Failed: {e}, falling back to RAG")

        # NOTE: Casual conversation detection removed (Dec 2025)
        # The ReAct loop + system prompt now handles this via QUERY CLASSIFICATION - STEP 0
        # The LLM decides when to use tools vs respond directly based on query type

        # Check Out-of-Domain Questions
        out_of_domain, reason = is_out_of_domain(query)
        if out_of_domain and reason:
            logger.info(f"🚫 [Out-of-Domain Stream] Query rejected: {reason}")
            response = OUT_OF_DOMAIN_RESPONSES.get(reason, OUT_OF_DOMAIN_RESPONSES["unknown"])
            yield {"type": "metadata", "data": {"status": "out-of-domain", "reason": reason}}
            for token in response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # After all early gates, delegate to OrchestratorStreamingCore
        logger.debug(f"Entering stream_query core. Query: {query}")

        full_answer = ""
        try:
            # Delegate to OrchestratorStreamingCore for main processing
            async for event in self.streaming_core.stream_query_core(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                session_id=session_id,
                images=images,
                tool_execution_counter=tool_execution_counter,
                correlation_id=correlation_id,
            ):
                # Accumulate tokens for memory saving
                if event.get("type") == "token":
                    full_answer += event.get("data", "")

                yield event

            # 🎯 PROACTIVITY: Generate follow-up questions
            followup_questions = []
            if full_answer and len(full_answer) > 50:  # Only for substantial answers
                try:
                    # Generate follow-up questions with logging
                    logger.debug(
                        "💡 [Orchestrator] Generating follow-up questions",
                        extra={
                            "component": "AgenticRAGOrchestrator",
                            "action": "generate_followups",
                            "user_id": user_id,
                            "query_length": len(query),
                            "response_length": len(result.answer) if hasattr(result, "answer") else 0,
                        },
                    )
                    followup_questions = await self.followup_service.get_followups(
                        query=query,
                        response=full_answer[:500],  # Use first 500 chars for efficiency
                        use_ai=True,  # AI generates in user's language (any language)
                        conversation_context=None,
                    )
                    if followup_questions:
                        logger.info(
                            f"📝 [Proactive] Generated {len(followup_questions)} follow-up questions"
                        )
                        # Emit metadata event with follow-up questions
                        yield {
                            "type": "metadata",
                            "data": {"followup_questions": followup_questions},
                        }
                except Exception as followup_err:
                    logger.warning(f"⚠️ [Proactive] Failed to generate follow-ups: {followup_err}")

        except Exception as e:
            # Use error classification for better error handling
            from backend.app.core.error_classification import ErrorClassifier, get_error_context

            error_category, error_severity = ErrorClassifier.classify_error(e)
            error_context = get_error_context(
                e,
                correlation_id=correlation_id,
                user_id=user_id,
                query=query[:100],
            )

            logger.exception("❌ [Stream] Fatal error in stream_query", extra=error_context)
            add_span_event("react.stream.error", {"error": str(e)})
            # Yield final error event
            yield self._create_error_event(
                "fatal_error", f"Stream failed: {str(e)}", correlation_id
            )
            metrics_collector.stream_fatal_error_total.inc()
            return

        # 🧠 MEMORY PERSISTENCE: Save facts in background after stream completes
        # Uses MemoryHandler which provides race condition protection via per-user locks
        self.memory_handler.create_save_task(
            user_id=user_id,
            query=query,
            answer=full_answer,
            metrics_collector=metrics_collector,
        )

        return
