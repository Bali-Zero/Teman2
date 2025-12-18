"""
ZANTARA AI Client - Primary engine for all conversational AI

AI Models Architecture:
- PRIMARY: Google Gemini 2.5 Pro (production)

Configuration:
- GOOGLE_API_KEY: API key for Gemini (primary)

UPDATED 2025-12-07:
- Refactored for better separation of concerns
- Added PromptManager, RetryHandler, TokenEstimator
- Improved error handling and performance
- Added input validation and connection pooling
"""

import asyncio
import logging
from typing import Any

# Import helper modules
from llm.fallback_messages import get_fallback_message
from llm.prompt_manager import PromptManager
from llm.retry_handler import RetryHandler
from llm.token_estimator import TokenEstimator

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import google.generativeai at module level
try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    logger.warning("⚠️ google.generativeai not available")


# Constants
class ZantaraAIClientConstants:
    """Constants for ZantaraAIClient configuration."""

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2.0
    RETRY_BACKOFF_FACTOR = 2
    MOCK_STREAM_DELAY = 0.05
    FALLBACK_STREAM_DELAY = 0.1
    DEFAULT_MAX_TOKENS = 2000  # Increased for comprehensive responses
    DEFAULT_TEMPERATURE = 0.4  # Lower for more factual, consistent responses
    DEFAULT_STREAM_MAX_TOKENS = (
        2000  # Aligned with DEFAULT_MAX_TOKENS - streaming needs same capacity
    )
    MAX_TEMPERATURE = 2.0
    MIN_TEMPERATURE = 0.0
    MAX_MAX_TOKENS = 8192
    MIN_MAX_TOKENS = 1


