import sys
import types
import importlib
from pathlib import Path

import pytest

# Add backend to path
backend_root = Path(__file__).parents[3] / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_llm_getattr_lazy_imports(monkeypatch):
    # Setup dummy modules
    prompt_module = types.ModuleType("backend.llm.prompt_manager")
    retry_module = types.ModuleType("backend.llm.retry_handler")
    token_module = types.ModuleType("backend.llm.token_estimator")
    zantara_module = types.ModuleType("backend.llm.zantara_ai_client")

    class PromptManager:
        pass

    class RetryHandler:
        pass

    class TokenEstimator:
        pass

    class ZantaraAIClient:
        pass

    class ZantaraAIClientConstants:
        pass

    prompt_module.PromptManager = PromptManager
    retry_module.RetryHandler = RetryHandler
    token_module.TokenEstimator = TokenEstimator
    zantara_module.ZantaraAIClient = ZantaraAIClient
    zantara_module.ZantaraAIClientConstants = ZantaraAIClientConstants

    monkeypatch.setitem(sys.modules, "backend.llm.prompt_manager", prompt_module)
    monkeypatch.setitem(sys.modules, "backend.llm.retry_handler", retry_module)
    monkeypatch.setitem(sys.modules, "backend.llm.token_estimator", token_module)
    monkeypatch.setitem(sys.modules, "backend.llm.zantara_ai_client", zantara_module)

    # Force fresh import of llm module
    if "llm" in sys.modules:
        del sys.modules["llm"]
    if "backend.llm" in sys.modules:
        del sys.modules["backend.llm"]
        
    import backend.llm as llm

    assert llm.PromptManager is PromptManager
    assert llm.RetryHandler is RetryHandler
    assert llm.TokenEstimator is TokenEstimator
    assert llm.ZantaraAIClient is ZantaraAIClient
    assert llm.ZantaraAIClientConstants is ZantaraAIClientConstants


def test_llm_getattr_unknown_raises():
    import backend.llm as llm
    try:
        _ = llm.UnknownThing
        assert False, "Expected AttributeError"
    except AttributeError as exc:
        assert "module 'llm' has no attribute" in str(exc)


def test_llm_all_exports():
    import backend.llm as llm
    required = {
        "LLMProvider",
        "LLMMessage",
        "LLMResponse",
        "UnifiedLLMClient",
        "create_default_client",
        "register_provider",
        "get_provider",
        "list_providers",
        "get_fallback_message",
        "FALLBACK_MESSAGES",
        "ZantaraAIClient",
        "ZantaraAIClientConstants",
        "PromptManager",
        "RetryHandler",
        "TokenEstimator",
    }
    assert set(llm.__all__) == required