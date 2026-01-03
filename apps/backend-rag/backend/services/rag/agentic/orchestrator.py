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
from collections import defaultdict
from collections.abc import AsyncGenerator
from typing import Any

import asyncpg
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.utils.tracing import add_span_event, set_span_attribute, set_span_status, trace_span
from services.classification.intent_classifier import IntentClassifier
from services.memory import MemoryOrchestrator
from services.misc.clarification_service import ClarificationService
from services.misc.context_window_manager import ContextWindowManager
from services.misc.emotional_attunement import EmotionalAttunementService
from services.misc.followup_service import FollowupService
from services.misc.golden_answer_service import GoldenAnswerService
from services.rag.agentic.entity_extractor import EntityExtractionService
from services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval
from services.response.cleaner import (
    OUT_OF_DOMAIN_RESPONSES,
    is_out_of_domain,
)
from services.search.semantic_cache import SemanticCache

from .context_manager import get_user_context
from .llm_gateway import LLMGateway
from .pipeline import create_default_pipeline
from .prompt_builder import SystemPromptBuilder
from .reasoning import ReasoningEngine, detect_team_query

# Conversation recall trigger phrases (multilingual)
RECALL_TRIGGERS = [
    # Italian
    "ti ricordi", "ricordi quando", "di che parlavamo", "di che cliente",
    "il cliente di cui", "che mi hai detto", "prima hai detto",
    # English
    "do you remember", "remember when", "what did i say", "what did you say",
    "the client we discussed", "earlier you said", "you mentioned before",
    "recall our conversation", "what we talked about",
    # Indonesian
    "ingat tidak", "kamu ingat", "tadi aku bilang", "sebelumnya",
    "klien yang tadi", "yang kita bahas",
]
from app.metrics import metrics_collector
from services.llm_clients.pricing import TokenUsage
from services.tools.definitions import AgentState, BaseTool

from .schema import CoreResult
from .tool_executor import execute_tool

logger = logging.getLogger(__name__)

# Model Tiers
TIER_FLASH = 0
TIER_LITE = 1
TIER_PRO = 2
TIER_OPENROUTER = 3


class StreamEvent(BaseModel):
    """Schema per eventi stream."""
    type: str
    data: Any
    timestamp: float | None = None
    correlation_id: str | None = None

    class Config:
        arbitrary_types_allowed = True


def _wrap_query_with_language_instruction(query: str) -> str:
    """
    Wrap non-Indonesian queries with explicit language instruction.

    CRITICAL: When using function calling, Gemini often ignores system prompt
    language constraints. This function adds the language instruction directly
    to the query to ensure it's respected.

    Rules:
    - Indonesian queries → No change (Jaksel style OK)
    - All other languages → Add instruction to respond in SAME language, NO Jaksel
    """
    if not query or len(query.strip()) < 2:
        return query

    query_lower = query.lower()

    # Indonesian markers - if found, allow Jaksel style
    indonesian_markers = [
        "apa", "bagaimana", "siapa", "dimana", "kapan", "mengapa",
        "yang", "dengan", "untuk", "dari", "saya", "aku", "kamu",
        "anda", "bisa", "mau", "ingin", "perlu", "tolong", "halo",
        "selamat", "terima kasih", "gimana", "gue", "gw", "lu",
        "dong", "nih", "banget", "keren", "mantap", "boleh"
    ]

    # Check if Indonesian
    indo_count = sum(1 for marker in indonesian_markers if marker in query_lower)
    if indo_count >= 1:
        # Indonesian detected - allow Jaksel, but still add tool instructions
        tool_instruction = """🛠️ TOOL USAGE:
Untuk pertanyaan faktual tentang visa, bisnis, pajak, harga, tim, atau regulasi:
→ SELALU gunakan vector_search tool DULU untuk mengambil informasi terverifikasi
→ Jangan jawab dari ingatan saja - cari di knowledge base
→ Jika tanya harga Bali Zero → gunakan pricing_tool
→ Jika tanya tentang tim → gunakan team_knowledge_tool

Pertanyaan User:
"""
        return tool_instruction + query

    # NOT Indonesian - detect the language and add explicit instruction
    # Detect specific language patterns for clearer instruction
    detected_lang = "the user's language"

    # Chinese detection (contains Chinese characters)
    if any('\u4e00' <= char <= '\u9fff' for char in query):
        detected_lang = "CHINESE (中文)"
    # Arabic detection
    elif any('\u0600' <= char <= '\u06ff' for char in query):
        detected_lang = "ARABIC (العربية)"
    # Cyrillic (Russian/Ukrainian)
    elif any('\u0400' <= char <= '\u04ff' for char in query):
        if any(word in query_lower for word in ["привіт", "як", "справи", "добре", "дякую"]):
            detected_lang = "UKRAINIAN (Українська)"
        else:
            detected_lang = "RUSSIAN (Русский)"
    # Check for specific language patterns
    elif any(word in query_lower for word in ["ciao", "come", "cosa", "voglio", "posso", "grazie", "perché"]):
        detected_lang = "ITALIAN (Italiano)"
    elif any(word in query_lower for word in ["bonjour", "comment", "pourquoi", "merci", "s'il vous"]):
        detected_lang = "FRENCH (Français)"
    elif any(word in query_lower for word in ["hola", "cómo", "como estas", "gracias", "por qué"]):
        detected_lang = "SPANISH (Español)"
    elif any(word in query_lower for word in ["hallo", "wie geht", "danke", "warum", "können"]):
        detected_lang = "GERMAN (Deutsch)"

    language_instruction = f"""
🔴 LANGUAGE: {detected_lang}
🔴 YOUR ENTIRE RESPONSE MUST BE IN {detected_lang}
🔴 DO NOT USE SLANG OR INFORMAL LANGUAGE unless specifically requested.

🛠️ TOOL USAGE INSTRUCTION:
→ ALWAYS use vector_search FIRST to retrieve verified documents from the knowledge base.
→ For relationship/prerequisite questions, use knowledge_graph_search AFTER vector_search (not instead of it).
→ Do NOT answer from memory alone - your evidence score depends on vector_search results.
→ WRONG: knowledge_graph_search only → Evidence=0 → ABSTAIN
→ RIGHT: vector_search → (optional) knowledge_graph_search → Answer with citations

User Query:
"""

    return language_instruction + query


