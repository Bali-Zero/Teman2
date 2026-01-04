import sys
import types

import llm


def test_llm_getattr_lazy_imports():
    prompt_module = types.ModuleType("llm.prompt_manager")
    retry_module = types.ModuleType("llm.retry_handler")
    token_module = types.ModuleType("llm.token_estimator")
    zantara_module = types.ModuleType("llm.zantara_ai_client")

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

    sys.modules["llm.prompt_manager"] = prompt_module
    sys.modules["llm.retry_handler"] = retry_module
    sys.modules["llm.token_estimator"] = token_module
    sys.modules["llm.zantara_ai_client"] = zantara_module

    assert llm.PromptManager is PromptManager
    assert llm.RetryHandler is RetryHandler
    assert llm.TokenEstimator is TokenEstimator
    assert llm.ZantaraAIClient is ZantaraAIClient
    assert llm.ZantaraAIClientConstants is ZantaraAIClientConstants


def test_llm_getattr_unknown_raises():
    try:
        _ = llm.UnknownThing
        assert False, "Expected AttributeError"
    except AttributeError as exc:
        assert "module 'llm' has no attribute" in str(exc)


def test_llm_all_exports():
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
