"""Hermetic OAuth-fleet regressions for WR3 Reflexion synthesis."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

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


def test_invoke_process_timeout_kills_and_reaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakePopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.returncode: int | None = None
            self.killed = False
            self.communicate_calls = 0

        def communicate(
            self,
            input: str | None = None,
            timeout: float | None = None,
        ) -> tuple[str, str]:
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout or 0)
            return "", ""

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

    fake = _FakePopen()
    monkeypatch.setattr(reflexion.subprocess, "Popen", lambda *a, **k: fake)

    returncode, stdout, stderr, timed_out = reflexion._invoke_process(
        ["claude"],
        "safe prompt",
        0.01,
        {},
    )

    assert timed_out
    assert returncode == -9
    assert stdout == ""
    assert stderr == ""
    assert fake.killed
    assert fake.communicate_calls == 2


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
