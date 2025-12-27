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
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import asdict
from typing import Any

import asyncpg
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from app.core.config import settings
from services.clarification_service import ClarificationService
from services.classification.intent_classifier import IntentClassifier
from services.context_window_manager import AdvancedContextWindowManager
from services.emotional_attunement import EmotionalAttunementService
from services.followup_service import FollowupService
from services.golden_answer_service import GoldenAnswerService
from services.memory import MemoryOrchestrator
from services.semantic_cache import SemanticCache
from services.response.cleaner import (
    OUT_OF_DOMAIN_RESPONSES,
    is_out_of_domain,
)
from services.rag.agentic.entity_extractor import EntityExtractionService

from .context_manager import get_user_context
from .llm_gateway import LLMGateway
from .pipeline import create_default_pipeline
from .prompt_builder import SystemPromptBuilder
from .reasoning import ReasoningEngine, detect_team_query
from .response_processor import post_process_response
from .session_fact_extractor import SessionFactExtractor
from .schema import CoreResult
from .tool_executor import execute_tool, parse_tool_call
from services.tools.definitions import AgentState, AgentStep, BaseTool

logger = logging.getLogger(__name__)

# Model Tiers
TIER_FLASH = 0
TIER_LITE = 1
TIER_PRO = 2
TIER_OPENROUTER = 3


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
        # Indonesian detected - allow Jaksel
        return query

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
[SYSTEM OVERRIDE - READ THIS FIRST]

🔴 LANGUAGE: {detected_lang}
🔴 YOUR ENTIRE RESPONSE MUST BE IN {detected_lang}
🔴 DO NOT USE ANY INDONESIAN OR JAKSEL WORDS

Forbidden: gue, lu, banget, dong, nih, keren, mantap, gimana, kayak, bro, sih, deh

