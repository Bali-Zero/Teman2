# scripts/zantara-gateway/test_claude_client.py
"""Tests for the Claude client backend selection (subprocess default | sdk pilot)."""

import asyncio
import sys
import types

import claude_client


async def _collect(agen):
    return [item async for item in agen]


# ── fakes for the claude_agent_sdk module (no real package required) ──


class _FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeToolUseBlock:
    def __init__(self, name: str):
        self.name = name
        self.input: dict = {}


class _FakeAssistantMessage:
    def __init__(self, content: list):
        self.content = content


class _FakeResultMessage:
    def __init__(self, subtype: str, result: str = ""):
        self.subtype = subtype
        self.result = result


class _FakeSystemMessage:
    """Shaped like the SDK's ``SystemMessage(subtype="init")`` — a lifecycle
    message that carries ``subtype`` but is NOT a ResultMessage (P1-1). Named
    with the ``_Fake`` prefix (not literally ``SystemMessage``) so this
    exercises the duck-typed fallback in ``_sdk_message_kind``, not the
    exact-class-name branch."""

    def __init__(self, subtype: str = "init"):
        self.subtype = subtype


class _FakeClaudeAgentOptions:
    """Captures kwargs like the real ClaudeAgentOptions dataclass would."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _make_fake_sdk_module(messages: list, captured_options: list):
    async def fake_query(*, prompt, options):
        captured_options.append(options)
        for message in messages:
            yield message

    module = types.ModuleType("claude_agent_sdk")
    module.query = fake_query
    module.ClaudeAgentOptions = _FakeClaudeAgentOptions
    return module


# ── backend dispatch ──


def test_default_backend_is_subprocess(monkeypatch):
    monkeypatch.delenv("ZANTARA_CLAUDE_BACKEND", raising=False)
    calls = {"subprocess": 0, "sdk": 0}

    async def fake_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        yield "data: [DONE]\n\n"

    async def fake_sdk(*args, **kwargs):
        calls["sdk"] += 1
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(claude_client, "_stream_via_subprocess", fake_subprocess)
    monkeypatch.setattr(claude_client, "_stream_via_sdk", fake_sdk)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client.stream_claude_cli("hi"))
    )

    assert calls == {"subprocess": 1, "sdk": 0}
    assert lines == ["data: [DONE]\n\n"]


def test_sdk_backend_falls_back_when_package_missing(monkeypatch):
    """ZANTARA_CLAUDE_BACKEND=sdk without the package installed → clean
    fallback to subprocess, never a crash. sys.modules[name] = None forces
    the import to raise ImportError without needing the real package."""
    monkeypatch.setenv("ZANTARA_CLAUDE_BACKEND", "sdk")
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)

    calls = {"subprocess": 0}

    async def fake_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(claude_client, "_stream_via_subprocess", fake_subprocess)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client.stream_claude_cli("hi"))
    )

    assert calls["subprocess"] == 1
    assert lines == ["data: [DONE]\n\n"]


# ── _stream_via_sdk message conversion ──


def test_stream_via_sdk_converts_messages_to_sse(monkeypatch):
    messages = [
        _FakeAssistantMessage([_FakeTextBlock("Hello ")]),
        _FakeAssistantMessage([_FakeTextBlock("world"), _FakeToolUseBlock("list_clients")]),
        _FakeResultMessage("success", result=""),
    ]
    captured: list = []
    fake_module = _make_fake_sdk_module(messages, captured)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi"))
    )

    assert lines[0] == 'data: {"type":"token","data":"Hello "}\n\n'
    assert lines[1] == 'data: {"type":"token","data":"world"}\n\n'
    assert '"type":"tool_call"' in lines[2]
    assert '"name":"list_clients"' in lines[2]
    assert lines[-1] == "data: [DONE]\n\n"
    assert len(captured) == 1


def test_stream_via_sdk_error_result_falls_back_to_subprocess(monkeypatch):
    messages = [_FakeResultMessage("error_max_turns", result="")]
    captured: list = []
    fake_module = _make_fake_sdk_module(messages, captured)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    calls = {"subprocess": 0}

    async def fake_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(claude_client, "_stream_via_subprocess", fake_subprocess)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi"))
    )

    assert calls["subprocess"] == 1
    assert lines == ["data: [DONE]\n\n"]


# ── P1-1: lifecycle messages (SystemMessage/Task*) must not be misread as a
# terminal error result ──


def test_stream_via_sdk_skips_system_init_message_no_fallback(monkeypatch):
    """A SystemMessage(subtype="init")-shaped object as the FIRST message
    (as the real SDK emits) must be skipped, not classified as a terminal
    error result — the old ``hasattr(message, "subtype")`` rule fell back to
    subprocess on literally every query before streaming a single token."""
    messages = [
        _FakeSystemMessage("init"),
        _FakeAssistantMessage([_FakeTextBlock("Hello ")]),
        _FakeAssistantMessage([_FakeTextBlock("world")]),
        _FakeResultMessage("success", result=""),
    ]
    captured: list = []
    fake_module = _make_fake_sdk_module(messages, captured)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    calls = {"subprocess": 0}

    async def fake_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(claude_client, "_stream_via_subprocess", fake_subprocess)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi"))
    )

    assert calls["subprocess"] == 0
    assert lines[0] == 'data: {"type":"token","data":"Hello "}\n\n'
    assert lines[1] == 'data: {"type":"token","data":"world"}\n\n'
    assert lines[-1] == "data: [DONE]\n\n"


def test_sdk_message_kind_classifies_lifecycle_vs_result():
    assert claude_client._sdk_message_kind(_FakeSystemMessage("init")) == "skip"
    assert (
        claude_client._sdk_message_kind(_FakeResultMessage("success", result="x")) == "result"
    )
    assert (
        claude_client._sdk_message_kind(_FakeAssistantMessage([_FakeTextBlock("x")]))
        == "assistant"
    )


# ── P1-2 / P3-b: no replay once tokens have already been streamed ──


def test_stream_via_sdk_error_after_yield_no_replay(monkeypatch):
    """An SDK error raised AFTER the first token has been yielded must NOT
    trigger a subprocess fallback (that would replay the whole response —
    duplicate SSE + double spend). It must emit a single error event + DONE
    instead."""

    async def fake_query(*, prompt, options):
        yield _FakeAssistantMessage([_FakeTextBlock("partial")])
        raise RuntimeError("boom mid-stream")

    module = types.ModuleType("claude_agent_sdk")
    module.query = fake_query
    module.ClaudeAgentOptions = _FakeClaudeAgentOptions
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)

    calls = {"subprocess": 0}

    async def fake_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(claude_client, "_stream_via_subprocess", fake_subprocess)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi"))
    )

    assert calls["subprocess"] == 0
    assert lines[0] == 'data: {"type":"token","data":"partial"}\n\n'
    assert any('"type":"error"' in line for line in lines)
    assert lines[-1] == "data: [DONE]\n\n"


def test_stream_via_sdk_timeout_after_yield_no_replay(monkeypatch):
    """A per-message timeout hitting AFTER the first token has been yielded
    must behave exactly like the post-yield error case: error event + DONE,
    never a subprocess fallback/replay."""

    async def fake_query(*, prompt, options):
        yield _FakeAssistantMessage([_FakeTextBlock("partial")])
        await asyncio.sleep(10)  # never reached within the short test timeout
        yield _FakeResultMessage("success", result="")

    module = types.ModuleType("claude_agent_sdk")
    module.query = fake_query
    module.ClaudeAgentOptions = _FakeClaudeAgentOptions
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)

    calls = {"subprocess": 0}

    async def fake_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(claude_client, "_stream_via_subprocess", fake_subprocess)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi", timeout=0.05))
    )

    assert calls["subprocess"] == 0
    assert lines[0] == 'data: {"type":"token","data":"partial"}\n\n'
    assert any('"type":"error"' in line for line in lines)
    assert lines[-1] == "data: [DONE]\n\n"


def test_stream_via_sdk_timeout_before_yield_falls_back_to_subprocess(monkeypatch):
    """A timeout with NOTHING yielded yet is still safe to fall back on —
    unchanged pre-P1-2 behavior, kept green as a regression guard."""

    async def fake_query(*, prompt, options):
        await asyncio.sleep(10)
        yield _FakeResultMessage("success", result="")

    module = types.ModuleType("claude_agent_sdk")
    module.query = fake_query
    module.ClaudeAgentOptions = _FakeClaudeAgentOptions
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)

    calls = {"subprocess": 0}

    async def fake_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(claude_client, "_stream_via_subprocess", fake_subprocess)

    lines = asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi", timeout=0.05))
    )

    assert calls["subprocess"] == 1
    assert lines == ["data: [DONE]\n\n"]


# ── P3-a / P3-c: cwd + effort passed to ClaudeAgentOptions ──


def test_sdk_options_include_cwd_and_effort_for_short_query(monkeypatch):
    captured: list = []
    fake_module = _make_fake_sdk_module(
        [_FakeResultMessage("success", result="")], captured
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi", cwd="/tmp/work"))
    )

    assert len(captured) == 1
    opts = captured[0]
    assert opts.cwd == "/tmp/work"
    assert opts.effort == "low"


def test_sdk_options_omit_effort_for_long_query(monkeypatch):
    captured: list = []
    fake_module = _make_fake_sdk_module(
        [_FakeResultMessage("success", result="")], captured
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    long_query = "x" * 150
    asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk(long_query))
    )

    assert len(captured) == 1
    assert not hasattr(captured[0], "effort")
    assert not hasattr(captured[0], "cwd")


# ── env hygiene ──


def test_sdk_env_strips_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-token")

    captured: list = []
    fake_module = _make_fake_sdk_module(
        [_FakeResultMessage("success", result="")], captured
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi"))
    )

    assert len(captured) == 1
    env = captured[0].env
    assert "ANTHROPIC_API_KEY" not in env
    assert env.get("CLAUDE_CODE_OAUTH_TOKEN") == "oauth-token"


def test_sdk_env_seeds_oauth_token_from_indexed_chain(monkeypatch):
    """Only CLAUDE_CODE_OAUTH_TOKEN_1 set, no legacy var — the SDK-spawned
    CLI must still get a token via CLAUDE_CODE_OAUTH_TOKEN (P2: previously
    it fell through to keychain/failure instead of using the chain)."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_2", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_3", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")

    captured: list = []
    fake_module = _make_fake_sdk_module(
        [_FakeResultMessage("success", result="")], captured
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi"))
    )

    assert len(captured) == 1
    env = captured[0].env
    assert env.get("CLAUDE_CODE_OAUTH_TOKEN") == "tok1"
    assert "ANTHROPIC_API_KEY" not in env