class ZantaraAIClient:
    """
    ZANTARA AI Client – primary engine for all conversational AI.

    AI Models:
    - PRIMARY: Google Gemini 2.5 Flash (production) - unlimited quota, fast, cost-effective

    Provider: Google AI (Gemini) - native implementation

    This client handles:
    - Chat completion (async)
    - Streaming responses
    - Tool calling (when needed)
    - Error handling with retry logic
    - Token estimation for cost tracking
    """

    # Class-level model cache for connection pooling
    _model_cache: dict[str, Any] = {}

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize ZantaraAIClient.

        Args:
            api_key: Google API key (defaults to settings.google_api_key)
            model: Model name (defaults to gemini-2.5-flash)

        Raises:
            ValueError: If API key is missing in production environment
        """
        self.api_key = api_key or settings.google_api_key
        self.mock_mode = False

        # Initialize Gemini client
        if self.api_key and GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                logger.info("✅ Gemini AI Client initialized in production mode")
            except Exception as e:
                logger.error(f"❌ Failed to configure Gemini: {e}")
                if settings.environment == "production":
                    raise ValueError(f"CRITICAL: Failed to configure Gemini in production: {e}")
                self.mock_mode = True
        else:
            if settings.environment == "production":
                logger.critical("❌ CRITICAL: No Gemini API key found in PRODUCTION environment")
                raise ValueError("GOOGLE_API_KEY is required in production environment")

            logger.warning("⚠️ No Gemini API key found - defaulting to MOCK MODE (Development only)")
            self.mock_mode = True

        # Default: use Gemini 2.5 Flash (unlimited quota, fast, cost-effective)
        # Changed from gemini-2.5-pro to gemini-2.5-flash for better quota availability
        self.model = model or "gemini-2.5-flash"

        # Initialize pricing even in mock mode
        self.pricing = {
            "input": getattr(settings, "zantara_ai_cost_input", 0.15),
            "output": getattr(settings, "zantara_ai_cost_output", 0.60),
        }

        # Initialize helper services
        self.prompt_manager = PromptManager()
        self.retry_handler = RetryHandler(
            max_retries=ZantaraAIClientConstants.MAX_RETRIES,
            base_delay=ZantaraAIClientConstants.BASE_RETRY_DELAY,
            backoff_factor=ZantaraAIClientConstants.RETRY_BACKOFF_FACTOR,
        )
        self.token_estimator = TokenEstimator(model=self.model)

        # Log configuration (without sensitive info)
        logger.debug("🔧 ZantaraAIClient Configuration:")
        logger.debug(f"   Model: {self.model}")
        logger.debug(f"   Mock Mode: {self.mock_mode}")
        logger.debug(
            f"   System Prompt: {len(self.prompt_manager._base_system_prompt)} chars loaded"
        )

        logger.info("✅ ZantaraAIClient initialized")
        logger.info(f"   Engine model: {self.model}")
        logger.info(f"   Mode: {'Mock' if self.mock_mode else 'Native Gemini'}")

    def _get_cached_model(self, model_name: str, system_instruction: str) -> Any:
        """
        Get or create cached GenerativeModel instance.

        Implements connection pooling by caching model instances.

        Args:
            model_name: Name of the model
            system_instruction: System instruction for the model

        Returns:
            Cached or new GenerativeModel instance
        """
        if not GENAI_AVAILABLE:
            return None

        # Create cache key from model name and system instruction hash
        cache_key = f"{model_name}:{hash(system_instruction)}"

        if cache_key not in self._model_cache:
            self._model_cache[cache_key] = genai.GenerativeModel(
                model_name, system_instruction=system_instruction
            )
            # Sanitize cache_key for logging (show only first 8 chars to avoid exposing sensitive data)
            sanitized_key = f"{cache_key[:8]}..." if len(cache_key) > 8 else cache_key[:8]
            logger.debug(f"✅ Created new cached model: {sanitized_key}")

        return self._model_cache[cache_key]

    def get_model_info(self) -> dict[str, Any]:
        """
        Get current model information.

        Returns:
            Dictionary with model, provider, and pricing info
        """
        return {
            "model": self.model,
            "provider": "mock" if self.mock_mode else "google_native",
            "pricing": self.pricing,
        }

    def _build_system_prompt(
        self,
        memory_context: str | None = None,
        identity_context: str | None = None,
        use_rich_prompt: bool = True,
    ) -> str:
        """
        Build ZANTARA system prompt with context injection.

        Delegates to PromptManager for actual building.

        Args:
            memory_context: Optional memory/RAG context to inject
            identity_context: Optional user identity context
            use_rich_prompt: Use rich prompt from file (default: True)

        Returns:
            System prompt string with all context properly structured
        """
        return self.prompt_manager.build_system_prompt(
            memory_context=memory_context,
            identity_context=identity_context,
            use_rich_prompt=use_rich_prompt,
        )

    def _validate_inputs(
        self,
        max_tokens: int | None = None,
        temperature: float | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> None:
        """
        Validate input parameters.

        Args:
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            messages: List of messages

        Raises:
            ValueError: If validation fails
        """
        if max_tokens is not None:
            if max_tokens < ZantaraAIClientConstants.MIN_MAX_TOKENS:
                raise ValueError(f"max_tokens must be >= {ZantaraAIClientConstants.MIN_MAX_TOKENS}")
            if max_tokens > ZantaraAIClientConstants.MAX_MAX_TOKENS:
                raise ValueError(f"max_tokens must be <= {ZantaraAIClientConstants.MAX_MAX_TOKENS}")

        if temperature is not None:
            if temperature < ZantaraAIClientConstants.MIN_TEMPERATURE:
                raise ValueError(
                    f"temperature must be >= {ZantaraAIClientConstants.MIN_TEMPERATURE}"
                )
            if temperature > ZantaraAIClientConstants.MAX_TEMPERATURE:
                raise ValueError(
                    f"temperature must be <= {ZantaraAIClientConstants.MAX_TEMPERATURE}"
                )

        if messages is not None:
            if not isinstance(messages, list):
                raise ValueError("messages must be a list")
            if len(messages) == 0:
                raise ValueError("messages must contain at least one message")
            for msg in messages:
                if not isinstance(msg, dict):
                    raise ValueError("Each message must be a dictionary")
                if "role" not in msg or "content" not in msg:
                    raise ValueError("Each message must have 'role' and 'content' keys")

    def _prepare_gemini_messages(self, messages: list[dict[str, str]]) -> tuple[list[dict], str]:
        """
        Prepare messages for Gemini API format.

        Args:
            messages: List of messages in standard format

        Returns:
            Tuple of (gemini_history, last_user_message)
        """
        gemini_history = []
        last_user_message = ""

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                continue

            if role == "user":
                last_user_message = content
                gemini_history.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_history.append({"role": "model", "parts": [content]})

        # Remove the last user message from history as it's the prompt
        if gemini_history and gemini_history[-1]["role"] == "user":
            gemini_history.pop()

        return gemini_history, last_user_message

    def _extract_response_text(self, response: Any) -> str:
        """
        Extract text from Gemini response, handling safety blocks.

        Args:
            response: Gemini API response object

        Returns:
            Extracted text content

        Raises:
            ValueError: If response is blocked by safety filters and no content available
        """
        if not hasattr(response, "candidates") or not response.candidates:
            return response.text if hasattr(response, "text") else ""

        candidate = response.candidates[0]

        # Check if blocked by safety filters
        if hasattr(candidate, "safety_ratings"):
            blocked = any(
                rating.probability.name in ["HIGH", "MEDIUM"] for rating in candidate.safety_ratings
            )
            if blocked:
                # Try to extract content anyway from parts
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    if candidate.content.parts:
                        return candidate.content.parts[0].text
                    else:
                        raise ValueError(
                            "Response blocked by safety filters and no content available"
                        )
                else:
                    raise ValueError("Response blocked by safety filters")

        return response.text

    def _estimate_tokens(
        self, messages: list[dict[str, str]], response_text: str
    ) -> dict[str, int]:
        """
        Estimate token counts for input and output.

        Args:
            messages: Input messages
            response_text: Output text

        Returns:
            Dictionary with 'input' and 'output' token counts
        """
        tokens_input = self.token_estimator.estimate_messages_tokens(messages)
        tokens_output = self.token_estimator.estimate_tokens(response_text)
        return {"input": tokens_input, "output": tokens_output}

    async def chat_async(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = ZantaraAIClientConstants.DEFAULT_MAX_TOKENS,
        temperature: float = ZantaraAIClientConstants.DEFAULT_TEMPERATURE,
        system: str | None = None,
        memory_context: str | None = None,
        identity_context: str | None = None,
        safety_settings: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Generate chat response using ZANTARA AI.

        Args:
            messages: Chat messages [{"role": "user", "content": "..."}]
            max_tokens: Max tokens to generate (default: 1500)
            temperature: Sampling temperature (default: 0.7)
            system: Optional system prompt override
            memory_context: Optional memory context to inject
            identity_context: Optional user identity context
            safety_settings: Optional safety settings for Gemini

        Returns:
            Dictionary with 'text', 'model', 'provider', 'tokens', 'cost'

        Raises:
            ValueError: If input validation fails
            Exception: If API call fails
        """
        # Validate inputs
        self._validate_inputs(max_tokens=max_tokens, temperature=temperature, messages=messages)

        # Build system prompt with all contexts
        if system is None:
            system = self._build_system_prompt(
                memory_context=memory_context,
                identity_context=identity_context,
            )

        # Debug logging
        logger.debug("=" * 80)
        logger.debug("🔍 [DRY RUN] Full Prompt Assembly for chat_async")
        logger.debug("=" * 80)
        logger.debug(f"System Prompt ({len(system)} chars):\n{system}")
        logger.debug(f"Messages ({len(messages)} messages):")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content_preview = msg.get("content", "")[:200] + (
                "..." if len(msg.get("content", "")) > 200 else ""
            )
            logger.debug(f"  [{i}] {role}: {content_preview}")
        logger.debug("=" * 80)

        # Handle Mock Mode
        if self.mock_mode:
            answer = "This is a MOCK response from ZantaraAIClient (Mock Mode)."
            return {
                "text": answer,
                "model": self.model,
                "provider": "mock",
                "tokens": {"input": 10, "output": 10},
                "cost": 0.0,
            }

        if not GENAI_AVAILABLE:
            logger.error("❌ Gemini client library not available")
            raise ValueError("Gemini client library is not available")

        try:
            client_with_sys = self._get_cached_model(self.model, system)
            gemini_history, last_user_message = self._prepare_gemini_messages(messages)
            chat = client_with_sys.start_chat(history=gemini_history)
            response = await chat.send_message_async(
                last_user_message,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens, temperature=temperature
                ),
                safety_settings=safety_settings,
            )
            answer = self._extract_response_text(response)
            tokens = self._estimate_tokens(messages, answer)
            return {
                "text": answer,
                "model": self.model,
                "provider": "google_native",
                "tokens": tokens,
                "cost": 0.0,
            }

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"❌ Native Gemini Connection Error: {e}")
            raise
        except Exception as e:
            error_msg = str(e).lower()
            # Check for API key leaked error (403)
            if "403" in error_msg or "leaked" in error_msg or "api key" in error_msg:
                logger.critical(
                    "🚨 CRITICAL: API key leaked or invalid (403). "
                    "Please replace GOOGLE_API_KEY in environment variables."
                )
                # Raise a specific exception that can be caught and handled gracefully
                raise ValueError(
                    "API key was reported as leaked. Please use another API key. "
                    "Contact the technical team to update GOOGLE_API_KEY."
                ) from e
            logger.error(f"❌ Native Gemini Error: {e}", exc_info=True)
            raise

    async def stream(
        self,
        message: str,
        user_id: str,
        conversation_history: list[dict[str, str]] | None = None,
        memory_context: str | None = None,
        identity_context: str | None = None,
        max_tokens: int = ZantaraAIClientConstants.DEFAULT_STREAM_MAX_TOKENS,
        language: str = "en",
    ):
        """
        Stream chat response token by token for SSE.

        Args:
            message: User message
            user_id: User identifier
            conversation_history: Optional chat history
            memory_context: Optional memory context
            identity_context: Optional user identity context
            max_tokens: Max tokens (default: 150)
            language: Language for fallback messages (default: 'en')

        Yields:
            str: Text chunks as they arrive from AI
        """
        logger.info(f"🌊 [ZantaraAI] Starting stream for user {user_id}")

        # Validate inputs
        self._validate_inputs(
            max_tokens=max_tokens, messages=[{"role": "user", "content": message}]
        )

        # Build system prompt
        system = self._build_system_prompt(
            memory_context=memory_context,
            identity_context=identity_context,
        )

        # Debug logging
        logger.debug("=" * 80)
        logger.debug("🔍 [DRY RUN] Full Prompt Assembly for stream")
        logger.debug("=" * 80)
        logger.debug(f"System Prompt ({len(system)} chars):\n{system}")
        logger.debug(f"User Message: {message}")
        if conversation_history:
            logger.debug(f"Conversation History ({len(conversation_history)} messages):")
            for i, msg in enumerate(conversation_history):
                role = msg.get("role", "unknown")
                content_preview = msg.get("content", "")[:200] + (
                    "..." if len(msg.get("content", "")) > 200 else ""
                )
                logger.debug(f"  [{i}] {role}: {content_preview}")
        else:
            logger.debug("Conversation History: None")
        logger.debug("=" * 80)

        # Mock Mode
        if self.mock_mode:
            logger.info(f"🎭 [ZantaraAI] MOCK MODE streaming for user {user_id}")
            response = f"This is a MOCK stream response to: {message}. In production mode, this would be connected to Gemini AI."
            words = response.split()
            for word in words:
                yield word + " "
                await asyncio.sleep(ZantaraAIClientConstants.MOCK_STREAM_DELAY)
            return

        if not GENAI_AVAILABLE:
            logger.error("❌ Native Gemini not available for streaming")
            fallback_response = get_fallback_message("service_unavailable", language)
            words = fallback_response.split()
            for word in words:
                yield word + " "
                await asyncio.sleep(ZantaraAIClientConstants.FALLBACK_STREAM_DELAY)
            return

        async def _stream_operation():
            """Inner function for retry handler."""
            client_with_sys = self._get_cached_model(self.model, system)

            gemini_history = []
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    if role == "user":
                        gemini_history.append({"role": "user", "parts": [content]})
                    elif role == "assistant":
                        gemini_history.append({"role": "model", "parts": [content]})

            chat = client_with_sys.start_chat(history=gemini_history)

            response = await chat.send_message_async(
                message,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=ZantaraAIClientConstants.DEFAULT_TEMPERATURE,
                ),
                stream=True,
            )

            stream_active = False
            async for chunk in response:
                stream_active = True
                if chunk.text:
                    yield chunk.text

            if not stream_active:
                logger.warning("⚠️ [ZantaraAI] No content received in stream")
                raise ValueError("No content received from stream")

        try:
            async for chunk in self.retry_handler.execute_with_retry(
                _stream_operation,
                operation_name=f"Stream for user {user_id}",
            ):
                yield chunk
            logger.info(f"✅ [ZantaraAI] Stream completed successfully for user {user_id}")
            return
        except ValueError as e:
            # Handle API key leaked error specifically
            error_msg = str(e).lower()
            if "leaked" in error_msg or "api key" in error_msg:
                logger.critical(f"🚨 [ZantaraAI] API key error for user {user_id}: {e}")
                fallback_response = get_fallback_message("api_key_error", language)
                words = fallback_response.split()
                for word in words:
                    yield word + " "
                    await asyncio.sleep(ZantaraAIClientConstants.FALLBACK_STREAM_DELAY)
                return
            # Re-raise other ValueError exceptions
            raise
        except Exception as e:
            logger.error(f"❌ [ZantaraAI] All streaming attempts failed for user {user_id}: {e}")
            error_msg = str(e).lower()
            # Check for API key errors in exception message
            if "403" in error_msg or "leaked" in error_msg or "api key" in error_msg:
                fallback_response = get_fallback_message("api_key_error", language)
            else:
                fallback_response = get_fallback_message("connection_error", language)
            words = fallback_response.split()
            for word in words:
                yield word + " "
                await asyncio.sleep(ZantaraAIClientConstants.FALLBACK_STREAM_DELAY)
            return

        # Should never reach here, but keep fallback guard
        logger.error("❌ Native Gemini encountered unexpected error during streaming")
        fallback_response = get_fallback_message("service_unavailable", language)
        words = fallback_response.split()
        for word in words:
            yield word + " "
            await asyncio.sleep(ZantaraAIClientConstants.FALLBACK_STREAM_DELAY)

    async def conversational(
        self,
        message: str,
        user_id: str,
        conversation_history: list[dict[str, str]] | None = None,
        memory_context: str | None = None,
        identity_context: str | None = None,
        max_tokens: int = ZantaraAIClientConstants.DEFAULT_STREAM_MAX_TOKENS,
    ) -> dict[str, Any]:
        """
        Compatible interface for IntelligentRouter - simple conversational response.

        Args:
            message: User message
            user_id: User identifier (unused, kept for compatibility)
            conversation_history: Optional chat history
            memory_context: Optional memory context
            identity_context: Optional user identity context
            max_tokens: Max tokens (default: 150)

        Returns:
            Dictionary with 'text', 'model', 'provider', 'ai_used', 'tokens'
        """
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        result = await self.chat_async(
            messages=messages,
            max_tokens=max_tokens,
            memory_context=memory_context,
            identity_context=identity_context,
        )

        return {
            "text": result["text"],
            "model": result["model"],
            "provider": result["provider"],
            "ai_used": "zantara-ai",
            "tokens": result["tokens"],
        }

    async def conversational_with_tools(
        self,
        message: str,
        user_id: str,
        conversation_history: list[dict[str, str]] | None = None,
        memory_context: str | None = None,
        identity_context: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        _tool_executor: Any | None = None,
        max_tokens: int = ZantaraAIClientConstants.DEFAULT_STREAM_MAX_TOKENS,
        _max_tool_iterations: int = 2,
    ) -> dict[str, Any]:
        """
        Compatible interface for IntelligentRouter - conversational WITH tool calling.

        Note: Tool calling is not fully implemented for Gemini native mode.
        Falls back to standard conversational if tools are provided.

        Args:
            message: User message
            user_id: User identifier
            conversation_history: Optional chat history
            memory_context: Optional memory context
            identity_context: Optional user identity context
            tools: Optional list of tool definitions (not used in Gemini native)
            _tool_executor: Tool executor (unused, kept for compatibility)
            max_tokens: Max tokens (default: 150)
            _max_tool_iterations: Max tool iterations (unused)

        Returns:
            Dictionary with 'text', 'model', 'provider', 'ai_used', 'tokens', 'tools_called', 'used_tools'
        """
        # Gemini native doesn't support tool calling in the same way as OpenAI
        # So we just use standard conversational
        if tools:
            logger.info(
                "🔧 [ZantaraAI] Tool use requested but not supported in Gemini native mode, using standard conversational"
            )

        result = await self.conversational(
            message=message,
            user_id=user_id,
            conversation_history=conversation_history,
            memory_context=memory_context,
            identity_context=identity_context,
            max_tokens=max_tokens,
        )
        result["tools_called"] = []
        result["used_tools"] = False
        return result

    def is_available(self) -> bool:
        """
        Check if ZANTARA AI is configured and available.

        Returns:
            True if API key is set and client is available
        """
        if self.mock_mode:
            return True
        return bool(self.api_key and GENAI_AVAILABLE)
