"""
LLM Gateway - Unified interface for LLM interactions with automatic fallback.

This module provides a centralized gateway for all Language Model interactions,
handling model initialization, tier-based routing, and automatic fallback cascades.

Key Features:
- Multi-tier Gemini model support (Pro, Flash, Flash-Lite)
- Automatic fallback cascade on quota/service errors
- OpenRouter integration as final fallback
- Native function calling support
- Error handling and retry logic
- Health check capabilities

Architecture:
    LLMGateway acts as the single source of truth for all LLM operations,
    abstracting model complexity from business logic. It ensures high
    availability through intelligent fallback routing.

Example:
    >>> gateway = LLMGateway(gemini_tools=[...])
    >>> response, model, obj = await gateway.send_message(
    ...     chat=chat_session,
    ...     message="What is KITAS?",
    ...     tier=TIER_FLASH,
    ... )
    >>> logger.info(f"Response from {model}: {response}")

Author: Nuzantara Team
Date: 2025-12-17
Version: 1.2.0

UPDATED 2025-12-23:
- Migrated to new google-genai SDK (replaced deprecated google-generativeai)
- Using GenAIClient wrapper for centralized client management
"""

import asyncio
import logging
from typing import Any

import httpx
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from backend.app.core.circuit_breaker import CircuitBreaker
from backend.app.core.constants import HttpTimeoutConstants
from backend.app.core.error_classification import ErrorClassifier, get_error_context
from backend.app.metrics import metrics_collector
from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient, get_genai_client, types
from backend.services.llm_clients.openrouter_client import ModelTier, OpenRouterClient
from backend.services.llm_clients.pricing import TokenUsage, create_token_usage
from backend.services.rag.agentic.chat_session import ChatSession, MockChatSession

logger = logging.getLogger(__name__)

# Model Tier Constants
TIER_FLASH = 0  # Fast, cost-effective (default) - gemini-3-flash
TIER_LITE = 1  # Alias for FLASH
TIER_PRO = 2  # Alias for FLASH (no separate pro tier)
TIER_FALLBACK = 3  # Stable fallback - gemini-2.5-flash