def test_sdk_env_no_chain_token_leaves_var_absent(monkeypatch):
    """No indexed token and no legacy var set at all — the chain resolves to
    the empty keychain sentinel, so CLAUDE_CODE_OAUTH_TOKEN must NOT be
    invented (current no-token behavior preserved)."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_1", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_2", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_3", raising=False)

    captured: list = []
    fake_module = _make_fake_sdk_module(
        [_FakeResultMessage("success", result="")], captured
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)

    asyncio.get_event_loop().run_until_complete(
        _collect(claude_client._stream_via_sdk("hi"))
    )

    assert len(captured) == 1
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in captured[0].env


# ── subprocess cmd budget cap ──


def test_subprocess_cmd_has_max_budget_not_max_turns(monkeypatch):
    monkeypatch.delenv("ZANTARA_CLAUDE_MAX_BUDGET_USD", raising=False)
    cmd = claude_client._build_subprocess_cmd("hi", "sonnet", "", "")

    assert "--max-budget-usd" in cmd
    assert "--max-turns" not in cmd
    idx = cmd.index("--max-budget-usd")
    assert cmd[idx + 1] == "5"

    monkeypatch.setenv("ZANTARA_CLAUDE_MAX_BUDGET_USD", "12.5")
    cmd2 = claude_client._build_subprocess_cmd("hi", "sonnet", "", "")
    idx2 = cmd2.index("--max-budget-usd")
    assert cmd2[idx2 + 1] == "12.5"
