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
from services.classification.intent_classifier import IntentClassifier
from services.context_window_manager import AdvancedContextWindowManager
from services.emotional_attunement import EmotionalAttunementService
from services.followup_service import FollowupService
from services.golden_answer_service import GoldenAnswerService
from services.memory import MemoryOrchestrator
from services.response.cleaner import (
    OUT_OF_DOMAIN_RESPONSES,
    is_out_of_domain,
)
from services.semantic_cache import SemanticCache
from services.tools.definitions import AgentState, AgentStep, BaseTool

from .cell_giant import (
    cell_calibrate,
    giant_reason,
    synthesize_as_zantara,
    synthesize_as_zantara_stream,
)
from .context_manager import get_user_context
from .llm_gateway import LLMGateway
from .pipeline import create_default_pipeline
from .prompt_builder import SystemPromptBuilder
from .reasoning import ReasoningEngine, detect_team_query
from .response_processor import post_process_response
from .session_fact_extractor import SessionFactExtractor
from .tool_executor import execute_tool, parse_tool_call

logger = logging.getLogger(__name__)

# Model Tiers
TIER_FLASH = 0
TIER_LITE = 1
TIER_PRO = 2
TIER_OPENROUTER = 3


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
        model_name: str = "gemini-1.5-pro",
        semantic_cache: SemanticCache = None,
        retriever: Any = None,
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

        Note:
            - Initializes Gemini models (Pro, Flash, Flash-Lite) for cascade fallback
            - Lazy loads OpenRouter client and MemoryOrchestrator on first use
            - Configures intent classifier and emotional attunement services
            - Converts tools to Gemini function declarations for native calling
        """
        logger.debug(f"AgenticRAGOrchestrator.__init__ started. Model: {model_name}")
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self.db_pool = db_pool
        self.model_name = model_name
        self.semantic_cache = semantic_cache
        self.retriever = retriever

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
        self.llm_gateway = LLMGateway(gemini_tools=self.gemini_tools)
        logger.debug("AgenticRAGOrchestrator: LLMGateway initialized")

        # Initialize Reasoning Engine (manages ReAct loop)
        logger.debug("AgenticRAGOrchestrator: Initializing ReasoningEngine...")
        self.reasoning_engine = ReasoningEngine(
            tool_map=self.tool_map, response_pipeline=self.response_pipeline
        )
        logger.debug("AgenticRAGOrchestrator: ReasoningEngine initialized")

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
    ):
        # Fix: evaluate at call time, not definition time
        start_time = start_time or time.time()
        """Main entry point for non-streaming query processing with full agentic reasoning.

        Implements the complete RAG pipeline with multi-step reasoning (ReAct pattern):
        1. Pattern matching: Check identity/hardcoded responses
        2. Domain validation: Filter out-of-domain queries
        3. Cache lookup: Check semantic cache for similar queries
        4. Intent classification: Route to appropriate model tier (Fast/Pro/DeepThink)
        5. Context retrieval: Load user profile, memory facts, conversation history
        6. ReAct loop: Iterative reasoning with tool execution
           - THOUGHT: Analyze what information is needed
           - ACTION: Execute tools (vector_search, get_pricing, etc.)
           - OBSERVATION: Process tool results
           - Repeat until sufficient context gathered
        7. Response generation: Synthesize final answer from gathered context
        8. Verification: Validate answer against context (draft->verify->correct loop)
        9. Post-processing: Clean response, apply communication rules
        10. Caching: Store result for future similar queries
        11. Memory persistence: Extract and save conversation facts (async)

        Args:
            query: User's natural language query
            user_id: User identifier (email/UUID) for personalization, or None for anonymous
            conversation_history: Previous conversation turns for context continuity
            start_time: Query start timestamp for latency tracking
            session_id: Optional session ID to filter conversation history by specific session

        Returns:
            Dict containing:
                - answer (str): Final generated response
                - sources (list): Evidence sources with metadata
                - context_used (int): Characters of context used
                - execution_time (float): Total processing time in seconds
                - route_used (str): Model tier used (e.g., "agentic-rag (gemini-2.0-flash)")
                - steps (list): Reasoning steps taken
                - tools_called (int): Number of tool invocations
                - total_steps (int): Total ReAct iterations
                - cache_hit (str, optional): Cache hit type if applicable

        Raises:
            ValueError: If user_id format is invalid

        Note:
            - Quality routing: DeepThink (complex) -> Pro (detailed) -> Fast (simple)
            - Model fallback: Flash -> Flash-Lite -> OpenRouter (automatic on quota/error)
            - Early exit optimization: Stops ReAct loop if sufficient context retrieved
            - Memory persistence: Runs in background (non-blocking)
            - Semantic cache: 5-minute TTL for query deduplication

        Example:
            >>> result = await orchestrator.process_query(
            ...     query="What is the cost of E33G Digital Nomad visa?",
            ...     user_id="user@example.com"
            ... )
            >>> print(result["answer"])
            >>> print(f"Sources: {len(result['sources'])}")
            >>> print(f"Execution time: {result['execution_time']:.2f}s")
        """
        # Security: Validate user_id format
        if user_id and user_id != "anonymous":
            if not isinstance(user_id, str) or len(user_id) < 1:
                raise ValueError("Invalid user_id format")

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # 0. Check Greetings (skip RAG for simple greetings)
        greeting_response = self.prompt_builder.check_greetings(query)
        if greeting_response:
            logger.info("👋 [Greeting] Returning direct greeting response (skipping RAG)")
            return {
                "answer": greeting_response,
                "sources": [],
                "context_used": 0,
                "execution_time": time.time() - start_time,
                "route_used": "greeting-pattern",
                "steps": [],
                "tools_called": 0,
                "total_steps": 0,
            }

        # 0.5 Check Identity / Hardcoded Patterns
        identity_response = self.prompt_builder.check_identity_questions(query)
        if identity_response:
            logger.info("🤖 [Identity] Returning hardcoded identity response")
            return {
                "answer": identity_response,
                "sources": [],
                "context_used": 0,
                "execution_time": time.time() - start_time,
                "route_used": "identity-pattern",
                "steps": [],
                "tools_called": 0,
                "total_steps": 0,
            }

        # 0.6 Check Casual Conversation (bypass tools, use direct LLM response)
        if self.prompt_builder.check_casual_conversation(query):
            logger.info("💬 [Casual] Detected casual conversation - bypassing RAG tools")
            try:
                # Build casual-focused prompt
                casual_prompt = """You are ZANTARA - a friendly, warm AI with Jaksel personality.
This is a CASUAL conversation - NOT a business query.

