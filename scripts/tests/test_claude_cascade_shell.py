"""Hermetic regression tests for the canonical Claude subscription cascade."""

from __future__ import annotations

import importlib.util
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
            'for forbidden in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN '
            "ANTHROPIC_BASE_URL AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY "
            "VERTEX_AI_PROJECT GOOGLE_APPLICATION_CREDENTIALS "
            "CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX; do\n"
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
    for label, path in {
        "agy": home / ".local/bin/agy",
        "kimi": home / ".kimi-code/bin/kimi",
        "codex": home / ".local/bin/codex",
    }.items():
        _write_executable(
            path,
            f'printf "nonclaude-{label}\\n" >> "$CALL_LOG"\n'
            f'printf "unexpected-{label}\\n"',
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


def test_attempt_timeout_rotates_to_next_seat(tmp_path: Path) -> None:
    bodies = _default_bodies()
    bodies.update(
        {
            "token1": "sleep 3\nexit 0",
            "token2": 'printf "after-timeout-success\\n"\nexit 0',
        }
    )
    call_log, _, env = _fake_fleet(tmp_path, bodies)
    env["CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC"] = "1"
    env["CLAUDE_CASCADE_DEADLINE_SEC"] = "5"

    started = time.monotonic()
    result = _run_cascade(env, "hermetic prompt", "--claude-only")
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    assert result.stdout == "after-timeout-success\n"
    assert _labels(call_log) == ["token1", "token2"]
    assert elapsed < 4


def test_global_deadline_prevents_later_seats_from_starting(tmp_path: Path) -> None:
    bodies = _default_bodies()
    bodies["token1"] = "sleep 3\nexit 0"
    call_log, temp_dir, env = _fake_fleet(tmp_path, bodies)
    env["CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC"] = "5"
    env["CLAUDE_CASCADE_DEADLINE_SEC"] = "1"

    started = time.monotonic()
    result = _run_cascade(env, "hermetic prompt", "--claude-only")
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert result.stdout == ""
    assert _labels(call_log) == ["token1"]
    assert elapsed < 4
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
