"""Hermetic regression tests for the canonical Claude subscription cascade."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import time
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CASCADE = REPO_ROOT / "infra/launchagents/wrappers/claude-cascade.sh"
TOKEN_VALUES = {
    "token1": "fixture-seat-one-secret",
    "token2": "fixture-seat-two-secret",
    "token3": "fixture-seat-three-secret",
    "token4": "fixture-seat-four-secret",
    "token5": "fixture-zero-team-secret",
    "legacy": "fixture-legacy-secret",
}


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _fake_fleet(
    tmp_path: Path,
    seat_bodies: dict[str, str],
    provider_bodies: dict[str, str] | None = None,
) -> tuple[Path, Path, dict[str, str]]:
    """Build one fake Claude binary that identifies only its selected token."""
    home = tmp_path / "home"
    temp_dir = tmp_path / "cascade-temp"
    temp_dir.mkdir()
    call_log = tmp_path / "calls.log"
    claude = home / ".local/share/mise/shims/claude"

    cases = "\n".join(
        f'  "{TOKEN_VALUES[label]}") label="{label}" ;;'
        for label in ("token1", "token2", "token3", "token4", "token5", "legacy")
    )
    actions = "\n".join(
        f'  "{label}") {seat_bodies[label]} ;;'
        for label in (
            "token1",
            "token2",
            "token3",
            "token4",
            "token5",
            "legacy",
            "keychain",
        )
    )
    _write_executable(
        claude,
        (
            'token="${CLAUDE_CODE_OAUTH_TOKEN:-}"\n'
            'label="keychain"\n'
            'case "$token" in\n'
            f"{cases}\n"
            "esac\n"
            'for forbidden in CLAUDE_CODE_OAUTH_TOKEN_1 '
            "CLAUDE_CODE_OAUTH_TOKEN_2 CLAUDE_CODE_OAUTH_TOKEN_3 "
            "CLAUDE_CODE_OAUTH_TOKEN_4 CLAUDE_CODE_OAUTH_TOKEN_5 "
            "ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN "
            "ANTHROPIC_BASE_URL AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY "
            "VERTEX_AI_PROJECT GOOGLE_APPLICATION_CREDENTIALS "
            "CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX OPENAI_API_KEY "
            "OPENROUTER_API_KEY GEMINI_API_KEY GOOGLE_API_KEY DEEPSEEK_API_KEY "
            "TOGETHER_API_KEY FIREWORKS_API_KEY MISTRAL_API_KEY COHERE_API_KEY "
            "GROQ_API_KEY XAI_API_KEY PERPLEXITY_API_KEY KIMI_API_KEY "
            "MOONSHOT_API_KEY OPENAI_ORG_ID GEMINI_ACCESS_TOKEN "
            "GOOGLE_OAUTH_ACCESS_TOKEN; do\n"
            '  eval "value=\\${$forbidden:-}"\n'
            '  [ -n "$value" ] && printf "LEAK:%s\\n" "$forbidden" >> "$CALL_LOG"\n'
            "done\n"
            'printf "%s:%s\\n" "$label" "${CLAUDE_CONFIG_DIR:-unset}" '
            '>> "$CALL_LOG"\n'
            'case "$label" in\n'
            f"{actions}\n"
            "esac"
        ),
    )

    _write_executable(
        home / ".local/bin/claude-zero-team",
        (
            'printf "team-wrapper:%s\\n" "${CLAUDE_CONFIG_DIR:-unset}" '
            '>> "$CALL_LOG"\n'
            f"{seat_bodies.get('team-wrapper', 'exit 1')}"
        ),
    )
    provider_bodies = provider_bodies or {}
    credential_probe = (
        'for forbidden in CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN_1 '
        "CLAUDE_CODE_OAUTH_TOKEN_2 CLAUDE_CODE_OAUTH_TOKEN_3 "
        "CLAUDE_CODE_OAUTH_TOKEN_4 CLAUDE_CODE_OAUTH_TOKEN_5 "
        "ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL "
        "AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY VERTEX_AI_PROJECT "
        "GOOGLE_APPLICATION_CREDENTIALS CLAUDE_CODE_USE_BEDROCK "
        "CLAUDE_CODE_USE_VERTEX OPENAI_API_KEY OPENROUTER_API_KEY "
        "GEMINI_API_KEY GOOGLE_API_KEY DEEPSEEK_API_KEY TOGETHER_API_KEY "
        "FIREWORKS_API_KEY MISTRAL_API_KEY COHERE_API_KEY GROQ_API_KEY "
        "XAI_API_KEY PERPLEXITY_API_KEY KIMI_API_KEY MOONSHOT_API_KEY "
        "OPENAI_ORG_ID GEMINI_ACCESS_TOKEN GOOGLE_OAUTH_ACCESS_TOKEN; do\n"
        '  eval "value=\\${$forbidden:-}"\n'
        '  [ -n "$value" ] && printf "LEAK:%s:%s\\n" "$label" "$forbidden" '
        '>> "$CALL_LOG"\n'
        "done\n"
    )
    for label, path in {
        "agy": home / ".local/bin/agy",
        "kimi": home / ".kimi-code/bin/kimi",
        "codex": home / ".local/bin/codex",
        "ollama": home / ".local/bin/ollama",
    }.items():
        provider_body = provider_bodies.get(
            label,
            f'printf "unexpected-{label}\\n"',
        )
        _write_executable(
            path,
            f'label="{label}"\n'
            f"{credential_probe}"
            f'printf "nonclaude-{label}\\n" >> "$CALL_LOG"\n'
            f"{provider_body}",
        )

    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(temp_dir),
        "CALL_LOG": str(call_log),
        "CLAUDE_CODE_OAUTH_TOKEN_1": TOKEN_VALUES["token1"],
        "CLAUDE_CODE_OAUTH_TOKEN_2": TOKEN_VALUES["token2"],
        "CLAUDE_CODE_OAUTH_TOKEN_3": TOKEN_VALUES["token3"],
        "CLAUDE_CODE_OAUTH_TOKEN_4": TOKEN_VALUES["token4"],
        "CLAUDE_CODE_OAUTH_TOKEN_5": TOKEN_VALUES["token5"],
        "CLAUDE_CODE_OAUTH_TOKEN": TOKEN_VALUES["legacy"],
        "CLAUDE_CASCADE_OLLAMA_BIN": str(home / ".local/bin/ollama"),
    }
    return call_log, temp_dir, env


def _default_bodies() -> dict[str, str]:
    return {
        "token1": "exit 1",
        "token2": "exit 1",
        "token3": "exit 1",
        "token4": "exit 1",
        "token5": "exit 1",
        "legacy": "exit 1",
        "keychain": "exit 1",
        "team-wrapper": "exit 1",
    }


def _run_cascade(
    env: dict[str, str],
    *args: str,
    timeout: float = 10,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/zsh", str(CASCADE), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=timeout,
    )


def _labels(call_log: Path) -> list[str]:
    return [
        line.split(":", maxsplit=1)[0]
        for line in call_log.read_text(encoding="utf-8").splitlines()
        if not line.startswith("LEAK:")
    ]


def test_exit_zero_auth_quota_and_empty_rotate_to_later_seat(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies.update(
        {
            "token1": 'printf "authentication required\\n" >&2\nexit 0',
            "token2": 'printf "weekly limit reached\\n"\nexit 0',
            "token3": "exit 0",
            "token4": 'printf "seat-four-success\\n"\nexit 0',
        }
    )
    call_log, temp_dir, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(
        env,
        "hermetic prompt",
        "--claude-only",
        "--model",
        "claude-sonnet-5",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "seat-four-success\n"
    assert _labels(call_log) == ["token1", "token2", "token3", "token4"]
    assert "used: claude-token-4-env" in result.stderr
    assert list(temp_dir.iterdir()) == []


@pytest.mark.parametrize(
    "diagnostic",
    (
        "401 Unauthorized",
        "HTTP 401 Unauthorized",
        "token_revoked",
        "Error: refresh_token",
        "Invalid API key",
        "Invalid API key · Please run /login",
        "Not logged in · Please run /login",
        "Please run /login",
        "You are out of extra usage. Your limit will reset soon.",
        "You have hit your session limit · resets 11:20pm (Asia/Makassar)",
        "Error: 401",
        '{"error":{"type":"refresh_token_reused","message":"login again"}}',
        (
            '{"type":"error","error":{"type":"authentication_error",'
            '"message":"Invalid authentication credentials"}}'
        ),
        (
            'API Error: 401 {"type":"error","error":'
            '{"type":"authentication_error"}}'
        ),
    ),
)
def test_exit_zero_stdout_error_envelopes_rotate(
    tmp_path: Path,
    diagnostic: str,
) -> None:
    bodies = _default_bodies()
    bodies.update(
        {
            "token1": f"printf '%s\\n' '{diagnostic}'\nexit 0",
            "token2": 'printf "seat-two-success\\n"\nexit 0',
        }
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "seat-two-success\n"
    assert _labels(call_log) == ["token1", "token2"]


def test_exit_zero_innocent_stdout_may_discuss_auth_and_quota(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies["token1"] = (
        'printf "Guide: a 401 unauthorized response or quota exceeded message '
        'should trigger operator review.\\n"\n'
        "exit 0"
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Guide:")
    assert _labels(call_log) == ["token1"]
    assert "used: claude-token-1-env" in result.stderr


def test_exit_zero_weekly_limit_prose_is_not_a_false_positive(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies["token1"] = (
        'printf "Weekly limit reached for seat 2 on Sunday; operators should '
        'rotate usage manually.\\n"\n'
        "exit 0"
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Weekly limit reached for seat 2")
    assert _labels(call_log) == ["token1"]


@pytest.mark.parametrize(
    "answer",
    (
        "Invalid API key handling is documented in this operator guide.",
        "Invalid API key · Please run /login is the example this guide explains.",
        "Not logged in is a user-interface state covered by this runbook.",
        "You are out of extra usage is the banner this test describes.",
        (
            "You have hit your session limit · resets 11:20pm "
            "(Asia/Makassar) is the banner this guide explains."
        ),
    ),
)
def test_exit_zero_cli_banner_prefix_prose_is_not_a_false_positive(
    tmp_path: Path,
    answer: str,
) -> None:
    bodies = _default_bodies()
    bodies["token1"] = f"printf '%s\\n' '{answer}'\nexit 0"
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{answer}\n"
    assert _labels(call_log) == ["token1"]


def test_exit_zero_innocent_401_metrics_on_stderr_are_preserved(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies["token1"] = (
        'printf "Indexed 401 documents in 401 ms\\n" >&2\n'
        'printf "valid-success\\n"\n'
        "exit 0"
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "valid-success\n"
    assert _labels(call_log) == ["token1"]


def test_exit_zero_innocent_api_401_metrics_on_stderr_are_preserved(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies["token1"] = (
        'printf "API indexed 401 documents successfully\\n" >&2\n'
        'printf "valid-success\\n"\n'
        "exit 0"
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "valid-success\n"
    assert _labels(call_log) == ["token1"]


@pytest.mark.parametrize(
    "answer",
    (
        "Unauthorized access is a topic in this security guide.",
        "Quota exceeded is the condition this runbook explains.",
    ),
)
def test_exit_zero_innocent_stdout_may_begin_with_failure_term(
    tmp_path: Path,
    answer: str,
) -> None:
    bodies = _default_bodies()
    bodies["token1"] = f"printf '%s\\n' '{answer}'\nexit 0"
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{answer}\n"
    assert _labels(call_log) == ["token1"]


def test_explicit_order_reaches_team_then_legacy_then_keychain(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies["keychain"] = 'printf "keychain-success\\n"\nexit 0'
    call_log, _, env = _fake_fleet(tmp_path, bodies)

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "keychain-success\n"
    assert _labels(call_log) == [
        "token1",
        "token2",
        "token3",
        "token4",
        "token5",
        "legacy",
        "keychain",
    ]
    assert "used: claude-keychain" in result.stderr


def test_team_wrapper_is_only_used_when_explicit_team_token_is_absent(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies["team-wrapper"] = 'printf "protected-team-success\\n"\nexit 0'
    call_log, _, env = _fake_fleet(tmp_path, bodies)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN_5")

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "protected-team-success\n"
    assert _labels(call_log) == [
        "token1",
        "token2",
        "token3",
        "token4",
        "team-wrapper",
    ]
    assert "used: claude-token-5-team-wrapper" in result.stderr


def test_claude_only_never_crosses_provider_boundary_when_all_seats_fail(
    tmp_path: Path,
) -> None:
    call_log, _, env = _fake_fleet(tmp_path, _default_bodies())

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 1
    assert not any(label.startswith("nonclaude-") for label in _labels(call_log))
    assert result.stdout == ""
    assert "ALL CLAUDE SEATS FAILED" in result.stderr


def test_named_agent_fails_closed_before_cross_family_fallback(
    tmp_path: Path,
) -> None:
    call_log, _, env = _fake_fleet(tmp_path, _default_bodies())

    result = _run_cascade(env, "hermetic prompt", "--agent", "nb-curator")

    assert result.returncode == 1
    assert result.stdout == ""
    assert not any(label.startswith("nonclaude-") for label in _labels(call_log))
    assert "cannot be preserved cross-family" in result.stderr


def test_claude_specific_extra_args_fail_closed_before_cross_family(
    tmp_path: Path,
) -> None:
    call_log, _, env = _fake_fleet(tmp_path, _default_bodies())

    result = _run_cascade(
        env,
        "hermetic prompt",
        "--",
        "--dangerously-skip-permissions",
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert not any(label.startswith("nonclaude-") for label in _labels(call_log))
    assert "arguments cannot be preserved cross-family" in result.stderr


def test_attempt_timeout_rotates_to_next_seat(tmp_path: Path) -> None:
    bodies = _default_bodies()
    bodies.update(
        {
            "token1": "sleep 5\nexit 0",
            "token2": 'printf "after-timeout-success\\n"\nexit 0',
        }
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)
    env["CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC"] = "2"
    env["CLAUDE_CASCADE_DEADLINE_SEC"] = "8"

    started = time.monotonic()
    result = _run_cascade(env, "hermetic prompt", "--claude-only")
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    assert result.stdout == "after-timeout-success\n"
    assert _labels(call_log) == ["token1", "token2"]
    assert elapsed < 6


def test_fast_success_reaps_watchdog_without_orphaned_sleep(tmp_path: Path) -> None:
    sleep_pids = tmp_path / "sleep-pids.log"
    fake_bin = tmp_path / "fake-bin"
    _write_executable(
        fake_bin / "sleep",
        (
            f'printf "%s\\n" "$$" >> "{sleep_pids}"\n'
            'exec /bin/sleep "$@"'
        ),
    )
    bodies = _default_bodies()
    bodies["token1"] = '/bin/sleep 0.2\nprintf "fast-success\\n"\nexit 0'
    call_log, _, env = _fake_fleet(tmp_path, bodies)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC"] = "30"
    env["CLAUDE_CASCADE_DEADLINE_SEC"] = "35"

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "fast-success\n"
    assert _labels(call_log) == ["token1"]
    assert not sleep_pids.exists(), "watchdog spawned an orphanable sleep process"


def test_attempt_timeout_kills_provider_descendants(tmp_path: Path) -> None:
    survivor_file = tmp_path / "survivor.pid"
    bodies = _default_bodies()
    bodies.update(
        {
            "token1": (
                "(trap '' TERM; while :; do sleep 1; done) &\n"
                f'printf "%s\\n" "$!" > "{survivor_file}"\n'
                "wait"
            ),
            "token2": 'printf "after-group-kill\\n"\nexit 0',
        }
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)
    env["CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC"] = "2"
    env["CLAUDE_CASCADE_DEADLINE_SEC"] = "8"

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "after-group-kill\n"
    assert _labels(call_log) == ["token1", "token2"]
    survivor_pid = int(survivor_file.read_text(encoding="utf-8").strip())
    for _ in range(20):
        try:
            os.kill(survivor_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail(f"timed-out provider descendant survived: pid={survivor_pid}")


def test_global_deadline_prevents_later_seats_from_starting(tmp_path: Path) -> None:
    bodies = _default_bodies()
    bodies["token1"] = "sleep 5\nexit 0"
    call_log, temp_dir, env = _fake_fleet(tmp_path, bodies)
    env["CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC"] = "5"
    env["CLAUDE_CASCADE_DEADLINE_SEC"] = "2"

    started = time.monotonic()
    result = _run_cascade(env, "hermetic prompt", "--claude-only")
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert result.stdout == ""
    assert _labels(call_log) == ["token1"]
    assert elapsed < 6
    assert list(temp_dir.iterdir()) == []


def test_paid_anthropic_bedrock_and_vertex_environment_is_scrubbed(
    tmp_path: Path,
) -> None:
    bodies = _default_bodies()
    bodies["token1"] = 'printf "scrubbed-success\\n"\nexit 0'
    call_log, _, env = _fake_fleet(tmp_path, bodies)
    env.update(
        {
            "ANTHROPIC_API_KEY": "paid-secret",
            "ANTHROPIC_AUTH_TOKEN": "wrong-auth-path",
            "ANTHROPIC_BASE_URL": "https://paid.invalid",
            "AWS_ACCESS_KEY_ID": "aws-id",
            "AWS_SECRET_ACCESS_KEY": "aws-secret",
            "VERTEX_AI_PROJECT": "vertex-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/vertex.json",
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "CLAUDE_CODE_USE_VERTEX": "1",
            "OPENAI_API_KEY": "openai-paid",
            "OPENROUTER_API_KEY": "openrouter-paid",
            "GEMINI_API_KEY": "gemini-paid",
            "GOOGLE_API_KEY": "google-paid",
            "DEEPSEEK_API_KEY": "deepseek-paid",
            "TOGETHER_API_KEY": "together-paid",
            "FIREWORKS_API_KEY": "fireworks-paid",
            "MISTRAL_API_KEY": "mistral-paid",
            "COHERE_API_KEY": "cohere-paid",
            "GROQ_API_KEY": "groq-paid",
            "XAI_API_KEY": "xai-paid",
            "PERPLEXITY_API_KEY": "perplexity-paid",
            "KIMI_API_KEY": "kimi-paid",
            "MOONSHOT_API_KEY": "moonshot-paid",
            "OPENAI_ORG_ID": "openai-org",
            "GEMINI_ACCESS_TOKEN": "gemini-access",
            "GOOGLE_OAUTH_ACCESS_TOKEN": "google-oauth",
        }
    )

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "scrubbed-success\n"
    assert not any(
        line.startswith("LEAK:")
        for line in call_log.read_text(encoding="utf-8").splitlines()
    )
    for value in env.values():
        if "secret" in value or value.startswith("https://paid"):
            assert value not in result.stderr


@pytest.mark.parametrize("successful_provider", ("agy", "kimi", "codex", "ollama"))
def test_cross_family_provider_environments_are_hermetic(
    tmp_path: Path,
    successful_provider: str,
) -> None:
    provider_order = ("agy", "kimi", "codex", "ollama")
    provider_bodies = {
        label: (
            f'printf "provider-{label}-success\\n"\nexit 0'
            if label == successful_provider
            else "exit 1"
        )
        for label in provider_order
    }
    call_log, _, env = _fake_fleet(
        tmp_path,
        _default_bodies(),
        provider_bodies=provider_bodies,
    )
    env.update(
        {
            "ANTHROPIC_API_KEY": "anthropic-paid",
            "ANTHROPIC_AUTH_TOKEN": "anthropic-oauth-ambient",
            "OPENAI_API_KEY": "openai-paid",
            "OPENROUTER_API_KEY": "openrouter-paid",
            "GEMINI_API_KEY": "gemini-paid",
            "GOOGLE_API_KEY": "google-paid",
            "DEEPSEEK_API_KEY": "deepseek-paid",
            "TOGETHER_API_KEY": "together-paid",
            "FIREWORKS_API_KEY": "fireworks-paid",
            "MISTRAL_API_KEY": "mistral-paid",
            "COHERE_API_KEY": "cohere-paid",
            "GROQ_API_KEY": "groq-paid",
            "XAI_API_KEY": "xai-paid",
            "PERPLEXITY_API_KEY": "perplexity-paid",
            "KIMI_API_KEY": "kimi-paid",
            "MOONSHOT_API_KEY": "moonshot-paid",
            "OPENAI_ORG_ID": "openai-org",
            "GEMINI_ACCESS_TOKEN": "gemini-access",
            "GOOGLE_OAUTH_ACCESS_TOKEN": "google-oauth",
        }
    )

    result = _run_cascade(env, "hermetic prompt")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"provider-{successful_provider}-success\n"
    lines = call_log.read_text(encoding="utf-8").splitlines()
    assert not any(line.startswith("LEAK:") for line in lines), lines
    expected_attempts = list(provider_order[: provider_order.index(successful_provider) + 1])
    assert [
        line.removeprefix("nonclaude-")
        for line in lines
        if line.startswith("nonclaude-")
    ] == expected_attempts


def test_cli_compat_shim_preserves_json_only_stdout(tmp_path: Path) -> None:
    bodies = _default_bodies()
    bodies["token1"] = (
        'payload="$(cat)"\n'
        'printf "diagnostic-on-stderr\\n" >&2\n'
        'printf \'{"action":"SKIP","reason":"%s"}\\n\' "$payload"\n'
        "exit 0"
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)
    shim = tmp_path / "shim/claude"
    shim.parent.mkdir(parents=True)
    shim.symlink_to(CASCADE)
    env.update(
        {
            "CLAUDE_CASCADE_MODE": "claude-only",
            "CLAUDE_CASCADE_CLI_COMPAT": "1",
        }
    )

    result = subprocess.run(
        [
            str(shim),
            "-p",
            "link decision",
            "--model",
            "claude-haiku-4-5-20251001",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == '{"action":"SKIP","reason":"link decision"}\n'
    assert _labels(call_log) == ["token1"]


@pytest.mark.parametrize(
    ("relative_path", "cascade_sentinel", "claude_only_sentinel"),
    (
        (
            "infra/healer/healer-run.sh",
            "HEALER_CASCADE_BIN",
            "--claude-only",
        ),
        (
            "infra/launchagents/wrappers/pro-healer.sh",
            "PRO_HEALER_CASCADE_BIN",
            "--claude-only",
        ),
        (
            "infra/launchagents/wrappers/regulatory-watcher-run.sh",
            "REGWATCH_CLAUDE_CASCADE_BIN",
            "--claude-only",
        ),
        (
            "scripts/docs_guardian.sh",
            "DOCS_GUARDIAN_CLAUDE_CASCADE_BIN",
            "CLAUDE_CASCADE_MODE=claude-only",
        ),
    ),
)
def test_existing_claude_specific_daemons_use_canonical_claude_only_cascade(
    relative_path: str,
    cascade_sentinel: str,
    claude_only_sentinel: str,
) -> None:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert "claude-cascade.sh" in source
    assert cascade_sentinel in source
    assert claude_only_sentinel in source


def test_docs_guardian_traps_temporary_shim_cleanup() -> None:
    source = (REPO_ROOT / "scripts/docs_guardian.sh").read_text(encoding="utf-8")

    assert "trap cleanup_docs_guardian_temp EXIT" in source
    assert 'rm -f -- "$L25_SHIM_DIR/claude"' in source
    assert 'rmdir -- "$L25_SHIM_DIR"' in source
    assert 'DOCS_GUARDIAN_CALL_TIMEOUT_SEC:-60' in source
    assert 'DOCS_GUARDIAN_CASCADE_DEADLINE_SEC:-50' in source
    assert 'DOCS_GUARDIAN_CASCADE_ATTEMPT_TIMEOUT_SEC:-7' in source
    assert '--timeout "$L25_CALL_TIMEOUT_SEC"' in source


@pytest.mark.parametrize(
    ("relative_path", "deadline_override", "attempt_override"),
    (
        (
            "infra/healer/healer-run.sh",
            "HEALER_CASCADE_DEADLINE_SEC",
            "HEALER_CASCADE_ATTEMPT_TIMEOUT_SEC",
        ),
        (
            "infra/launchagents/wrappers/pro-healer.sh",
            "PRO_HEALER_CASCADE_DEADLINE_SEC",
            "PRO_HEALER_CASCADE_ATTEMPT_TIMEOUT_SEC",
        ),
    ),
)
def test_healer_cascade_deadline_precedes_outer_watchdog(
    relative_path: str,
    deadline_override: str,
    attempt_override: str,
) -> None:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert f"${{{deadline_override}:-$((MAX_WALL_S - 120))}}" in source
    assert (
        f"${{{attempt_override}:-$((CLAUDE_CASCADE_DEADLINE_SEC - 60))}}"
        in source
    )
    assert '"$CLAUDE_CASCADE_DEADLINE_SEC" -ge "$MAX_WALL_S"' in source
    assert "sleep \"$MAX_WALL_S\"" not in source
    assert "time.sleep(float(sys.argv[2]))" in source
    assert 'wait "$WPID" 2>/dev/null || true' in source


def test_organ_birth_imprints_claude_only_cascade() -> None:
    module_path = REPO_ROOT / "scripts/organ_birth.py"
    spec = importlib.util.spec_from_file_location("organ_birth_cascade_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module, ModuleType)

    wrapper = module.wrapper_template(
        "mini.fixture",
        "mini",
        "llm-cron",
        "fixture",
    )

    assert "MINI_FIXTURE_CLAUDE_CASCADE_BIN" in wrapper
    assert (
        'CASCADE_BIN="${MINI_FIXTURE_CLAUDE_CASCADE_BIN:-'
        '$HOME/scripts/claude-cascade.sh}"'
    ) in wrapper
    assert '"$CASCADE_BIN" "TODO: your standing mandate here"' in wrapper
    assert "--claude-only --model" in wrapper
    assert '"$CLAUDE_BIN" -p' not in wrapper
    assert (
        'CLAUDE_CASCADE_DEADLINE_SEC="${MINI_FIXTURE_CLAUDE_CASCADE_DEADLINE_SEC:-'
        '$((MAX_WALL_S - 120))}"'
    ) in wrapper
    assert (
        'CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC="${MINI_FIXTURE_CLAUDE_CASCADE_'
        'ATTEMPT_TIMEOUT_SEC:-$((CLAUDE_CASCADE_DEADLINE_SEC - 60))}"'
    ) in wrapper
    assert '"$CLAUDE_CASCADE_DEADLINE_SEC" -ge "$MAX_WALL_S"' in wrapper
    assert 'sleep "$MAX_WALL_S"' not in wrapper
    assert "time.sleep(float(sys.argv[2]))" in wrapper
    assert 'wait "$WPID" 2>/dev/null || true' in wrapper
    syntax = subprocess.run(
        ["/bin/bash", "-n"],
        input=wrapper,
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr
