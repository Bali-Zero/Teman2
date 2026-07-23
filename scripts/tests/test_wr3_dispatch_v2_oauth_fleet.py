"""Hermetic OAuth-fleet regressions for the WR3 v2 dispatcher."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_dispatch_v2 as dispatch  # noqa: E402


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


def _contract(*, gate: bool = False, core: bool = True) -> Any:
    return SimpleNamespace(
        name="wr3-script-editor",
        model="sonnet",
        cost=SimpleNamespace(ceiling_usd=0.30),
        cost_class="core",
        is_gate=gate,
        is_core=core,
    )


class _FakeProcess:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        hangs: bool = False,
    ) -> None:
        self._planned_returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._hangs = hangs
        self.returncode: int | None = None
        self.killed = False
        self.reaped = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._hangs and not self.killed:
            await asyncio.sleep(60)
        self.returncode = self._planned_returncode
        return self._stdout.encode(), self._stderr.encode()

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        self.reaped = True
        return self.returncode or 0


def _success(result: str = "ok") -> str:
    return json.dumps(
        {
            "type": "result",
            "is_error": False,
            "total_cost_usd": 0.01,
            "result": result,
        }
    )


def _install_factory(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: list[_FakeProcess],
    seen_envs: list[dict[str, str]],
) -> None:
    async def _create(*args: Any, **kwargs: Any) -> _FakeProcess:
        seen_envs.append(kwargs["env"])
        return outcomes.pop(0)

    monkeypatch.setattr(dispatch.asyncio, "create_subprocess_exec", _create)
    monkeypatch.setattr(dispatch.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(dispatch, "_agent_system_prompt", lambda _: "safe system")


@pytest.mark.asyncio
async def test_slot5_team_succeeds_after_quota_auth_empty_and_429(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    tokens = [f"sentinel-secret-{slot}" for slot in range(1, 6)]
    for slot, token in enumerate(tokens, start=1):
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", token)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", tokens[0])
    for key in _PROVIDER_KEYS:
        monkeypatch.setenv(key, f"provider-secret-{key}")

    outcomes = [
        _FakeProcess(stdout="You've hit your weekly limit"),
        _FakeProcess(stdout="authentication failed: refresh_token revoked"),
        _FakeProcess(stdout=" \n"),
        _FakeProcess(returncode=1, stderr="429 rate limit"),
        _FakeProcess(stdout=_success("slot-five-success")),
    ]
    seen_envs: list[dict[str, str]] = []
    _install_factory(monkeypatch, outcomes, seen_envs)

    with caplog.at_level(logging.INFO, logger=dispatch.__name__):
        result = await dispatch.dispatch_claude_print(
            _contract(),
            "safe prompt",
            timeout_ms=1000,
        )

    assert result.raw_output == "slot-five-success"
    assert [env["CLAUDE_CODE_OAUTH_TOKEN"] for env in seen_envs] == tokens
    for env in seen_envs:
        assert not (_PROVIDER_KEYS & env.keys())
        assert not any(key.startswith("CLAUDE_CODE_OAUTH_TOKEN_") for key in env)
    logs = caplog.text
    assert "slot5-team" in logs
    assert all(token not in logs for token in tokens)
    assert all(f"provider-secret-{key}" not in logs for key in _PROVIDER_KEYS)


def test_token_chain_is_deduplicated_and_keychain_is_last(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_5", "team")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "legacy")

    assert dispatch._collect_claude_seats() == [
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


@pytest.mark.asyncio
async def test_real_process_tree_timeout_kills_descendant_and_empty_rotates(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "timeout-seat")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "empty-seat")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_3", "healthy-seat")
    child_pid_path = tmp_path / "descendant.pid"
    monkeypatch.setenv("WR3_TEST_DESCENDANT_PID", str(child_pid_path))
    claude = tmp_path / "claude"
    claude.write_text(
        """#!/bin/sh
case "${CLAUDE_CODE_OAUTH_TOKEN:-}" in
    timeout-seat)
        trap '' TERM
        (
            trap '' TERM
            sleep 30
        ) &
        child_pid=$!
        printf '%s' "$child_pid" > "$WR3_TEST_DESCENDANT_PID"
        wait
        ;;
    empty-seat)
        printf '%s\n' '{"type":"result","is_error":false,"result":"  "}'
        ;;
    *)
        printf '%s\n' '{"type":"result","is_error":false,"total_cost_usd":0.01,"result":"real-tree-success"}'
        ;;
