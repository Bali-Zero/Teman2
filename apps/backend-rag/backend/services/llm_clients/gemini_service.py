"""
Gemini Jaksel Service with OpenRouter Fallback

Primary: Google Gemini API (gemini-3-flash-preview)
Fallback: OpenRouter free models when quota exceeded (429)

UPDATED 2025-12-23:
- Migrated to new google-genai SDK (replaced deprecated google-generativeai)
"""

import logging
from collections.abc import AsyncGenerator

from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from prompts.jaksel_persona import FEW_SHOT_EXAMPLES, SYSTEM_INSTRUCTION

from app.core.config import settings
from llm.genai_client import GenAIClient, GENAI_AVAILABLE, get_genai_client

logger = logging.getLogger(__name__)


class GeminiJakselService:
    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        """
        Initialize Gemini Service with Jaksel Persona and OpenRouter fallback.

        Args:
            model_name: "gemini-3-flash-preview" (Fast/Medium thinking) or "gemini-3-pro-preview" (High thinking)

        Note:
            - Free tier: 2.0 Flash (high quota), 2.5 Pro (lower quota)
            - Ultra plan: Both unlimited for normal use
            - Automatic fallback to OpenRouter free models on 429
        """
        # Store model name (new SDK doesn't need 'models/' prefix)
        self.model_name = model_name.replace("models/", "")
        self.system_instruction = SYSTEM_INSTRUCTION

        # Initialize GenAI client using singleton (supports API Key & Service Account)
        self._genai_client = None
        self._available = False
        if GENAI_AVAILABLE:
            try:
                self._genai_client = get_genai_client()
                self._available = self._genai_client.is_available
                if self._available:
                    auth_method = getattr(self._genai_client, '_auth_method', 'unknown')
                    logger.info(f"✅ Gemini Jaksel Service initialized (model: {self.model_name}, auth: {auth_method})")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

        # Pre-compute history from examples for "Few-Shot" prompting
        self.few_shot_history = []
        for ex in FEW_SHOT_EXAMPLES:
            self.few_shot_history.append({
                "role": ex["role"],
                "content": ex["content"],
            })

        # OpenRouter client for fallback (lazy loaded)
        self._openrouter_client = None

    def _get_openrouter_client(self):
        """Lazy load OpenRouter client"""
        if self._openrouter_client is None:
            try:
                from .openrouter_client import ModelTier, OpenRouterClient

                self._openrouter_client = OpenRouterClient(default_tier=ModelTier.RAG)
            except ImportError as e:
                logger.error(f"Failed to import OpenRouter client: {e}")
        return self._openrouter_client

    def _convert_to_openai_messages(
        self, message: str, history: list[dict] | None, context: str
    ) -> list[dict]:
        """Convert Gemini-style inputs to OpenAI message format for OpenRouter"""
        messages = []

        # Add system instruction
        messages.append({"role": "system", "content": self.system_instruction})

        # Add few-shot examples
        for ex in FEW_SHOT_EXAMPLES:
            role = "user" if ex["role"] == "user" else "assistant"
            messages.append({"role": role, "content": ex["content"]})

        # Add conversation history
        if history:
            for msg in history:
                role = "user" if msg.get("role") == "user" else "assistant"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        # Build final message with context
        if context and context.strip():
            final_message = f"CONTEXT (Use this data):\n{context}\n\nUSER QUERY:\n{message}"
        else:
            final_message = message

        messages.append({"role": "user", "content": final_message})

        return messages

    async def _fallback_to_openrouter(
        self, message: str, history: list[dict] | None, context: str
    ) -> str:
        """Fallback to OpenRouter when Gemini fails"""
        client = self._get_openrouter_client()
        if not client:
            raise RuntimeError("OpenRouter fallback not available")

        messages = self._convert_to_openai_messages(message, history, context)

        try:
            from .openrouter_client import ModelTier

            result = await client.complete(messages, tier=ModelTier.RAG)
            logger.info(f"OpenRouter fallback used: {result.model_name}")
            return result.content
        except Exception as e:
            logger.error(f"OpenRouter fallback failed: {e}")
            raise

    async def _fallback_to_openrouter_stream(
        self, message: str, history: list[dict] | None, context: str
    ) -> AsyncGenerator[str, None]:
        """Streaming fallback to OpenRouter"""
        client = self._get_openrouter_client()
        if not client:
            raise RuntimeError("OpenRouter fallback not available")

        messages = self._convert_to_openai_messages(message, history, context)

        try:
            from .openrouter_client import ModelTier

            logger.info("Using OpenRouter streaming fallback")
            async for chunk in client.complete_stream(messages, tier=ModelTier.RAG):
                yield chunk
        except Exception as e:
            logger.error(f"OpenRouter streaming fallback failed: {e}")
            raise

    async def generate_response_stream(
        self, message: str, history: list[dict] | None = None, context: str = ""
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response in Jaksel style with automatic fallback.

        Args:
            message: Current user message
            history: Conversation history (excluding few-shot)
            context: RAG context / documents to ground the answer

        Yields:
            Chunks of text
        """
        # Initialize history if None
        if history is None:
            history = []

        # Try Gemini first (if available)
        if self._available and self._genai_client:
            try:
                # Combine few-shot history with actual conversation history
                chat_history = self.few_shot_history.copy()

                # Convert app history format
                for msg in history:
                    content = msg.get("content", "")
                    if content:
                        chat_history.append({
                            "role": msg.get("role", "user"),
                            "content": content,
                        })

                # Build final message
                if context and context.strip():
                    final_message = f"CONTEXT (Use this data):\n{context}\n\nUSER QUERY:\n{message}"
                else:
                    final_message = message

                # Create chat session with new SDK wrapper
                chat = self._genai_client.create_chat(
                    model=self.model_name,
                    system_instruction=self.system_instruction,
                    history=chat_history,
                )

                # Stream response
                async for chunk in chat.send_message_stream(final_message):
                    yield chunk

                return  # Success, exit generator

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(f"Gemini quota exceeded, falling back to OpenRouter: {e}")
                # Fall through to OpenRouter fallback

            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    logger.warning(f"Gemini rate limited, falling back to OpenRouter: {e}")
                    # Fall through to OpenRouter fallback
                else:
                    logger.error(f"Unexpected Gemini error: {e}")
                    raise

        # Fallback to OpenRouter
        logger.info("Using OpenRouter fallback for streaming")
        async for chunk in self._fallback_to_openrouter_stream(message, history, context):
            yield chunk

    async def generate_response(
        self, message: str, history: list[dict] | None = None, context: str = ""
    ) -> str:
        """
        Generate full response (non-streaming) with automatic fallback.
        """
        # Initialize history if None
        if history is None:
            history = []

        # Try Gemini first (if available)
        if self._available and self._genai_client:
            try:
                # Use streaming internally to collect full response
                full_response = ""
                async for chunk in self.generate_response_stream(message, history, context):
                    full_response += chunk
                return full_response

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(f"Gemini quota exceeded: {e}")
                # Fall through to OpenRouter

            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str:
                    logger.warning(f"Gemini rate limited: {e}")
                else:
                    raise

        # Fallback to OpenRouter
        return await self._fallback_to_openrouter(message, history, context)


# Singleton instance
gemini_jaksel = GeminiJakselService()


# Alias for compatibility with tests
class GeminiService:
    """
    Wrapper class for GeminiJakselService to maintain compatibility with tests.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize GeminiService.

        Args:
            api_key: Google API key (optional, uses settings if not provided)
        """
        # API key is passed to the service constructor now
        self._service = GeminiJakselService()

    async def generate_response(
        self, prompt: str, context: list[str] | None = None, **kwargs
    ) -> str:
        """
        Generate response from Gemini.

        Args:
            prompt: User prompt
            context: Optional context list (converted to string)
            **kwargs: Additional arguments

        Returns:
            Generated response text
        """
        context_str = "\n".join(context) if context else ""
        return await self._service.generate_response(prompt, context=context_str)

    async def stream_response(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        Stream response from Gemini.

        Args:
            prompt: User prompt
            **kwargs: Additional arguments

        Yields:
            Response chunks
        """
        async for chunk in self._service.generate_response_stream(prompt):
            yield chunk


if __name__ == "__main__":
    import asyncio

    async def test():
        logger.info("🚀 Testing Gemini Jaksel Service with OpenRouter Fallback...")
        logger.info(f"   Gemini API Key: {'✅ Set' if settings.google_api_key else '❌ Not set'}")
        logger.info(
            f"   OpenRouter API Key: {'✅ Set' if settings.openrouter_api_key else '❌ Not set'}"
        )

        # Test Query
        query = "Bro, gue mau bikin PT PMA tapi modal gue pas-pasan. Ada solusi gak?"
        logger.info(f"\nUser: {query}")
        logger.info("Assistant: ", end="", flush=True)

        try:
            async for chunk in gemini_jaksel.generate_response_stream(query):
                logger.info(chunk, end="", flush=True)
            logger.info("\n")
        except Exception as e:
            logger.error(f"\n❌ Error: {e}")

    asyncio.run(test())
