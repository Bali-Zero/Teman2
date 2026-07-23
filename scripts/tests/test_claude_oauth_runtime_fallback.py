"""Behavior tests for five-seat Claude OAuth rotation outside backend runtime."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(relative_path: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_five_slots(monkeypatch: Any) -> None:
    for slot in range(1, 6):
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", f"sentinel-{slot}")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "must-not-leak")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://must-not-leak.invalid")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "must-not-leak")
    monkeypatch.setenv("VERTEX_AI_PROJECT", "must-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-leak")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-leak")
    monkeypatch.setenv("GOOGLE_API_KEY", "must-not-leak")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-leak")
    monkeypatch.setenv("TOGETHER_API_KEY", "must-not-leak")
    monkeypatch.setenv("FIREWORKS_API_KEY", "must-not-leak")
    monkeypatch.setenv("MISTRAL_API_KEY", "must-not-leak")
    monkeypatch.setenv("COHERE_API_KEY", "must-not-leak")
    monkeypatch.setenv("GROQ_API_KEY", "must-not-leak")
    monkeypatch.setenv("XAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "must-not-leak")


def _five_outcome_runner(
    monkeypatch: Any,
    module: ModuleType,
    success_stdout: str,
) -> list[str]:
    outcomes = (
        SimpleNamespace(returncode=0, stdout="401 unauthorized", stderr=""),
        SimpleNamespace(returncode=0, stdout="weekly limit reached", stderr=""),
        SimpleNamespace(returncode=0, stdout=" \n", stderr=""),
        "timeout",
        SimpleNamespace(returncode=0, stdout=success_stdout, stderr=""),
    )
    seen_tokens: list[str] = []

    def _run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        env = kwargs["env"]
        seen_tokens.append(env["CLAUDE_CODE_OAUTH_TOKEN"])
        for key in (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "CLAUDE_CODE_USE_BEDROCK",
            "AWS_ACCESS_KEY_ID",
            "VERTEX_AI_PROJECT",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "DEEPSEEK_API_KEY",
            "TOGETHER_API_KEY",
            "FIREWORKS_API_KEY",
            "MISTRAL_API_KEY",
            "COHERE_API_KEY",
            "GROQ_API_KEY",
            "XAI_API_KEY",
            "PERPLEXITY_API_KEY",
        ):
            assert key not in env
        outcome = outcomes[len(seen_tokens) - 1]
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args[0] if args else "claude", timeout=1)
        return outcome

    monkeypatch.setattr(module.subprocess, "run", _run)
    return seen_tokens


def test_auto_verifier_reaches_slot_five_after_auth_quota_and_empty(
    monkeypatch: Any,
) -> None:
    module = _load_module(
        "apps/backend-rag/scripts/auto_verifier.py", "oauth_auto_verifier"
    )
    _install_five_slots(monkeypatch)
    module._VERIFIER_EXHAUSTED.clear()
    seen = _five_outcome_runner(
        monkeypatch,
        module,
        "VERDICT: FAITHFUL\nREASON: Grounded in the cited excerpt.",
    )

    result = module.call_claude_verifier("IM-001", "claim", "source")

    assert result.verdict == "FAITHFUL"
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_verified_generator_reaches_slot_five_after_auth_quota_and_empty(
    monkeypatch: Any,
) -> None:
    module = _load_module(
        "apps/backend-rag/scripts/verified_generator.py", "oauth_verified_generator"
    )
    _install_five_slots(monkeypatch)
    module._GEN_EXHAUSTED.clear()
    seen = _five_outcome_runner(
        monkeypatch,
        module,
        "Complete grounded guide [IM-001]",
    )

    output = module.generate_document(
        "immigration",
        "topic",
        {"IM-001": {"claim": "claim", "pasal_ref": "Article 1"}},
        "",
        "",
        "",
    )

    assert output == "Complete grounded guide [IM-001]"
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_image_style_reaches_slot_five_after_auth_quota_and_empty(
    monkeypatch: Any,
) -> None:
    module = _load_module(
        "apps/bali-intel-scraper/scripts/bz_image_style.py", "oauth_bz_image_style"
    )
    _install_five_slots(monkeypatch)
    module._IMG_EXHAUSTED_TOKENS.clear()
    expected = "A cinematic grounded visual concept with enough detail for rendering."
    seen = _five_outcome_runner(monkeypatch, module, expected)

    output = module._prompt_via_claude("Title", "visa", "Summary", "crisis")

    assert output == expected
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_dlq_reasoner_reaches_slot_five_after_auth_quota_and_empty(
    monkeypatch: Any,
) -> None:
    module = _load_module("scripts/dlq_autopilot.py", "oauth_dlq_autopilot")
    _install_five_slots(monkeypatch)
    module._EXHAUSTED_TOKENS.clear()
    success = json.dumps(
        {
            "fix_type": "config",
            "fix_instruction": "Restore the missing runtime setting.",
            "confidence": 0.9,
            "needs_code_change": False,
        }
    )
    seen = _five_outcome_runner(monkeypatch, module, success)

    result = module.claude_reason(
        {
            "job": "test-job",
            "error_summary": "A sufficiently detailed test failure",
            "log_tail": "",
            "files_implicated": [],
        }
    )

    assert result is not None
    assert result["_token_used"] == "token_5"
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_mata_runtime_reaches_slot_five_after_auth_quota_and_empty(
    monkeypatch: Any,
) -> None:
    module = _load_module(
        "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
        "oauth_mata_cli_runtime",
    )
    _install_five_slots(monkeypatch)
    module.reset_exhausted_tokens()
    outcomes = (
        SimpleNamespace(returncode=0, stdout="401 unauthorized", stderr=""),
        SimpleNamespace(returncode=0, stdout="weekly limit reached", stderr=""),
        SimpleNamespace(returncode=0, stdout=" \n", stderr=""),
        "timeout",
        SimpleNamespace(returncode=0, stdout="slot-five-success", stderr=""),
    )
    seen: list[str] = []

    def _run_subprocess(
        cmd: list[str],
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> SimpleNamespace:
        assert env is not None
        assert "ANTHROPIC_API_KEY" not in env
        seen.append(env["CLAUDE_CODE_OAUTH_TOKEN"])
        outcome = outcomes[len(seen) - 1]
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout=timeout)
        return outcome

    runtime = module.CLIRuntime(model="claude")
    monkeypatch.setattr(runtime, "_run_subprocess", _run_subprocess)

    result = runtime.invoke("safe test prompt")

    assert result.success
    assert result.output == "slot-five-success"
    assert result.token_used == "CLAUDE_CODE_OAUTH_TOKEN_5"
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_daily_briefing_reaches_slot_five(
    monkeypatch: Any,
) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "apps/mata-garuda"))
    module = _load_module(
        "apps/mata-garuda/mata_garuda/agents/daily_briefing_agent.py",
        "oauth_daily_briefing",
    )
    _install_five_slots(monkeypatch)
    seen = _five_outcome_runner(monkeypatch, module, "two-line summary")

    output = module._tldr_claude("Title", "Body")

    assert output == "two-line summary"
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_weekly_digest_reaches_slot_five(
    monkeypatch: Any,
) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "apps/mata-garuda"))
    module = _load_module(
        "apps/mata-garuda/mata_garuda/agents/weekly_digest_agent.py",
        "oauth_weekly_digest",
    )
    _install_five_slots(monkeypatch)
    seen = _five_outcome_runner(monkeypatch, module, "weekly analysis")

    output = module.call_claude("safe prompt")

    assert output == "weekly analysis"
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_ai_digest_reaches_slot_five(
    monkeypatch: Any,
) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "apps/mata-garuda"))
    module = _load_module(
        "apps/mata-garuda/scripts/run_ai_digest.py",
        "oauth_ai_digest",
    )
    _install_five_slots(monkeypatch)
    seen = _five_outcome_runner(monkeypatch, module, "AI digest")

    output = module.call_claude_synthesis("safe prompt")

    assert output == "AI digest"
    assert seen == [f"sentinel-{slot}" for slot in range(1, 6)]


def test_mata_keychain_fallbacks_strip_paid_api_key(
    monkeypatch: Any,
) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "apps/mata-garuda"))
    for slot in range(1, 6):
        monkeypatch.delenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    seen_envs: list[dict[str, str]] = []

    def _run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        env = kwargs["env"]
        assert "ANTHROPIC_API_KEY" not in env
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in env
        seen_envs.append(env)
        return SimpleNamespace(returncode=0, stdout="keychain-success", stderr="")

    daily = _load_module(
        "apps/mata-garuda/mata_garuda/agents/daily_briefing_agent.py",
        "oauth_daily_briefing_keychain",
    )
    weekly = _load_module(
        "apps/mata-garuda/mata_garuda/agents/weekly_digest_agent.py",
        "oauth_weekly_digest_keychain",
    )
    digest = _load_module(
        "apps/mata-garuda/scripts/run_ai_digest.py",
        "oauth_ai_digest_keychain",
    )
    monkeypatch.setattr(subprocess, "run", _run)

    assert daily._tldr_claude("Title", "Body") == "keychain-success"
    assert weekly.call_claude("safe prompt") == "keychain-success"
    assert digest.call_claude_synthesis("safe prompt") == "keychain-success"
    assert len(seen_envs) == 3


def _child_environment_snapshot(
    env: dict[str, str],
    keys: tuple[str, ...],
) -> dict[str, str | None]:
    """Inspect the actual environment inherited by a real child process."""
    code = (
        "import json, os, sys; "
        "keys=json.loads(sys.argv[1]); "
        "print(json.dumps({key: os.environ.get(key) for key in keys}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, json.dumps(keys)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_python_claude_consumers_isolate_actual_child_environments(
    monkeypatch: Any,
) -> None:
    _install_five_slots(monkeypatch)
    modules_and_builders = (
        (
            _load_module(
                "apps/backend-rag/scripts/auto_verifier.py",
                "oauth_env_auto_verifier",
            ),
            "_verifier_oauth_env",
        ),
        (
            _load_module(
                "apps/backend-rag/scripts/verified_generator.py",
                "oauth_env_verified_generator",
            ),
            "_gen_oauth_env",
        ),
        (
            _load_module(
                "apps/bali-intel-scraper/scripts/bz_image_style.py",
                "oauth_env_bz_image_style",
            ),
            "_img_oauth_env",
        ),
        (
            _load_module(
                "scripts/dlq_autopilot.py",
                "oauth_env_dlq_autopilot",
            ),
            "_claude_oauth_env",
        ),
        (
            _load_module(
                "apps/evaluator/nlm_deep_research/t4_monitor.py",
                "oauth_env_t4_monitor",
            ),
            "_oauth_cli_env",
        ),
        (
            _load_module(
                "scripts/zantara-gateway/claude_client.py",
                "oauth_env_gateway",
            ),
            "_oauth_cli_env",
        ),
    )
    keys = (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "CLAUDE_CODE_OAUTH_TOKEN_5",
        "CLAUDE_CODE_USE_BEDROCK",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "VERTEX_AI_PROJECT",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
        "MISTRAL_API_KEY",
        "COHERE_API_KEY",
        "GROQ_API_KEY",
        "XAI_API_KEY",
        "PERPLEXITY_API_KEY",
    )

    for module, builder_name in modules_and_builders:
        child = _child_environment_snapshot(
            getattr(module, builder_name)("selected-seat"),
            keys,
        )
        assert child["CLAUDE_CODE_OAUTH_TOKEN"] == "selected-seat"
        assert all(
            value is None
            for key, value in child.items()
            if key != "CLAUDE_CODE_OAUTH_TOKEN"
        ), f"{module.__name__} leaked credentials: {child}"

    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
    vision = importlib.import_module("wr2_html_renderer.claude_vision")
    child = _child_environment_snapshot(
        vision._oauth_cli_env(dict(os.environ), "selected-seat"),
        keys,
    )
    assert child["CLAUDE_CODE_OAUTH_TOKEN"] == "selected-seat"
    assert all(
        value is None
        for key, value in child.items()
        if key != "CLAUDE_CODE_OAUTH_TOKEN"
    ), f"claude_vision leaked credentials: {child}"


def test_mata_provider_environments_retain_only_selected_provider_credentials(
    monkeypatch: Any,
) -> None:
    module = _load_module(
        "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
        "oauth_env_mata_runtime",
    )
    _install_five_slots(monkeypatch)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/google.json")
    monkeypatch.setenv("CLOUD_ML_REGION", "asia-southeast2")
    keys = (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "ANTHROPIC_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "CLOUD_ML_REGION",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
    )

    claude_child = _child_environment_snapshot(
        module.provider_cli_env("claude", "selected-seat"),
        keys,
    )
    assert claude_child["CLAUDE_CODE_OAUTH_TOKEN"] == "selected-seat"
    assert all(
        value is None
        for key, value in claude_child.items()
        if key != "CLAUDE_CODE_OAUTH_TOKEN"
    )

    agy_child = _child_environment_snapshot(
        module.provider_cli_env("agy"),
        keys,
    )
    assert agy_child["GOOGLE_APPLICATION_CREDENTIALS"] == "/tmp/google.json"
    assert agy_child["CLOUD_ML_REGION"] == "asia-southeast2"
    assert agy_child["GOOGLE_API_KEY"] == "must-not-leak"
    assert agy_child["GEMINI_API_KEY"] == "must-not-leak"
    assert all(
        agy_child[key] is None
        for key in (
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN_1",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "DEEPSEEK_API_KEY",
        )
    )

    codex_child = _child_environment_snapshot(
        module.provider_cli_env("codex"),
        keys,
    )
    assert codex_child["OPENAI_API_KEY"] == "must-not-leak"
    assert all(
        codex_child[key] is None
        for key in (
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN_1",
            "ANTHROPIC_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "CLOUD_ML_REGION",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "DEEPSEEK_API_KEY",
        )
    )


def test_python_retry_classifiers_are_guilty_only_for_diagnostics() -> None:
    modules_and_classifiers = (
        (
            _load_module(
                "apps/backend-rag/scripts/auto_verifier.py",
                "oauth_classifier_auto_verifier",
            ),
            "_verifier_retry_reason",
        ),
        (
            _load_module(
                "apps/backend-rag/scripts/verified_generator.py",
                "oauth_classifier_verified_generator",
            ),
            "_gen_retry_reason",
        ),
        (
            _load_module(
                "apps/bali-intel-scraper/scripts/bz_image_style.py",
                "oauth_classifier_bz_image_style",
            ),
            "_img_retry_reason",
        ),
        (
            _load_module(
                "scripts/dlq_autopilot.py",
                "oauth_classifier_dlq_autopilot",
            ),
            "_retry_reason",
        ),
        (
            _load_module(
                "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
                "oauth_classifier_mata_runtime",
            ),
            "classify_claude_retry",
        ),
    )
    success_envelope = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "result": "Explain quota planning without changing accounts.",
        }
    )
    error_envelope = json.dumps(
        {
            "type": "result",
            "subtype": "error",
            "result": "weekly limit reached",
        }
    )

    for module, classifier_name in modules_and_classifiers:
        classify = getattr(module, classifier_name)
        assert classify("quota planning is part of this valid report", "") is None
        assert classify(success_envelope, "") is None
        assert classify("weekly limit reached", "") is not None
        assert classify(error_envelope, "") is not None
        assert classify("valid answer", "warning: quota exhausted") is not None

    t4 = _load_module(
        "apps/evaluator/nlm_deep_research/t4_monitor.py",
        "oauth_classifier_t4_monitor",
    )
    assert not t4._claude_retryable(
        "quota planning is part of this valid report",
        "",
    )
    assert not t4._claude_retryable(success_envelope, "")
    assert t4._claude_retryable("weekly limit reached", "")
    assert t4._claude_retryable(error_envelope, "")
    assert t4._claude_retryable("valid answer", "warning: quota exhausted")

    vision = importlib.import_module("wr2_html_renderer.claude_vision")
    success_payload = json.loads(success_envelope)
    error_payload = json.loads(error_envelope)
    assert (
        vision._vision_retry_reason(
            success_payload,
            success_envelope,
            "",
        )
        is None
    )
    assert (
        vision._vision_retry_reason(
            error_payload,
            error_envelope,
            "",
        )
        == "rate_limit"
    )
    assert (
        vision._vision_retry_reason(
            None,
            "quota planning is part of this valid report",
            "",
        )
        is None
    )
    assert (
        vision._vision_retry_reason(
            None,
            "valid answer",
            "warning: quota exhausted",
        )
        == "rate_limit"
    )


def test_all_python_token_chains_deduplicate_values_before_budgeting(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_3", "other")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_4", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_5", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "same")
    modules_and_chains = (
        (
            _load_module(
                "apps/backend-rag/scripts/auto_verifier.py",
                "oauth_chain_auto_verifier",
            ),
            "_verifier_token_chain",
        ),
        (
            _load_module(
                "apps/backend-rag/scripts/verified_generator.py",
                "oauth_chain_verified_generator",
            ),
            "_gen_token_chain",
        ),
        (
            _load_module(
                "apps/bali-intel-scraper/scripts/bz_image_style.py",
                "oauth_chain_bz_image_style",
            ),
            "_load_img_token_chain",
        ),
        (
            _load_module(
                "scripts/dlq_autopilot.py",
                "oauth_chain_dlq_autopilot",
            ),
            "_load_token_chain",
        ),
        (
            _load_module(
                "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
                "oauth_chain_mata_runtime",
            ),
            "claude_token_chain",
        ),
        (
            _load_module(
                "apps/evaluator/nlm_deep_research/t4_monitor.py",
                "oauth_chain_t4_monitor",
            ),
            "_claude_token_chain",
        ),
        (
            _load_module(
                "scripts/zantara-gateway/claude_client.py",
                "oauth_chain_gateway",
            ),
            "_token_chain",
        ),
    )

    for module, chain_name in modules_and_chains:
        values = [value for _, value in getattr(module, chain_name)()]
        assert values == ["same", "other", ""], module.__name__

    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
    vision = importlib.import_module("wr2_html_renderer.claude_vision")
    values = [
        value
        for _, value in vision._vision_token_chain(
            {
                "CLAUDE_CODE_OAUTH_TOKEN_1": "same",
                "CLAUDE_CODE_OAUTH_TOKEN_2": "same",
                "CLAUDE_CODE_OAUTH_TOKEN_3": "other",
                "CLAUDE_CODE_OAUTH_TOKEN": "same",
            }
        )
    ]
    assert values == ["same", "other", ""]


def test_mata_direct_callers_accept_valid_quota_prose_without_rotation(
    monkeypatch: Any,
) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "apps/mata-garuda"))
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "first-seat")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "second-seat")
    for slot in (3, 4, 5):
        monkeypatch.delenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    callers = (
        (
            _load_module(
                "apps/mata-garuda/mata_garuda/agents/daily_briefing_agent.py",
                "oauth_innocence_daily_briefing",
            ),
            lambda module: module._tldr_claude("Title", "Body"),
        ),
        (
            _load_module(
                "apps/mata-garuda/mata_garuda/agents/weekly_digest_agent.py",
                "oauth_innocence_weekly_digest",
            ),
            lambda module: module.call_claude("safe prompt"),
        ),
        (
            _load_module(
                "apps/mata-garuda/scripts/run_ai_digest.py",
                "oauth_innocence_ai_digest",
            ),
            lambda module: module.call_claude_synthesis("safe prompt"),
        ),
    )

    for module, invoke in callers:
        seen: list[str] = []

        def _run(*args: Any, **kwargs: Any) -> SimpleNamespace:
            seen.append(kwargs["env"]["CLAUDE_CODE_OAUTH_TOKEN"])
            return SimpleNamespace(
                returncode=0,
                stdout="Valid guidance about quota planning.",
                stderr="",
            )

        monkeypatch.setattr(module.subprocess, "run", _run)
        assert "quota planning" in invoke(module)
        assert seen == ["first-seat"]


def _write_fake_claude(path: Path) -> None:
    path.write_text(
        """#!/bin/bash
