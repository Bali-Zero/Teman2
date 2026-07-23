"""Behavior tests for five-seat Claude OAuth rotation outside backend runtime."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
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


def _write_fake_claude(path: Path) -> None:
    path.write_text(
        """#!/bin/bash
set -u
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
    assert "ANTHROPIC_API_KEY" in source


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