RESPOND with personality:
- Mix Indonesian/English naturally (Jaksel style)
- Be warm, friendly, share opinions
- For restaurant/food questions: recommend real Bali places you know
- For music/lifestyle: share genuine preferences
- For personal chat: be engaging and ask follow-up questions
- Keep it conversational and fun!

User says: """ + query

                # Create a fresh chat without tools for casual response
                casual_chat = self.llm_gateway.create_chat_with_history(
                    history_to_use=[], model_tier=TIER_FLASH
                )

                casual_response, model_used, _ = await self.llm_gateway.send_message(
                    casual_chat,
                    casual_prompt,
                    system_prompt="",
                    tier=TIER_FLASH,
                    enable_function_calling=False,  # NO tools for casual chat
                )

                logger.info(f"✅ [Casual] Generated response with {model_used}")
                return {
                    "answer": casual_response,
                    "sources": [],
                    "context_used": len(casual_prompt),
                    "execution_time": time.time() - start_time,
                    "route_used": f"casual-conversation ({model_used})",
                    "steps": [],
                    "tools_called": 0,
                    "total_steps": 0,
                }
            except Exception as e:
                logger.warning(f"⚠️ [Casual] Direct response failed, falling back to RAG: {e}")
                # Fall through to normal RAG processing

        # 0.7 Check Out-of-Domain Questions
        out_of_domain, reason = is_out_of_domain(query)
        if out_of_domain and reason:
            logger.info(f"🚫 [Out-of-Domain] Query rejected: {reason}")
            return {
                "answer": OUT_OF_DOMAIN_RESPONSES.get(reason, OUT_OF_DOMAIN_RESPONSES["unknown"]),
                "sources": [],
                "context_used": 0,
                "execution_time": time.time() - start_time,
                "route_used": f"out-of-domain-{reason}",
                "steps": [],
                "tools_called": 0,
                "total_steps": 0,
            }

        # OPTIMIZATION 1: Check semantic cache first
        if self.semantic_cache:
            try:
                cached = await self.semantic_cache.get_cached_result(query)
                if cached:
                    logger.info("✅ [Cache Hit] Returning cached result for query")
                    result = cached.get("result", cached)
                    result["cache_hit"] = cached.get("cache_hit", "exact")
                    result["execution_time"] = time.time() - start_time
                    return result
            except (KeyError, ValueError, RuntimeError) as e:
                logger.warning(f"Cache lookup failed: {e}", exc_info=True)

        # --- QUALITY ROUTING: DETERMINE MODEL TIER ---
        # Classify intent to select the right model (Fast/Pro/DeepThink)
        intent = await self.intent_classifier.classify_intent(query)
        suggested_ai = intent.get("suggested_ai", "fast")

        # Determine model tier
        model_tier = TIER_FLASH
        deep_think_mode = False

        if suggested_ai == "deep_think":
            model_tier = TIER_PRO
            deep_think_mode = True
            logger.info("🧠 [Routing] DeepThink Mode activated (Gemini Pro + Reasoning)")
        elif suggested_ai == "pro":
            model_tier = TIER_PRO
            logger.info("🌟 [Routing] Pro Mode activated (Gemini Pro)")
        else:
            model_tier = TIER_FLASH
            logger.info("⚡ [Routing] Fast Mode activated (Gemini Flash)")

        state = AgentState(query=query)

        # 1. Retrieve User Context (with query for semantic collective memory retrieval)
        memory_orchestrator = await self._get_memory_orchestrator()
        user_context = await get_user_context(
            self.db_pool, user_id, memory_orchestrator, query=query, session_id=session_id
        )

        # Use provided conversation_history if available, otherwise use from user_context
        history_to_use = (
            conversation_history if conversation_history else user_context.get("history", [])
        )

        # DEFENSIVE: Ensure history_to_use is a list of dicts, not a string or list of strings
        if not isinstance(history_to_use, list):
            logger.warning(
                f"⚠️ history_to_use is not a list (type: {type(history_to_use)}), resetting to empty list"
            )
            history_to_use = []
        elif history_to_use and not isinstance(history_to_use[0], dict):
            logger.warning(
                f"⚠️ history_to_use contains non-dict items (first item type: {type(history_to_use[0])}), resetting to empty list"
            )
            history_to_use = []

        # 2. Build Dynamic System Prompt (with query for explanation level detection)
        system_prompt = self.prompt_builder.build_system_prompt(
            user_id, user_context, query, deep_think_mode=deep_think_mode
        )

        # Process conversation history with Advanced Context Window Manager
        processed_history = None
        history_text = ""
        session_facts_block = ""

        if history_to_use:
            # STEP 1: Extract session facts BEFORE any trimming (from original history)
            try:
                session_extractor = SessionFactExtractor()
                session_facts = session_extractor.extract_from_history(history_to_use)
                session_facts_block = session_facts.to_prompt_block()
            except Exception as e:
                logger.warning(f"⚠️ SessionFactExtractor failed: {e}", exc_info=True)
                session_facts_block = ""

            # STEP 2: Trim history with AdvancedContextWindowManager
            try:
                # Initialize context manager
                context_manager = AdvancedContextWindowManager(
                    max_tokens=12000,
                    recent_window_tokens=6000,
                    summary_max_tokens=8192,
                )

                # Process conversation history
                processed_history = await context_manager.process_conversation_history(
                    conversation_history=history_to_use,
                    system_prompt=system_prompt,
                    current_query=query,
                )

                # Use processed messages
                history_to_use = processed_history["messages"]
                history_text = processed_history["formatted_context"]

                # Log statistics
                stats = processed_history["stats"]
                total = stats["total_messages"]
                in_context = stats["messages_in_context"]
                tokens = stats["tokens"]
                compression = in_context / total if total > 0 else 1.0
                logger.info(
                    f"💬 [Advanced Context] Processed {total} messages: "
                    f"{in_context} in context ({tokens} tokens), "
                    f"compression: {compression:.1%}"
                )

            except (ValueError, KeyError, RuntimeError) as e:
                logger.warning(
                    f"⚠️ Advanced context manager failed, using fallback: {e}", exc_info=True
                )
                # Fallback to simple truncation
                # Defensive: ensure history_to_use is a list
                if not isinstance(history_to_use, list):
                    logger.warning(
                        f"⚠️ history_to_use is not a list (type: {type(history_to_use)}), resetting to empty"
                    )
                    history_to_use = []
                history_to_use = (
                    history_to_use[-10:] if len(history_to_use) > 10 else history_to_use
                )
                history_text = "\n\nCONVERSATION HISTORY:\n"
                for msg in history_to_use:
                    # Defensive: skip if msg is not a dict
                    if not isinstance(msg, dict):
                        logger.warning(f"⚠️ Skipping non-dict message in history: {type(msg)}")
                        continue
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if len(content) > 8000:
                        content = content[:8000] + "..."
                    history_text += f"{role.upper()}: {content}\n"

        # Create chat session with conversation history using LLMGateway
        chat = self.llm_gateway.create_chat_with_history(
            history_to_use=history_to_use, model_tier=model_tier
        )

        initial_prompt = f"""{system_prompt}