set -u
for credential_name in \
  CLAUDE_CODE_OAUTH_TOKEN_1 CLAUDE_CODE_OAUTH_TOKEN_2 \
  CLAUDE_CODE_OAUTH_TOKEN_3 CLAUDE_CODE_OAUTH_TOKEN_4 \
  CLAUDE_CODE_OAUTH_TOKEN_5 CLAUDE_CODE_USE_BEDROCK \
  ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL \
  AWS_TEST_SENTINEL VERTEX_AI_TEST_SENTINEL OPENAI_API_KEY \
  OPENROUTER_API_KEY GEMINI_API_KEY GOOGLE_API_KEY DEEPSEEK_API_KEY \
  TOGETHER_API_KEY FIREWORKS_API_KEY MISTRAL_API_KEY COHERE_API_KEY \
  GROQ_API_KEY XAI_API_KEY PERPLEXITY_API_KEY
do
  [ -z "${!credential_name:-}" ] || exit 20
done
case "${CLAUDE_CODE_OAUTH_TOKEN:-keychain}" in
  sentinel-1) echo "401 unauthorized" >&2; exit 1 ;;
  sentinel-2) echo "weekly limit reached" >&2; exit 1 ;;
  sentinel-3) exit 0 ;;
  sentinel-4) echo "quota exhausted" >&2; exit 1 ;;
  sentinel-5)
    [ -z "${ANTHROPIC_API_KEY:-}" ] || exit 9
    [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] || exit 10
    [ -z "${ANTHROPIC_BASE_URL:-}" ] || exit 11
    [ -z "${AWS_TEST_SENTINEL:-}" ] || exit 12
    [ -z "${VERTEX_AI_TEST_SENTINEL:-}" ] || exit 13
    echo "slot-five-success"
    exit 0
    ;;
  *) echo "unexpected account" >&2; exit 7 ;;
