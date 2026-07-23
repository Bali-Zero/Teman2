"""Hermetic OAuth-fleet regressions for WR3 Reflexion synthesis."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_reflexion_synthesis as reflexion  # noqa: E402


_PROVIDER_KEYS = {
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_BEDROCK_ANTHROPIC_KEY",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_CLOUD_PROJECT",
    "CLOUD_ML_REGION",
    "CLAUDE_CODE_USE_FOUNDRY",
    "FOUNDRY_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
}


@pytest.fixture
def clean_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for slot in range(1, 6):
        monkeypatch.delenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    for key in _PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)


def _synthesis(note: str = "slot-five-success") -> str:
    return json.dumps({"week": "2026-W30", "lessons": [], "synthesis_notes": note})


def test_slot5_team_succeeds_after_quota_auth_empty_and_429(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tokens = [f"reflexion-secret-{slot}" for slot in range(1, 6)]
    for slot, token in enumerate(tokens, start=1):
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", token)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", tokens[0])
    for key in _PROVIDER_KEYS:
        monkeypatch.setenv(key, f"provider-secret-{key}")
    monkeypatch.setattr(reflexion, "LLM_TIMEOUT_S", 10)

    outcomes = iter(
        [
            (0, "weekly usage limit reached", "", False),
            (0, "authentication failed: refresh_token revoked", "", False),
            (0, " \n", "", False),
            (1, "", "429 rate limit", False),
            (0, _synthesis(), "", False),
        ]
    )
    seen_envs: list[dict[str, str]] = []

    def _invoke(
        cmd: list[str],
        prompt: str,
        timeout_s: float,
        env: dict[str, str],
    ) -> tuple[int, str, str, bool]:
        seen_envs.append(env)
        return next(outcomes)

    monkeypatch.setattr(reflexion, "_invoke_process", _invoke)

    output = reflexion._run_claude_fleet("safe prompt")

    assert json.loads(output or "")["synthesis_notes"] == "slot-five-success"
    assert [env["CLAUDE_CODE_OAUTH_TOKEN"] for env in seen_envs] == tokens
    for env in seen_envs:
        assert not (_PROVIDER_KEYS & env.keys())
        assert not any(key.startswith("CLAUDE_CODE_OAUTH_TOKEN_") for key in env)
    stderr = capsys.readouterr().err
    assert "slot5-team" in stderr
    assert all(token not in stderr for token in tokens)
    assert all(f"provider-secret-{key}" not in stderr for key in _PROVIDER_KEYS)


def test_token_chain_is_deduplicated_and_keychain_is_last(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_5", "team")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "legacy")

    assert reflexion._collect_claude_seats() == [
        ("slot1", "same"),
        ("slot5-team", "team"),
        ("legacy", "legacy"),
        ("keychain", ""),
    ]


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    status = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return bool(status) and not status.startswith("Z")


def test_real_process_tree_timeout_kills_descendant_and_respects_deadline(
    tmp_path: Path,
) -> None:
    child_pid_path = tmp_path / "descendant.pid"
    runner = tmp_path / "tree_runner.py"
    runner.write_text(
        """import os
import signal
import subprocess
import sys
import time

child_code = (
    "import os,signal,time;"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
    "open(os.environ['WR3_TEST_DESCENDANT_PID'],'w').write(str(os.getpid()));"
    "time.sleep(30)"
)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
subprocess.Popen(
    [sys.executable, "-c", child_code],
    stdout=sys.stdout,
    stderr=sys.stderr,
    env=os.environ,
)
time.sleep(30)
""",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["WR3_TEST_DESCENDANT_PID"] = str(child_pid_path)

    started = time.monotonic()
    returncode, stdout, stderr, timed_out = reflexion._invoke_process(
        [sys.executable, str(runner)],
        "safe prompt",
        1.0,
        env,
    )
    elapsed = time.monotonic() - started

    assert timed_out
    assert returncode == -9
    assert stdout == ""
    assert stderr == ""
    assert elapsed < 1.1
    assert child_pid_path.exists()
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 1.0
    while _pid_is_running(child_pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not _pid_is_running(child_pid)


def test_unknown_diagnostic_never_logs_oauth_secret(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "reflexion-super-secret"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", secret)

    def _invoke(
        cmd: list[str],
        prompt: str,
        timeout_s: float,
        env: dict[str, str],
    ) -> tuple[int, str, str, bool]:
        return 2, "", f"unexpected failure bearer {secret}", False

    monkeypatch.setattr(reflexion, "_invoke_process", _invoke)

    assert reflexion._run_claude_fleet("safe prompt") is None
    stderr = capsys.readouterr().err
    assert secret not in stderr
    assert "slot1" in stderr


def test_exit_zero_invalid_schema_rotates_to_next_seat(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "invalid-seat")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "valid-seat")
    outcomes = iter(
        [
            (0, '{"type":"result","is_error":true}', "", False),
            (0, _synthesis(), "", False),
        ]
    )
    monkeypatch.setattr(
        reflexion,
        "_invoke_process",
        lambda cmd, prompt, timeout_s, env: next(outcomes),
    )

    output = reflexion._run_claude_fleet("safe prompt")

    assert json.loads(output or "")["synthesis_notes"] == "slot-five-success"


def test_empty_transport_retries_but_honest_zero_lessons_is_valid() -> None:
    honest_empty = _synthesis("no reliable lesson this week")

    assert reflexion._retry_reason(
        stdout="  ",
        stderr="",
        returncode=0,
        valid_success=False,
    ) == "empty-output"
    assert reflexion._valid_synthesis_json(honest_empty)
    assert reflexion._retry_reason(
        stdout=honest_empty,
        stderr="",
        returncode=0,
        valid_success=True,
    ) is None


def test_portable_reflexion_contract_keeps_gemini_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _run(tier: str, prompt: str) -> str | None:
        calls.append(tier)
        if tier == "claude":
            return None
        return _synthesis("gemini-portable")

    monkeypatch.setattr(reflexion, "_run_tier", _run)

    result = reflexion.call_llm_synthesis("safe prompt")

    assert result is not None
    assert result["synthesis_notes"] == "gemini-portable"
    assert calls == ["claude", "gemini"]
