"""
Google GenAI Client Wrapper

Unified client for Google's new GenAI SDK (google-genai).
Replaces the deprecated google-generativeai package.

This module provides:
- Centralized client management with connection pooling
- Async support via client.aio
- Streaming support
- Chat session management
- Backward-compatible interface for migration

Usage:
    from llm.genai_client import get_genai_client, GenAIClient

    client = get_genai_client()
    response = await client.generate_content("Hello!")

    # Or streaming:
    async for chunk in client.generate_content_stream("Hello!"):
        print(chunk, end="")

Author: Nuzantara Team
Date: 2025-12-23
"""

import json
import logging
import os
import tempfile
from typing import Any, AsyncGenerator

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import new SDK
GENAI_AVAILABLE = False
genai = None
types = None

try:
    from google import genai as google_genai
    from google.genai import types as genai_types

    genai = google_genai
    types = genai_types
    GENAI_AVAILABLE = True
    logger.info("✅ google-genai SDK loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️ google-genai SDK not available: {e}")
    # Try legacy SDK as fallback
    try:
        import google.generativeai as legacy_genai
        logger.warning("⚠️ Using deprecated google-generativeai as fallback")
    except ImportError:
        logger.error("❌ No Google AI SDK available")


def _setup_service_account_credentials() -> tuple[bool, str | None]:
    """
    Setup Service Account credentials from GOOGLE_CREDENTIALS_JSON env var.

    Writes the JSON to a temp file and sets GOOGLE_APPLICATION_CREDENTIALS.
    This enables Application Default Credentials (ADC) for the SDK.

    Returns:
        Tuple of (success, project_id)
    """
    creds_json = (
        getattr(settings, 'google_credentials_json', None)
        or os.environ.get('GOOGLE_CREDENTIALS_JSON')
        or os.environ.get('GEMINI_SA_TOKEN')  # Support GEMINI_SA_TOKEN alias
    )

    if not creds_json:
        return False, None

    try:
        # Parse to validate JSON
        if isinstance(creds_json, str):
            creds_dict = json.loads(creds_json)
        else:
            creds_dict = creds_json

        # Extract project_id for Vertex AI
        project_id = creds_dict.get('project_id')

        # Validate private key format
        private_key = creds_dict.get('private_key', '')
        if not private_key:
            logger.warning("⚠️ Service Account credentials missing private_key")
            return False, None

        # Fix escaped newlines from environment variables (literal \n -> actual newline)
        if '\\n' in private_key:
            private_key = private_key.replace('\\n', '\n')
            creds_dict['private_key'] = private_key
            logger.info("✅ Fixed escaped newlines in private key")

        # Check that newlines are properly formatted (not merged with header)
        lines = private_key.split('\n')
        if len(lines) < 10:
            logger.warning(f"⚠️ Service Account private key has too few lines ({len(lines)}), likely corrupted")
            return False, None

        # Header should be exactly "-----BEGIN PRIVATE KEY-----"
        header = lines[0].strip()
        if header != "-----BEGIN PRIVATE KEY-----":
            logger.warning(f"⚠️ Service Account private key has invalid header: '{header[:50]}...'")
            return False, None

        # Write to temp file
        creds_file = '/tmp/google_credentials.json'
        with open(creds_file, 'w') as f:
            json.dump(creds_dict, f)

        # Set environment variable for ADC
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_file

        logger.info(f"✅ Service Account credentials configured: {creds_dict.get('client_email', 'unknown')} (project: {project_id})")
        return True, project_id

    except (json.JSONDecodeError, KeyError, IOError) as e:
        logger.warning(f"⚠️ Failed to setup Service Account credentials: {e}")
        return False, None


# Try to setup Service Account on module load
_sa_configured, _sa_project_id = _setup_service_account_credentials()


# Singleton client instance
_client_instance = None