esac
""",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _cross_provider_shell_sentinels() -> dict[str, str]:
    return {
        "CLAUDE_CODE_USE_BEDROCK": "1",
        "OPENAI_API_KEY": "must-not-leak",
        "OPENROUTER_API_KEY": "must-not-leak",
        "GEMINI_API_KEY": "must-not-leak",
        "GOOGLE_API_KEY": "must-not-leak",
        "DEEPSEEK_API_KEY": "must-not-leak",
        "TOGETHER_API_KEY": "must-not-leak",
        "FIREWORKS_API_KEY": "must-not-leak",
        "MISTRAL_API_KEY": "must-not-leak",
        "COHERE_API_KEY": "must-not-leak",
        "GROQ_API_KEY": "must-not-leak",
        "XAI_API_KEY": "must-not-leak",
        "PERPLEXITY_API_KEY": "must-not-leak",
    }


def _write_fake_claude_legacy_success(path: Path) -> None:
    path.write_text(
        """#!/bin/bash
set -u
[ -z "${ANTHROPIC_API_KEY:-}" ] || exit 9
[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] || exit 10
[ -z "${AWS_TEST_SENTINEL:-}" ] || exit 11
token="${CLAUDE_CODE_OAUTH_TOKEN:-keychain}"
echo "$token" >> "$OAUTH_TRACE_FILE"
case "$token" in
  sentinel-1|sentinel-2|sentinel-3|sentinel-4|sentinel-5)
    echo "weekly limit reached" >&2
    exit 1
    ;;
  legacy-sentinel)
    echo "legacy-success"
    exit 0
    ;;
  *) echo "unexpected account" >&2; exit 7 ;;
