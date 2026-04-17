"""LangChain BaseChatModel backed by ``claude -p`` (Max OAuth subprocess).

Lets LangGraph/LangChain code paths use Claude without importing
``langchain_anthropic`` (which requires ``ANTHROPIC_API_KEY``).

Minimal on purpose:
- no streaming (``_astream`` is unimplemented),
- no tool-use / function-calling (the CLI has no built-in channel for it),
- flattens the entire conversation into a single prompt before handing off
  to :func:`backend.llm.claude_oauth_client.complete_async`.

If any of those limitations bite a consumer, we fix that consumer — we do
NOT bring back the SDK.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.llm.claude_oauth_client import (
    ClaudeOAuthError,
    ClaudeOAuthNotAvailable,
    complete_async,
)

logger = logging.getLogger(__name__)


def _import_langchain_core() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Lazy-import LangChain Core so test collection doesn't require it."""
    from langchain_core.callbacks.manager import (  # noqa: PLC0415
        AsyncCallbackManagerForLLMRun,
        CallbackManagerForLLMRun,
    )
    from langchain_core.language_models.chat_models import BaseChatModel  # noqa: PLC0415
    from langchain_core.messages import AIMessage, BaseMessage  # noqa: PLC0415
    from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: PLC0415

    return (
        AsyncCallbackManagerForLLMRun,
        CallbackManagerForLLMRun,
        BaseChatModel,
        AIMessage,
        BaseMessage,
        (ChatGeneration, ChatResult),
    )


def _flatten_messages(messages: list[Any]) -> str:
    """Fold a LangChain message list into a single prompt string.

    The CLI takes one prompt — we preserve role tags as plain-text
    prefixes so the model can still read the conversation structure.
    """
    lines: list[str] = []
    for msg in messages:
        role = getattr(msg, "type", None) or getattr(msg, "role", "user")
        content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(content, list):
            # content blocks (e.g. multimodal) → take text parts only
            text_parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = "\n".join(t for t in text_parts if t)
        lines.append(f"[{role}]\n{content}")
    return "\n\n".join(lines)


def build_claude_oauth_chat_model(
    model: str = "claude-sonnet-4-6",
    timeout_s: int = 120,
) -> Any:
    """Return a ``BaseChatModel`` instance that talks to Claude via OAuth.

    Built lazily (inside the function) so callers that don't use LangChain
    never pay the import cost. The returned object is fully compatible
    with ``LLMCompatibility``-style LangGraph nodes that expect
    ``ainvoke(messages) -> AIMessage``.
    """
    (
        _AsyncCbMgr,
        _CbMgr,
        BaseChatModel,
        AIMessage,
        _BaseMessage,
        (ChatGeneration, ChatResult),
    ) = _import_langchain_core()

    class ClaudeOAuthChatModel(BaseChatModel):  # type: ignore[misc, valid-type]
        """LangChain chat wrapper around :mod:`claude_oauth_client`."""

        model_name: str = model
        request_timeout_s: int = timeout_s

        @property
        def _llm_type(self) -> str:
            return "claude-oauth-subprocess"

        def _generate(
            self,
            messages: list[Any],
            stop: list[str] | None = None,
            run_manager: Any | None = None,
            **_: Any,
        ) -> Any:
            # LangGraph in our codebase always uses the async path, but
            # keep a sync fallback that just forwards to asyncio.run.
            import asyncio

            del stop, run_manager
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                raise RuntimeError(
                    "ClaudeOAuthChatModel._generate called inside a running "
                    "event loop; use _agenerate / ainvoke instead",
                )
            prompt = _flatten_messages(messages)
            resp = asyncio.run(
                complete_async(prompt, model=self.model_name, timeout_s=self.request_timeout_s),
            )
            gen = ChatGeneration(message=AIMessage(content=resp.text))
            return ChatResult(generations=[gen])

        async def _agenerate(
            self,
            messages: list[Any],
            stop: list[str] | None = None,
            run_manager: Any | None = None,
            **_: Any,
        ) -> Any:
            del stop, run_manager
            prompt = _flatten_messages(messages)
            try:
                resp = await complete_async(
                    prompt,
                    model=self.model_name,
                    timeout_s=self.request_timeout_s,
                )
            except (ClaudeOAuthError, ClaudeOAuthNotAvailable):
                raise
            gen = ChatGeneration(message=AIMessage(content=resp.text))
            return ChatResult(generations=[gen])

    return ClaudeOAuthChatModel()
