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
    >>> print(f"Response from {model}: {response}")

Author: Nuzantara Team
Date: 2025-12-17
Version: 1.2.0

UPDATED 2025-12-23:
- Migrated to new google-genai SDK (replaced deprecated google-generativeai)
- Using GenAIClient wrapper for centralized client management
"""

import json
import logging
from typing import Any

import httpx
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from llm.genai_client import GENAI_AVAILABLE, GenAIClient, get_genai_client, types

from app.core.circuit_breaker import CircuitBreaker
from app.core.constants import HttpTimeoutConstants
from app.core.error_classification import ErrorClassifier, get_error_context
from app.metrics import metrics_collector
from app.utils.tracing import set_span_attribute, set_span_status, trace_span
from services.llm_clients.openrouter_client import ModelTier, OpenRouterClient
from services.llm_clients.pricing import TokenUsage, create_token_usage

logger = logging.getLogger(__name__)

# Model Tier Constants
TIER_FLASH = 0  # Fast, cost-effective (default) - gemini-3-flash-preview
TIER_LITE = 1  # Alias for FLASH
TIER_PRO = 2  # Alias for FLASH (no separate pro tier)
TIER_FALLBACK = 3  # Stable fallback - gemini-2.0-flash


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
        model_name_pro (str): Gemini 3 Flash Preview model name (same as flash)
        model_name_flash (str): Gemini 3 Flash Preview model name
        _openrouter_client (OpenRouterClient): Lazy-loaded OpenRouter client

    Note:
        - Uses new google-genai SDK via GenAIClient wrapper
        - OpenRouter client is lazy-loaded to avoid unnecessary initialization
    """

    def __init__(self, gemini_tools: list = None):
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
        self.gemini_tools = gemini_tools or []

        # Initialize GenAI client (new SDK)
        # Uses singleton client that supports both API Key and Service Account (Vertex AI)
        logger.debug("LLMGateway: Initializing GenAI client...")
        self._genai_client: GenAIClient | None = None
        self._available = False

        if GENAI_AVAILABLE:
            try:
                # Use singleton client - it handles both API key and Service Account auth
                self._genai_client = get_genai_client()
                self._available = self._genai_client.is_available
                if self._available:
                    auth_method = getattr(self._genai_client, "_auth_method", "unknown")
                    logger.info(f"✅ LLMGateway: GenAI client initialized (auth: {auth_method})")
                else:
                    logger.warning(
                        "⚠️ LLMGateway: GenAI client not available - will use OpenRouter fallback"
                    )
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client: {e}")

        # Model name constants - Gemini 3 Flash Preview (Primary)
        self.model_name_pro = "gemini-3-flash-preview"  # Same as flash (no separate pro)
        self.model_name_flash = "gemini-3-flash-preview"  # Primary: fast, cost-effective
        self.model_name_fallback = "gemini-2.0-flash"  # Fallback: stable, reliable

        logger.info(
            "✅ LLMGateway: Model configuration ready (3-flash-preview primary, 2.0-flash fallback)"
        )

        # Lazy-loaded OpenRouter client (fallback)
        self._openrouter_client: OpenRouterClient | None = None

        # Circuit breaker configuration using CircuitBreaker class
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = HttpTimeoutConstants.CIRCUIT_BREAKER_TIMEOUT  # seconds
        self._max_fallback_depth = 3
        self._max_fallback_cost_usd = 0.10  # Max $0.10 per query

    def set_gemini_tools(self, tools: list) -> None:
        """Set or update Gemini function declarations for tool calling.

        Allows tools to be set after initialization, useful when tools
        are created after the LLMGateway instance.

        Args:
            tools: List of Gemini function declarations for native tool calling
        """
        self.gemini_tools = tools or []
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
            >>> print(f"[{model}] {response} (cost: ${usage.cost_usd:.6f})")
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
                from app.metrics import llm_all_models_failed_total

                llm_all_models_failed_total.inc()
            except ImportError:
                pass
            raise RuntimeError(f"All LLM models failed: {e}")

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

    def _record_success(self, model_name: str):
        """Record successful call."""
        circuit = self._get_circuit_breaker(model_name)
        circuit.record_success()

    def _record_failure(self, model_name: str, error: Exception):
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
                from app.metrics import llm_circuit_breaker_opened_total

                llm_circuit_breaker_opened_total.labels(
                    model=model_name, error_type=error_type
                ).inc()
            except ImportError:
                pass

    def _get_fallback_chain(self, model_tier: int) -> list[str]:
        """Get fallback chain for given tier."""
        chain = []
        if model_tier == TIER_PRO:
            chain.append(self.model_name_pro)
        if model_tier <= TIER_FLASH:
            chain.append(self.model_name_flash)
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
            - OpenRouter uses regex fallback (no function calling)
            - Vision mode: pass images for multimodal Gemini support

        Example:
            >>> response, model, resp_obj = await self._send_with_fallback(
            ...     chat, "What is KITAS?", system_prompt, TIER_PRO, True, []
            ... )
            >>> # Check for function calls in resp_obj.candidates[0].content.parts
            >>> print(f"Response from {model}: {response}")
        """

        # Helper to build config with optional tools
        def _build_config(with_tools: bool = False) -> Any:
            """Build GenerateContentConfig with optional function calling tools."""
            if not GENAI_AVAILABLE or types is None:
                return None

            config_kwargs = {
                "max_output_tokens": 8192,
                "temperature": 0.4,
            }

            if system_prompt:
                config_kwargs["system_instruction"] = system_prompt

            if with_tools and self.gemini_tools:
                # Convert tool dicts to proper FunctionDeclaration format for new SDK
                function_declarations = []
                for tool_dict in self.gemini_tools:
                    # Create FunctionDeclaration with correct Schema format
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

                # NOTE: Gemini doesn't allow mixing function declarations with Google Search tool
                # Error: "Multiple tools are supported only when they are all search tools"
                # So we use function declarations only, and web search via WebSearchTool (Brave)
                config_kwargs["tools"] = [types.Tool(function_declarations=function_declarations)]

                # CRITICAL: Add tool_config to encourage function calling
                # Mode "AUTO" lets model decide, but with tools registered it will use them
                # FunctionCallingConfig ensures the model knows it should use tools
                try:
                    config_kwargs["tool_config"] = types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(mode="AUTO")
                    )
                    logger.debug(
                        f"🔧 [LLMGateway] Tool config set with {len(function_declarations)} functions"
                    )
                except (AttributeError, TypeError) as e:
                    logger.warning(f"⚠️ [LLMGateway] Could not set tool_config: {e}")

            return types.GenerateContentConfig(**config_kwargs)

        # Helper to build multimodal content with images
        def _build_multimodal_content(text: str, imgs: list[dict] | None) -> Any:
            """Build content with text and optional images for Gemini vision."""
            if not imgs:
                return text  # Plain text, no images

            # Build multimodal content with images
            parts = []

            # Add text part first
            if text:
                parts.append({"text": text})

            # Add image parts
            for img in imgs:
                try:
                    base64_data = img.get("base64", "")
                    # Parse data URI: data:image/jpeg;base64,/9j/4AAQ...
                    if base64_data.startswith("data:"):
                        # Extract mime type and base64 data
                        header, b64_content = base64_data.split(",", 1)
                        # header = "data:image/jpeg;base64"
                        mime_type = header.split(":")[1].split(";")[0]
                    else:
                        # Assume JPEG if no prefix
                        b64_content = base64_data
                        mime_type = "image/jpeg"

                    parts.append(
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_content,
                            }
                        }
                    )
                    logger.debug(
                        f"🖼️ Added image to content: {img.get('name', 'unknown')} ({mime_type})"
                    )
                except Exception as img_err:
                    logger.warning(f"⚠️ Failed to process image: {img_err}")

            if not parts:
                return text  # Fallback to plain text if no parts built

            # Return as content structure for Gemini
            return [{"parts": parts}]

        # Helper to call model
        async def _call_model(
            model_name: str, with_tools: bool = False
        ) -> tuple[str, Any, TokenUsage]:
            """Call a specific model and return (text, response, token_usage)."""
            if not self._genai_client or not self._genai_client.is_available:
                raise RuntimeError("GenAI client not available")

            # Build content (plain text or multimodal with images)
            content = _build_multimodal_content(message, images)
            has_images = images is not None and len(images) > 0

            # 🔍 TRACING: Span for LLM call
            with trace_span(
                "llm.call",
                {
                    "model": model_name,
                    "with_tools": with_tools,
                    "message_length": len(message),
                    "has_images": has_images,
                    "image_count": len(images) if images else 0,
                },
            ):
                config = _build_config(with_tools)

                if has_images:
                    logger.info(f"🖼️ Vision mode: sending {len(images)} images to {model_name}")

                response = await self._genai_client._client.aio.models.generate_content(
                    model=model_name,
                    contents=content,
                    config=config,
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
                    f"= {token_usage.total_tokens} total (${token_usage.cost_usd:.6f})"
                )
                set_span_attribute("prompt_tokens", prompt_tokens)
                set_span_attribute("completion_tokens", completion_tokens)
                set_span_attribute("cost_usd", token_usage.cost_usd)

                # Extract text, handling function call responses
                try:
                    text_content = response.text if hasattr(response, "text") else ""
                    # text_content can be None if Gemini returns a function call
                    if text_content is None:
                        text_content = ""
                        set_span_attribute("has_function_call", "true")
                    else:
                        set_span_attribute("has_function_call", "false")
                    set_span_attribute("response_length", len(text_content))
                except ValueError:
                    # Function call detected - reasoning.py will extract it from response_obj
                    text_content = ""
                    set_span_attribute("has_function_call", "true")
                    set_span_attribute("response_length", 0)

                set_span_status("ok")
                return text_content, response, token_usage

        # Get fallback chain
        models_to_try = self._get_fallback_chain(model_tier)

        for model_name in models_to_try:
            # Check circuit breaker
            if self._is_circuit_open(model_name):
                logger.debug(f"Circuit breaker OPEN for {model_name}, skipping")
                try:
                    from app.metrics import llm_circuit_breaker_open_total

                    llm_circuit_breaker_open_total.labels(model=model_name).inc()
                except ImportError:
                    pass
                continue

            # Check cost limit
            if query_cost_tracker["cost"] >= self._max_fallback_cost_usd:
                logger.warning(
                    f"Cost limit reached ({query_cost_tracker['cost']:.4f} USD), "
                    f"stopping fallback cascade"
                )
                try:
                    from app.metrics import llm_cost_limit_reached_total

                    llm_cost_limit_reached_total.inc()
                except ImportError:
                    pass
                break

            # Check fallback depth
            if query_cost_tracker["depth"] >= self._max_fallback_depth:
                logger.warning(
                    f"Max fallback depth reached ({query_cost_tracker['depth']}), stopping cascade"
                )
                try:
                    from app.metrics import llm_max_depth_reached_total

                    llm_max_depth_reached_total.inc()
                except ImportError:
                    pass
                break

            # Check if model is available
            if not self._available:
                continue

            try:
                # Try model
                text_content, response, token_usage = await _call_model(
                    model_name,
                    with_tools=enable_function_calling,
                )

                # Success - reset circuit breaker
                self._record_success(model_name)
                query_cost_tracker["cost"] += token_usage.cost_usd
                query_cost_tracker["depth"] += 1

                try:
                    from app.metrics import llm_fallback_depth, llm_query_cost_usd

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
                    from app.metrics import llm_quota_exhausted_total

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
                    from app.metrics import llm_service_unavailable_total

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
                    from app.metrics import llm_model_error_total

                    llm_model_error_total.labels(model=model_name, error_type=error_type).inc()
                except ImportError:
                    pass
                metrics_collector.record_llm_fallback(model_name, "next_model")
                continue

        # All models failed
        raise RuntimeError("All models in fallback chain failed")

    async def _call_openrouter(self, messages: list[dict], system_prompt: str) -> str:
        """Call OpenRouter as final fallback when Gemini models are unavailable.

        Uses third-party OpenRouter API for model access. Requires user consent
        in production environments for GDPR/privacy compliance.

        Args:
            messages: Conversation history as list of role/content dicts
            system_prompt: System instructions for model behavior

        Returns:
            Generated response text from OpenRouter model

        Raises:
            RuntimeError: If OpenRouter client is not available

        Note:
            - Logs warning for audit trail (third-party data processing)
            - In production: should check user consent before calling
            - Uses ModelTier.RAG for cost-optimized model selection
        """

        # Log that we're using third-party (for audit)
        logger.warning("🌐 LLMGateway: Using OpenRouter fallback (third-party service)")

        # In production: check user consent for third-party processing
        # if not await self._check_user_consent_for_openrouter(user_id):
        #     raise ModelAuthenticationError("User has not consented to third-party AI processing")

        client = self._get_openrouter_client()
        if not client:
            raise RuntimeError("OpenRouter client not available")

        # Build messages with system prompt
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        logger.debug(f"LLMGateway: OpenRouter full_messages: {json.dumps(full_messages, indent=2)}")

        result = await client.complete(full_messages, tier=ModelTier.RAG)
        logger.info(f"✅ LLMGateway: OpenRouter fallback used: {result.model_name}")
        return result.content

    def create_chat_with_history(
        self, history_to_use: list[dict] | None = None, model_tier: int = TIER_FLASH
    ) -> Any:
        """Create a chat session with conversation history.

        Args:
            history_to_use: Conversation history in format [{"role": "user|assistant", "content": "..."}]
            model_tier: Model tier to use (TIER_PRO, TIER_FLASH, TIER_LITE)

        Returns:
            ChatSession object from genai_client or None

        Note:
            - Converts generic conversation history to Gemini format
            - Returns None if no suitable model is available
            - Uses new google-genai SDK via GenAIClient wrapper
        """
        if not self._genai_client or not self._available:
            logger.warning("⚠️ LLMGateway: GenAI client not available for chat creation")
            return None

        # Select model name based on tier (primary: gemini-3-flash-preview, fallback: gemini-2.0-flash)
        selected_model_name = self.model_name_flash  # Default: gemini-3-flash-preview

        if model_tier == TIER_PRO:
            selected_model_name = self.model_name_pro  # Same as flash (gemini-3-flash-preview)
        # TIER_LITE and TIER_FLASH both use model_name_flash

        # Convert conversation history to Gemini format
        gemini_history = []
        if history_to_use:
            # Defensive: ensure history_to_use is a list
            if not isinstance(history_to_use, list):
                logger.warning(
                    f"⚠️ history_to_use is not a list (type: {type(history_to_use)}), resetting to empty"
                )
                history_to_use = []

            for msg in history_to_use:
                # Defensive: skip if msg is not a dict
                if not isinstance(msg, dict):
                    logger.warning(f"⚠️ Skipping non-dict message in history: {type(msg)}")
                    continue

                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    gemini_history.append({"role": "user", "content": content})
                elif role == "assistant":
                    gemini_history.append({"role": "assistant", "content": content})

        # Create and return chat session using GenAIClient wrapper
        logger.debug(
            f"LLMGateway: Created chat session with {len(gemini_history)} history messages"
        )
        return self._genai_client.create_chat_session(
            model=selected_model_name,
            history=gemini_history,
        )

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
            ...     print("Flash is available")
            >>> else:
            ...     print("Flash is down, will use fallback")
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

            # Test Gemini Flash (2.5)
            try:
                result_flash = await self._genai_client.generate_content(
                    contents="ping",
                    model=self.model_name_flash,
                    max_output_tokens=8192,
                )
                if result_flash and result_flash.get("text"):
                    status["gemini_flash"] = True
                    logger.debug("✅ LLMGateway Health: Gemini Flash is healthy")
            except Exception as e:
                logger.warning(f"⚠️ LLMGateway Health: Gemini Flash check failed: {e}")

        # Test OpenRouter (lazy init)
        client = self._get_openrouter_client()
        if client:
            status["openrouter"] = True
            logger.debug("✅ LLMGateway Health: OpenRouter client initialized")

        return status