esac
""",
        encoding="utf-8",
    )
    path.chmod(0o700)


def test_ai_dispatch_shell_reaches_slot_five(
    monkeypatch: Any, tmp_path: Path
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    _write_fake_claude(fake_claude)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CLAUDE_CODE_OAUTH_TOKEN_1": "sentinel-1",
            "CLAUDE_CODE_OAUTH_TOKEN_2": "sentinel-2",
            "CLAUDE_CODE_OAUTH_TOKEN_3": "sentinel-3",
            "CLAUDE_CODE_OAUTH_TOKEN_4": "sentinel-4",
            "CLAUDE_CODE_OAUTH_TOKEN_5": "sentinel-5",
            "ANTHROPIC_API_KEY": "must-not-leak",
            "ANTHROPIC_AUTH_TOKEN": "must-not-leak",
            "ANTHROPIC_BASE_URL": "https://must-not-leak.invalid",
            "AWS_TEST_SENTINEL": "must-not-leak",
            "VERTEX_AI_TEST_SENTINEL": "must-not-leak",
        }
    )
    env.update(_cross_provider_shell_sentinels())
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "scripts/ai-dispatch.sh"),
            "claude-explain",
            "Explain this harmless test.",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "slot-five-success" in result.stdout


def test_ai_dispatch_shell_tries_legacy_before_keychain(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    _write_fake_claude_legacy_success(fake_claude)
    trace_file = tmp_path / "oauth-trace.txt"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CLAUDE_CODE_OAUTH_TOKEN_1": "sentinel-1",
            "CLAUDE_CODE_OAUTH_TOKEN_2": "sentinel-2",
            "CLAUDE_CODE_OAUTH_TOKEN_3": "sentinel-3",
            "CLAUDE_CODE_OAUTH_TOKEN_4": "sentinel-4",
            "CLAUDE_CODE_OAUTH_TOKEN_5": "sentinel-5",
            "CLAUDE_CODE_OAUTH_TOKEN": "legacy-sentinel",
            "ANTHROPIC_API_KEY": "must-not-leak",
            "ANTHROPIC_AUTH_TOKEN": "must-not-leak",
            "AWS_TEST_SENTINEL": "must-not-leak",
            "OAUTH_TRACE_FILE": str(trace_file),
        }
    )
    env.update(_cross_provider_shell_sentinels())

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "scripts/ai-dispatch.sh"),
            "claude-explain",
            "Explain this harmless legacy fallback test.",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "legacy-success" in result.stdout
    assert trace_file.read_text(encoding="utf-8").splitlines() == [
        "sentinel-1",
        "sentinel-2",
        "sentinel-3",
        "sentinel-4",
        "sentinel-5",
        "legacy-sentinel",
    ]


def test_wr2_metrics_wrapper_declares_real_account_rotation() -> None:
    source = (
        REPO_ROOT
        / "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh"
    ).read_text(encoding="utf-8")

    assert "run_claude_account" in source
    assert (
        "CLAUDE_CODE_OAUTH_TOKEN_1 CLAUDE_CODE_OAUTH_TOKEN_2 "
        "CLAUDE_CODE_OAUTH_TOKEN_3 CLAUDE_CODE_OAUTH_TOKEN_4 "
        "CLAUDE_CODE_OAUTH_TOKEN_5"
    ) in source
    assert "returned empty output" not in source or "grep -q '[^[:space:]]'" in source
    assert "ANTHROPIC_*" in source


def test_wr2_metrics_wrapper_reaches_slot_five(tmp_path: Path) -> None:
    fake_claude = tmp_path / "claude"
    _write_fake_claude(fake_claude)
    fake_home = tmp_path / "home"
    queue_dir = (
        fake_home
        / "nuzantara/apps/war-room/output/queue"
    )
    queue_dir.mkdir(parents=True)
    items = [
        {
            "state": "published",
            "engagement_metrics": {"likes": index},
        }
        for index in range(10)
    ]
    (queue_dir / "human-review-queue.json").write_text(
        json.dumps({"items": items}), encoding="utf-8"
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(fake_home),
            "WR2_IG_CLAUDE_BIN": str(fake_claude),
            "WR2_IG_METRICS_TIMEOUT_SECS": "350",
            "WR2_IG_METRICS_POLL_SECS": "1",
            "CLAUDE_CODE_OAUTH_TOKEN_1": "sentinel-1",
            "CLAUDE_CODE_OAUTH_TOKEN_2": "sentinel-2",
            "CLAUDE_CODE_OAUTH_TOKEN_3": "sentinel-3",
            "CLAUDE_CODE_OAUTH_TOKEN_4": "sentinel-4",
            "CLAUDE_CODE_OAUTH_TOKEN_5": "sentinel-5",
            "ANTHROPIC_API_KEY": "must-not-leak",
            "ANTHROPIC_AUTH_TOKEN": "must-not-leak",
            "ANTHROPIC_BASE_URL": "https://must-not-leak.invalid",
            "AWS_TEST_SENTINEL": "must-not-leak",
            "VERTEX_AI_TEST_SENTINEL": "must-not-leak",
        }
    )
    env.update(_cross_provider_shell_sentinels())
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

    result = subprocess.run(
        [
            "bash",
            str(
                REPO_ROOT
                / "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    log = (fake_home / "logs/wr2-ig-metrics-analyst.log").read_text(
        encoding="utf-8"
    )
    assert result.returncode == 0, result.stderr
    assert "used: CLAUDE_CODE_OAUTH_TOKEN_5" in log
    assert "total=350s max_attempts=7 account_timeout=50s" in log


def _write_fake_claude_with_mode(path: Path) -> None:
    path.write_text(
        """#!/bin/bash
