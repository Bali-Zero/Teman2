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

from app.core.config import settings
from app.utils.tracing import trace_span, set_span_attribute, set_span_status, add_span_event
from llm.genai_client import GenAIClient, GENAI_AVAILABLE, types, get_genai_client
from services.llm_clients.openrouter_client import ModelTier, OpenRouterClient

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
        model_name_pro (str): Gemini 2.5 Pro model name
        model_name_flash (str): Gemini 2.5 Flash model name
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
                    auth_method = getattr(self._genai_client, '_auth_method', 'unknown')
                    logger.info(f"✅ LLMGateway: GenAI client initialized (auth: {auth_method})")
                else:
                    logger.warning("⚠️ LLMGateway: GenAI client not available - will use OpenRouter fallback")
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client: {e}")

        # Model name constants - Gemini 3 Flash Preview (Primary)
        self.model_name_pro = "gemini-3-flash-preview"  # Same as flash (no separate pro)
        self.model_name_flash = "gemini-3-flash-preview"  # Primary: fast, cost-effective
        self.model_name_fallback = "gemini-2.0-flash"  # Fallback: stable, reliable

        logger.info("✅ LLMGateway: Model configuration ready (3-flash-preview primary, 2.0-flash fallback)")

        # Lazy-loaded OpenRouter client (fallback)
        self._openrouter_client: OpenRouterClient | None = None

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
    ) -> tuple[str, str, Any]:
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

        Returns:
            Tuple of (response_text, model_name_used, response_object)
            - response_text (str): Generated response content
            - model_name_used (str): Model that generated the response
            - response_object (Any): Full response object (for function call parsing)

        Raises:
            RuntimeError: If all models fail (including OpenRouter)

        Example:
            >>> response, model, obj = await gateway.send_message(
            ...     chat=chat_session,
            ...     message="What is the capital of Indonesia?",
            ...     tier=TIER_FLASH,
            ... )
            >>> print(f"[{model}] {response}")
        """
        return await self._send_with_fallback(
            chat=chat,
            message=message,
            system_prompt=system_prompt,
            model_tier=tier,
            enable_function_calling=enable_function_calling,
            conversation_messages=conversation_messages or [],
        )

    async def _send_with_fallback(
        self,
        chat: Any,
        message: str,
        system_prompt: str,
        model_tier: int,
        enable_function_calling: bool,
        conversation_messages: list[dict],
    ) -> tuple[str, str, Any]:
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
                                    description=v.get("description", "")
                                )
                                for k, v in params.get("properties", {}).items()
                            },
                            required=params.get("required", [])
                        )
                    )
                    function_declarations.append(func_decl)

                config_kwargs["tools"] = [types.Tool(function_declarations=function_declarations)]

            return types.GenerateContentConfig(**config_kwargs)

        # Helper to call model
        async def _call_model(model_name: str, with_tools: bool = False) -> tuple[str, Any]:
            """Call a specific model and return (text, response)."""
            if not self._genai_client or not self._genai_client.is_available:
                raise RuntimeError("GenAI client not available")

            # 🔍 TRACING: Span for LLM call
            with trace_span("llm.call", {
                "model": model_name,
                "with_tools": with_tools,
                "message_length": len(message),
            }):
                config = _build_config(with_tools)

                response = await self._genai_client._client.aio.models.generate_content(
                    model=model_name,
                    contents=message,
                    config=config,
                )

                # Extract text, handling function call responses
                try:
                    text_content = response.text if hasattr(response, "text") else ""
                    set_span_attribute("response_length", len(text_content))
                    set_span_attribute("has_function_call", "false")
                except ValueError:
                    # Function call detected - reasoning.py will extract it from response_obj
                    text_content = ""
                    set_span_attribute("has_function_call", "true")

                set_span_status("ok")
                return text_content, response

        # 1. Try PRO Tier (if requested) - same as flash (gemini-3-flash-preview)
        if model_tier == TIER_PRO and self._available:
            try:
                text_content, response = await _call_model(
                    self.model_name_pro,
                    with_tools=enable_function_calling,
                )
                logger.debug("✅ LLMGateway: Gemini 3 Flash Preview (pro tier) response received")
                return (text_content, "gemini-3-flash-preview", response)

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(
                    f"⚠️ LLMGateway: Gemini 3 Flash quota exceeded, falling back to 2.0: {e}"
                )
                add_span_event("llm.fallback", {"from": "gemini-3-flash-preview", "to": "gemini-2.0-flash", "reason": "quota"})
                model_tier = TIER_FALLBACK
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(
                    f"❌ LLMGateway: Gemini 3 Flash error: {e}. Trying 2.0 fallback.", exc_info=True
                )
                add_span_event("llm.fallback", {"from": "gemini-3-flash-preview", "to": "gemini-2.0-flash", "reason": str(e)[:100]})
                model_tier = TIER_FALLBACK

        # 2. Try Flash (Tier 0) - gemini-3-flash-preview (Standard)
        if model_tier <= TIER_FLASH and self._available:
            try:
                text_content, response = await _call_model(
                    self.model_name_flash,
                    with_tools=enable_function_calling,
                )
                logger.debug("✅ LLMGateway: Gemini 3 Flash Preview response received")
                return (text_content, "gemini-3-flash-preview", response)

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(f"⚠️ LLMGateway: Gemini 3 Flash Preview quota exceeded, trying 2.0 fallback: {e}")
                add_span_event("llm.fallback", {"from": "gemini-3-flash-preview", "to": "gemini-2.0-flash", "reason": "quota"})
                model_tier = TIER_FALLBACK
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(
                    f"❌ LLMGateway: Gemini 3 Flash Preview error: {e}. Trying 2.0 fallback.",
                    exc_info=True,
                )
                add_span_event("llm.fallback", {"from": "gemini-3-flash-preview", "to": "gemini-2.0-flash", "reason": str(e)[:100]})
                model_tier = TIER_FALLBACK

        # 3. Try Gemini 2.0 Flash (Fallback Tier) - gemini-2.0-flash
        if model_tier in (TIER_LITE, TIER_FALLBACK) and self._available:
            try:
                text_content, response = await _call_model(
                    self.model_name_fallback,
                    with_tools=enable_function_calling,
                )
                logger.debug("✅ LLMGateway: Gemini 2.0 Flash (fallback) response received")
                return (text_content, "gemini-2.0-flash", response)

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.error(
                    f"❌ LLMGateway: All Gemini models quota exceeded: {e}"
                )
                raise RuntimeError(f"All Gemini models unavailable: {e}")
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(
                    f"❌ LLMGateway: Gemini 2.0 Flash error: {e}", exc_info=True
                )
                raise RuntimeError(f"Gemini fallback failed: {e}")

        # 4. No models available - raise error
        raise RuntimeError("No Gemini models available - check Service Account configuration")

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
        return self._genai_client.create_chat(
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
