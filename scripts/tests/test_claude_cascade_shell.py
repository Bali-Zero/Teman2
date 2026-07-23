"""Hermetic regression tests for the canonical Claude subscription cascade."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CASCADE = REPO_ROOT / "infra/launchagents/wrappers/claude-cascade.sh"


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _fake_fleet(tmp_path: Path, seat_bodies: dict[str, str]) -> tuple[Path, dict[str, str]]:
    home = tmp_path / "home"
    call_log = tmp_path / "calls.log"
    seat_paths = {
        "default": home / ".local/share/mise/shims/claude",
        "acct2": home / ".local/bin/claude-acct2",
        "acct3": home / ".local/bin/claude-acct3",
        "acct4": home / ".local/bin/claude-acct4",
        "zero-team": home / ".local/bin/claude-zero-team",
    }
    for label, path in seat_paths.items():
        body = (
            'if [ "${CLAUDE_CODE_OAUTH_TOKEN+x}" = "x" ]; then '
            'token_state=set; else token_state=unset; fi\n'
            f'printf "%s:%s\\n" "{label}" "$token_state" >> "$CALL_LOG"\n'
            f"{seat_bodies[label]}"
        )
        _write_executable(path, body)

    for label, path in {
        "agy": home / ".local/bin/agy",
        "kimi": home / ".kimi-code/bin/kimi",
        "codex": home / ".local/bin/codex",
    }.items():
        _write_executable(
            path,
            f'printf "nonclaude-{label}\\n" >> "$CALL_LOG"\nprintf "unexpected-{label}\\n"',
        )

    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "CALL_LOG": str(call_log),
        "CLAUDE_CODE_OAUTH_TOKEN": "default-seat",
    }
    return call_log, env


def _run_cascade(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/zsh", str(CASCADE), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=10,
    )


def test_claude_only_retries_auth_quota_empty_then_later_seat(
    tmp_path: Path,
) -> None:
    call_log, env = _fake_fleet(
        tmp_path,
        {
            "default": 'printf "authentication required\\n" >&2\nexit 1',
            "acct2": 'printf "weekly limit reached\\n"\nexit 0',
            "acct3": "exit 0",
            "acct4": 'printf "seat-four-success\\n"\nexit 0',
            "zero-team": 'printf "unexpected-zero-team\\n"\nexit 0',
        },
    )

    result = _run_cascade(
        env,
        "hermetic prompt",
        "--claude-only",
        "--model",
        "claude-sonnet-5",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "seat-four-success\n"
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "default:set",
        "acct2:unset",
        "acct3:unset",
        "acct4:unset",
    ]
    assert "used: tier2c-claude-acct4" in result.stderr


def test_claude_only_never_crosses_provider_boundary_when_all_seats_fail(
    tmp_path: Path,
) -> None:
    call_log, env = _fake_fleet(
        tmp_path,
        {
            "default": "exit 1",
            "acct2": 'printf "quota exceeded\\n"\nexit 0',
            "acct3": "exit 0",
            "acct4": "exit 2",
            "zero-team": 'printf "not logged in\\n" >&2\nexit 1',
        },
    )

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 1
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert [line.split(":", maxsplit=1)[0] for line in calls] == [
        "default",
        "acct2",
        "acct3",
        "acct4",
        "zero-team",
    ]
    assert not any(line.startswith("nonclaude-") for line in calls)
    assert "ALL CLAUDE SEATS FAILED" in result.stderr


def test_cli_compat_shim_preserves_json_only_stdout(tmp_path: Path) -> None:
    call_log, env = _fake_fleet(
        tmp_path,
        {
            "default": (
                'payload="$(cat)"\n'
                'printf "diagnostic-on-stderr\\n" >&2\n'
                'printf \'{"action":"SKIP","reason":"%s"}\\n\' "$payload"\n'
                "exit 0"
            ),
            "acct2": "exit 1",
            "acct3": "exit 1",
            "acct4": "exit 1",
            "zero-team": "exit 1",
        },
    )
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
    assert "diagnostic-on-stderr" in result.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "default:set"
    ]


@pytest.mark.parametrize(
    ("target_index", "expected_label"),
    (
        (2, "tier2-claude-acct2-env"),
        (3, "tier2b-claude-acct3-env"),
        (4, "tier2c-claude-acct4-env"),
    ),
)
def test_missing_account_wrapper_uses_indexed_env_token_without_logging_value(
    tmp_path: Path,
    target_index: int,
    expected_label: str,
) -> None:
    token_var = f"CLAUDE_CODE_OAUTH_TOKEN_{target_index}"
    config_dir = f"$HOME/.claude-acct{target_index}"
    call_log, env = _fake_fleet(
        tmp_path,
        {
            "default": (
                f'if [ "${{CLAUDE_CONFIG_DIR:-}}" = "{config_dir}" ] '
                '&& [ "${CLAUDE_CODE_OAUTH_TOKEN:-}" = '
                f'"${{{token_var}:-}}" ]; then\n'
                f'  printf "env-seat-{target_index}-success\\n"\n'
                "  exit 0\n"
                "fi\n"
                'printf "authentication required\\n" >&2\n'
                "exit 1"
            ),
            "acct2": "exit 1",
            "acct3": "exit 0",
            "acct4": "exit 1",
            "zero-team": "exit 1",
        },
    )
    for index in (2, 3, 4):
        (Path(env["HOME"]) / f".local/bin/claude-acct{index}").unlink()
    fixture_token = f"fixture-slot-{target_index}-value"
    env[token_var] = fixture_token

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"env-seat-{target_index}-success\n"
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert calls == [
        "default:set",
        "default:set",
    ]
    assert fixture_token not in result.stdout
    assert fixture_token not in result.stderr
    assert f"used: {expected_label}" in result.stderr


def test_locked_default_config_retries_indexed_slot_one_token(
    tmp_path: Path,
) -> None:
    call_log, env = _fake_fleet(
        tmp_path,
        {
            "default": (
                'if [ "${CLAUDE_CONFIG_DIR:-}" = "$HOME/.claude" ] '
                '&& [ "${CLAUDE_CODE_OAUTH_TOKEN:-}" = '
                '"${CLAUDE_CODE_OAUTH_TOKEN_1:-}" ]; then\n'
                '  printf "env-seat-one-success\\n"\n'
                "  exit 0\n"
                "fi\n"
                'printf "authentication required\\n" >&2\n'
                "exit 1"
            ),
            "acct2": "exit 1",
            "acct3": "exit 1",
            "acct4": "exit 1",
            "zero-team": "exit 1",
        },
    )
    env["CLAUDE_CODE_OAUTH_TOKEN_1"] = "fixture-slot-one-value"

    result = _run_cascade(env, "hermetic prompt", "--claude-only")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "env-seat-one-success\n"
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "default:set",
        "default:set",
    ]
    assert "fixture-slot-one-value" not in result.stdout
    assert "fixture-slot-one-value" not in result.stderr
    assert "used: tier1b-claude-token1-env" in result.stderr


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