def get_genai_client() -> "GenAIClient":
    """
    Get or create singleton GenAI client instance.

    Returns:
        GenAIClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GenAIClient()
    return _client_instance


class GenAIClient:
    """
    Unified Google GenAI client wrapper.

    Provides a clean interface for:
    - Content generation (sync and async)
    - Streaming responses
    - Chat sessions
    - Model configuration

    The client uses connection pooling internally for efficiency.
    """

    # Default models - using Gemini 3 Flash Preview (Primary)
    # Primary tier
    DEFAULT_MODEL = "gemini-3-flash-preview"  # Primary: fast, cost-effective
    PRO_MODEL = "gemini-3-flash-preview"  # Same as default (no separate pro)

    # Fallback tier (Gemini 2.0 - stable)
    FALLBACK_FLASH = "gemini-2.0-flash"  # Fallback: stable, reliable
    FALLBACK_PRO = "gemini-2.0-flash"  # Fallback for pro

    # Aliases for clarity
    FLASH_MODEL = "gemini-3-flash-preview"  # Primary model
    PRO_HIGH_MODEL = "gemini-3-flash-preview"  # Same as flash

    def __init__(self, api_key: str | None = None):
        """
        Initialize GenAI client.

        Supports two authentication methods:
        1. Service Account (preferred for production) - via GOOGLE_CREDENTIALS_JSON (uses Vertex AI)
        2. API Key (fallback) - via GOOGLE_API_KEY or GOOGLE_IMAGEN_API_KEY (uses AI Studio)

        Args:
            api_key: Google API key (defaults to settings.google_api_key)
        """
        # Try multiple API key sources
        self.api_key = api_key or settings.google_api_key or settings.google_imagen_api_key
        self._client = None
        self._available = False
        self._auth_method = None

        if not GENAI_AVAILABLE:
            logger.warning("⚠️ google-genai SDK not available")
            return

        # Try Service Account first (Vertex AI mode) - PREFERRED for production
        if _sa_configured and _sa_project_id:
            try:
                self._client = genai.Client(
                    vertexai=True,
                    project=_sa_project_id,
                    location="global"  # Required for Gemini 3 preview models
                )
                self._available = True
                self._auth_method = "service_account_vertexai"
                logger.info(f"✅ GenAI client initialized with Vertex AI (project: {_sa_project_id})")
                return
            except Exception as e:
                logger.warning(f"⚠️ Vertex AI Service Account auth failed: {e}")

        # Fallback to GOOGLE_API_KEY (AI Studio)
        if not self.api_key:
            logger.warning("⚠️ No Google API key provided and Service Account not configured")
            return

        try:
            self._client = genai.Client(api_key=self.api_key)
            self._available = True
            self._auth_method = "api_key"
            logger.info("✅ GenAI client initialized with API Key (AI Studio)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize GenAI client: {e}")

    @property
    def is_available(self) -> bool:
        """Check if client is available and configured."""
        return self._available and self._client is not None

    def _get_config(
        self,
        system_instruction: str | None = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        safety_settings: list | None = None,
    ) -> Any:
        """
        Build GenerateContentConfig.

        Args:
            system_instruction: System prompt
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            safety_settings: Optional safety settings

        Returns:
            GenerateContentConfig object
        """
        if not GENAI_AVAILABLE or types is None:
            return None

        config_kwargs = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        if safety_settings:
            config_kwargs["safety_settings"] = safety_settings

        return types.GenerateContentConfig(**config_kwargs)

    async def generate_content(
        self,
        contents: str | list,
        model: str | None = None,
        system_instruction: str | None = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        safety_settings: list | None = None,
    ) -> dict[str, Any]:
        """
        Generate content asynchronously.

        Args:
            contents: User message or list of messages
            model: Model name (defaults to gemini-3-flash-preview)
            system_instruction: System prompt
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            safety_settings: Optional safety settings

        Returns:
            Dictionary with 'text', 'model', 'usage' keys
        """
        if not self.is_available:
            raise RuntimeError("GenAI client not available")

        model = model or self.DEFAULT_MODEL
        config = self._get_config(
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            safety_settings=safety_settings,
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            return {
                "text": response.text,
                "model": model,
                "usage": {
                    "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                    "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                },
            }
        except Exception as e:
            logger.error(f"❌ GenAI generate_content failed: {e}")
            raise

    async def generate_content_stream(
        self,
        contents: str | list,
        model: str | None = None,
        system_instruction: str | None = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        safety_settings: list | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming.

        Args:
            contents: User message or list of messages
            model: Model name (defaults to gemini-3-flash-preview)
            system_instruction: System prompt
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            safety_settings: Optional safety settings

        Yields:
            Text chunks as they arrive
        """
        if not self.is_available:
            raise RuntimeError("GenAI client not available")

        model = model or self.DEFAULT_MODEL
        config = self._get_config(
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            safety_settings=safety_settings,
        )

        try:
            async for chunk in self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"❌ GenAI stream failed: {e}")
            raise

    def create_chat(
        self,
        model: str | None = None,
        system_instruction: str | None = None,
        history: list[dict] | None = None,
    ) -> "ChatSession":
        """
        Create a new chat session.

        Args:
            model: Model name (defaults to gemini-3-flash-preview)
            system_instruction: System prompt
            history: Optional conversation history

        Returns:
            ChatSession instance
        """
        if not self.is_available:
            raise RuntimeError("GenAI client not available")

        return ChatSession(
            client=self,
            model=model or self.DEFAULT_MODEL,
            system_instruction=system_instruction,
            history=history,
        )


class ChatSession:
    """
    Chat session wrapper for multi-turn conversations.

    Maintains conversation history and provides methods for
    sending messages with context.
    """

    def __init__(
        self,
        client: GenAIClient,
        model: str,
        system_instruction: str | None = None,
        history: list[dict] | None = None,
    ):
        """
        Initialize chat session.

        Args:
            client: GenAIClient instance
            model: Model name
            system_instruction: System prompt
            history: Optional initial history
        """
        self._client = client
        self._model = model
        self._system_instruction = system_instruction
        self._history: list[dict] = history or []

    def _format_contents(self, message: str) -> list[dict]:
        """
        Format conversation history + new message for API.

        Args:
            message: New user message

        Returns:
            Formatted contents list
        """
        contents = []

        # Add history
        for msg in self._history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Map "assistant" to "model" for Gemini
            if role == "assistant":
                role = "model"
            contents.append({"role": role, "parts": [{"text": content}]})

        # Add new message
        contents.append({"role": "user", "parts": [{"text": message}]})

        return contents

    async def send_message(
        self,
        message: str,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        """
        Send a message and get response.

        Args:
            message: User message
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dictionary with 'text', 'model', 'usage' keys
        """
        contents = self._format_contents(message)

        result = await self._client.generate_content(
            contents=contents,
            model=self._model,
            system_instruction=self._system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        # Update history
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": result["text"]})

        return result

    async def send_message_stream(
        self,
        message: str,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
    ) -> AsyncGenerator[str, None]:
        """
        Send a message and stream response.

        Args:
            message: User message
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive
        """
        contents = self._format_contents(message)
        full_response = ""

        async for chunk in self._client.generate_content_stream(
            contents=contents,
            model=self._model,
            system_instruction=self._system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        ):
            full_response += chunk
            yield chunk

        # Update history after stream completes
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": full_response})

    @property
    def history(self) -> list[dict]:
        """Get conversation history."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history = []