class LLMGateway:
    """
    Unified gateway for LLM interactions with intelligent fallback routing.

    Responsibilities:
    - Initialize and manage Gemini models (Pro, Flash, Flash-Lite) via GenAIClient
    - Handle OpenRouter fallback for high availability
    - Route requests to appropriate model tier
    - Cascade fallback on quota/service errors: Flash → Flash-Lite → OpenRouter
    - Support native function calling and regex fallback
    - Provide health check capabilities

    The gateway ensures that user requests are always served, even when
    primary models are unavailable, by automatically falling back to
    alternative models.

    Attributes:
        gemini_tools (list): Function declarations for native tool calling
        _genai_client (GenAIClient): Centralized GenAI client instance
        model_name_pro (str): Gemini 2.5 Flash (same as flash tier)
        model_name_flash (str): Gemini 2.5 Flash (primary model)
        model_name_fallback (str): Gemini 2.0 Flash (stable fallback)
        thinking_level (str): Gemini reasoning depth ("minimal", "low", "medium", "high")
        _openrouter_client (OpenRouterClient): Lazy-loaded OpenRouter client

    Note:
        - Uses new google-genai SDK via GenAIClient wrapper
        - OpenRouter client is lazy-loaded to avoid unnecessary initialization
    """

    def __init__(self, gemini_tools: list = None) -> None:
        """Initialize LLM Gateway with Gemini models and OpenRouter fallback.

        Sets up all Gemini model instances and prepares for automatic fallback
        to OpenRouter if needed. Configures native function calling if tools
        are provided.

        Args:
            gemini_tools: Optional list of Gemini function declarations for tool use.
                These enable native function calling in Gemini models.

        Note:
            - Requires GOOGLE_API_KEY in settings
            - OpenRouter client is initialized lazily on first use
            - GenAI client handles connection pooling
        """
        self._gemini_tools = gemini_tools or []

        # Initialize GenAI client (new SDK)
        # Uses singleton client that supports both API Key and Service Account (Vertex AI)
        self._genai_client: GenAIClient | None = None

        # Model name constants - Updated 2026-04-06
        # Gemini 3 Flash GA (Dec 2025)
        # - GPQA Diamond: 90.4%, 3x faster than 2.5 Flash
        # - Cost: $0.50/1M input, $3/1M output
        # - Available via AI Studio API (no allowlist needed)
        self.model_name_pro = "gemini-3-flash"  # Primary: GA release
        self.model_name_flash = "gemini-3-flash"
        self.model_name_fallback = "gemini-2.5-flash"  # Fallback: previous gen stable

        logger.info(
            "✅ LLMGateway: Model configuration ready (gemini-3-flash primary, "
            "gemini-2.5-flash fallback)",
        )

        # Future 3-tier models (when implemented)
        # Tier 2: claude-3-5-haiku (Anthropic) - complex reasoning
        # Tier 3: gpt-4o-mini (OpenAI) - reliable fallback

        # Lazy-loaded OpenRouter client (fallback)
        self._openrouter_client: OpenRouterClient | None = None

        # Circuit breaker configuration using CircuitBreaker class
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = HttpTimeoutConstants.CIRCUIT_BREAKER_TIMEOUT  # seconds
        self._max_fallback_depth = 3
        self._max_fallback_cost_usd = 0.10  # Max $0.10 per query

    def _get_genai_client(self) -> GenAIClient | None:
        """Lazy load GenAI client."""
        if self._genai_client is None and GENAI_AVAILABLE:
            try:
                # Use singleton client - it handles both API key and Service Account auth
                client = get_genai_client()
                if client.is_available:
                    self._genai_client = client
                    auth_method = getattr(self._genai_client, "_auth_method", "unknown")
                    logger.debug(f"✅ LLMGateway: GenAI client loaded (auth: {auth_method})")
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client: {e}")
        return self._genai_client

    @property
    def _available(self) -> bool:
        """Check availability dynamically.

        Returns the actual client availability unless a test override is set.
        Tests can set gateway._available = True/False to mock availability.
        """
        # Check if test override is set
        if "_available_override" in self.__dict__:
            return self.__dict__["_available_override"]
        # Return actual availability
        client = self._get_genai_client()
        return client.is_available if client else False

    @_available.setter
    def _available(self, value: bool) -> None:
        """Set availability for testing purposes.

        This setter allows tests to mock the availability state.
        In production, availability is determined by the GenAI client state.
        """
        self.__dict__["_available_override"] = value

    @property
    def gemini_tools(self) -> list:
        """Get the Gemini function declarations for tool calling.

        Returns:
            List of Gemini function declarations
        """
        return self._gemini_tools

    def set_gemini_tools(self, tools: list) -> None:
        """Set or update Gemini function declarations for tool calling.

        Allows tools to be set after initialization, useful when tools
        are created after the LLMGateway instance.

        Args:
            tools: List of Gemini function declarations for native tool calling
        """
        self._gemini_tools = tools or []
        logger.debug(f"LLMGateway: Updated gemini_tools ({len(self.gemini_tools)} tools)")

    def _get_openrouter_client(self) -> OpenRouterClient | None:
        """Lazy load OpenRouter client for third-party fallback.

        Creates OpenRouter client only when needed to avoid unnecessary API calls.
        Used as final fallback when all Gemini models are unavailable.

        Returns:
            OpenRouterClient instance or None if initialization fails

        Note:
            - Requires user consent for third-party processing in production
            - Logs warnings for audit trail compliance
            - Uses ModelTier.RAG for cost-optimized model selection
        """
        if self._openrouter_client is None:
            try:
                self._openrouter_client = OpenRouterClient(default_tier=ModelTier.RAG)
                logger.info("✅ LLMGateway: OpenRouter client initialized (lazy)")
            except (httpx.HTTPError, ValueError, KeyError) as e:
                logger.error(f"❌ LLMGateway: Failed to initialize OpenRouter: {e}", exc_info=True)
                return None
        return self._openrouter_client

    def create_chat_with_history(
        self,
        history_to_use: list[dict] | None,
        model_tier: int = TIER_FLASH,
        system_instruction: str = "",
    ) -> "ChatSession":
        """
        Create a ChatSession with conversation history for multi-turn chat.

        Best Practice 2026: Use startChat() with history for context persistence.

        Args:
            history_to_use: Previous conversation messages [{role, content}, ...]
            model_tier: Model tier (TIER_FLASH, TIER_PRO, etc.)
            system_instruction: System prompt for the session

        Returns:
            ChatSession object with history
        """
        client = self._get_genai_client()
        if not client or not client.is_available:
            logger.warning("GenAI client not available, returning mock session")
            return MockChatSession(history=history_to_use or [])

        # Convert history to Gemini format
        gemini_history = []
        for msg in history_to_use or []:
            if not isinstance(msg, dict):
                continue
            role = "user" if msg.get("role") == "user" else "model"
            gemini_history.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

        # Create chat session with history
        model_name = self._get_model_for_tier(model_tier)

        return ChatSession(
            client=client,
            model=model_name,
            history=gemini_history,
            system_instruction=system_instruction,
        )

    def _get_model_for_tier(self, tier: int) -> str:
        """Get model name for given tier."""
        if tier == TIER_PRO:
            return self.model_name_pro
        if tier in (TIER_LITE, TIER_FALLBACK):
            return self.model_name_fallback
        return self.model_name_flash

    async def send_message(
        self,
        chat: Any,
        message: str,
        system_prompt: str = "",
        tier: int = TIER_FLASH,
        enable_function_calling: bool = True,
        conversation_messages: list[dict] | None = None,
        images: list[dict]
        | None = None,  # Vision: [{"base64": "data:image/...", "name": "file.jpg"}]
    ) -> tuple[str, str, Any, TokenUsage]:
        """Send message to LLM with tier-based routing and automatic fallback.

        Main public API for sending messages to language models. Implements
        intelligent cascade fallback to ensure high availability.

        Fallback Chain:
            1. Try requested tier (Pro/Flash/Lite)
            2. On quota/error → fall back to next cheaper tier
            3. Final fallback → OpenRouter

        Args:
            chat: Active Gemini chat session (or None to create new)
            message: User message or continuation prompt
            system_prompt: System instructions (used for OpenRouter fallback)
            tier: Requested model tier (TIER_PRO=2, TIER_FLASH=0, TIER_LITE=1)
            enable_function_calling: Enable native function calling for Gemini models
            conversation_messages: Conversation history for OpenRouter fallback
            images: List of images for vision (base64 encoded with data URI prefix)

        Returns:
            Tuple of (response_text, model_name_used, response_object, token_usage)
            - response_text (str): Generated response content
            - model_name_used (str): Model that generated the response
            - response_object (Any): Full response object (for function call parsing)
            - token_usage (TokenUsage): Token counts and cost information

        Raises:
            RuntimeError: If all models fail (including OpenRouter)

        Example:
            >>> response, model, obj, usage = await gateway.send_message(
            ...     chat=chat_session,
            ...     message="What is the capital of Indonesia?",
            ...     tier=TIER_FLASH,
            ... )
            >>> logger.info(f"[{model}] {response} (cost: ${usage.cost_usd:.6f})")
        """
        query_cost_tracker = {"cost": 0.0, "depth": 0}
        try:
            return await self._send_with_fallback(
                chat=chat,
                message=message,
                system_prompt=system_prompt,
                model_tier=tier,
                enable_function_calling=enable_function_calling,
                conversation_messages=conversation_messages or [],
                query_cost_tracker=query_cost_tracker,
                images=images,
            )
        except Exception as e:
            logger.exception(
                "All LLM models failed",
                extra={
                    "tier": tier,
                    "fallback_depth": query_cost_tracker["depth"],
                    "total_cost": query_cost_tracker["cost"],
                },
            )
            try:
                from backend.app.metrics import llm_all_models_failed_total

                llm_all_models_failed_total.inc()
            except ImportError:
                pass
            raise RuntimeError(f"All LLM models failed: {e}") from None

    def _get_circuit_breaker(self, model_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for model."""
        if model_name not in self._circuit_breakers:
            self._circuit_breakers[model_name] = CircuitBreaker(
                failure_threshold=self._circuit_breaker_threshold,
                success_threshold=2,
                timeout=self._circuit_breaker_timeout,
                name=f"llm_{model_name}",
            )
        return self._circuit_breakers[model_name]

    def _is_circuit_open(self, model_name: str) -> bool:
        """Check if circuit breaker is open."""
        circuit = self._get_circuit_breaker(model_name)
        return circuit.is_open()

    def _record_success(self, model_name: str) -> None:
        """Record successful call."""
        circuit = self._get_circuit_breaker(model_name)
        circuit.record_success()

    def _record_failure(self, model_name: str, error: Exception) -> None:
        """Record failed call with error classification."""
        circuit = self._get_circuit_breaker(model_name)
        circuit.record_failure()

        # Classify error and log metrics
        error_category, error_severity = ErrorClassifier.classify_error(error)
        error_type = type(error).__name__

        # Log with structured context
        error_context = get_error_context(error, model=model_name)
        logger.warning(f"LLM call failed for {model_name}", extra=error_context)

        # Record metrics if circuit opened
        if circuit.is_open():
            try:
                from backend.app.metrics import llm_circuit_breaker_opened_total

                llm_circuit_breaker_opened_total.labels(
                    model=model_name, error_type=error_type,
                ).inc()
            except ImportError:
                pass

    def _get_fallback_chain(self, model_tier: int) -> list[str]:
        """Get fallback chain for given tier."""
        chain = []
        if model_tier == TIER_PRO:
            chain.append(self.model_name_pro)

        # RAG-06 Fix: Ensure TIER_LITE (1) and TIER_PRO (2) also try the flash model
        if model_tier <= TIER_PRO and self.model_name_flash not in chain:
            chain.append(self.model_name_flash)

        if self.model_name_fallback not in chain:
            chain.append(self.model_name_fallback)

        return chain

    async def _send_with_fallback(
        self,
        chat: Any,
        message: str,
        system_prompt: str,
        model_tier: int,
        enable_function_calling: bool,
        conversation_messages: list[dict],
        query_cost_tracker: dict,
        images: list[dict] | None = None,
    ) -> tuple[str, str, Any, TokenUsage]:
        """Send message with tier-based routing, native function calling, and cascade fallback.

        Implements intelligent model selection with automatic degradation:
        1. Try requested tier (Pro/Flash/Lite) with native function calling
        2. On quota/error: cascade to next cheaper tier
        3. Final fallback: OpenRouter (third-party) with regex parsing

        This ensures high availability while optimizing costs.

        Args:
            chat: Active chat session (unused in new SDK, kept for API compatibility)
            message: User message or continuation prompt
            system_prompt: System instructions (used for OpenRouter fallback)
            model_tier: Requested tier (TIER_PRO=2, TIER_FLASH=0, TIER_LITE=1)
            enable_function_calling: Whether to enable native function calling (default: True)
            conversation_messages: Message history for OpenRouter
            images: Optional list of images for vision capability

        Returns:
            Tuple of (response_text, model_name_used, response_object)
            response_object contains parts that may include function_call

        Raises:
            RuntimeError: If all models fail (including OpenRouter)

        Note:
            - Uses new google-genai SDK with client.aio.models.generate_content
            - Logs all tier transitions for monitoring
            - Extracts user query from structured prompts for OpenRouter
            - Native function calling enabled for Gemini models
        """
        # Get fallback chain
        models_to_try = self._get_fallback_chain(model_tier)

        for model_name in models_to_try:
            # Check circuit breaker
            if self._is_circuit_open(model_name):
                logger.debug(f"Circuit breaker OPEN for {model_name}, skipping")
                try:
                    from backend.app.metrics import llm_circuit_breaker_open_total

                    llm_circuit_breaker_open_total.labels(model=model_name).inc()
                except ImportError:
                    pass
                continue

            # Check cost limit
            if query_cost_tracker["cost"] >= self._max_fallback_cost_usd:
                logger.warning(
                    f"Cost limit reached ({query_cost_tracker['cost']:.4f} USD), "
                    f"stopping fallback cascade",
                )
                try:
                    from backend.app.metrics import llm_cost_limit_reached_total

                    llm_cost_limit_reached_total.inc()
                except ImportError:
                    pass
                break

            # Check fallback depth
            if query_cost_tracker["depth"] >= self._max_fallback_depth:
                logger.warning(
                    f"Max fallback depth reached ({query_cost_tracker['depth']}), stopping cascade",
                )
                try:
                    from backend.app.metrics import llm_max_depth_reached_total

                    llm_max_depth_reached_total.inc()
                except ImportError:
                    pass
                break

            # Check if model is available
            if not self._available:
                continue

            try:
                # Try model
                text_content, response, token_usage = await self._call_model(
                    model_name,
                    with_tools=enable_function_calling,
                    chat=chat,
                    message=message,
                    images=images,
                    _system_prompt=system_prompt,
                )

                # Success - reset circuit breaker
                self._record_success(model_name)
                query_cost_tracker["cost"] += token_usage.cost_usd
                query_cost_tracker["depth"] += 1

                try:
                    from backend.app.metrics import llm_fallback_depth, llm_query_cost_usd

                    llm_fallback_depth.observe(query_cost_tracker["depth"])
                    llm_query_cost_usd.observe(query_cost_tracker["cost"])
                except ImportError:
                    pass

                logger.debug(f"✅ LLMGateway: {model_name} response received")
                return (text_content, model_name, response, token_usage)

            except ResourceExhausted as e:
                # Quota exceeded - record failure with error classification
                self._record_failure(model_name, e)
                logger.warning(f"Quota exhausted for {model_name}: {e}")
                try:
                    from backend.app.metrics import llm_quota_exhausted_total

                    llm_quota_exhausted_total.labels(model=model_name).inc()
                except ImportError:
                    pass
                metrics_collector.record_llm_fallback(model_name, "next_model")
                continue

            except ServiceUnavailable as e:
                # Service unavailable - record failure with error classification
                self._record_failure(model_name, e)
                logger.warning(f"Service unavailable for {model_name}: {e}")
                try:
                    from backend.app.metrics import llm_service_unavailable_total

                    llm_service_unavailable_total.labels(model=model_name).inc()
                except ImportError:
                    pass
                metrics_collector.record_llm_fallback(model_name, "next_model")
                continue

            except Exception as e:
                # Other errors - record failure with error classification
                self._record_failure(model_name, e)
                error_type = type(e).__name__
                logger.warning(f"Error with {model_name}: {e}")
                try:
                    from backend.app.metrics import llm_model_error_total

                    llm_model_error_total.labels(model=model_name, error_type=error_type).inc()
                except ImportError:
                    pass
                metrics_collector.record_llm_fallback(model_name, "next_model")
                continue

        # All Gemini models failed - try OpenRouter as final fallback
        logger.warning("⚠️ LLMGateway: All Gemini models failed, attempting OpenRouter fallback")
        try:
            # Build messages list for OpenRouter (it expects role/content format)
            openrouter_messages = conversation_messages or [{"role": "user", "content": message}]

            openrouter_response, token_usage = await self._call_openrouter(
                openrouter_messages, system_prompt,
            )

            # Record cost
            query_cost_tracker["cost"] += token_usage.cost_usd
            query_cost_tracker["depth"] += 1

            return (openrouter_response, "openrouter", None, token_usage)
        except Exception as openrouter_error:
            logger.error(f"❌ LLMGateway: OpenRouter fallback also failed: {openrouter_error}")
            # All fallbacks exhausted
            raise RuntimeError(
                "All models in fallback chain failed (including OpenRouter)",
            ) from None

    async def _call_model(
        self,
        model_name: str,
        with_tools: bool = False,
        chat: Any = None,
        message: str = "",
        images: list[dict] | None = None,
        _system_prompt: str = "",
    ) -> tuple[str, Any, TokenUsage]:
        """Call a specific model and return (text, response, token_usage)."""
        if not self._available:
            raise RuntimeError("GenAI client not available")
        client = self._get_genai_client()

        # Helper function to build multimodal content
        def _build_multimodal_content(text: str, imgs: list[dict] | None) -> Any:
            """Build content structure for multimodal input (text + images)."""
            parts = [{"text": text}]

            if imgs:
                for img in imgs:
                    try:
                        # Handle different image formats
                        if img.get("format") == "base64":
                            import base64

                            image_data = base64.b64decode(img["data"])
                        else:
                            # Assume raw bytes
                            image_data = img["data"]

                        import mimetypes

                        mime_type = img.get(
                            "mime_type",
                            mimetypes.guess_type(img.get("filename", ""))[0] or "image/jpeg",
                        )

                        # Import Part inline to avoid circular imports
                        from google.genai.types import Part

                        parts.append(
                            Part.from_data(
                                data=image_data,
                                mime_type=mime_type,
                            ),
                        )
                    except Exception as img_err:
                        logger.warning(f"⚠️ Failed to process image: {img_err}")

            if not parts:
                return text  # Fallback to plain text if no parts built

            # Return as content structure for Gemini
            return [{"parts": parts}]

        # Helper function to build config
        def _build_config(with_tools: bool = False, sys_prompt: str = "") -> Any:
            """Build configuration for model generation."""
            config_args = {}
            if with_tools and self._gemini_tools:
                # Convert tool dicts to proper FunctionDeclaration format for new SDK
                # (Same conversion as in the class-level _build_config method)
                function_declarations = []
                for tool_dict in self._gemini_tools:
                    params = tool_dict.get("parameters", {})
                    func_decl = types.FunctionDeclaration(
                        name=tool_dict["name"],
                        description=tool_dict["description"],
                        parameters=types.Schema(
                            type=params.get("type", "OBJECT"),
                            properties={
                                k: types.Schema(
                                    type=v.get("type", "STRING"),
                                    description=v.get("description", ""),
                                )
                                for k, v in params.get("properties", {}).items()
                            },
                            required=params.get("required", []),
                        ),
                    )
                    function_declarations.append(func_decl)
                config_args["tools"] = [types.Tool(function_declarations=function_declarations)]
                # Add tool_config to encourage function calling
                import contextlib

                with contextlib.suppress(AttributeError, TypeError):
                    config_args["tool_config"] = types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(mode="AUTO"),
                    )

            # Inject system instruction if present
            if sys_prompt:
                config_args["system_instruction"] = sys_prompt

            return types.GenerateContentConfig(**config_args)

        # CRITICAL: Use chat session if available to maintain conversation context
        # This ensures Gemini 3 maintains full conversation history across ReAct loop steps

        # Build configuration first
        config = _build_config(with_tools, sys_prompt=_system_prompt)

        # Determine contents (history + new message)
        contents = []

        if chat and hasattr(chat, "history"):
            logger.debug(f"💬 Using ChatSession with {len(chat.history)} history messages")

            # 1. Convert history to correct format/roles
            for item in chat.history:
                role = item.get("role", "user")
                # Fix common role errors
                if role == "assistant":
                    role = "model"

                parts = item.get("parts", [])
                # Ensure parts are valid
                if parts:
                    contents.append({"role": role, "parts": parts})

            # 2. Add new message
            # Reset text content holder
            text_content = ""

            # Build current message content
            current_content_parts = []

            # Handle text
            if message:
                current_content_parts.append({"text": message})

            # Handle images (multimodal)
            if images:
                processed_images = _build_multimodal_content("", images)
                if (
                    isinstance(processed_images, list)
                    and processed_images
                    and "parts" in processed_images[0]
                ):
                    # _build_multimodal_content returns [{"parts": [...]}]
                    current_content_parts.extend(processed_images[0]["parts"])

            if current_content_parts:
                contents.append({"role": "user", "parts": current_content_parts})

            # 3. Call model with full history (with timeout to avoid hang)
            response = await asyncio.wait_for(
                client._client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                ),
                timeout=HttpTimeoutConstants.DEFAULT_TIMEOUT,
            )

            # 4. Update chat history manually
            # Extract response text with safety checks
            text_content = ""
            if hasattr(response, "text") and response.text:
                text_content = response.text
            elif hasattr(response, "candidates") and response.candidates:
                # Try to extract from candidates if text property is empty
                for candidate in response.candidates:
                    if hasattr(candidate, "content") and candidate.content:
                        for part in candidate.content.parts:
                            if hasattr(part, "text") and part.text:
                                text_content += part.text

            # Log warning if response is empty (could be safety block)
            if not text_content:
                finish_reason = None
                if hasattr(response, "candidates") and response.candidates:
                    finish_reason = getattr(response.candidates[0], "finish_reason", None)
                logger.warning(
                    f"⚠️ LLMGateway: Empty response from {model_name}. "
                    f"Finish reason: {finish_reason}. Possible safety block or content filter.",
                )

            # Add user message to history
            chat.history.append({"role": "user", "parts": current_content_parts})

            # Add model response to history (if text exists)
            # Function calls are handled separately in response object but history needs text or parts
            # For simplicity in history we store text if available
            if text_content:
                chat.history.append({"role": "model", "parts": [{"text": text_content}]})
            elif hasattr(response, "function_calls") and response.function_calls:
                # Store function call in history if needed, but for now we skip to avoid complexity
                # as ReAct loop handles function calls via tool outputs
                pass

            # Extract token usage
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = (
                    getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                )

            token_usage = create_token_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model_name,
            )
            return text_content, response, token_usage

        # Fallback: Build content directly (for backward compatibility or when chat is None)
        # Build content (plain text or multimodal with images)
        content = _build_multimodal_content(message, images)
        has_images = images is not None and len(images) > 0

        # 🔍 TRACING: Span for LLM call
        with trace_span(
            "backend.llm.call",
            {
                "model": model_name,
                "with_tools": with_tools,
                "message_length": len(message),
                "has_images": has_images,
                "image_count": len(images) if images else 0,
            },
        ):
            config = _build_config(with_tools, sys_prompt=_system_prompt)

            if has_images:
                logger.info(f"🖼️ Vision mode: sending {len(images)} images to {model_name}")

            response = await asyncio.wait_for(
                client._client.aio.models.generate_content(
                    model=model_name,
                    contents=content,
                    config=config,
                ),
                timeout=HttpTimeoutConstants.DEFAULT_TIMEOUT,
            )

            # Extract token usage from response
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = (
                    getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                )

            token_usage = create_token_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model_name,
            )

            # Log token usage for monitoring
            logger.debug(
                f"📊 [LLMGateway] Token usage: {prompt_tokens} prompt + {completion_tokens} completion "
                f"= {token_usage.total_tokens} total (${token_usage.cost_usd:.6f})",
            )
            set_span_attribute("prompt_tokens", prompt_tokens)
            set_span_attribute("completion_tokens", completion_tokens)
            set_span_attribute("cost_usd", token_usage.cost_usd)

            # Extract text, handling function call responses
            try:
                text_content = ""
                if hasattr(response, "text") and response.text:
                    text_content = response.text
                elif hasattr(response, "candidates") and response.candidates:
                    # Try to extract from candidates if text property is empty
                    for candidate in response.candidates:
                        if hasattr(candidate, "content") and candidate.content:
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    text_content += part.text

                # text_content can be None/empty if Gemini returns a function call
                if not text_content:
                    # Check if this is a function call
                    has_function_call = (
                        hasattr(response, "function_calls") and response.function_calls
                    ) or (
                        hasattr(response, "candidates")
                        and response.candidates
                        and hasattr(response.candidates[0], "content")
                        and response.candidates[0].content
                        and any(
                            hasattr(p, "function_call") and p.function_call
                            for p in response.candidates[0].content.parts
                        )
                    )
                    if has_function_call:
                        set_span_attribute("has_function_call", "true")
                    else:
                        set_span_attribute("has_function_call", "false")
                        # Log warning for truly empty responses
                        finish_reason = (
                            getattr(response.candidates[0], "finish_reason", None)
                            if hasattr(response, "candidates") and response.candidates
                            else None
                        )
                        logger.warning(
                            f"⚠️ LLMGateway: Empty text response from {model_name}. "
                            f"Finish reason: {finish_reason}. Possible safety block.",
                        )
                else:
                    set_span_attribute("has_function_call", "false")

                set_span_attribute("response_length", len(text_content))
            except ValueError as e:
                # Function call detected or other error - reasoning.py will extract it from response_obj
                logger.warning(f"⚠️ LLMGateway: ValueError extracting text: {e}")
                text_content = ""
                set_span_attribute("has_function_call", "true")
                set_span_attribute("response_length", 0)

            set_span_status("ok")
            return text_content, response, token_usage

    async def _call_openrouter(
        self, messages: list[dict], system_prompt: str,
    ) -> tuple[str, TokenUsage]:
        """Call OpenRouter as final fallback when Gemini models are unavailable.

        Uses third-party OpenRouter API for model access. Requires user consent
        in production environments for GDPR/privacy compliance.

        Args:
            messages: Conversation history as list of role/content dicts
            system_prompt: System instructions for model behavior

        Returns:
            Tuple of (response_text, token_usage)

        Raises:
            RuntimeError: If OpenRouter client is not available
        """

        # Log that we're using third-party (for audit)
        logger.warning("🌐 LLMGateway: Using OpenRouter fallback (third-party service)")

        client = self._get_openrouter_client()
        if not client:
            raise RuntimeError("OpenRouter client not available")

        # Build messages with system prompt
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        result = await client.complete(full_messages, tier=ModelTier.RAG)
        logger.info(f"✅ LLMGateway: OpenRouter fallback used: {result.model_name}")

        # Convert OpenRouter usage to TokenUsage object
        usage = create_token_usage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            model=result.model_used,
        )

        return result.content, usage

    async def health_check(self) -> dict[str, bool]:
        """Check health of all LLM providers.

        Tests connectivity and availability of Gemini models and OpenRouter.
        Useful for monitoring and debugging.

        Returns:
            Dict mapping provider names to availability status:
            {
                "gemini_pro": bool,
                "gemini_flash": bool,
                "gemini_flash_lite": bool,
                "openrouter": bool,
            }

        Example:
            >>> status = await gateway.health_check()
            >>> if status["gemini_flash"]:
            ...     logger.info("Flash is available")
            >>> else:
            ...     logger.warning("Flash is down, will use fallback")
        """
        status = {
            "gemini_pro": False,
            "gemini_flash": False,
            "gemini_flash_lite": False,
            "openrouter": False,
        }

        if not self._genai_client or not self._available:
            logger.warning("⚠️ LLMGateway Health: GenAI client not available")
        else:
            # Test Gemini Flash (most commonly used)
            try:
                result = await self._genai_client.generate_content(
                    contents="ping",
                    model=self.model_name_flash,
                    max_output_tokens=8192,
                )
                if result and result.get("text"):
                    status["gemini_flash"] = True
                    logger.debug("✅ LLMGateway Health: Gemini Flash is healthy")
            except Exception as e:
                logger.warning(f"⚠️ LLMGateway Health: Gemini Flash check failed: {e}")

            # Test Gemini Pro
            try:
                result_pro = await self._genai_client.generate_content(
                    contents="ping",
                    model=self.model_name_pro,
                    max_output_tokens=8192,
                )
                if result_pro and result_pro.get("text"):
                    status["gemini_pro"] = True
                    logger.debug("✅ LLMGateway Health: Gemini Pro is healthy")
            except Exception as e:
                logger.warning(f"⚠️ LLMGateway Health: Gemini Pro check failed: {e}")

            # Test Gemini Fallback (Stable)
            try:
                result_fallback = await self._genai_client.generate_content(
                    contents="ping",
                    model=self.model_name_fallback,
                    max_output_tokens=8192,
                )
                if result_fallback and result_fallback.get("text"):
                    status["gemini_flash_lite"] = True
                    logger.debug("✅ LLMGateway Health: Gemini Fallback is healthy")
            except Exception as e:
                logger.warning(f"⚠️ LLMGateway Health: Gemini Fallback check failed: {e}")

        # Test OpenRouter (lazy init)
        client = self._get_openrouter_client()
        if client:
            status["openrouter"] = True
            logger.debug("✅ LLMGateway Health: OpenRouter client initialized")

        return status

    async def close(self) -> None:
        """
        Shut down all persistent LLM clients managed by this gateway.
        Should be called during application shutdown via lifespan.
        """
        if self._openrouter_client:
            try:
                await self._openrouter_client.close()
                logger.info("✅ LLMGateway: OpenRouter client closed")
            except Exception as e:
                logger.warning(f"⚠️ LLMGateway: Error closing OpenRouter client: {e}")

        # GenAI client pooling is managed by SDK, but we null it out for safety
        self._genai_client = None
        logger.info("✅ LLMGateway: All clients shut down")