{session_facts_block}### CONVERSATION HISTORY (FROM PREVIOUS TURNS):
{history_text}
### END HISTORY

User Query: {query}

IMPORTANT: Use the KEY FACTS above to answer questions about user's company, budget, location. Do NOT start with philosophical statements. If you need more info, use tools."""
        logger.info(
            f"🐛 [DEBUG PROMPT] history_to_use (len={len(history_to_use)}), session_facts: {bool(session_facts_block)}"
        )
        logger.info(f"🐛 [DEBUG PROMPT] initial_prompt (last 500 chars): {initial_prompt[-500:]}")

        # Execute ReAct loop using ReasoningEngine
        (
            state,
            model_used_name,
            conversation_messages,
        ) = await self.reasoning_engine.execute_react_loop(
            state=state,
            llm_gateway=self.llm_gateway,
            chat=chat,
            initial_prompt=initial_prompt,
            system_prompt=system_prompt,
            query=query,
            user_id=user_id or "anonymous",
            model_tier=model_tier,
            tool_execution_counter=tool_execution_counter,
        )

        # Calculate execution time
        execution_time = time.time() - start_time

        # Extract sources from tool results
        # Use state.sources if available (structured), otherwise fallback to text extraction
        if hasattr(state, "sources") and state.sources:
            sources = state.sources
        else:
            sources = [s.action.result for s in state.steps if s.action and s.action.result]

        # Calculate context used (sum of observation lengths)
        context_used = sum(len(s.observation or "") for s in state.steps)

        result = {
            "answer": state.final_answer,
            "sources": sources,
            "context_used": len(initial_prompt),
            "execution_time": execution_time,
            "route_used": f"agentic-rag ({model_used_name})",
            "debug_info": {
                "history_len": len(history_to_use),
                "history_capture": history_to_use,
                "initial_prompt_tail": initial_prompt[-1000:],
                "memory_error": user_context.get("memory_error"),
            },
            # Keep legacy fields for backward compatibility
            "steps": [
                {
                    "step": s.step_number,
                    "thought": s.thought,
                    "tool_used": s.action.tool_name if s.action else None,
                    "tool_result": s.action.result[:200] if s.action and s.action.result else None,
                }
                for s in state.steps
            ],
            "tools_called": len([s for s in state.steps if s.action]),
            "total_steps": len(state.steps),
        }

        # OPTIMIZATION 3: Cache the result for future similar queries
        if self.semantic_cache and state.final_answer:
            try:
                import numpy as np

                query_embedding = None
                
                # Try to generate real semantic embedding first
                if self.retriever and hasattr(self.retriever, "embedder"):
                    try:
                        # This should be async but usually the underlying call is sync or wrapped
                        # If generate_query_embedding is async, we need await
                        # Assuming synchronous for now based on common patterns, but check if await needed
                        if asyncio.iscoroutinefunction(self.retriever.embedder.generate_query_embedding):
                            query_embedding = await self.retriever.embedder.generate_query_embedding(query)
                        else:
                            query_embedding = self.retriever.embedder.generate_query_embedding(query)
                        
                        # Ensure it's a numpy array of float32
                        if isinstance(query_embedding, list):
                            query_embedding = np.array(query_embedding, dtype=np.float32)
                    except Exception as e:
                        logger.warning(f"Failed to generate semantic embedding: {e}")

                # Fallback to hash-based embedding (exact match only) if semantic fails
                if query_embedding is None:
                    import hashlib
                    logger.warning("⚠️ Using hash-based embedding for cache (Exact Match Only) - Semantic search degraded")
                    # Create hash-based embedding for exact match caching
                    query_hash = hashlib.sha256(query.lower().strip().encode()).digest()
                    # Convert hash bytes to float32 array (32 bytes = 8 floats, pad to 384)
                    hash_floats = np.frombuffer(query_hash, dtype=np.float32)
                    query_embedding = np.zeros(384, dtype=np.float32)
                    query_embedding[:len(hash_floats)] = hash_floats
                    # Normalize to unit vector for cosine similarity
                    norm = np.linalg.norm(query_embedding)
                    if norm > 0:
                        query_embedding = query_embedding / norm

                await self.semantic_cache.cache_result(query, query_embedding, result)
                logger.info("✅ [Cache Write] Result cached for future queries")
            except (ValueError, RuntimeError, KeyError) as e:
                logger.warning(f"Failed to cache result: {e}", exc_info=True)

        # 🧠 MEMORY PERSISTENCE: Save facts from conversation in background
        memory_save_info = None
        if state.final_answer and user_id and user_id != "anonymous":
            if user_id.startswith("ltm_user_"):
                try:
                    logger.info(f"🧪 [AgenticRAG] Synchronous memory save for test user {user_id}")
                    mem_orch = await self._get_memory_orchestrator()
                    if mem_orch:
                        res = await mem_orch.process_conversation(
                            user_email=user_id, user_message=query, ai_response=state.final_answer
                        )
                        memory_save_info = {
                            "extracted": res.facts_extracted,
                            "saved": res.facts_saved,
                            "error": None,
                        }
                    else:
                        memory_save_info = {"error": "No memory orchestrator"}
                except Exception as e:
                    logger.error(f"Test memory save failed: {e}")
                    memory_save_info = {"error": str(e)}
            else:
                # Fix: Add error callback to prevent silent failures
                task = asyncio.create_task(
                    self._save_conversation_memory(
                        user_id=user_id,
                        query=query,
                        answer=state.final_answer,
                    )
                )
                task.add_done_callback(
                    lambda t: logger.error(f"❌ Memory save failed: {t.exception()}")
                    if t.exception() else None
                )

        if memory_save_info:
            result["debug_info"]["memory_save_result"] = memory_save_info

        return result

    async def process_query_cell_giant(
        self,
        query: str,
        user_id: str | None = None,
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Process query using Cell-Giant architecture.

        Three-phase reasoning:
        1. Giant: Reasons deeply on the query (strategy, legal, options)
        2. Cell: Calibrates with verified data (corrections, pricing, insights)
        3. Zantara: Synthesizes into a single voice

        The user sees ONLY Zantara. The Giant is invisible.

        Args:
            query: User's natural language query
            user_id: User identifier for personalization
            conversation_history: Previous conversation turns
            session_id: Optional session ID for filtering history

        Returns:
            Dict with answer, sources, execution_time, route_used, etc.
        """
        start_time = time.time()

        # 0. Check Greetings (skip Cell-Giant for simple greetings)
        greeting_response = self.prompt_builder.check_greetings(query)
        if greeting_response:
            logger.info("👋 [Cell-Giant] Greeting detected, returning direct response")
            return {
                "answer": greeting_response,
                "sources": [],
                "context_used": 0,
                "execution_time": time.time() - start_time,
                "route_used": "greeting-pattern",
                "steps": [],
                "tools_called": 0,
                "total_steps": 0,
            }

        # 0.5 Check Identity
        identity_response = self.prompt_builder.check_identity_questions(query)
        if identity_response:
            logger.info("🤖 [Cell-Giant] Identity question detected")
            return {
                "answer": identity_response,
                "sources": [],
                "context_used": 0,
                "execution_time": time.time() - start_time,
                "route_used": "identity-pattern",
                "steps": [],
                "tools_called": 0,
                "total_steps": 0,
            }

        # 1. Build user context
        user_context_str = ""
        user_facts: list[str] = []

        try:
            memory_orchestrator = await self._get_memory_orchestrator()
            user_context = await get_user_context(
                self.db_pool, user_id, memory_orchestrator, query=query, session_id=session_id
            )
            # Extract user facts for Cell
            if user_context.get("memory_facts"):
                user_facts = [f.get("fact", "") for f in user_context.get("memory_facts", [])]
            # Build context string for Giant
            if user_context.get("user_profile"):
                profile = user_context["user_profile"]
                user_context_str = f"User: {profile.get('name', 'Unknown')}"
                if profile.get("company"):
                    user_context_str += f", Company: {profile['company']}"
        except Exception as e:
            logger.warning(f"⚠️ [Cell-Giant] Context retrieval failed: {e}")

        # ========================================================================
        # PHASE 1: GIANT REASONS
        # The Giant thinks deeply about the query
        # ========================================================================
        logger.info("🧠 [Cell-Giant] Phase 1: Giant reasoning...")
        try:
            from app.core.config import settings
            giant_timeout = getattr(settings, 'timeout_ai_response', 60.0)
            giant_result = await asyncio.wait_for(
                giant_reason(query=query, user_context=user_context_str),
                timeout=giant_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"⏱️ [Cell-Giant] Giant reasoning timeout after {giant_timeout}s")
            giant_result = {
                "reasoning": "Reasoning timeout - sistema temporaneamente sovraccarico.",
                "key_points": [],
                "warnings": ["Timeout durante il ragionamento"],
                "quality_score": 0.1,
                "detected_domain": "general"
            }
        logger.info(
            f"✅ [Cell-Giant] Giant done: {len(giant_result.get('reasoning', ''))} chars, "
            f"{len(giant_result.get('key_points', []))} points, "
            f"{len(giant_result.get('warnings', []))} warnings"
        )

        # ========================================================================
        # PHASE 2: CELL CALIBRATES
        # The Cell provides corrections, calibrations, enhancements
        # ========================================================================
        logger.info("🔬 [Cell-Giant] Phase 2: Cell calibrating...")
        try:
            from app.core.config import settings
            cell_timeout = getattr(settings, 'timeout_rag_query', 10.0)
            cell_result = await asyncio.wait_for(
                cell_calibrate(
                    query=query,
                    giant_reasoning=giant_result,
                    user_id=user_id,
                    user_facts=user_facts,
                ),
                timeout=cell_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"⏱️ [Cell-Giant] Cell calibration timeout after {cell_timeout}s")
            cell_result = {
                "corrections": [],
                "enhancements": [],
                "calibrations": {},
                "user_memory": user_facts or [],
                "legal_sources": []
            }
        logger.info(
            f"✅ [Cell-Giant] Cell done: {len(cell_result.get('corrections', []))} corrections, "
            f"{len(cell_result.get('enhancements', []))} enhancements, "
            f"{len(cell_result.get('calibrations', {}))} calibrations"
        )

        # ========================================================================
        # PHASE 3: ZANTARA SYNTHESIZES
        # The final voice - the user sees only this
        # ========================================================================
        logger.info("🎭 [Cell-Giant] Phase 3: Zantara synthesizing...")
        try:
            from app.core.config import settings
            zantara_timeout = getattr(settings, 'timeout_ai_response', 60.0)
            final_answer = await asyncio.wait_for(
                synthesize_as_zantara(
                    query=query,
                    giant_reasoning=giant_result,
                    cell_calibration=cell_result,
                ),
                timeout=zantara_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"⏱️ [Cell-Giant] Zantara synthesis timeout after {zantara_timeout}s")
            from services.rag.agentic.cell_giant.zantara_synthesizer import _fallback_synthesis
            final_answer = _fallback_synthesis(giant_result, cell_result)
        logger.info(f"✅ [Cell-Giant] Zantara done: {len(final_answer)} chars")

        # Calculate metrics
        execution_time = time.time() - start_time

        # Build sources from Cell's legal_sources
        sources = cell_result.get("legal_sources", [])

        result = {
            "answer": final_answer,
            "sources": sources,
            "context_used": len(giant_result.get("reasoning", "")),
            "execution_time": execution_time,
            "route_used": "cell-giant",
            "steps": [
                {"step": 1, "phase": "giant", "output_len": len(giant_result.get("reasoning", ""))},
                {"step": 2, "phase": "cell", "corrections": len(cell_result.get("corrections", []))},
                {"step": 3, "phase": "zantara", "output_len": len(final_answer)},
            ],
            "tools_called": 1 if cell_result.get("legal_sources") else 0,
            "total_steps": 3,
            "debug_info": {
                "giant_key_points": giant_result.get("key_points", []),
                "giant_warnings": giant_result.get("warnings", []),
                "cell_corrections": cell_result.get("corrections", []),
                "cell_enhancements": cell_result.get("enhancements", [])[:5],
                "cell_calibrations": list(cell_result.get("calibrations", {}).keys()),
            },
        }

        # 🧠 MEMORY PERSISTENCE (background)
        if final_answer and user_id and user_id != "anonymous":
            task = asyncio.create_task(
                self._save_conversation_memory(
                    user_id=user_id,
                    query=query,
                    answer=final_answer,
                )
            )
            task.add_done_callback(
                lambda t: logger.error(f"❌ Memory save failed: {t.exception()}")
                if t.exception() else None
            )

        return result

    async def stream_query_cell_giant(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream Cell-Giant reasoning process with intelligent SSE events.

        This method exposes the internal cognition process:
        1. Giant Phase (Deep Reasoning) -> Emits 'reasoning_step' events
        2. Cell Phase (Calibration) -> Emits 'reasoning_step' events with corrections
        3. Zantara Phase (Synthesis) -> Emits 'token' events for the final answer

        Args:
            query: User's query
            user_id: User identifier
            conversation_history: Previous context
            session_id: Session identifier

        Yields:
            SSE events for frontend visualization
        """
        start_time = time.time()
        
        # Initial Metadata
        yield {
            "type": "metadata", 
            "data": {
                "status": "started", 
                "model": "gemini-pro-reasoning", 
                "mode": "deep_think_cell_giant"
            }
        }

        # 1. Build user context (Silent phase)
        user_context_str = ""
        user_facts: list[str] = []
        try:
            memory_orchestrator = await self._get_memory_orchestrator()
            user_context = await get_user_context(
                self.db_pool, user_id, memory_orchestrator, query=query, session_id=session_id
            )
            if user_context.get("memory_facts"):
                user_facts = [f.get("fact", "") for f in user_context.get("memory_facts", [])]
            if user_context.get("user_profile"):
                profile = user_context["user_profile"]
                user_context_str = f"User: {profile.get('name', 'Unknown')}"
                if profile.get("company"):
                    user_context_str += f", Company: {profile['company']}"
        except Exception as e:
            logger.warning(f"⚠️ [Stream Cell-Giant] Context retrieval failed: {e}")

        # ========================================================================
        # PHASE 1: GIANT REASONS
        # ========================================================================
        yield {
            "type": "reasoning_step",
            "data": {
                "phase": "giant",
                "status": "in_progress",
                "message": "Consulting the Giant Reasoner...",
                "description": "Analyzing complex implications and strategy."
            }
        }
        
        # Execute Giant Reasoning
        giant_result = await giant_reason(query=query, user_context=user_context_str)
        
        # Emit Giant Insights
        key_points = giant_result.get("key_points", [])
        warnings = giant_result.get("warnings", [])
        yield {
            "type": "reasoning_step",
            "data": {
                "phase": "giant",
                "status": "completed",
                "message": "Reasoning complete.",
                "details": {
                    "key_points": key_points[:3], # Show top 3 points
                    "warnings": warnings[:2]      # Show top 2 warnings
                }
            }
        }

        # ========================================================================
        # PHASE 2: CELL CALIBRATES
        # ========================================================================
        yield {
            "type": "reasoning_step",
            "data": {
                "phase": "cell",
                "status": "in_progress",
                "message": "Cell Verification Protocol active...",
                "description": "Cross-referencing against Indonesian Law & Bali Zero standards."
            }
        }

        # Execute Cell Calibration
        cell_result = await cell_calibrate(
            query=query,
            giant_reasoning=giant_result,
            user_id=user_id,
            user_facts=user_facts,
        )
        
        # Emit Cell Corrections
        corrections = cell_result.get("corrections", [])
        yield {
            "type": "reasoning_step",
            "data": {
                "phase": "cell",
                "status": "completed",
                "message": f"Calibration applied ({len(corrections)} adjustments).",
                "details": {
                    "corrections": corrections,
                    "verified_sources": len(cell_result.get("legal_sources", []))
                }
            }
        }

        # Emit Sources early if available
        legal_sources = cell_result.get("legal_sources", [])
        if legal_sources:
             yield {"type": "sources", "data": legal_sources}

        # ========================================================================
        # PHASE 3: ZANTARA SYNTHESIZES
        # ========================================================================
        yield {
            "type": "status", 
            "data": "Synthesizing final answer..."
        }

        # Execute Synthesis (Real Streaming)
        final_answer_acc = ""
        async for token in synthesize_as_zantara_stream(
            query=query,
            giant_reasoning=giant_result,
            cell_calibration=cell_result,
        ):
            final_answer_acc += token
            yield {"type": "token", "data": token}
        
        final_answer = final_answer_acc

        # Final Cleanup
        execution_time = time.time() - start_time
        
        # Check for Golden Answer
        golden_answer_used = False
        if self.golden_answer_service:
            try:
                ga = await self.golden_answer_service.lookup_golden_answer(query, user_id)
                if ga:
                    golden_answer_used = True
            except Exception as e:
                logger.warning(f"Golden answer lookup failed: {e}")

        # Generate Follow-up Questions
        followup_questions = []
        try:
            followup_questions = await self.followup_service.get_followups(
                query=query, response=final_answer
            )
        except Exception as e:
            logger.warning(f"Follow-up generation failed: {e}")

        # Yield Final Metadata Event
        yield {
            "type": "metadata",
            "data": {
                "status": "completed",
                "execution_time": execution_time,
                "route_used": "cell-giant (DeepThink)",
                "context_length": len(giant_result.get("reasoning", "")),
                "verification_score": 100 if not corrections else 85,
                "user_memory_facts": user_facts,
                "collective_memory_facts": user_context.get("collective_facts", []),
                "golden_answer_used": golden_answer_used,
                "followup_questions": followup_questions,
            },
        }

        # Save Memory (Background)
        if final_answer and user_id and user_id != "anonymous":
            task = asyncio.create_task(
                self._save_conversation_memory(
                    user_id=user_id,
                    query=query,
                    answer=final_answer,
                )
            )
            task.add_done_callback(
                lambda t: logger.error(f"❌ Memory save failed: {t.exception()}")
                if t.exception() else None
            )

        yield {"type": "done", "data": {"execution_time": execution_time}}

    async def stream_query(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream agentic reasoning process with real-time status updates.

        Implements the same ReAct pipeline as process_query() but yields incremental
        events for real-time UI updates. This enables transparent AI reasoning with
        progress indicators and token-by-token streaming.

        Event Flow:
        1. metadata: Query started, model selected, reasoning mode
        2. status: "Step N: Thinking..." progress updates
        3. tool_start: Tool name and arguments when tool is called
        4. tool_end: Tool execution result (truncated)
        5. token: Individual tokens of final answer (for typewriter effect)
        6. sources: Citation sources with metadata (for inline references)
        7. metadata: Completion stats (execution time, emotional state, etc.)
        8. done: Stream finished

        Args:
            query: User's natural language query
            user_id: User identifier for personalization (default: "anonymous")
            conversation_history: Previous conversation turns for context
            session_id: Optional session ID to filter conversation history by specific session

        Yields:
            Dict events with structure:
                - type (str): Event type (metadata/status/tool_start/tool_end/token/sources/done)
                - data (Any): Event-specific payload

        Raises:
            ValueError: If user_id format is invalid

        Note:
            - Out-of-domain queries: Immediately stream rejection message
            - Intent classification: Determines model tier (Fast/Pro/DeepThink)
            - Token streaming: Splits final answer by words/punctuation for smooth UX
            - Sources deduplication: Removes duplicate citations before emitting
            - Memory persistence: Runs in background after streaming completes
            - Error handling: Yields error events instead of raising exceptions

        Example:
            >>> async for event in orchestrator.stream_query(
            ...     query="Explain PT PMA setup process",
            ...     user_id="user@example.com"
            ... ):
            ...     if event["type"] == "token":
            ...         print(event["data"], end="", flush=True)
            ...     elif event["type"] == "tool_start":
            ...         print(f"\n[Calling {event['data']['name']}...]")
            ...     elif event["type"] == "sources":
            ...         print(f"\nCitations: {len(event['data'])}")
        """
        # Security: Validate user_id format
        if user_id and user_id != "anonymous":
            if not isinstance(user_id, str) or len(user_id) < 1:
                raise ValueError("Invalid user_id format")

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # Check Greetings first (skip RAG for simple greetings)
        greeting_response = self.prompt_builder.check_greetings(query)
        if greeting_response:
            logger.info("👋 [Greeting Stream] Returning direct greeting response (skipping RAG)")
            yield {"type": "metadata", "data": {"status": "greeting", "route": "greeting-pattern"}}
            for token in greeting_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # EARLY TEAM QUERY CHECK - handle team questions immediately
        is_team_query, team_query_type, team_search_term = detect_team_query(query)
        if is_team_query and "team_knowledge" in self.tool_map:
            logger.info(f"🎯 [Early Team Route] Forcing team_knowledge for: {team_query_type}={team_search_term}")
            yield {"type": "metadata", "data": {"status": "team-query", "route": "team-knowledge"}}
            yield {"type": "status", "data": "Fetching team data..."}
            try:
                team_result = await execute_tool(
                    self.tool_map,
                    "team_knowledge",
                    {"query_type": team_query_type, "search_term": team_search_term},
                    user_id,
                    tool_execution_counter,
                )
                if team_result and len(team_result) > 20:
                    # Build simple prompt with team context
                    team_prompt = f"""You are ZANTARA. Answer this question using the team data below.
Be direct and factual. Use Jaksel style (mix Indonesian/English).

TEAM DATA:
{team_result}

USER QUESTION: {query}

Answer directly. Example: "Zainal Abidin è il CEO di Bali Zero."
"""
                    team_chat = self.llm_gateway.create_chat_with_history(
                        history_to_use=[], model_tier=TIER_FLASH
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
        if self.prompt_builder.check_casual_conversation(query):
            logger.info("💬 [Casual Stream] Detected casual conversation - bypassing RAG tools")
            try:
                casual_prompt = """You are ZANTARA - a friendly, warm AI with Jaksel personality.
This is a CASUAL conversation - NOT a business query.

RESPOND with personality:
- Mix Indonesian/English naturally (Jaksel style)
- Be warm, friendly, share opinions
- For restaurant/food questions: recommend real Bali places you know
- For music/lifestyle: share genuine preferences
- For personal chat: be engaging and ask follow-up questions
- Keep it conversational and fun!

User says: """ + query

                casual_chat = self.llm_gateway.create_chat_with_history(
                    history_to_use=[], model_tier=TIER_FLASH
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

        # 1. Retrieve User Context (with query for semantic collective memory retrieval)
        memory_orchestrator = await self._get_memory_orchestrator()
        user_context = await get_user_context(
            self.db_pool, user_id, memory_orchestrator, query=query, session_id=session_id
        )

        # Use provided conversation_history if available, otherwise use from user_context
        history_to_use = (
            conversation_history if conversation_history else user_context.get("history", [])
        )

        # DEFENSIVE: Ensure history_to_use is a list of dicts, not a string or list of strings
        if not isinstance(history_to_use, list):
            logger.warning(
                f"⚠️ history_to_use is not a list (type: {type(history_to_use)}), resetting to empty list"
            )
            history_to_use = []
        elif history_to_use and not isinstance(history_to_use[0], dict):
            logger.warning(
                f"⚠️ history_to_use contains non-dict items (first item type: {type(history_to_use[0])}), resetting to empty list"
            )
            history_to_use = []

        logger.debug(f"User context retrieved. History len: {len(history_to_use)}")
        
        # --- QUALITY ROUTING: CELL-GIANT HANDOFF ---
        # If DeepThink is selected, we use the advanced Cell-Giant architecture
        if suggested_ai == "deep_think":
            logger.info(f"🧠 [Stream] Delegating to Cell-Giant architecture for user {user_id}")
            async for event in self.stream_query_cell_giant(
                query=query,
                user_id=user_id,
                conversation_history=history_to_use,
                session_id=session_id
            ):
                yield event
            return

        # 2. Build Dynamic System Prompt (with query for explanation level detection)
        system_prompt = self.prompt_builder.build_system_prompt(
            user_id, user_context, query, deep_think_mode=deep_think_mode
        )
        logger.debug("System prompt built")

        # Report model being used
        model_name = "gemini-1.5-pro" if model_tier == TIER_PRO else "gemini-2.0-flash"
        yield {
            "type": "metadata",
            "data": {"status": "started", "model": model_name, "mode": suggested_ai},
        }
        logger.debug("Yielded metadata")

        # Process conversation history with Advanced Context Window Manager
        processed_history = None
        history_text = ""
        session_facts_block = ""

        if history_to_use:
            # STEP 1: Extract session facts BEFORE any trimming (from original history)
            try:
                session_extractor = SessionFactExtractor()
                session_facts = session_extractor.extract_from_history(history_to_use)
                session_facts_block = session_facts.to_prompt_block()
            except Exception as e:
                logger.warning(f"⚠️ SessionFactExtractor failed in stream: {e}", exc_info=True)
                session_facts_block = ""

            # STEP 2: Trim history with AdvancedContextWindowManager
            try:
                # Initialize context manager
                context_manager = AdvancedContextWindowManager(
                    max_tokens=12000,
                    recent_window_tokens=6000,
                    summary_max_tokens=8192,
                )

                # Process conversation history
                processed_history = await context_manager.process_conversation_history(
                    conversation_history=history_to_use,
                    system_prompt=system_prompt,
                    current_query=query,
                )

                # Use processed messages
                history_to_use = processed_history["messages"]
                history_text = processed_history["formatted_context"]

                # Log statistics
                stats = processed_history["stats"]
                total = stats["total_messages"]
                in_context = stats["messages_in_context"]
                tokens = stats["tokens"]
                logger.info(
                    f"💬 [Advanced Context Stream] Processed {total} messages: "
                    f"{in_context} in context ({tokens} tokens)"
                )

            except (ValueError, KeyError, RuntimeError) as e:
                logger.warning(
                    f"⚠️ Advanced context manager failed, using fallback: {e}", exc_info=True
                )
                # Fallback to simple truncation
                # Defensive: ensure history_to_use is a list
                if not isinstance(history_to_use, list):
                    logger.warning(
                        f"⚠️ history_to_use is not a list (type: {type(history_to_use)}), resetting to empty"
                    )
                    history_to_use = []
                history_to_use = (
                    history_to_use[-10:] if len(history_to_use) > 10 else history_to_use
                )
                history_text = "\n\nCONVERSATION HISTORY:\n"
                for msg in history_to_use:
                    # Defensive: skip if msg is not a dict
                    if not isinstance(msg, dict):
                        logger.warning(f"⚠️ Skipping non-dict message in history: {type(msg)}")
                        continue
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if len(content) > 8000:
                        content = content[:8000] + "..."
                    history_text += f"{role.upper()}: {content}\n"

        # Create chat session with conversation history using LLMGateway
        chat = self.llm_gateway.create_chat_with_history(
            history_to_use=history_to_use, model_tier=model_tier
        )
        logger.debug("Chat initialized")

        initial_prompt = f"""{system_prompt}

{session_facts_block}### CONVERSATION HISTORY (FROM PREVIOUS TURNS):
{history_text}
### END HISTORY

User Query: {query}

IMPORTANT: Use the KEY FACTS above to answer questions about user's company, budget, location. Do NOT start with philosophical statements. If you need more info, use tools."""

        # ==================== TEAM QUERY PRE-ROUTING (STREAMING) ====================
        # Force team_knowledge tool for CEO, founder, and team member queries
        is_team_query, team_query_type, team_search_term = detect_team_query(query)
        if is_team_query and "team_knowledge" in self.tool_map:
            logger.info(
                f"🎯 [Stream Pre-Route] Forcing team_knowledge for: {team_query_type}={team_search_term}"
            )
            yield {"type": "status", "data": "Fetching team data..."}
            try:
                team_result = await execute_tool(
                    self.tool_map,
                    "team_knowledge",
                    {"query_type": team_query_type, "search_term": team_search_term},
                    user_id,
                    tool_execution_counter,
                )
                # Inject team context into initial prompt
                if team_result and len(team_result) > 20:
                    initial_prompt = f"""TEAM CONTEXT (use this to answer):
{team_result}

{session_facts_block}### CONVERSATION HISTORY:
{history_text}
### END HISTORY

User Query: {query}

Use the team information above to answer. DO NOT call any tools.
IMPORTANT: Start your response with "Final Answer:" followed by your answer.
Example: "Final Answer: Zainal Abidin è il CEO di Bali Zero, esperto in management."
"""
                    logger.info(
                        f"✅ [Stream Pre-Route] Team context injected ({len(team_result)} chars)"
                    )
            except Exception as e:
                logger.warning(f"[Stream Pre-Route] Failed to pre-fetch team data: {e}")

        # REACT LOOP (Streaming)
        while state.current_step < state.max_steps:
            state.current_step += 1

            yield {"type": "status", "data": f"Step {state.current_step}: Thinking..."}

            try:
                if state.current_step == 1:
                    message = initial_prompt
                else:
                    last_observation = state.steps[-1].observation if state.steps else ""
                    message = f"""Observation: {last_observation}

Now answer "{query}" using the facts above. Start with "Final Answer:" and give CONCRETE facts, NOT a greeting."""

                text_response, model_used, response_obj = await self.llm_gateway.send_message(
                    chat, message, system_prompt, tier=model_tier, enable_function_calling=True
                )

            except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                logger.error(f"Error during streaming chat interaction: {e}", exc_info=True)
                yield {"type": "error", "data": str(e)}
                break

            # Parse for tool calls - try native function calling first, then regex fallback
            tool_call = None
            use_native = response_obj is not None

            # Check for function call in response parts (native mode)
            if response_obj and hasattr(response_obj, "candidates"):
                for candidate in response_obj.candidates:
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            tool_call = parse_tool_call(part, use_native=True)
                            if tool_call:
                                logger.info("✅ [Stream Native Function Call] Detected")
                                break
                        if tool_call:
                            break

            # Fallback to regex parsing if no native function call found
            if not tool_call:
                tool_call = parse_tool_call(text_response, use_native=False)

            if tool_call:
                yield {
                    "type": "tool_start",
                    "data": {"name": tool_call.tool_name, "args": tool_call.arguments},
                }

                tool_result = await execute_tool(
                    self.tool_map,
                    tool_call.tool_name,
                    tool_call.arguments,
                    user_id,
                    tool_execution_counter,
                )

                # --- CITATION HANDLING (STREAMING PATH) ---
                if tool_call.tool_name == "vector_search":
                    try:
                        parsed_result = json.loads(tool_result)
                        if isinstance(parsed_result, dict) and "sources" in parsed_result:
                            content = parsed_result.get("content", "")
                            new_sources = parsed_result.get("sources", [])

                            if not hasattr(state, "sources"):
                                state.sources = []

                            if isinstance(new_sources, list):
                                state.sources.extend(
                                    [s for s in new_sources if isinstance(s, dict)]
                                )

                            # Replace observation with just the retrieved content (not JSON envelope)
                            if isinstance(content, str) and content:
                                tool_result = content
                    except json.JSONDecodeError as json_err:
                        logger.error(
                            f"JSONDecodeError in stream parsing: {str(json_err)}", exc_info=True
                        )
                        pass
                    except (KeyError, ValueError, TypeError) as e:
                        logger.warning(
                            f"Failed to parse vector_search result in stream: {e}", exc_info=True
                        )
                tool_call.result = tool_result

                yield {
                    "type": "tool_end",
                    "data": {
                        "result": tool_result[:200] + "..."
                        if len(tool_result) > 200
                        else tool_result
                    },
                }

                step = AgentStep(
                    step_number=state.current_step,
                    thought=text_response,
                    action=tool_call,
                    observation=tool_result,
                )
                state.steps.append(step)
                state.context_gathered.append(tool_result)

            else:
                if "Final Answer:" in text_response or state.current_step >= state.max_steps:
                    final_text = text_response
                    if "Final Answer:" in final_text:
                        final_text = final_text.split("Final Answer:")[-1].strip()

                    # Quick post-process for streaming (full pipeline runs later)
                    final_text = post_process_response(final_text, query)
                    state.final_answer = final_text
                    step = AgentStep(
                        step_number=state.current_step, thought=text_response, is_final=True
                    )
                    state.steps.append(step)

                    # Simulate token streaming for the final answer (only if we have content)
                    # Use lower threshold (20 chars) to support short team answers like "X is the CEO"
                    if final_text and len(final_text) >= 20:
                        import re

                        tokens = re.findall(r"\S+|\s+", final_text)
                        for token in tokens:
                            yield {"type": "token", "data": token}
                            await asyncio.sleep(0.01)  # Tiny delay for UX
                    else:
                        yield {"type": "status", "data": "Generating enhanced answer..."}

                    break
                else:
                    step = AgentStep(step_number=state.current_step, thought=text_response)
                    state.steps.append(step)

        # Generate final answer if not present
        if not state.final_answer and state.context_gathered:
            yield {"type": "status", "data": "Generating final answer..."}
            context = "\n\n".join(state.context_gathered)
            final_prompt = f"Based on: {context}\n\nAnswer: {query}"
            try:
                raw_answer, _, _ = await self.llm_gateway.send_message(
                    chat,
                    final_prompt,
                    system_prompt,
                    tier=model_tier,
                    enable_function_calling=False,
                )
                # Post-process response: clean and enforce communication rules
                state.final_answer = post_process_response(raw_answer, query)

                # Stream tokens only if we have content (20 char min for short answers)
                if state.final_answer and len(state.final_answer) >= 20:
                    import re

                    tokens = re.findall(r"\S+|\s+", state.final_answer)
                    for token in tokens:
                        yield {"type": "token", "data": token}
                        await asyncio.sleep(0.01)
                else:
                    yield {
                        "type": "status",
                        "data": "Answer too short, searching for more information...",
                    }
            except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                logger.error("Failed to generate final answer in stream", exc_info=True)
                yield {"type": "error", "data": "Failed to generate final answer."}

        # Calculate final metrics
        execution_time = time.time() - start_time

        # Run pipeline for verification and citation processing (after streaming)
        verification_score = 1.0
        processed_citations = []

        if state.final_answer:
            try:
                pipeline_data = {
                    "response": state.final_answer,
                    "query": query,
                    "context_chunks": state.context_gathered,
                    "sources": state.sources if hasattr(state, "sources") else [],
                }

                # Process through pipeline
                processed = await self.response_pipeline.process(pipeline_data)

                # Extract verification score
                verification_score = processed.get("verification_score", 1.0)

                # Extract processed citations
                processed_citations = processed.get("citations", [])

                logger.info(
                    f"[Stream Pipeline] Verification: {verification_score:.2f}, "
                    f"Citations: {len(processed_citations)}"
                )

            except (ValueError, RuntimeError, KeyError) as e:
                logger.warning(f"[Stream Pipeline] Processing failed: {e}", exc_info=True)

        # Analyze emotional state of the answer/interaction
        emotional_profile = self.emotional_service.analyze_message(state.final_answer or "")
        emotional_state = emotional_profile.detected_state if emotional_profile else "NEUTRAL"

        # Check for Golden Answer
        golden_answer_used = False
        if self.golden_answer_service:
            try:
                ga = await self.golden_answer_service.lookup_golden_answer(query, user_id)
                if ga:
                    golden_answer_used = True
            except Exception as e:
                logger.warning(f"Golden answer lookup failed: {e}")

        # Generate Follow-up Questions
        followup_questions = []
        try:
            followup_questions = await self.followup_service.get_followups(
                query=query, response=state.final_answer or ""
            )
        except Exception as e:
            logger.warning(f"Follow-up generation failed: {e}")

        # Yield Final Metadata Event (Trust & Explainability)
        yield {
            "type": "metadata",
            "data": {
                "status": "completed",
                "execution_time": execution_time,
                "route_used": f"{suggested_ai} ({model_name})",
                "context_length": len(history_text) if history_text else 0,
                "emotional_state": emotional_state,
                "verification_score": int(verification_score * 100),  # Convert to percentage
                "user_memory_facts": user_context.get("facts", []),
                "collective_memory_facts": user_context.get("collective_facts", []),
                "golden_answer_used": golden_answer_used,
                "followup_questions": followup_questions,
            },
        }

        # Emit processed citations from pipeline
        if processed_citations:
            try:
                # Add IDs and prepare for frontend
                safe_sources: list[dict[str, Any]] = []
                for idx, citation in enumerate(processed_citations, start=1):
                    safe_src = {
                        "id": idx,
                        "title": citation.get("title", ""),
                        "collection": citation.get("collection", ""),
                        "score": citation.get("score", 0),
                        "url": citation.get("url", ""),
                        "snippet": citation.get("snippet", ""),
                    }
                    safe_sources.append(safe_src)

                yield {"type": "sources", "data": safe_sources}
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Failed to emit citations in stream: {e}", exc_info=True)

        # 🧠 MEMORY PERSISTENCE: Save facts from conversation
        # For LTM tests, run synchronously to debug; otherwise background
        memory_save_info = None
        if state.final_answer and user_id and user_id != "anonymous":
            if user_id.startswith("ltm_user_"):
                try:
                    logger.info(f"🧪 [AgenticRAG] Synchronous memory save for test user {user_id}")
                    # We need to await it here
                    # Note: We can't easily await a method that isn't async if this function is async generator
                    # But stream_query IS async generator.
                    # We need to call the method directly.

                    # We need to manually construct the result to pass back
                    mem_orch = await self._get_memory_orchestrator()
                    if mem_orch:
                        res = await mem_orch.process_conversation(
                            user_email=user_id, user_message=query, ai_response=state.final_answer
                        )
                        memory_save_info = {
                            "extracted": res.facts_extracted,
                            "saved": res.facts_saved,
                            "error": None,
                        }
                    else:
                        memory_save_info = {"error": "No memory orchestrator"}
                except Exception as e:
                    logger.error(f"Test memory save failed: {e}")
                    memory_save_info = {"error": str(e)}
            else:
                task = asyncio.create_task(
                    self._save_conversation_memory(
                        user_id=user_id,
                        query=query,
                        answer=state.final_answer,
                    )
                )
                task.add_done_callback(
                    lambda t: logger.error(f"❌ Memory save failed: {t.exception()}")
                    if t.exception() else None
                )

        # Update debug_info with memory save results if available
        if memory_save_info:
            # We need to inject this into the LAST chunk's debug_info
            # But the yield happens usually before?
            # Wait, the yield {"type": "done", "data": ...} happens below.
            pass

        # Convert dataclass to dict (AgentState is a dataclass, not Pydantic)
        state_dict = asdict(state)

        yield {
            "type": "done",
            "data": {
                **state_dict,
                "debug_info": {
                    **state_dict.get("debug_info", {}),
                    "memory_save_result": memory_save_info,
                },
            },
        }