set -u
token="${CLAUDE_CODE_OAUTH_TOKEN:-keychain}"
echo "$token" >> "$OAUTH_TRACE_FILE"
for credential_name in \
  CLAUDE_CODE_OAUTH_TOKEN_1 CLAUDE_CODE_OAUTH_TOKEN_2 \
  CLAUDE_CODE_OAUTH_TOKEN_3 CLAUDE_CODE_OAUTH_TOKEN_4 \
  CLAUDE_CODE_OAUTH_TOKEN_5 CLAUDE_CODE_USE_BEDROCK \
  ANTHROPIC_API_KEY AWS_TEST_SENTINEL VERTEX_AI_TEST_SENTINEL \
  OPENAI_API_KEY OPENROUTER_API_KEY GEMINI_API_KEY GOOGLE_API_KEY \
  DEEPSEEK_API_KEY TOGETHER_API_KEY FIREWORKS_API_KEY MISTRAL_API_KEY \
  COHERE_API_KEY GROQ_API_KEY XAI_API_KEY PERPLEXITY_API_KEY
do
  [ -z "${!credential_name:-}" ] || exit 20
done
case "${FAKE_CLAUDE_MODE:-valid}" in
  valid)
    echo "A valid operational report about quota planning."
    exit 0
    ;;
  retry)
    echo "quota exhausted"
    exit 0
    ;;
  dedupe)
    if [ "$token" = "duplicate-seat" ]; then
      echo "weekly limit reached" >&2
      exit 1
    fi
    echo "dedupe-success"
    exit 0
    ;;
