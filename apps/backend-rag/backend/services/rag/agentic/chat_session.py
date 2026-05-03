"""
ChatSession and MockChatSession classes for LLM Gateway.

These classes provide a unified interface for multi-turn conversations
with Gemini models, following Best Practice 2026 for chat history management.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)


class ChatSession:
    """
    Gemini ChatSession wrapper for multi-turn conversations.

    Provides a unified interface for chat operations with history persistence.
    Follows Firebase/Gemini best practices for context management.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        history: list[dict] | None = None,
        system_instruction: str = "",
    ) -> None:
        """
        Initialize ChatSession with model and history.

        Args:
            client: GenAI client instance
            model: Model name (e.g., "gemini-1.5-flash")
            history: Previous conversation history
            system_instruction: System prompt for the session
        """
        self.client = client
        self.model = model
        self.history = history or []
        self.system_instruction = system_instruction
        self._chat_session = None

        # Initialize the actual chat session
        self._initialize_session()

    def _initialize_session(self) -> None:
        """Initialize the underlying Gemini chat session."""
        try:
            # Create the chat session with history
            self._chat_session = self.client.start_chat(
                model=self.model,
                history=self.history,
                system_instruction=self.system_instruction,
            )
            logger.debug(f"ChatSession initialized with {len(self.history)} history items")
        except Exception as e:
            logger.error(f"Failed to initialize ChatSession: {e}", exc_info=True)
            raise

    async def send_message(self, message: str) -> Any:
        """
        Send a message to the chat session.

        Args:
            message: User message to send

        Returns:
            Response from the model
        """
        if not self._chat_session:
            raise RuntimeError("ChatSession not initialized")

        try:
            response = self._chat_session.send_message(message)
            logger.debug(f"Message sent to {self.model}, response received")
            return response
        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            raise

    async def send_message_stream(self, message: str) -> AsyncGenerator[str, None]:
        """
        Send a message and stream the response.

        Args:
            message: User message to send

        Yields:
            Response tokens as they become available
        """
        if not self._chat_session:
            raise RuntimeError("ChatSession not initialized")

        try:
            # Stream response token by token
            response = self._chat_session.send_message(message, stream=True)

            for chunk in response:
                if hasattr(chunk, "text"):
                    yield chunk.text
                elif hasattr(chunk, "candidates") and chunk.candidates:
                    candidate = chunk.candidates[0]
                    if hasattr(candidate, "content") and candidate.content:
                        for part in candidate.content.parts:
                            if hasattr(part, "text"):
                                yield part.text

        except Exception as e:
            logger.error(f"Failed to stream message: {e}", exc_info=True)
            raise

    def get_history(self) -> list[dict]:
        """Get current conversation history."""
        return self.history.copy()

    def add_to_history(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: "user" or "model"
            content: Message content
        """
        self.history.append({"role": role, "parts": [{"text": content}]})
        logger.debug(f"Added {role} message to history")


class MockChatSession:
    """
    Mock ChatSession for fallback when GenAI client is unavailable.

    Provides a minimal interface to prevent crashes when the main
    LLM service is down. Returns simple responses indicating unavailability.
    """

    def __init__(
        self,
        history: list[dict] | None = None,
        model: str = "mock",
        system_instruction: str = "",
    ) -> None:
        """
        Initialize MockChatSession.

        Args:
            history: Conversation history (ignored in mock)
            model: Model name (ignored in mock)
            system_instruction: System instruction (ignored in mock)
        """
        self.history = history or []
        self.model = model
        self.system_instruction = system_instruction
        logger.warning("Using MockChatSession - LLM service unavailable")

    async def send_message(self, _message: str) -> Any:
        """
        Mock send_message that returns a fallback response.

        Args:
            message: User message (ignored)

        Returns:
            Mock response object with text attribute
        """
        response_text = (
            "Mi dispiace, il servizio di intelligenza artificiale non è disponibile al momento. "
            "Per favore, riprova più tardi o contatta l'assistenza."
        )

        class MockResponse:
            def __init__(self, text: str) -> None:
                self.text = text
                self.candidates = []

        return MockResponse(response_text)

    async def send_message_stream(self, _message: str) -> AsyncGenerator[str, None]:
        """
        Mock streaming that yields the fallback response word by word.

        Args:
            message: User message (ignored)

        Yields:
            Response tokens one by one
        """
        response_text = (
            "Mi dispiace, il servizio di intelligenza artificiale non è disponibile al momento. "
            "Per favore, riprova più tardi o contatta l'assistenza."
        )

        # Split into words and yield with small delays
        words = response_text.split()
        for word in words:
            yield word + " "

    def get_history(self) -> list[dict]:
        """Get current conversation history."""
        return self.history.copy()

    def add_to_history(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history (mock implementation).

        Args:
            role: "user" or "model"
            content: Message content
        """
        self.history.append({"role": role, "parts": [{"text": content}]})
