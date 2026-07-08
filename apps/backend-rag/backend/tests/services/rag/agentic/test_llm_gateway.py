from types import SimpleNamespace

import pytest

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.llm_gateway import (
    TIER_FALLBACK,
    TIER_FLASH,
    TIER_LITE,
    TIER_PRO,
    LLMGateway,
    MockChatSession,
)


class FakeGenAIClient:
    is_available = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate_content(self, *, contents: str, model: str, max_output_tokens: int) -> dict:
        assert contents == "ping"
        assert max_output_tokens == 8192
        self.calls.append(model)
        return {"text": "pong"}


def test_gemini_tools_can_be_read_and_replaced() -> None:
    gateway = LLMGateway(gemini_tools=[{"name": "vector_search"}])

    assert gateway.gemini_tools == [{"name": "vector_search"}]

    gateway.set_gemini_tools([{"name": "calculator"}])
    assert gateway.gemini_tools == [{"name": "calculator"}]

    gateway.set_gemini_tools(None)
    assert gateway.gemini_tools == []


def test_model_tier_and_fallback_chain_are_deterministic() -> None:
    gateway = LLMGateway()
    gateway.model_name_pro = "pro-model"
    gateway.model_name_flash = "flash-model"
    gateway.model_name_fallback = "fallback-model"

    assert gateway._get_model_for_tier(TIER_PRO) == "pro-model"
    assert gateway._get_model_for_tier(TIER_FLASH) == "flash-model"
    assert gateway._get_model_for_tier(TIER_LITE) == "fallback-model"
    assert gateway._get_model_for_tier(TIER_FALLBACK) == "fallback-model"
    assert gateway._get_fallback_chain(TIER_PRO) == [
        "pro-model",
        "flash-model",
        "fallback-model",
    ]
    assert gateway._get_fallback_chain(TIER_FLASH) == ["flash-model", "fallback-model"]


def test_create_chat_with_history_returns_mock_when_client_unavailable(monkeypatch) -> None:
    gateway = LLMGateway()
    monkeypatch.setattr(gateway, "_get_genai_client", lambda: None)

    chat = gateway.create_chat_with_history(
        history_to_use=[{"role": "user", "content": "hello"}],
        model_tier=TIER_FLASH,
    )

    assert isinstance(chat, MockChatSession)
    assert chat.history == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_send_message_delegates_to_fallback_runner(monkeypatch) -> None:
    gateway = LLMGateway()
    seen: dict[str, object] = {}

    async def fake_send_with_fallback(**kwargs):
        seen.update(kwargs)
        return (
            "answer",
            "fake-model",
            SimpleNamespace(text="answer"),
            TokenUsage(prompt_tokens=1, completion_tokens=2, cost_usd=0.0),
        )

    monkeypatch.setattr(gateway, "_send_with_fallback", fake_send_with_fallback)

    text, model, response, usage = await gateway.send_message(
        chat=None,
        message="What is KITAS?",
        system_prompt="system",
        tier=TIER_PRO,
        conversation_messages=[{"role": "user", "content": "What is KITAS?"}],
    )

    assert text == "answer"
    assert model == "fake-model"
    assert response.text == "answer"
    assert usage.total_tokens == 3
    assert seen["model_tier"] == TIER_PRO
    assert seen["message"] == "What is KITAS?"
    assert seen["system_prompt"] == "system"
    assert seen["conversation_messages"] == [{"role": "user", "content": "What is KITAS?"}]
    assert seen["query_cost_tracker"] == {"cost": 0.0, "depth": 0}


@pytest.mark.asyncio
async def test_health_check_uses_injected_clients(monkeypatch) -> None:
    gateway = LLMGateway()
    gateway.model_name_pro = "pro-model"
    gateway.model_name_flash = "flash-model"
    gateway.model_name_fallback = "fallback-model"
    gateway._genai_client = FakeGenAIClient()
    monkeypatch.setattr(gateway, "_get_openrouter_client", object)

    status = await gateway.health_check()

    assert status == {
        "gemini_pro": True,
        "gemini_flash": True,
        "gemini_flash_lite": True,
        "openrouter": True,
    }
    assert gateway._genai_client.calls == ["flash-model", "pro-model", "fallback-model"]