esac
""",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _prepare_wr2_test_home(fake_home: Path) -> None:
    queue_dir = fake_home / "nuzantara/apps/war-room/output/queue"
    queue_dir.mkdir(parents=True)
    items = [
        {
            "state": "published",
            "engagement_metrics": {"likes": index},
        }
        for index in range(10)
    ]
    (queue_dir / "human-review-queue.json").write_text(
        json.dumps({"items": items}),
        encoding="utf-8",
    )


def _write_timeout_passthrough(path: Path) -> None:
    path.write_text(
        "#!/bin/bash\nshift\nexec \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _base_shell_env(
    fake_claude: Path,
    trace_file: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_CODE_OAUTH_TOKEN_1": "first-seat",
            "CLAUDE_CODE_OAUTH_TOKEN_2": "second-seat",
            "ANTHROPIC_API_KEY": "must-not-leak",
            "AWS_TEST_SENTINEL": "must-not-leak",
            "VERTEX_AI_TEST_SENTINEL": "must-not-leak",
            "OAUTH_TRACE_FILE": str(trace_file),
            "WR2_IG_CLAUDE_BIN": str(fake_claude),
            "CRON_AGENT_CLAUDE_BIN": str(fake_claude),
        }
    )
    env.update(_cross_provider_shell_sentinels())
    for slot in (3, 4, 5):
        env.pop(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", None)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


def test_ai_dispatch_accepts_valid_quota_prose_without_rotation(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    _write_fake_claude_with_mode(fake_claude)
    trace = tmp_path / "trace"
    env = _base_shell_env(fake_claude, trace)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "scripts/ai-dispatch.sh"),
            "claude-explain",
            "Explain a harmless topic.",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "valid operational report about quota planning" in result.stdout
    assert trace.read_text(encoding="utf-8").splitlines() == ["first-seat"]


def test_wr2_wrapper_accepts_valid_quota_prose_without_rotation(
    tmp_path: Path,
) -> None:
    fake_claude = tmp_path / "claude"
    _write_fake_claude_with_mode(fake_claude)
    trace = tmp_path / "trace"
    fake_home = tmp_path / "home"
    _prepare_wr2_test_home(fake_home)
    env = _base_shell_env(fake_claude, trace)
    env.update(
        {
            "HOME": str(fake_home),
            "WR2_IG_METRICS_TIMEOUT_SECS": "20",
            "WR2_IG_METRICS_ACCOUNT_TIMEOUT_SECS": "5",
            "WR2_IG_METRICS_POLL_SECS": "1",
        }
    )

    result = subprocess.run(
        [
            "bash",
            str(
                REPO_ROOT
                / "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == ["first-seat"]


def test_cron_agent_accepts_valid_quota_prose_without_rotation(
    tmp_path: Path,
) -> None:
    fake_claude = tmp_path / "claude"
    _write_fake_claude_with_mode(fake_claude)
    trace = tmp_path / "trace"
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Harmless test prompt.", encoding="utf-8")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_timeout = tmp_path / "timeout"
    _write_timeout_passthrough(fake_timeout)
    env = _base_shell_env(fake_claude, trace)
    env.update(
        {
            "HOME": str(fake_home),
            "CRON_AGENT_HOME": str(fake_home),
            "CRON_AGENT_TIMEOUT": "10",
            "CRON_AGENT_TIMEOUT_BIN": str(fake_timeout),
        }
    )

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "infra/launchagents/wrappers/cron-agent.sh"),
            "agent",
            "quota-innocence",
            str(prompt),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    log = (fake_home / "logs/cron-agent/quota-innocence.log").read_text(
        encoding="utf-8"
    )

    assert result.returncode == 0, result.stderr
    assert "] [quota-innocence] OK " in log
    assert trace.read_text(encoding="utf-8").splitlines() == ["first-seat"]


def test_cron_agent_all_retryable_attempts_fail_and_dedupe(
    tmp_path: Path,
) -> None:
    fake_claude = tmp_path / "claude"
    _write_fake_claude_with_mode(fake_claude)
    trace = tmp_path / "trace"
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Harmless test prompt.", encoding="utf-8")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_timeout = tmp_path / "timeout"
    _write_timeout_passthrough(fake_timeout)
    env = _base_shell_env(fake_claude, trace)
    env.update(
        {
            "HOME": str(fake_home),
            "CRON_AGENT_HOME": str(fake_home),
            "CRON_AGENT_TIMEOUT": "10",
            "CRON_AGENT_TIMEOUT_BIN": str(fake_timeout),
            "FAKE_CLAUDE_MODE": "retry",
            "CLAUDE_CODE_OAUTH_TOKEN_1": "duplicate-seat",
            "CLAUDE_CODE_OAUTH_TOKEN_2": "duplicate-seat",
            "CLAUDE_CODE_OAUTH_TOKEN_3": "other-seat",
            "CLAUDE_CODE_OAUTH_TOKEN": "duplicate-seat",
        }
    )

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "infra/launchagents/wrappers/cron-agent.sh"),
            "agent",
            "quota-guilt",
            str(prompt),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    log = (fake_home / "logs/cron-agent/quota-guilt.log").read_text(
        encoding="utf-8"
    )

    assert result.returncode != 0
    assert "] [quota-guilt] OK " not in log
    assert trace.read_text(encoding="utf-8").splitlines() == [
        "duplicate-seat",
        "other-seat",
        "keychain",
    ]


def test_ai_dispatch_deduplicates_numbered_and_legacy_tokens(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    _write_fake_claude_with_mode(fake_claude)
    trace = tmp_path / "trace"
    env = _base_shell_env(fake_claude, trace)
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "FAKE_CLAUDE_MODE": "dedupe",
            "CLAUDE_CODE_OAUTH_TOKEN_1": "duplicate-seat",
            "CLAUDE_CODE_OAUTH_TOKEN_2": "duplicate-seat",
            "CLAUDE_CODE_OAUTH_TOKEN_3": "unique-seat",
            "CLAUDE_CODE_OAUTH_TOKEN": "duplicate-seat",
        }
    )

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "scripts/ai-dispatch.sh"),
            "claude-explain",
            "Explain a harmless topic.",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == [
        "duplicate-seat",
        "unique-seat",
    ]


def _write_descendant_claude(path: Path) -> None:
    path.write_text(
        """#!/bin/bash
