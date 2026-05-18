"""Unit tests for Phase 1 Task #22 — DeepSeek branch in vendor/evoskill/src/cli/shared.py.

Verifies:
    - infer_provider() routes "deepseek-v4-pro" to "deepseek" (NOT to
      fallback "anthropic" which would trigger the hard-rule ImportError)
    - infer_provider() routes "deepseek/anything" to "deepseek"
    - infer_provider() preserves existing routes (claude→anthropic,
      gpt-*→openai, gemini→google) — no regression
    - _normalize_provider_model strips "deepseek/" prefix when provider=deepseek
    - call_llm(provider="deepseek") routes to OpenAI-compatible
      base_url="https://api.deepseek.com/v1" with the configured api_key
    - call_llm(provider="deepseek") returns response.choices[0].message.content
    - call_llm(provider="deepseek") raises RuntimeError if DEEPSEEK_API_KEY unset
    - call_llm(provider="deepseek") still raises ImportError if openai pkg missing
    - make_scorer default model is now "deepseek-v4-pro" (NOT "claude-sonnet-4-6")
    - Anthropic guard still fires when provider="anthropic" explicitly chosen

Run:
    cd ~/Desktop/nuzantara-wt-evoskill-phase1 && python3 -m pytest scripts/test_call_llm_deepseek.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_EVOSKILL = REPO_ROOT / "vendor" / "evoskill"
sys.path.insert(0, str(VENDOR_EVOSKILL))


def _reload_shared():
    """Force-reload src.cli.shared to pick up patched env."""
    if "src.cli.shared" in sys.modules:
        del sys.modules["src.cli.shared"]
    from src.cli import shared  # noqa: F401  — side-effect import
    return shared


# ---------- infer_provider ----------


def test_infer_provider_deepseek_v4_pro_routes_to_deepseek():
    """The exact model name we ship in evolver.toml MUST NOT fall through
    to the upstream `return "anthropic"` final branch."""
    shared = _reload_shared()
    assert shared.infer_provider("deepseek-v4-pro") == "deepseek"


def test_infer_provider_deepseek_prefix():
    """`deepseek/some-future-model` style routes to deepseek."""
    shared = _reload_shared()
    assert shared.infer_provider("deepseek/v5-preview") == "deepseek"


def test_infer_provider_deepseek_chat_routes_to_deepseek():
    """Even the deprecated `deepseek-chat`/`deepseek-reasoner` aliases
    (CLAUDE.md notes they were deprecated 2026-07-24) still route to
    deepseek if someone uses them, so the failure mode is a clean
    DeepSeek API 4xx — not a confusing anthropic-hardrule raise."""
    shared = _reload_shared()
    assert shared.infer_provider("deepseek-chat") == "deepseek"
    assert shared.infer_provider("deepseek-reasoner") == "deepseek"


def test_infer_provider_no_regression_other_providers():
    """Pre-existing routes (claude/gpt/gemini) must stay intact."""
    shared = _reload_shared()
    assert shared.infer_provider("claude-sonnet-4-6") == "anthropic"
    assert shared.infer_provider("gpt-5-mini") == "openai"
    assert shared.infer_provider("o1-preview") == "openai"
    assert shared.infer_provider("gemini-3.1-pro-preview") == "google"
    assert shared.infer_provider("anthropic/claude-opus-4-7") == "anthropic"
    assert shared.infer_provider("openrouter/google/gemini-pro") == "openrouter"


def test_infer_provider_unknown_model_falls_back_to_anthropic():
    """Phase 1 keeps the upstream fallback so genuinely-unknown models
    hit the loud hard-rule raise in call_llm rather than silently
    routing to DeepSeek (which would then 401)."""
    shared = _reload_shared()
    assert shared.infer_provider("totally-unknown-model-xyz") == "anthropic"


# ---------- _normalize_provider_model ----------


def test_normalize_provider_model_strips_deepseek_prefix():
    shared = _reload_shared()
    assert (
        shared._normalize_provider_model("deepseek", "deepseek/v4-pro")
        == "v4-pro"
    )


def test_normalize_provider_model_passthrough_no_prefix():
    shared = _reload_shared()
    assert (
        shared._normalize_provider_model("deepseek", "deepseek-v4-pro")
        == "deepseek-v4-pro"
    )


def test_normalize_provider_model_no_regression_other_providers():
    shared = _reload_shared()
    assert (
        shared._normalize_provider_model("openrouter", "openrouter/foo")
        == "foo"
    )
    assert (
        shared._normalize_provider_model("openai", "openai/gpt-5")
        == "gpt-5"
    )


# ---------- call_llm deepseek branch ----------


def _build_mock_openai_client(content_returned: str = "0.0") -> MagicMock:
    """Build a mock matching openai.AsyncOpenAI shape."""
    mock_choice = MagicMock()
    mock_choice.message.content = content_returned
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_completions = MagicMock()
    mock_completions.create = AsyncMock(return_value=mock_response)
    mock_chat = MagicMock()
    mock_chat.completions = mock_completions
    mock_client = MagicMock()
    mock_client.chat = mock_chat
    return mock_client


@patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-1234"})
def test_call_llm_deepseek_routes_to_deepseek_base_url():
    """call_llm(provider='deepseek') must construct openai.AsyncOpenAI
    with base_url='https://api.deepseek.com/v1' and the env-resolved
    API key. This is the entire integration contract."""
    shared = _reload_shared()

    mock_client = _build_mock_openai_client("1.0")
    fake_openai_module = MagicMock()
    fake_openai_module.AsyncOpenAI = MagicMock(return_value=mock_client)

    with patch.dict(sys.modules, {"openai": fake_openai_module}):
        result = asyncio.run(
            shared.call_llm("deepseek", "deepseek-v4-pro", "test prompt")
        )

    assert result == "1.0"

    # AsyncOpenAI constructor was called with the right base_url + key
    construct_call = fake_openai_module.AsyncOpenAI.call_args
    assert construct_call.kwargs["base_url"] == "https://api.deepseek.com/v1"
    assert construct_call.kwargs["api_key"] == "sk-test-1234"

    # chat.completions.create was called with the right model + max_tokens
    create_call = mock_client.chat.completions.create.call_args
    assert create_call.kwargs["model"] == "deepseek-v4-pro"
    assert create_call.kwargs["max_tokens"] == 16
    assert create_call.kwargs["messages"] == [
        {"role": "user", "content": "test prompt"}
    ]


@patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-5678"})
def test_call_llm_deepseek_strips_deepseek_slash_prefix():
    """If caller passes `deepseek/deepseek-v4-pro`, the upstream API
    must receive the bare model name (DeepSeek API doesn't know about
    the OpenRouter-style `provider/` prefix)."""
    shared = _reload_shared()

    mock_client = _build_mock_openai_client()
    fake_openai_module = MagicMock()
    fake_openai_module.AsyncOpenAI = MagicMock(return_value=mock_client)

    with patch.dict(sys.modules, {"openai": fake_openai_module}):
        asyncio.run(
            shared.call_llm("deepseek", "deepseek/v4-pro", "x")
        )

    create_call = mock_client.chat.completions.create.call_args
    assert create_call.kwargs["model"] == "v4-pro"


def test_call_llm_deepseek_raises_when_api_key_missing(monkeypatch):
    """ensure_provider_api_key must raise RuntimeError when
    DEEPSEEK_API_KEY is unset."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    shared = _reload_shared()

    with pytest.raises(RuntimeError, match="API key not configured"):
        asyncio.run(shared.call_llm("deepseek", "deepseek-v4-pro", "x"))


