import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


class DummyTokenEstimator:
    def __init__(self, model=None):
        self.model = model

    def estimate_messages_tokens(self, messages):
        return len(messages) * 2

    def estimate_tokens(self, text):
        return len(text.split())


class DummyPromptManager:
    def __init__(self):
        self._base_system_prompt = "base"

    def build_system_prompt(self, **_kwargs):
        return "SYSTEM"


class DummyRetryHandler:
    def __init__(self, **_kwargs):
        self.calls = []

    async def execute_with_retry(self, func, operation_name=""):
        async for chunk in func():
            yield chunk


class DummyGenAIChat:
    def __init__(self, response_text="ok", stream_chunks=None):
        self.response_text = response_text
        self.stream_chunks = stream_chunks or []

    async def send_message(self, message, max_output_tokens=None, temperature=None):
        return {"text": self.response_text}

    async def send_message_stream(self, message, max_output_tokens=None, temperature=None):
        for chunk in self.stream_chunks:
            yield chunk


class DummyGenAIClient:
    def __init__(self, api_key=None, chat=None, available=True):
        self.is_available = available
        self._auth_method = "api_key"
        self._chat = chat or DummyGenAIChat()

    def create_chat(self, **_kwargs):
        return self._chat


def _load_client_module(
    *,
    genai_available=True,
    genai_client=None,
    env="development",
    api_key="key",
    has_service_account=False,
):
    app_module = types.ModuleType("app")
    app_core_module = types.ModuleType("app.core")
    app_config_module = types.ModuleType("app.core.config")
    app_config_module.settings = types.SimpleNamespace(
        google_api_key=api_key,
        environment=env,
        zantara_ai_cost_input=0.15,
        zantara_ai_cost_output=0.6,
    )

    llm_module = types.ModuleType("llm")
    fallback_module = types.ModuleType("llm.fallback_messages")
    fallback_module.get_fallback_message = lambda key, lang="en": f"{key}-{lang}"

    genai_module = types.ModuleType("llm.genai_client")
    genai_module.GENAI_AVAILABLE = genai_available
    genai_module.GenAIClient = DummyGenAIClient

    prompt_module = types.ModuleType("llm.prompt_manager")
    prompt_module.PromptManager = DummyPromptManager

    retry_module = types.ModuleType("llm.retry_handler")
    retry_module.RetryHandler = DummyRetryHandler

    token_module = types.ModuleType("llm.token_estimator")
    token_module.TokenEstimator = DummyTokenEstimator

    sys.modules.update(
        {
            "app": app_module,
            "app.core": app_core_module,
            "app.core.config": app_config_module,
            "llm": llm_module,
            "llm.fallback_messages": fallback_module,
            "llm.genai_client": genai_module,
            "llm.prompt_manager": prompt_module,
            "llm.retry_handler": retry_module,
            "llm.token_estimator": token_module,
        }
    )

    module_path = Path(__file__).resolve().parents[3] / "backend" / "llm" / "zantara_ai_client.py"
    spec = importlib.util.spec_from_file_location("llm.zantara_ai_client", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    if genai_client:
        genai_module.GenAIClient = genai_client

    spec.loader.exec_module(module)

    if has_service_account:
        module.os.environ["GOOGLE_CREDENTIALS_JSON"] = "1"
    return module


def test_init_mock_mode_when_no_creds():
    module = _load_client_module(genai_available=False, api_key=None)
    client = module.ZantaraAIClient(api_key=None)
    assert client.mock_mode is True
    assert client.is_available() is True


def test_init_production_without_creds_raises():
    module = _load_client_module(genai_available=False, api_key=None, env="production")
    with pytest.raises(ValueError):
        module.ZantaraAIClient(api_key=None)


def test_validate_inputs():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")
    with pytest.raises(ValueError):
        client._validate_inputs(max_tokens=0, messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(ValueError):
        client._validate_inputs(temperature=3.0, messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(ValueError):
        client._validate_inputs(messages=[])


def test_prepare_gemini_messages():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "last"},
    ]
    history, last_user = client._prepare_gemini_messages(messages)
    assert last_user == "last"
    assert history[-1]["role"] == "model"


def test_extract_response_text_with_block():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")

    class Rating:
        def __init__(self, name):
            self.probability = types.SimpleNamespace(name=name)

    class Candidate:
        safety_ratings = [Rating("HIGH")]
        content = types.SimpleNamespace(parts=[types.SimpleNamespace(text="blocked text")])

    response = types.SimpleNamespace(candidates=[Candidate()], text="fallback")
    assert client._extract_response_text(response) == "blocked text"


@pytest.mark.asyncio
async def test_chat_async_mock_mode():
    module = _load_client_module(genai_available=False, api_key=None)
    client = module.ZantaraAIClient(api_key=None)
    result = await client.chat_async(messages=[{"role": "user", "content": "hi"}])
    assert result["provider"] == "mock"


@pytest.mark.asyncio
async def test_chat_async_success():
    module = _load_client_module()
    chat = DummyGenAIChat(response_text="hello")
    client = module.ZantaraAIClient(api_key="key")
    client._genai_client = DummyGenAIClient(chat=chat, available=True)
    result = await client.chat_async(messages=[{"role": "user", "content": "hi"}])
    assert result["text"] == "hello"
    assert result["provider"] == "google_genai"


@pytest.mark.asyncio
async def test_chat_async_api_key_error():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")

    class DummyChat:
        async def send_message(self, *_a, **_k):
            raise RuntimeError("403 leaked api key")

    client._genai_client = DummyGenAIClient(chat=DummyChat(), available=True)
    with pytest.raises(ValueError):
        await client.chat_async(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_stream_mock_mode():
    module = _load_client_module(genai_available=False, api_key=None)
    client = module.ZantaraAIClient(api_key=None)
    chunks = []
    async for chunk in client.stream("hi", "user"):
        chunks.append(chunk)
    assert chunks


@pytest.mark.asyncio
async def test_stream_genai_unavailable_fallback():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")
    client._genai_client = None
    chunks = []
    async for chunk in client.stream("hi", "user", language="id"):
        chunks.append(chunk)
    assert "service_unavailable-id" in "".join(chunks)


@pytest.mark.asyncio
async def test_stream_success():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")
    chat = DummyGenAIChat(stream_chunks=["a", "b"])
    client._genai_client = DummyGenAIClient(chat=chat, available=True)
    chunks = []
    async for chunk in client.stream("hi", "user"):
        chunks.append(chunk)
    assert chunks == ["a", "b"]


@pytest.mark.asyncio
async def test_stream_value_error_api_key():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")

    class DummyChat:
        async def send_message_stream(self, *_a, **_k):
            if False:
                yield ""
            raise ValueError("api key")

    client._genai_client = DummyGenAIClient(chat=DummyChat(), available=True)
    chunks = []
    async for chunk in client.stream("hi", "user", language="en"):
        chunks.append(chunk)
    assert "api_key_error-en" in "".join(chunks)


@pytest.mark.asyncio
async def test_stream_exception_fallback():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")

    class DummyRetry(DummyRetryHandler):
        async def execute_with_retry(self, func, operation_name=""):
            if False:
                yield ""
            gen = func()
            await gen.aclose()
            raise RuntimeError("boom")

    client.retry_handler = DummyRetry()
    chunks = []
    async for chunk in client.stream("hi", "user", language="en"):
        chunks.append(chunk)
    assert "connection_error-en" in "".join(chunks)


@pytest.mark.asyncio
async def test_conversational_and_tools():
    module = _load_client_module()
    client = module.ZantaraAIClient(api_key="key")
    client.chat_async = AsyncMock(
        return_value={"text": "ok", "model": "m", "provider": "p", "tokens": {}}
    )
    result = await client.conversational("hi", "user")
    assert result["ai_used"] == "zantara-ai"
    result_tools = await client.conversational_with_tools("hi", "user", tools=[{"name": "t"}])
    assert result_tools["used_tools"] is False