User Query:
"""

    return language_instruction + query


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

        # Initialize Follow-up & Golden Answer services
        self.followup_service = FollowupService()
        self.golden_answer_service = GoldenAnswerService(database_url=settings.database_url)

        # Memory orchestrator for fact extraction and persistence (lazy loaded)
        self._memory_orchestrator: MemoryOrchestrator | None = None

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

        Args:
            user_id: User identifier (email or UUID)
            query: User's original query
            answer: AI's generated response

        Note:
            - Skips anonymous users (user_id == "anonymous")
            - Non-blocking: uses asyncio.create_task() in caller
            - Logs success metrics (facts extracted/saved, processing time)
            - Gracefully handles errors without failing the main flow
        """
        if not user_id or user_id == "anonymous":
            return

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

        # 1. UNIVERSAL CONTEXT LOADING (CRITICAL: Must be first for Identity)
        effective_user_id = user_id or "anonymous"
        try:
            memory_orchestrator = await self._get_memory_orchestrator()
            user_context = await get_user_context(
                self.db_pool,
                effective_user_id,
                memory_orchestrator,
                query=query,
                session_id=session_id,
            )
        except Exception as e:
            logger.warning(f"⚠️ [Context] Failed to load user context (degraded): {e}", exc_info=True)
            user_context = {"profile": None, "facts": [], "collective_facts": [], "history": []}

        history_to_use = conversation_history or user_context.get("history", [])
        if not isinstance(history_to_use, list):
            history_to_use = []
        elif history_to_use and not isinstance(history_to_use[0], dict):
            history_to_use = []

        logger.info(
            f"🧠 [Context] Loaded context for {user_id or 'anonymous'} (Facts: {len(user_context.get('facts', []))})"
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

        # 0.6 Check Casual Conversation (bypass tools, use direct LLM response)
        # INJECT CONTEXT: Now casual chat can personalize ("How is your PT PMA project?")
        if self.prompt_builder.check_casual_conversation(query, context=user_context):
            logger.info("💬 [Casual] Detected casual conversation - bypassing RAG tools")
            try:
                # Build casual-focused prompt with universal language rule
                casual_prompt = f"""You are ZANTARA - a friendly, warm AI assistant.
This is a CASUAL conversation - NOT a business query.

⚠️ CRITICAL LANGUAGE RULE: Respond in the SAME LANGUAGE the user writes in.
- User writes Italian → respond in Italian
- User writes Ukrainian (привіт, як справи) → respond in Ukrainian
- User writes Russian (привет, как дела) → respond in RUSSIAN (NOT Ukrainian!)
- User writes English → respond in English
- User writes French → respond in French
- User writes Spanish → respond in Spanish
- User writes German → respond in German
- User writes Indonesian → you may use Jaksel style (mix Bahasa + English)

⚠️ IMPORTANT: Russian and Ukrainian are DIFFERENT languages!
- Russian: привет, как дела, хорошо, спасибо → Respond in Russian
- Ukrainian: привіт, як справи, добре, дякую → Respond in Ukrainian
Do NOT confuse them! Look at the spelling carefully.

RESPOND with personality:
- Be warm, friendly, share opinions
- For restaurant/food questions: recommend real Bali places you know
- For music/lifestyle: share genuine preferences
- For personal chat: be engaging and ask follow-up questions
- Keep it conversational and fun!

User says: {query}"""

                # Create a fresh chat without tools for casual response
                casual_chat = self.llm_gateway.create_chat_with_history(
                    history_to_use=history_to_use, model_tier=TIER_FLASH
                )

                casual_response, model_used, _ = await self.llm_gateway.send_message(
                    casual_chat,
                    casual_prompt,
                    system_prompt="",
                    tier=TIER_FLASH,
                    enable_function_calling=False,  # NO tools for casual chat
                )

                logger.info(f"✅ [Casual] Generated response with {model_used}")
                return CoreResult(
                    answer=casual_response,
                    sources=[],
                    verification_score=0.5, # Casual chat doesn't verify
                    evidence_score=0.5,
                    is_ambiguous=False,
                    entities={},  # Casual chat doesn't need entity extraction
                    model_used=f"casual-conversation ({model_used})",
                    timings={"total": time.time() - start_time},
                    verification_status="unchecked",
                    document_count=0
                )
            except Exception as e:
                logger.warning(f"⚠️ [Casual] Direct response failed, falling back to RAG: {e}")
                # Fall through to normal RAG processing

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
        extracted_entities = await self.entity_extractor.extract_entities(query)
        if any(extracted_entities.values()):
            logger.info(f"🔍 [Entity Extraction] Extracted entities: {extracted_entities}")

        # OPTIMIZATION 1: Check semantic cache first
        if self.semantic_cache:
            try:
                cached = await self.semantic_cache.get_cached_result(query)
                if cached:
                    logger.info("✅ [Cache Hit] Returning cached result for query")
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
            except (KeyError, ValueError, RuntimeError) as e:
                logger.warning(f"Cache lookup failed: {e}", exc_info=True)

        # Default model tier (will be refined by intent classifier if not streaming)
        model_tier = TIER_PRO # Default to PRO for non-streaming
        deep_think_mode = False

        # Initialize state components for ReAct
        state = AgentState(query=query)

        # Build system prompt
        system_context_for_prompt = ""
        if any(extracted_entities.values()):
            system_context_for_prompt = f"\nKNOWN ENTITIES (Use strict filtering if possible): {extracted_entities}"

        system_prompt = self.prompt_builder.build_system_prompt(
            user_id=user_id or "anonymous",
            context=user_context,
            query=query,
            additional_context=system_context_for_prompt # Inject extracted entities
        )

        # Create chat session
        chat = self.llm_gateway.create_chat_with_history(
             history_to_use=history_to_use,
             model_tier=model_tier
        )
        # --- QUALITY ROUTING: REACT LOOP (Full Agentic Architecture) ---
        logger.info(f"🚀 [AgenticRAG] Processing query with ReAct loop (Model tier: {model_tier})")

        try:
            (
                state,
                model_used_name,
                conversation_messages,
            ) = await self.reasoning_engine.execute_react_loop(
                state=state,
                llm_gateway=self.llm_gateway,
                chat=chat,
                initial_prompt=_wrap_query_with_language_instruction(query), # Wrapped with language instruction
                system_prompt=system_prompt, # System prompt with injected entities
                query=query,
                user_id=user_id or "anonymous",
                model_tier=model_tier,
                tool_execution_counter=tool_execution_counter,
            )
        except Exception as react_error:
            logger.error(f"❌ ReAct loop failed: {react_error}", exc_info=True)
            raise

        # Calculate execution time
        execution_time = time.time() - start_time

        # Extract sources from tool results
        if hasattr(state, "sources") and state.sources:
            sources = state.sources
        else:
            sources = [s.action.result for s in state.steps if s.action and s.action.result]

        # Calculate context used (sum of observation lengths)
        context_used = sum(len(s.observation or "") for s in state.steps)

        # Build CoreResult
        return CoreResult(
            answer=state.final_answer,
            sources=sources,
            verification_score=getattr(state, "verification_score", 0.0), # Assuming state has this
            evidence_score=getattr(state, "evidence_score", 0.0),
            is_ambiguous=False,
            entities=extracted_entities,
            model_used=model_used_name,
            completion_tokens=0, # TODO: Track tokens
            prompt_tokens=0, # TODO: Track tokens,
            verification_status="passed" if getattr(state, "verification_score", 0.0) > 0.7 else "unchecked",
            document_count=len(sources),
            timings={"total": execution_time, "reasoning": execution_time}, # More granular if available
            warnings=[]
        )

    async def stream_query(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        # Security: Validate user_id format
        if user_id and user_id != "anonymous":
            if not isinstance(user_id, str) or len(user_id) < 1:
                raise ValueError("Invalid user_id format")

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # UNIVERSAL CONTEXT LOADING (Stream)
        try:
             memory_orchestrator = await self._get_memory_orchestrator()
             user_context = await get_user_context(
                 self.db_pool,
                 user_id,
                 memory_orchestrator,
                 query=query,
                 conversation_history=conversation_history,
                 session_id=session_id
             )
        except Exception as e:
             logger.warning(f"⚠️ Failed to load user context in stream: {e}")
             user_context = {}

        history_to_use = conversation_history or user_context.get("history", [])
        if not isinstance(history_to_use, list):
            history_to_use = []
        elif history_to_use and not isinstance(history_to_use[0], dict):
            history_to_use = []

        logger.info(f"🧠 [Stream Context] Loaded context for {user_id or 'anonymous'}")

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

Answer directly. Example: "Zainal Abidin è il CEO di Bali Zero."
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

        # Check Casual Conversation (bypass tools, use direct LLM response)
        # INJECT CONTEXT
        if self.prompt_builder.check_casual_conversation(query, context=user_context):
            logger.info("💬 [Casual Stream] Detected casual conversation - bypassing RAG tools")
            try:
                # Simplified: Model auto-detects language from user's message
                casual_prompt = f"""You are ZANTARA - a friendly, warm AI assistant.
This is a CASUAL conversation - NOT a business query.

IMPORTANT: Respond in the SAME LANGUAGE the user is writing in.
If Indonesian, you may use Jaksel style (mix Bahasa + English slang).
For all other languages, be warm and fun but stay in their language.

RESPOND with personality:
- Be warm, friendly, share opinions
- For restaurant/food questions: recommend real Bali places you know
- For music/lifestyle: share genuine preferences
- For personal chat: be engaging and ask follow-up questions
- Keep it conversational and fun!

User says: """ + query

                casual_chat = self.llm_gateway.create_chat_with_history(
                    history_to_use=history_to_use, model_tier=TIER_FLASH
                )

                casual_response, model_used, _ = await self.llm_gateway.send_message(
                    casual_chat,
                    casual_prompt,
                    system_prompt="",
                    tier=TIER_FLASH,
                    enable_function_calling=False,
                )

                yield {"type": "metadata", "data": {"status": "casual", "route": f"casual-conversation ({model_used})"}}
                import re

                tokens = re.findall(r"\S+|\s+", casual_response)
                for token in tokens:
                    yield {"type": "token", "data": token}
                    await asyncio.sleep(0.01)
                yield {"type": "done", "data": None}
                return
            except Exception as e:
                logger.warning(f"⚠️ [Casual Stream] Direct response failed, falling back to RAG: {e}")
                # Fall through to normal RAG processing

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
        extracted_entities = await self.entity_extractor.extract_entities(query)
        if any(extracted_entities.values()):
            logger.info(f"🔍 [Entity Extraction Stream] Extracted entities: {extracted_entities}")
            yield {
                "type": "metadata",
                "data": {"extracted_entities": extracted_entities}
            }

        # 1. SEMANTIC CACHE CHECK
        if self.semantic_cache:
            try:
                cached = await self.semantic_cache.get_cached_result(query)
                if cached:
                    logger.info("✅ [Cache Hit Stream] Returning cached result for query")
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
            except (KeyError, ValueError, RuntimeError) as e:
                logger.warning(f"Cache lookup failed: {e}", exc_info=True)

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

        state = AgentState(query=query)
        logger.debug(f"User context retrieved (early). History len: {len(history_to_use)}")

        # --- QUALITY ROUTING: REACT LOOP STREAMING (Full Agentic Architecture) ---
        logger.info(f"🧠 [Stream] Processing query with ReAct loop for user {user_id}")

        # Build system prompt
        system_context_for_prompt = ""
        if any(extracted_entities.values()):
            system_context_for_prompt = f"\nKNOWN ENTITIES (Use strict filtering if possible): {extracted_entities}"

        system_prompt = self.prompt_builder.build_system_prompt(
            user_id, user_context, query, deep_think_mode=deep_think_mode,
            additional_context=system_context_for_prompt # Inject extracted entities
        )

        # Create chat session
        chat = self.llm_gateway.create_chat_with_history(
            history_to_use=history_to_use, model_tier=model_tier
        )

        # Stream response using New Streaming ReAct Logic
        full_answer = ""
        try:
             async for event in self.reasoning_engine.execute_react_loop_stream(
                state=state,
                llm_gateway=self.llm_gateway,
                chat=chat,
                initial_prompt=_wrap_query_with_language_instruction(query), # Wrapped with language instruction
                system_prompt=system_prompt, # System prompt with injected entities
                query=query,
                user_id=user_id or "anonymous",
                model_tier=model_tier,
                tool_execution_counter=tool_execution_counter,
             ):
                # Accumulate for memory saving later
                if event["type"] == "token":
                    full_answer += event["data"]

                # Yield event to frontend
                yield event

             # Emit done event (and save memory)
             execution_time = time.time() - start_time

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
            logger.error(f"❌ Stream failed: {e}", exc_info=True)
            yield {"type": "error", "data": {"message": str(e)}}
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