set -u
(
  trap '' TERM
  sleep 60
) &
descendant=$!
echo "$descendant" > "$DESCENDANT_PID_FILE"
wait "$descendant"
""",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _assert_pid_disappears(pid_file: Path) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not pid_file.exists():
            time.sleep(0.02)
            continue
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    pid = int(pid_file.read_text(encoding="utf-8").strip())
    raise AssertionError(f"descendant pid {pid} survived process-group cleanup")


def test_ai_dispatch_bash_timeout_kills_descendant_process_group(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    _write_descendant_claude(fake_claude)
    trace = tmp_path / "unused-trace"
    pid_file = tmp_path / "descendant.pid"
    env = _base_shell_env(fake_claude, trace)
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "DESCENDANT_PID_FILE": str(pid_file),
            "AI_DISPATCH_FORCE_BASH_TIMEOUT": "1",
            "AI_DISPATCH_CLAUDE_TIMEOUT": "1",
            "AI_DISPATCH_TIMEOUT_GRACE_SECS": "0",
        }
    )
    env.pop("CLAUDE_CODE_OAUTH_TOKEN_2", None)

    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "scripts/ai-dispatch.sh"),
            "claude-explain",
            "Explain a harmless topic.",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert pid_file.exists()
    _assert_pid_disappears(pid_file)


def test_wr2_timeout_kills_descendant_process_group(
    tmp_path: Path,
) -> None:
    fake_claude = tmp_path / "claude"
    _write_descendant_claude(fake_claude)
    trace = tmp_path / "unused-trace"
    pid_file = tmp_path / "descendant.pid"
    fake_home = tmp_path / "home"
    _prepare_wr2_test_home(fake_home)
    env = _base_shell_env(fake_claude, trace)
    env.update(
        {
            "HOME": str(fake_home),
            "DESCENDANT_PID_FILE": str(pid_file),
            "WR2_IG_METRICS_TIMEOUT_SECS": "1",
            "WR2_IG_METRICS_ACCOUNT_TIMEOUT_SECS": "1",
            "WR2_IG_METRICS_POLL_SECS": "1",
            "WR2_IG_METRICS_KILL_GRACE_SECS": "0",
        }
    )
    env.pop("CLAUDE_CODE_OAUTH_TOKEN_2", None)

    result = subprocess.run(
        [
            "bash",
            str(
                REPO_ROOT
                / "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert pid_file.exists()
    _assert_pid_disappears(pid_file)