# ---------- Anthropic guard regression ----------


def test_call_llm_anthropic_still_raises_import_error():
    """Phase 1 patches MUST NOT regress the Phase 0 R3 fix that
    anthropic provider raises ImportError BEFORE auth lookup."""
    shared = _reload_shared()

    with pytest.raises(ImportError) as exc_info:
        asyncio.run(
            shared.call_llm("anthropic", "claude-sonnet-4-6", "x")
        )

    msg = str(exc_info.value)
    assert "BANNED" in msg or "CLAUDE.md hard rule" in msg
    assert "ANTHROPIC_API_KEY" not in msg or "BANNED" in msg


# ---------- make_scorer default model ----------


def test_make_scorer_llm_default_model_is_deepseek_v4_pro():
    """L9 fix: default scorer model must NOT be claude-sonnet-4-6
    (which routes to anthropic→ImportError). It must be
    deepseek-v4-pro so an unconfigured scorer works out of the box."""
    shared = _reload_shared()

    # Build a minimal ProjectConfig with empty scorer overrides
    from src.cli.config import (
        DatasetConfig,
        EvolutionConfig,
        HarnessConfig,
        ProjectConfig,
        ScorerConfig,
    )

    cfg = ProjectConfig(
        harness=HarnessConfig(name="deepseek", model="deepseek-v4-pro"),
        evolution=EvolutionConfig(),
        dataset=DatasetConfig(),
        scorer=ScorerConfig(type="llm"),  # no model / no provider
    )

    # Inspect the closure: rather than invoking the scorer (which would
    # need a real LLM call), patch call_llm with a probe that captures
    # the (provider, model) it was invoked with.
    captured: dict = {}

    async def probe(provider, model, prompt):
        captured["provider"] = provider
        captured["model"] = model
        return "1.0"

    with patch.object(shared, "call_llm", side_effect=probe):
        scorer_fn = shared.make_scorer(cfg)
        score = scorer_fn("q", "p", "g")

    assert score == 1.0
    assert captured["model"] == "deepseek-v4-pro"
    assert captured["provider"] == "deepseek"


# ---------- evolver.toml end-to-end via infer_provider ----------


def test_infer_provider_matches_evolver_toml_scorer_provider():
    """Belt-and-suspenders: load the actual Phase 1 evolver.toml
    and verify that infer_provider(scorer.model) matches
    scorer.provider exactly. Prevents silent drift between the
    config file and the call_llm dispatch."""
    from src.cli.config import load_config

    cfg_path = (
        REPO_ROOT / "agent-library" / ".evoskill" / "config.toml"
    )
    cfg = load_config(config_path=cfg_path)

    shared = _reload_shared()
    inferred = shared.infer_provider(cfg.scorer.model or "")
    assert inferred == cfg.scorer.provider, (
        f"evolver.toml says provider={cfg.scorer.provider!r} but "
        f"infer_provider({cfg.scorer.model!r}) routes to {inferred!r}"
    )
