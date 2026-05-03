"""Tests for claude_oauth_client — subprocess behavior mocked end-to-end."""

from __future__ import annotations

import asyncio
import importlib
from typing import Any

import pytest


@pytest.fixture
def clear_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "CLAUDE_CODE_OAUTH_TOKEN_2",
        "CLAUDE_CODE_OAUTH_TOKEN_3",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)


def _fake_proc(stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> Any:
    class _P:
        def __init__(self) -> None:
            self.returncode = returncode

        async def communicate(self) -> tuple[bytes, bytes]:
            return stdout, stderr

        async def wait(self) -> None:
            return None

        def kill(self) -> None:
            self.returncode = -9

    return _P()


@pytest.mark.asyncio
async def test_collect_tokens_ordering(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_3", "tok3")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok_legacy")

    got = mod._collect_tokens()

    assert [label for _, label in got] == ["token_1", "token_3", "token_legacy", "keychain"]
    assert [t for t, _ in got] == ["tok1", "tok3", "tok_legacy", ""]


@pytest.mark.asyncio
async def test_collect_tokens_deduplicates(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "same")

    got = mod._collect_tokens()

    assert [label for _, label in got] == ["token_1", "keychain"]


@pytest.mark.asyncio
async def test_build_env_strips_api_key(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("ANTHROPIC_API_KEY", "should_not_leak")
    env = mod._build_env("tok_xyz")

    assert "ANTHROPIC_API_KEY" not in env
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok_xyz"


@pytest.mark.asyncio
async def test_complete_async_happy_path(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")

    calls: list[dict[str, Any]] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        calls.append({"args": args, "env_has_api_key": "ANTHROPIC_API_KEY" in kwargs.get("env", {})})
        return _fake_proc(stdout=b"hello world", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping", model="claude-sonnet-4-6")

    assert resp.text == "hello world"
    assert resp.token_label == "token_1"
    assert resp.attempts == 1
    assert len(calls) == 1
    assert calls[0]["env_has_api_key"] is False


@pytest.mark.asyncio
async def test_complete_async_rate_limit_falls_through(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "t2")

    attempts: list[int] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            return _fake_proc(stdout=b"", stderr=b"Error: rate limit exceeded", returncode=1)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert resp.text == "ok"
    assert resp.token_label == "token_2"
    assert resp.attempts == 2


@pytest.mark.asyncio
async def test_complete_async_empty_output_falls_through(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")

    counter = {"n": 0}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        counter["n"] += 1
        if counter["n"] == 1:
            return _fake_proc(stdout=b"   \n", returncode=0)  # empty after trim
        return _fake_proc(stdout=b"fine", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert resp.text == "fine"
    assert resp.token_label == "keychain"
    assert resp.attempts == 2


@pytest.mark.asyncio
async def test_complete_async_all_fail(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        return _fake_proc(stdout=b"", stderr=b"generic failure", returncode=2)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthError):
        await mod.complete_async("ping")


@pytest.mark.asyncio
async def test_complete_async_cli_missing(
    monkeypatch: pytest.MonkeyPatch, clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("no claude binary")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthNotAvailable):
        await mod.complete_async("ping")


def test_module_imports_without_anthropic_sdk() -> None:
    """Integrity test: the OAuth client must not import the Anthropic SDK.

    The entire point of this module is to remove the SDK dependency for
    Claude calls.
    """
    import backend.llm.claude_oauth_client as mod
    importlib.reload(mod)

    src = open(mod.__file__).read()
    assert "import anthropic" not in src
    assert "from anthropic" not in src