esac
""",
        encoding="utf-8",
    )
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(dispatch, "_agent_system_prompt", lambda _: "safe system")

    started = time.monotonic()
    result = await dispatch.dispatch_claude_print(
        _contract(),
        "safe prompt",
        timeout_ms=8000,
    )
    elapsed = time.monotonic() - started

    assert result.raw_output == "real-tree-success"
    assert elapsed < 3.1
    assert child_pid_path.exists()
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 1.0
    while _pid_is_running(child_pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not _pid_is_running(child_pid)


@pytest.mark.asyncio
async def test_unknown_failure_diagnostic_redacts_oauth_secret(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sentinel-super-secret"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", secret)
    outcomes = [
        _FakeProcess(
            returncode=2,
            stderr=f"unexpected failure bearer {secret}",
        )
    ]
    seen_envs: list[dict[str, str]] = []
    _install_factory(monkeypatch, outcomes, seen_envs)

    with pytest.raises(dispatch.WR3DispatchError) as exc_info:
        await dispatch.dispatch_claude_print(
            _contract(),
            "safe prompt",
            timeout_ms=100,
        )

    assert secret not in str(exc_info.value)
    assert "slot1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unknown_json_error_result_is_not_accepted_as_success(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "error-seat")
    error_envelope = json.dumps(
        {"type": "result", "is_error": True, "result": "unclassified runtime failure"}
    )
    outcomes = [_FakeProcess(stdout=error_envelope)]
    seen_envs: list[dict[str, str]] = []
    _install_factory(monkeypatch, outcomes, seen_envs)

    with pytest.raises(dispatch.WR3DispatchError, match="returned an error result"):
        await dispatch.dispatch_claude_print(
            _contract(),
            "safe prompt",
            timeout_ms=100,
        )


@pytest.mark.asyncio
async def test_core_only_uses_existing_cross_family_cascade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract(core=True)
    contracts = SimpleNamespace(for_agent=lambda _: contract)
    expected = SimpleNamespace(raw_output="gemini-safe")
    monkeypatch.setattr(
        dispatch,
        "dispatch_claude_print",
        AsyncMock(side_effect=dispatch.ClaudeFleetExhaustedError("fleet")),
    )
    gemini = AsyncMock(return_value=expected)
    monkeypatch.setattr(dispatch, "_dispatch_gemini_cli", gemini)

    result = await dispatch.dispatch_agent_v2(
        contracts,
        "wr3-script-editor",
        "safe prompt",
    )

    assert result is expected
    gemini.assert_awaited_once_with(contract, "safe prompt")


@pytest.mark.asyncio
async def test_real_gemini_child_receives_only_allowlisted_environment(
    clean_auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in _PROVIDER_KEYS:
        monkeypatch.setenv(key, f"secret-{key}")
    monkeypatch.setenv("SIBLING_PROVIDER_SECRET", "sibling-secret")
    for slot in range(1, 6):
        monkeypatch.setenv(
            f"CLAUDE_CODE_OAUTH_TOKEN_{slot}",
            f"oauth-secret-{slot}",
        )
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "legacy-secret")

    agy = tmp_path / "agy"
    agy.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

dump_path = pathlib.Path(sys.stdin.read().strip())
dump_path.write_text(json.dumps(dict(os.environ)), encoding="utf-8")
print("gemini-safe")
""",
        encoding="utf-8",
    )
    agy.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    contract = _contract(core=True)
    contracts = SimpleNamespace(for_agent=lambda _: contract)
    monkeypatch.setattr(
        dispatch,
        "dispatch_claude_print",
        AsyncMock(side_effect=dispatch.ClaudeFleetExhaustedError("fleet")),
    )
    dump_path = tmp_path / "gemini-env.json"

    result = await dispatch.dispatch_agent_v2(
        contracts,
        "wr3-script-editor",
        str(dump_path),
    )

    child_env = json.loads(dump_path.read_text(encoding="utf-8"))
    assert result.raw_output.strip() == "gemini-safe"
    assert child_env["HOME"] == os.environ["HOME"]
    assert child_env["PATH"] == os.environ["PATH"]
    assert not any(
        key.startswith(("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_"))
        for key in child_env
    )
    assert not (_PROVIDER_KEYS & child_env.keys())
    assert "SIBLING_PROVIDER_SECRET" not in child_env


@pytest.mark.asyncio
async def test_gate_fails_closed_without_cross_family_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract(gate=True, core=True)
    contracts = SimpleNamespace(for_agent=lambda _: contract)
    monkeypatch.setattr(
        dispatch,
        "dispatch_claude_print",
        AsyncMock(side_effect=dispatch.ClaudeFleetExhaustedError("fleet")),
    )
    gemini = AsyncMock()
    monkeypatch.setattr(dispatch, "_dispatch_gemini_cli", gemini)
    monkeypatch.setattr(dispatch, "telegram_p0", AsyncMock())

    with pytest.raises(dispatch.HardHaltException):
        await dispatch.dispatch_agent_v2(
            contracts,
            "wr3-pre-render-gatekeeper",
            "safe prompt",
        )

    gemini.assert_not_awaited()
