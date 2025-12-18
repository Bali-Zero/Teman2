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
Version: 1.0.0
"""

import json
import logging
from typing import Any

import google.generativeai as genai
import httpx
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from app.core.config import settings
from services.openrouter_client import ModelTier, OpenRouterClient

logger = logging.getLogger(__name__)

# Model Tier Constants
TIER_FLASH = 0  # Fast, cost-effective (default)
TIER_LITE = 1  # Ultra-light, highest throughput
TIER_PRO = 2  # Most capable, highest quality
TIER_OPENROUTER = 3  # Third-party fallback


class LLMGateway:
    """
    Unified gateway for LLM interactions with intelligent fallback routing.

    Responsibilities:
    - Initialize and manage Gemini models (Pro, Flash, Flash-Lite)
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
        model_pro (GenerativeModel): Gemini 2.5 Pro model instance
        model_flash (GenerativeModel): Gemini 2.0 Flash model instance
        model_flash_lite (GenerativeModel): Gemini 2.0 Flash-Lite model instance
        _openrouter_client (OpenRouterClient): Lazy-loaded OpenRouter client

    Note:
        OpenRouter client is lazy-loaded to avoid unnecessary initialization
        when Gemini models are sufficient.
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
            - All Gemini models are initialized immediately
        """
        self.gemini_tools = gemini_tools or []

        # Configure Gemini API
        logger.debug("LLMGateway: Configuring Gemini API...")
        genai.configure(api_key=settings.google_api_key)

        # Initialize Gemini models
        self.model_pro = genai.GenerativeModel("models/gemini-2.5-pro")
        self.model_flash = genai.GenerativeModel("models/gemini-2.0-flash")
        self.model_flash_lite = genai.GenerativeModel("models/gemini-2.0-flash-lite")

        logger.info("✅ LLMGateway: Gemini models initialized (Pro, Flash, Flash-Lite)")

        # Lazy-loaded OpenRouter client (fallback)
        self._openrouter_client: OpenRouterClient | None = None

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
            chat: Active chat session (Gemini chat object or None)
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
            - Automatically creates new chat session if model changes
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

        # 1. Try PRO Tier (if requested)
        if model_tier == TIER_PRO and self.model_pro:
            try:
                # If chat is None or bound to a different model, create new session
                if chat is None or (hasattr(chat, "model") and chat.model != self.model_pro):
                    chat = self.model_pro.start_chat(history=[])

                # Use native function calling if enabled
                if enable_function_calling and self.gemini_tools:
                    response = await chat.send_message_async(message, tools=self.gemini_tools)
                else:
                    response = await chat.send_message_async(message)

                logger.debug("✅ LLMGateway: Gemini Pro response received")
                # Handle function calling - response.text throws error when response contains function_call
                try:
                    text_content = response.text if hasattr(response, "text") else ""
                except ValueError:
                    # Function call detected - reasoning.py will extract it from response_obj
                    text_content = ""
                return (
                    text_content,
                    "gemini-2.5-pro",
                    response,
                )

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(
                    f"⚠️ LLMGateway: Gemini Pro quota exceeded, falling back to Flash: {e}"
                )
                model_tier = TIER_FLASH  # Fallback to Flash
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(
                    f"❌ LLMGateway: Gemini Pro error: {e}. Switching to OpenRouter.", exc_info=True
                )
                # Direct fallback to OpenRouter instead of Flash if Pro fails hard (e.g. Auth error)
                model_tier = TIER_OPENROUTER

        # 2. Try Flash (Tier 0) - Primary or Fallback
        if model_tier <= TIER_FLASH and self.model_flash:
            try:
                if chat is None or (hasattr(chat, "model") and chat.model != self.model_flash):
                    chat = self.model_flash.start_chat(history=[])

                # Use native function calling if enabled
                if enable_function_calling and self.gemini_tools:
                    response = await chat.send_message_async(message, tools=self.gemini_tools)
                else:
                    response = await chat.send_message_async(message)

                logger.debug("✅ LLMGateway: Gemini Flash response received")
                # Handle function calling - response.text throws error when response contains function_call
                try:
                    text_content = response.text if hasattr(response, "text") else ""
                except ValueError:
                    # Function call detected - reasoning.py will extract it from response_obj
                    text_content = ""
                return (
                    text_content,
                    "gemini-2.0-flash",
                    response,
                )

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(f"⚠️ LLMGateway: Gemini Flash quota exceeded, trying Flash-Lite: {e}")
                model_tier = TIER_LITE
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(
                    f"❌ LLMGateway: Gemini Flash error: {e}. Switching to OpenRouter.",
                    exc_info=True,
                )
                model_tier = TIER_OPENROUTER

        # 3. Try Flash-Lite (Tier 1)
        if model_tier == TIER_LITE and self.model_flash_lite:
            try:
                # Always new chat for lite fallback to avoid context issues
                chat_lite = self.model_flash_lite.start_chat(history=[])

                # Use native function calling if enabled
                if enable_function_calling and self.gemini_tools:
                    response = await chat_lite.send_message_async(message, tools=self.gemini_tools)
                else:
                    response = await chat_lite.send_message_async(message)

                logger.debug("✅ LLMGateway: Gemini Flash-Lite response received")
                # Handle function calling - response.text throws error when response contains function_call
                try:
                    text_content = response.text if hasattr(response, "text") else ""
                except ValueError:
                    # Function call detected - reasoning.py will extract it from response_obj
                    text_content = ""
                return (
                    text_content,
                    "gemini-2.0-flash-lite",
                    response,
                )

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(
                    f"⚠️ LLMGateway: Gemini Flash-Lite quota exceeded, switching to OpenRouter: {e}"
                )
                model_tier = TIER_OPENROUTER
            except (ValueError, RuntimeError, AttributeError) as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    logger.warning(
                        f"⚠️ LLMGateway: Gemini Flash-Lite rate limited, switching to OpenRouter: {e}"
                    )
                    model_tier = TIER_OPENROUTER
                else:
                    logger.error(
                        f"❌ LLMGateway: Gemini Flash-Lite unexpected error: {e}", exc_info=True
                    )
                    raise

        # 4. Use OpenRouter fallback (Tier 3)
        logger.info("🌐 LLMGateway: Using OpenRouter (final fallback - no native function calling)")

        # Prepare messages for OpenRouter.
        # `_call_openrouter` will add the system_prompt automatically.
        # We need to extract just the user's current turn content.

        user_turn_content = message
        user_query_marker = "User Query:"

        # Check if the message contains the initial prompt structure for a user query
        if user_query_marker in message:
            start_index = message.find(user_query_marker)
            if start_index != -1:
                user_turn_content = message[start_index + len(user_query_marker) :].strip()

                # Remove any trailing "IMPORTANT: Do NOT start with philosophical statements..."
                important_instruction_marker = (
                    "IMPORTANT: Do NOT start with philosophical statements"
                )
                important_instruction_start = user_turn_content.find(important_instruction_marker)
                if important_instruction_start != -1:
                    user_turn_content = user_turn_content[:important_instruction_start].strip()

        # If after stripping, the content is too short or empty, revert to the original message
        if not user_turn_content or len(user_turn_content) < 10:
            user_turn_content = message

        messages_for_openrouter = [{"role": "user", "content": user_turn_content}]
        result_text = await self._call_openrouter(messages_for_openrouter, system_prompt)

        # Return None for response object since OpenRouter doesn't support function calling
        return (result_text, "openrouter-fallback", None)

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
        """Create a Gemini chat session with conversation history.

        Args:
            history_to_use: Conversation history in format [{"role": "user|assistant", "content": "..."}]
            model_tier: Model tier to use (TIER_PRO, TIER_FLASH, TIER_LITE)

        Returns:
            Gemini chat session object or None

        Note:
            - Converts generic conversation history to Gemini format
            - Returns None if no suitable model is available
        """
        # Select model based on tier
        selected_model = self.model_flash  # Default

        if model_tier == TIER_PRO and self.model_pro:
            selected_model = self.model_pro
        elif model_tier == TIER_LITE and self.model_flash_lite:
            selected_model = self.model_flash_lite

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
                    gemini_history.append({"role": "user", "parts": [content]})
                elif role == "assistant":
                    gemini_history.append({"role": "model", "parts": [content]})

        # Create and return chat session
        if selected_model:
            logger.debug(
                f"LLMGateway: Created chat session with {len(gemini_history)} history messages"
            )
            return selected_model.start_chat(history=gemini_history)
        return None

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

        # Test Gemini Flash (most commonly used)
        try:
            test_chat = self.model_flash.start_chat()
            test_response = await test_chat.send_message_async("ping")
            if test_response and hasattr(test_response, "text"):
                status["gemini_flash"] = True
                logger.debug("✅ LLMGateway Health: Gemini Flash is healthy")
        except Exception as e:
            logger.warning(f"⚠️ LLMGateway Health: Gemini Flash check failed: {e}")

        # Test Gemini Pro
        try:
            test_chat_pro = self.model_pro.start_chat()
            test_response_pro = await test_chat_pro.send_message_async("ping")
            if test_response_pro and hasattr(test_response_pro, "text"):
                status["gemini_pro"] = True
                logger.debug("✅ LLMGateway Health: Gemini Pro is healthy")
        except Exception as e:
            logger.warning(f"⚠️ LLMGateway Health: Gemini Pro check failed: {e}")

        # Test Gemini Flash-Lite
        try:
            test_chat_lite = self.model_flash_lite.start_chat()
            test_response_lite = await test_chat_lite.send_message_async("ping")
            if test_response_lite and hasattr(test_response_lite, "text"):
                status["gemini_flash_lite"] = True
                logger.debug("✅ LLMGateway Health: Gemini Flash-Lite is healthy")
        except Exception as e:
            logger.warning(f"⚠️ LLMGateway Health: Gemini Flash-Lite check failed: {e}")

        # Test OpenRouter (lazy init)
        client = self._get_openrouter_client()
        if client:
            status["openrouter"] = True
            logger.debug("✅ LLMGateway Health: OpenRouter client initialized")

        return status