def _is_conversation_recall_query(query: str) -> bool:
    """
    Detect if user is asking to recall something from THIS conversation.

    These questions should NOT trigger RAG search because the information
    is in the conversation history, not in the knowledge base.

    Examples:
    - "Ti ricordi il cliente di cui abbiamo parlato?" → True
    - "Quanto costa un visto E31A?" → False
    """
    query_lower = query.lower()
    return any(trigger in query_lower for trigger in RECALL_TRIGGERS)


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
        self.tools = {tool.name: tool for tool in tools} # Changed to dict for direct access
        self.db_pool = db_pool
        self.model_name = model_name
        self.semantic_cache = semantic_cache
        self.retriever = retriever
        self.clarification_service = clarification_service
        self.llm_gateway = llm_gateway or LLMGateway() # Initialize LLMGateway here

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
        self.llm_gateway.set_gemini_tools(self.gemini_tools) # Set tools after LLMGateway is initialized
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
        self.entity_extractor = entity_extractor or EntityExtractionService(llm_gateway=self.llm_gateway)
        logger.debug("AgenticRAGOrchestrator: EntityExtractionService initialized")

        # Initialize KG-Enhanced Retrieval Service
        self.kg_retrieval = KGEnhancedRetrieval(db_pool) if db_pool else None
        if self.kg_retrieval:
            logger.info("✅ KG-Enhanced Retrieval initialized")

        # Initialize Follow-up & Golden Answer services
        self.followup_service = FollowupService()
        self.golden_answer_service = GoldenAnswerService(database_url=settings.database_url)

        # Memory orchestrator for fact extraction and persistence (lazy loaded)
        self._memory_orchestrator: MemoryOrchestrator | None = None

        # Race condition protection: locks per user_id for memory save operations
        self._memory_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._lock_timeout = 5.0  # seconds

        # Stream event validation configuration
        self._event_validation_enabled = True
        self._max_event_errors = 10  # Max errori prima di abortire stream

        # Context Window Manager for conversation history summarization
        # Summarizes older messages to preserve key facts while managing token budget
        self.context_window_manager = ContextWindowManager(
            max_messages=20,  # Keep last 20 messages in full
            summary_threshold=30  # Start summarizing when >30 messages
        )
        logger.debug("AgenticRAGOrchestrator: ContextWindowManager initialized")

        logger.debug("AgenticRAGOrchestrator.__init__ completed")

    async def _get_memory_orchestrator(self) -> MemoryOrchestrator | None:
        """Lazy load and initialize memory orchestrator for fact extraction.

        Creates MemoryOrchestrator instance on first use to avoid initialization
        overhead when memory features are not needed.

        Returns:
            MemoryOrchestrator instance or None if initialization fails

        Note:
            - Non-fatal errors: returns None and logs warning
            - Used for extracting and persisting conversation facts
            - Requires database pool to be configured
        """
        if self._memory_orchestrator is None:
            try:
                self._memory_orchestrator = MemoryOrchestrator(db_pool=self.db_pool)
                await self._memory_orchestrator.initialize()
                logger.info("✅ MemoryOrchestrator initialized for AgenticRAG")
            except (asyncpg.PostgresError, asyncpg.InterfaceError, ValueError, RuntimeError) as e:
                logger.warning(f"⚠️ Failed to initialize MemoryOrchestrator: {e}", exc_info=True)
                return None
        return self._memory_orchestrator

    async def _save_conversation_memory(self, user_id: str, query: str, answer: str) -> None:
        """Save memory facts from conversation for future personalization.

        Extracts facts from user messages and AI responses, then persists them
        to the database for future context enrichment. Called asynchronously
        after response generation to avoid blocking.

        RACE CONDITION PROTECTION: Uses per-user lock to prevent concurrent
        memory saves for the same user from corrupting data.

        Args:
            user_id: User identifier (email or UUID)
            query: User's original query
            answer: AI's generated response

        Note:
            - Skips anonymous users (user_id == "anonymous")
            - Non-blocking: uses asyncio.create_task() in caller
            - Logs success metrics (facts extracted/saved, processing time)
            - Gracefully handles errors without failing the main flow
            - Lock timeout: 5 seconds (prevents deadlocks)
        """
        if not user_id or user_id == "anonymous":
            return

        lock = self._memory_locks[user_id]
        lock_start_time = time.time()

        try:
            # Acquire lock with timeout to prevent deadlocks
            await asyncio.wait_for(lock.acquire(), timeout=self._lock_timeout)
            try:
                orchestrator = await self._get_memory_orchestrator()
                if not orchestrator:
                    return

                result = await orchestrator.process_conversation(
                    user_email=user_id,
                    user_message=query,
                    ai_response=answer,
                )

                if result.success and result.facts_saved > 0:
                    logger.info(
                        f"💾 [AgenticRAG] Saved {result.facts_saved}/{result.facts_extracted} "
                        f"facts for {user_id} ({result.processing_time_ms:.1f}ms)"
                    )

                # Record lock contention metric
                lock_wait_time = time.time() - lock_start_time
                if lock_wait_time > 0.01:  # Only record if waited > 10ms
                    metrics_collector.record_memory_lock_contention(
                        operation="save_memory",
                        wait_time_seconds=lock_wait_time
                    )

            finally:
                lock.release()

        except asyncio.TimeoutError:
            logger.warning(
                f"⚠️ [AgenticRAG] Memory save lock timeout for user {user_id} "
                f"(timeout: {self._lock_timeout}s)"
            )
            metrics_collector.record_memory_lock_timeout(user_id=user_id)
        except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
            logger.warning(f"⚠️ [AgenticRAG] Failed to save memory: {e}", exc_info=True)

    async def process_query(
        self,
        query: str,
        user_id: str | None = None,
        conversation_history: list[dict] | None = None,
        start_time: float | None = None,
        session_id: str | None = None,
    ) -> CoreResult:
        # Fix: evaluate at call time, not definition time
        start_time = start_time or time.time()

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # 🔍 TRACING: Parent span for entire query processing
        with trace_span("orchestrator.process_query", {
            "user_id": user_id or "anonymous",
            "query_length": len(query),
            "session_id": session_id or "none",
            "has_history": bool(conversation_history),
        }):
            # 1. UNIVERSAL CONTEXT LOADING (CRITICAL: Must be first for Identity)
            effective_user_id = user_id or "anonymous"
            with trace_span("context.load_user", {"user_id": effective_user_id}):
                try:
                    memory_orchestrator = await self._get_memory_orchestrator()
                    user_context = await get_user_context(
                        self.db_pool,
                        effective_user_id,
                        memory_orchestrator,
                        query=query,
                        session_id=session_id,
                    )
                    set_span_attribute("facts_count", len(user_context.get("facts", [])))
                    set_span_status("ok")
                except Exception as e:
                    logger.warning(f"⚠️ [Context] Failed to load user context (degraded): {e}", exc_info=True)
                    user_context = {"profile": None, "facts": [], "collective_facts": [], "history": []}
                    set_span_status("error", str(e))

        history_to_use = conversation_history or user_context.get("history", [])
        if not isinstance(history_to_use, list) or history_to_use and not isinstance(history_to_use[0], dict):
            history_to_use = []

        # Apply context window management for long conversations
        # This prevents "lost in the middle" phenomenon by summarizing older messages
        if len(history_to_use) > 0:
            trim_result = self.context_window_manager.trim_conversation_history(history_to_use)
            if trim_result["needs_summarization"]:
                logger.info(f"📊 [ContextWindow] Summarizing {len(trim_result['messages_to_summarize'])} older messages")
                try:
                    summary = await self.context_window_manager.generate_summary(
                        trim_result["messages_to_summarize"],
                        trim_result["context_summary"]
                    )
                    history_to_use = self.context_window_manager.inject_summary_into_history(
                        trim_result["trimmed_messages"],
                        summary
                    )
                    logger.info(f"✅ [ContextWindow] Summarized to {len(history_to_use)} messages with summary")
                except Exception as e:
                    logger.warning(f"⚠️ [ContextWindow] Summarization failed, using trimmed history: {e}")
                    history_to_use = trim_result["trimmed_messages"]
            else:
                history_to_use = trim_result["trimmed_messages"]

        logger.info(
            f"🧠 [Context] Loaded context for {user_id or 'anonymous'} (Facts: {len(user_context.get('facts', []))}, History: {len(history_to_use)} msgs)"
        )

        # -1. SECURITY GATE: Prompt Injection Detection (MUST BE FIRST!)
        is_injection, injection_response = self.prompt_builder.detect_prompt_injection(query)
        if is_injection:
            logger.warning("🛡️ [Security] Blocked prompt injection/off-topic request")
            return CoreResult(
                answer=injection_response,
                sources=[],
                verification_score=1.0,
                evidence_score=1.0,
                is_ambiguous=False,
                entities={},
                model_used="security-gate",
                timings={"total": time.time() - start_time},
                verification_status="blocked",
                document_count=0
            )

        # 0. Check Greetings (skip RAG for simple greetings)
        # INJECT CONTEXT: Now check_greetings knows who the user is
        greeting_response = self.prompt_builder.check_greetings(query, context=user_context)
        if greeting_response:
            logger.info("👋 [Greeting] Returning direct greeting response (skipping RAG)")
            return CoreResult(
                answer=greeting_response,
                sources=[],
                verification_score=1.0,  # Trusted pattern
                evidence_score=1.0,
                is_ambiguous=False,
                entities={},
                model_used="greeting-pattern",
                timings={"total": time.time() - start_time},
                verification_status="passed",
                document_count=0
            )

        # 0.05 Check Casual Conversation (skip RAG for "come stai", "how are you", etc.)
        casual_response = self.prompt_builder.get_casual_response(query, context=user_context)
        if casual_response:
            logger.info("💬 [Casual] Returning direct casual response (skipping RAG)")
            return CoreResult(
                answer=casual_response,
                sources=[],
                verification_score=1.0,
                evidence_score=1.0,
                is_ambiguous=False,
                entities={},
                model_used="casual-pattern",
                timings={"total": time.time() - start_time},
                verification_status="passed",
                document_count=0
            )

        # 0.1 CLARIFICATION GATE (Ambiguity Detection)
        # Check if query is ambiguous and needs clarification before expensive RAG
        if self.clarification_service:
            ambiguity_info = self.clarification_service.detect_ambiguity(
                query, conversation_history or user_context.get("history", [])
            )
            if (
                ambiguity_info["is_ambiguous"]
                and ambiguity_info["confidence"] > 0.6  # High confidence ambiguity
                and ambiguity_info["clarification_needed"]
            ):
                logger.info(
                    f"🛑 [Clarification Gate] Stopped ambiguous query: {ambiguity_info['reasons']}"
                )
                clarification_msg = self.clarification_service.generate_clarification_request(
                    query, ambiguity_info
                )

                return CoreResult(
                    answer=clarification_msg,
                    sources=[],
                    verification_score=0.0,
                    evidence_score=0.0,
                    is_ambiguous=True,
                    clarification_question=clarification_msg,
                    entities=ambiguity_info.get("entities", {}), # Pass if available, else empty
                    model_used="clarification-gate",
                    timings={"total": time.time() - start_time},
                    verification_status="skipped",
                    document_count=0
                )

        # 0.5 Check Identity / Hardcoded Patterns
        identity_response = self.prompt_builder.check_identity_questions(query, context=user_context)
        if identity_response:
            logger.info("🤖 [Identity] Returning hardcoded identity response")
            return CoreResult(
                answer=identity_response,
                sources=[],
                verification_score=1.0,
                evidence_score=1.0,
                is_ambiguous=False,
                entities={},
                model_used="identity-pattern",
                timings={"total": time.time() - start_time},
                verification_status="passed",
                document_count=0
            )

        # NOTE: Casual conversation detection removed (Dec 2025)
        # The ReAct loop + system prompt now handles this via QUERY CLASSIFICATION - STEP 0
        # The LLM decides when to use tools vs respond directly based on query type

        # 0.7 Check Out-of-Domain Questions
        out_of_domain, reason = is_out_of_domain(query)
        if out_of_domain and reason:
            logger.info(f"🚫 [Out-of-Domain] Query rejected: {reason}")
            answer_text = OUT_OF_DOMAIN_RESPONSES.get(reason, OUT_OF_DOMAIN_RESPONSES["unknown"])
            return CoreResult(
                    answer=answer_text,
                    sources=[],
                    verification_score=0.0,
                    evidence_score=0.0,
                    is_ambiguous=False,
                    entities={},
                    model_used=f"out-of-domain-{reason}",
                    timings={"total": time.time() - start_time},
                    verification_status="blocked",
                    document_count=0,
                    warnings=[f"Query blocked: {reason}"]
                )

        # 0.8 PRE-RAG ENTITY EXTRACTION
        with trace_span("entity.extraction", {"query_length": len(query)}):
            extracted_entities = await self.entity_extractor.extract_entities(query)
            if any(extracted_entities.values()):
                logger.info(f"🔍 [Entity Extraction] Extracted entities: {extracted_entities}")
                set_span_attribute("entities_found", str(extracted_entities))
            set_span_status("ok")

        # OPTIMIZATION 1: Check semantic cache first
        with trace_span("cache.semantic_check", {"cache_enabled": bool(self.semantic_cache)}):
            if self.semantic_cache:
                try:
                    cached = await self.semantic_cache.get_cached_result(query)
                    if cached:
                        logger.info("✅ [Cache Hit] Returning cached result for query")
                        set_span_attribute("cache_hit", "true")
                        set_span_status("ok")
                        # If cached is already a dict compatible with CoreResult?
                        # Semantic Cache stores dicts. We might need to map it back to CoreResult.
                        # Assuming cached['result'] is the answer if it's the old format.
                        # Best effort mapping for now:

                        cached_result = cached.get("result", cached) # Handle wrapper

                        # Check if it's a dict that looks like CoreResult (has 'model_used' etc) or old result
                        answer = cached_result.get("answer", "")
                        sources = cached_result.get("sources", [])

                        return CoreResult(
                            answer=answer,
                            sources=sources,
                            model_used="cache",
                            cache_hit=True,
                            timings={"total": time.time() - start_time},
                            entities=extracted_entities,
                            document_count=len(sources)
                        )
                    else:
                        set_span_attribute("cache_hit", "false")
                except (KeyError, ValueError, RuntimeError) as e:
                    logger.warning(f"Cache lookup failed: {e}", exc_info=True)
                    set_span_status("error", str(e))

        # Default model tier (will be refined by intent classifier if not streaming)
        model_tier = TIER_PRO # Default to PRO for non-streaming
        deep_think_mode = False

        # Initialize state components for ReAct
        # Non-streaming defaults to business_complex to allow multi-tool reasoning
        state = AgentState(query=query, intent_type="business_complex")

        # Build system prompt with KG context
        system_context_for_prompt = ""
        if any(extracted_entities.values()):
            system_context_for_prompt = f"\nKNOWN ENTITIES (Use strict filtering if possible): {extracted_entities}"

        # KG-Enhanced Retrieval: Get graph context for query
        kg_context = None
        if self.kg_retrieval:
            try:
                kg_context = await self.kg_retrieval.get_context_for_query(query, max_depth=1)
                if kg_context and kg_context.graph_summary:
                    system_context_for_prompt += "\n" + kg_context.graph_summary
                    logger.info(f"🔗 [KG] Added {len(kg_context.entities_found)} entities, {len(kg_context.relationships)} relationships to context")
            except Exception as e:
                logger.warning(f"⚠️ [KG] Failed to get graph context: {e}")

        system_prompt = self.prompt_builder.build_system_prompt(
            user_id=user_id or "anonymous",
            context=user_context,
            query=query,
            additional_context=system_context_for_prompt, # Inject extracted entities + KG context
            conversation_history=history_to_use  # Pass history for greeting check
        )

        # Create chat session
        chat = self.llm_gateway.create_chat_with_history(
             history_to_use=history_to_use,
             model_tier=model_tier
        )
        # --- QUALITY ROUTING: REACT LOOP (Full Agentic Architecture) ---
        logger.info(f"🚀 [AgenticRAG] Processing query with ReAct loop (Model tier: {model_tier})")

        # 🔍 EXTENDED TRACING: Metrics Collection
        timings = {
            "total": 0.0,
            "embedding": 0.0,
            "search": 0.0,
            "rerank": 0.0,
            "llm": 0.0,
            "reasoning": 0.0
        }

        # Initialize token usage for tracking (default if exception occurs)
        token_usage = TokenUsage()

        with trace_span("react.loop", {
            "model_tier": model_tier,
            "user_id": user_id or "anonymous",
            "query_length": len(query),
        }):
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
                    initial_prompt=_wrap_query_with_language_instruction(query),
                    system_prompt=system_prompt,
                    query=query,
                    user_id=user_id or "anonymous",
                    model_tier=model_tier,
                    tool_execution_counter=tool_execution_counter,
                )
                loop_duration = time.time() - loop_start
                timings["reasoning"] = loop_duration

                # Note: Granular timing extraction moved to post-loop processing
                # where we iterate over state.steps and use step.action.execution_time

                set_span_attribute("model_used", model_used_name)
                set_span_attribute("steps_count", len(state.steps))
                set_span_attribute("tools_executed", tool_execution_counter["count"])
                set_span_status("ok")
            except Exception as react_error:
                logger.error(f"❌ ReAct loop failed: {react_error}", exc_info=True)
                set_span_status("error", str(react_error))
                raise

        # Calculate execution time
        execution_time = time.time() - start_time
        timings["total"] = execution_time

        # Extract sources from tool results
        if hasattr(state, "sources") and state.sources:
            sources = state.sources
        else:
            sources = [s.action.result for s in state.steps if s.action and s.action.result]

        # Calculate context used (sum of observation lengths)
        context_used = sum(len(s.observation or "") for s in state.steps)

        # 🔍 Extract REAL timings from tool execution_time (Dec 2025 fix)
        # Each ToolCall now has execution_time populated by execute_tool()
        search_latency_accum = 0.0
        tool_latency_accum = 0.0
        collections_used = set()

        for step in state.steps:
            if step.action:
                # Get real execution time from the tool call
                tool_time = getattr(step.action, "execution_time", 0.0)
                tool_latency_accum += tool_time

                if step.action.tool_name == "vector_search":
                    search_latency_accum += tool_time
                    # Try to extract collection from arguments
                    if step.action.arguments:
                        col = step.action.arguments.get("collection")
                        if col:
                            collections_used.add(col)

        # Calculate timing breakdown
        if tool_latency_accum > 0:
            timings["search"] = search_latency_accum
            timings["tools"] = tool_latency_accum
            # LLM time = total reasoning time minus tool execution time
            timings["llm"] = max(0, timings["reasoning"] - tool_latency_accum)
        else:
            # No tools executed - all time was LLM
            timings["llm"] = timings["reasoning"]

        # 📊 Record RAG query metrics for Prometheus/Grafana
        primary_collection = next(iter(collections_used), "unknown")
        route_used = "agentic" if tool_execution_counter["count"] > 0 else "direct"
        metrics_collector.record_rag_query(
            collection=primary_collection,
            route_used=route_used,
            status="success",
            context_tokens=context_used,
        )

        # Record token usage metrics for Prometheus
        metrics_collector.record_llm_token_usage(
            model=model_used_name,
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            cost_usd=token_usage.cost_usd,
            endpoint="chat",
        )

        # Build CoreResult
        return CoreResult(
            answer=state.final_answer,
            sources=sources,
            verification_score=getattr(state, "verification_score", 0.0),
            evidence_score=getattr(state, "evidence_score", 0.0),
            is_ambiguous=False,
            entities=extracted_entities,
            model_used=model_used_name,
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            total_tokens=token_usage.total_tokens,
            cost_usd=token_usage.cost_usd,
            verification_status="passed" if getattr(state, "verification_score", 0.0) > 0.7 else "unchecked",
            document_count=len(sources),
            timings=timings,
            warnings=[]
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
        event_error_count = 0

        # Security: Validate user_id format
        if user_id and user_id != "anonymous":
            if not isinstance(user_id, str) or len(user_id) < 1:
                raise ValueError("Invalid user_id format")

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # 🔍 TRACING: Add span event for stream query start
        add_span_event("stream_query.start", {
            "user_id": user_id,
            "query_length": len(query),
            "session_id": session_id or "none",
            "images_count": len(images) if images else 0,
        })

        # Log vision mode if images are attached
        if images:
            logger.info(f"🖼️ Vision mode: {len(images)} images attached to query")

        # UNIVERSAL CONTEXT LOADING (Stream)
        with trace_span("context.load_user_stream", {"user_id": user_id}):
            try:
                memory_orchestrator = await self._get_memory_orchestrator()
                user_context = await get_user_context(
                    self.db_pool,
                    user_id,
                    memory_orchestrator,
                    query=query,
                    session_id=session_id
                )
                set_span_attribute("facts_count", len(user_context.get("facts", [])))
                set_span_status("ok")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load user context in stream: {e}")
                user_context = {}
                set_span_status("error", str(e))

        history_to_use = conversation_history or user_context.get("history", [])
        if not isinstance(history_to_use, list) or history_to_use and not isinstance(history_to_use[0], dict):
            history_to_use = []

        # Apply context window management for long conversations
        # This prevents "lost in the middle" phenomenon by summarizing older messages
        if len(history_to_use) > 0:
            trim_result = self.context_window_manager.trim_conversation_history(history_to_use)
            if trim_result["needs_summarization"]:
                logger.info(f"📊 [ContextWindow Stream] Summarizing {len(trim_result['messages_to_summarize'])} older messages")
                try:
                    summary = await self.context_window_manager.generate_summary(
                        trim_result["messages_to_summarize"],
                        trim_result["context_summary"]
                    )
                    history_to_use = self.context_window_manager.inject_summary_into_history(
                        trim_result["trimmed_messages"],
                        summary
                    )
                    logger.info(f"✅ [ContextWindow Stream] Summarized to {len(history_to_use)} messages with summary")
                except Exception as e:
                    logger.warning(f"⚠️ [ContextWindow Stream] Summarization failed, using trimmed history: {e}")
                    history_to_use = trim_result["trimmed_messages"]
            else:
                history_to_use = trim_result["trimmed_messages"]

        logger.info(f"🧠 [Stream Context] Loaded context for {user_id or 'anonymous'} (History: {len(history_to_use)} msgs)")

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
        identity_response = self.prompt_builder.check_identity_questions(query, context=user_context)
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
                        "reasons": ambiguity_info["reasons"]
                    }
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
        if is_team_query and "team_knowledge" in self.tools: # Changed self.tool_map to self.tools
            logger.info(f"🎯 [Early Team Route] Forcing team_knowledge for: {team_query_type}={team_search_term}")
            yield {"type": "metadata", "data": {"status": "team-query", "route": "team-knowledge"}}
            yield {"type": "status", "data": "Fetching team data..."}
            try:
                team_result = await execute_tool(
                    self.tools, # Changed self.tool_map to self.tools
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
                        team_chat, team_prompt, system_prompt="", tier=TIER_FLASH, enable_function_calling=False
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
            yield {"type": "metadata", "data": {"status": "recall", "route": "conversation-history"}}
            yield {"type": "status", "data": "Ricordando la conversazione..."}

            # Format conversation history for the prompt
            history_text = "\n".join([
                f"{'USER' if msg.get('role') == 'user' else 'ASSISTANT'}: {msg.get('content', '')}"
                for msg in history_to_use[-20:]  # Last 20 messages
            ])

            recall_prompt = f"""You are ZANTARA. The user is asking you to recall something from THIS conversation.

CRITICAL: The answer is in the CONVERSATION HISTORY below. Do NOT say you don't have information - read the history!

CONVERSATION HISTORY:
{history_text}

USER QUESTION: {query}

Answer directly using information from the conversation above. Be specific with names, details, and facts the user mentioned.
Respond in the SAME language the user is using."""

            try:
                recall_chat = self.llm_gateway.create_chat_with_history(
                    history_to_use=[], model_tier=TIER_FLASH  # Empty history - we put it in prompt
                )
                recall_response, model_used, _, _ = await self.llm_gateway.send_message(
                    recall_chat, recall_prompt, system_prompt="", tier=TIER_FLASH, enable_function_calling=False
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

        logger.debug(f"Entering stream_query. Query: {query}")
        # 0. Start Timer & Initialize
        start_time = time.time()

        # 0.2 PRE-RAG ENTITY EXTRACTION
        with trace_span("entity.extraction_stream", {"query_length": len(query)}):
            extracted_entities = await self.entity_extractor.extract_entities(query)
            if any(extracted_entities.values()):
                logger.info(f"🔍 [Entity Extraction Stream] Extracted entities: {extracted_entities}")
                set_span_attribute("entities_found", str(extracted_entities))
                yield {
                    "type": "metadata",
                    "data": {"extracted_entities": extracted_entities}
                }
            set_span_status("ok")

        # 1. SEMANTIC CACHE CHECK
        with trace_span("cache.semantic_check_stream", {"cache_enabled": bool(self.semantic_cache)}):
            if self.semantic_cache:
                try:
                    cached = await self.semantic_cache.get_cached_result(query)
                    if cached:
                        logger.info("✅ [Cache Hit Stream] Returning cached result for query")
                        set_span_attribute("cache_hit", "true")
                        set_span_status("ok")
                        result = cached.get("result", cached)
                        result["cache_hit"] = cached.get("cache_hit", "exact")
                        result["execution_time"] = time.time() - start_time

                        yield {"type": "metadata", "data": {"status": "cache-hit", "route": "semantic-cache"}}
                        for token in result["answer"].split():
                            yield {"type": "token", "data": token + " "}
                            await asyncio.sleep(0.01)
                        if result.get("sources"):
                            yield {"type": "sources", "data": result["sources"]}
                        yield {"type": "done", "data": result}
                        return
                    else:
                        set_span_attribute("cache_hit", "false")
                except (KeyError, ValueError, RuntimeError) as e:
                    logger.warning(f"Cache lookup failed: {e}", exc_info=True)
                    set_span_status("error", str(e))

        # 1. User Context & Intent Classification
        logger.debug("Calling verify_intent...")
        intent = await self.intent_classifier.classify_intent(query)
        logger.debug(f"Intent classified: {intent}")
        suggested_ai = intent.get("suggested_ai", "FLASH")
        # Ensure deep_think_mode is bool
        deep_think_mode = bool(intent.get("deep_think_mode", False))

        if suggested_ai == "deep_think":
            model_tier = TIER_PRO
            deep_think_mode = True
        elif suggested_ai == "pro":
            model_tier = TIER_PRO
        else:
            model_tier = TIER_FLASH

        # Pass skip_rag flag for general tasks (translation, summarization, etc.)
        skip_rag = intent.get("skip_rag", False)
        intent_category = intent.get("category", "simple")
        state = AgentState(query=query, skip_rag=skip_rag, intent_type=intent_category)
        logger.debug(f"User context retrieved (early). History len: {len(history_to_use)}")

        # --- QUALITY ROUTING: REACT LOOP STREAMING (Full Agentic Architecture) ---
        logger.info(f"🧠 [Stream] Processing query with ReAct loop for user {user_id}")

        # Build system prompt with KG context
        system_context_for_prompt = ""
        if any(extracted_entities.values()):
            system_context_for_prompt = f"\nKNOWN ENTITIES (Use strict filtering if possible): {extracted_entities}"

        # KG-Enhanced Retrieval: Get graph context for query
        if self.kg_retrieval:
            try:
                kg_context = await self.kg_retrieval.get_context_for_query(query, max_depth=1)
                if kg_context and kg_context.graph_summary:
                    system_context_for_prompt += "\n" + kg_context.graph_summary
                    logger.info(f"🔗 [KG] Added {len(kg_context.entities_found)} entities, {len(kg_context.relationships)} relationships to context")
            except Exception as e:
                logger.warning(f"⚠️ [KG] Failed to get graph context: {e}")

        system_prompt = self.prompt_builder.build_system_prompt(
            user_id, user_context, query, deep_think_mode=deep_think_mode,
            additional_context=system_context_for_prompt, # Inject extracted entities + KG context
            conversation_history=history_to_use  # Pass history for greeting check
        )

        # Create chat session
        chat = self.llm_gateway.create_chat_with_history(
            history_to_use=history_to_use, model_tier=model_tier
        )

        # Stream response using New Streaming ReAct Logic
        # 🔍 TRACING: Add event for ReAct stream start
        add_span_event("react.stream.start", {
            "model_tier": model_tier,
            "user_id": user_id,
        })

        full_answer = ""
        try:
            # Yield initial status
            yield {
                "type": "status",
                "data": {"status": "processing", "correlation_id": correlation_id},
                "timestamp": time.time(),
            }

            async for raw_event in self.reasoning_engine.execute_react_loop_stream(
                state=state,
                llm_gateway=self.llm_gateway,
                chat=chat,
                initial_prompt=_wrap_query_with_language_instruction(query), # Wrapped with language instruction
                system_prompt=system_prompt, # System prompt with injected entities
                query=query,
                user_id=user_id or "anonymous",
                model_tier=model_tier,
                tool_execution_counter=tool_execution_counter,
                images=images,  # Pass vision images to reasoning loop
            ):
                # Validate event structure
                try:
                    if raw_event is None:
                        event_error_count += 1
                        logger.warning(
                            "⚠️ [Stream] None event received",
                            extra={
                                "correlation_id": correlation_id,
                                "user_id": user_id,
                                "error_count": event_error_count,
                            }
                        )
                        metrics_collector.stream_event_none_total.inc()

                        if event_error_count >= self._max_event_errors:
                            yield self._create_error_event(
                                "too_many_errors",
                                "Stream aborted due to too many malformed events",
                                correlation_id
                            )
                            break
                        continue

                    if not isinstance(raw_event, dict):
                        event_error_count += 1
                        logger.error(
                            f"❌ [Stream] Invalid event type: {type(raw_event)}",
                            extra={
                                "correlation_id": correlation_id,
                                "user_id": user_id,
                                "event_type": str(type(raw_event)),
                                "error_count": event_error_count,
                            }
                        )
                        metrics_collector.stream_event_invalid_type_total.inc()
                        continue

                    # Validate event schema
                    if self._event_validation_enabled:
                        try:
                            validated_event = StreamEvent(**raw_event)
                            event = validated_event.model_dump(exclude_none=True)
                        except ValidationError as e:
                            event_error_count += 1
                            logger.error(
                                f"❌ [Stream] Event validation failed: {e}",
                                extra={
                                    "correlation_id": correlation_id,
                                    "user_id": user_id,
                                    "validation_errors": str(e.errors()),
                                    "raw_event": str(raw_event)[:200],
                                }
                            )
                            metrics_collector.stream_event_validation_failed_total.inc()

                            # Yield error event to client
                            yield self._create_error_event(
                                "validation_error",
                                f"Event validation failed: {str(e)}",
                                correlation_id
                            )
                            continue
                    else:
                        # Skip validation but still yield
                        event = raw_event

                    # Accumulate for memory saving later
                    if event.get("type") == "token":
                        full_answer += event.get("data", "")

                    # Yield validated event to frontend
                    yield event

                except Exception as e:
                    event_error_count += 1
                    # Use error classification for better error handling
                    from app.core.error_classification import ErrorClassifier, get_error_context
                    error_category, error_severity = ErrorClassifier.classify_error(e)
                    error_context = get_error_context(
                        e,
                        correlation_id=correlation_id,
                        user_id=user_id,
                        event_error_count=event_error_count,
                    )

                    logger.exception(
                        "❌ [Stream] Unexpected error processing event",
                        extra=error_context
                    )
                    metrics_collector.stream_event_processing_error_total.inc()

                    if event_error_count >= self._max_event_errors:
                        yield self._create_error_event(
                            "processing_error",
                            f"Stream aborted: {str(e)}",
                            correlation_id
                        )
                        break

            # Emit done event (and save memory)
            execution_time = time.time() - start_time

            # 🔍 TRACING: Add event for stream completion
            add_span_event("react.stream.complete", {
                "execution_time_ms": int(execution_time * 1000),
                "answer_length": len(full_answer),
                "tools_executed": tool_execution_counter["count"],
            })

            # 🎯 PROACTIVITY: Generate follow-up questions
            followup_questions = []
            if full_answer and len(full_answer) > 50:  # Only for substantial answers
                try:
                    followup_questions = await self.followup_service.get_followups(
                        query=query,
                        response=full_answer[:500],  # Use first 500 chars for efficiency
                        use_ai=True,  # AI generates in user's language (any language)
                        conversation_context=None
                    )
                    if followup_questions:
                        logger.info(f"📝 [Proactive] Generated {len(followup_questions)} follow-up questions")
                        # Emit metadata event with follow-up questions
                        yield {
                            "type": "metadata",
                            "data": {"followup_questions": followup_questions}
                        }
                except Exception as followup_err:
                    logger.warning(f"⚠️ [Proactive] Failed to generate follow-ups: {followup_err}")

            # 🧠 MEMORY PERSISTENCE (background)
            if full_answer and user_id and user_id != "anonymous":
                try:
                    asyncio.create_task(
                        self._save_conversation_memory(user_id, query, full_answer)
                    )
                except Exception as mem_err:
                    logger.warning(f"Failed to trigger memory save: {mem_err}")

            yield {
                "type": "done",
                "data": {
                    "execution_time": execution_time,
                    "route_used": f"agentic-rag-stream ({self.llm_gateway._genai_client.DEFAULT_MODEL})",
                },
            }
        except Exception as e:
            # Use error classification for better error handling
            from app.core.error_classification import ErrorClassifier, get_error_context
            error_category, error_severity = ErrorClassifier.classify_error(e)
            error_context = get_error_context(
                e,
                correlation_id=correlation_id,
                user_id=user_id,
                query=query[:100],
            )

            logger.exception(
                "❌ [Stream] Fatal error in stream_query",
                extra=error_context
            )
            add_span_event("react.stream.error", {"error": str(e)})
            # Yield final error event
            yield self._create_error_event(
                "fatal_error",
                f"Stream failed: {str(e)}",
                correlation_id
            )
            metrics_collector.stream_fatal_error_total.inc()
            return

        # 🧠 MEMORY PERSISTENCE: Save facts in background after stream completes
        if full_answer and user_id and user_id != "anonymous":
            task = asyncio.create_task(
                self._save_conversation_memory(
                    user_id=user_id,
                    query=query,
                    answer=full_answer,
                )
            )
            task.add_done_callback(
                lambda t: logger.error(f"❌ Memory save failed: {t.exception()}")
                if t.exception() else None
            )

        return
