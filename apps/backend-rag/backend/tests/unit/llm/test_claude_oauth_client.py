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
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
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
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "same")

    got = mod._collect_tokens()

    assert [label for _, label in got] == ["token_1", "keychain"]


@pytest.mark.asyncio
async def test_build_env_strips_api_key(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("ANTHROPIC_API_KEY", "should_not_leak")
    env = mod._build_env("tok_xyz")

    assert "ANTHROPIC_API_KEY" not in env
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok_xyz"


@pytest.mark.asyncio
async def test_complete_async_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")

    calls: list[dict[str, Any]] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        calls.append(
            {"args": args, "env_has_api_key": "ANTHROPIC_API_KEY" in kwargs.get("env", {})}
        )
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
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
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
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
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
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
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
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("no claude binary")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthNotAvailable):
        await mod.complete_async("ping")


@pytest.mark.asyncio
async def test_complete_async_argv_is_hardened(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """The built argv must drop bypassPermissions, end with a ``--`` sentinel
    immediately before the prompt, and reject non-allowlisted model slugs."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")

    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    # (iv) a valid, allowlisted slug passes and reaches the subprocess.
    resp = await mod.complete_async("untrusted prompt", model="claude-sonnet-4-6")
    assert resp.text == "ok"

    cmd = captured["cmd"]
    # (i) the dangerous permission bypass is gone.
    assert "bypassPermissions" not in cmd
    assert "--permission-mode" not in cmd
    # tools are explicitly disallowed instead.
    assert "--disallowedTools" in cmd
    # (ii) the `--` sentinel is present and sits immediately before the prompt.
    assert "--" in cmd
    assert cmd[-2] == "--"
    assert cmd[-1] == "untrusted prompt"
    # the model slug was forwarded.
    assert "--model" in cmd
    assert "claude-sonnet-4-6" in cmd

    # (iii) a non-allowlisted model (flag-shaped) raises before any subprocess.
    with pytest.raises(ValueError):
        await mod.complete_async("ping", model="--evil-flag")


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


# ---------------------------------------------------------------------------
# --json-schema structured-output path (SPEC v2)
# ---------------------------------------------------------------------------

_ENVELOPE_OK = (
    b'{"type":"result","subtype":"success","is_error":false,'
    b'"result":"The domain is visa.",'
    b'"structured_output":{"domain":"visa","confidence":0.95},'
    b'"usage":{"input_tokens":120,"output_tokens":18}}'
)


@pytest.fixture
def force_schema_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the memoized --json-schema capability probe to True."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setattr(mod, "_JSON_SCHEMA_SUPPORTED", True)


@pytest.fixture
def force_schema_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setattr(mod, "_JSON_SCHEMA_SUPPORTED", False)


_SCHEMA = {
    "type": "object",
    "properties": {"domain": {"type": "string"}, "confidence": {"type": "number"}},
    "required": ["domain", "confidence"],
}


@pytest.mark.asyncio
async def test_json_schema_none_is_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """json_schema=None must NOT add --output-format/--json-schema to argv (D1)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"plain text", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert resp.text == "plain text"
    assert resp.structured is None
    assert "--json-schema" not in captured["cmd"]
    assert "--output-format" not in captured["cmd"]


@pytest.mark.asyncio
async def test_json_schema_envelope_parsed(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """A well-formed envelope yields structured + flags placed before `--` (D2/D6)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=_ENVELOPE_OK, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", model="claude-haiku-4-5-20251001", json_schema=_SCHEMA)

    # structured_output is the real answer; text is the PROSE result (D2).
    assert resp.structured == {"domain": "visa", "confidence": 0.95}
    assert resp.text == "The domain is visa."
    cmd = captured["cmd"]
    # flags present and the `--` sentinel still sits immediately before the prompt (D6).
    assert "--output-format" in cmd and "json" in cmd
    assert "--json-schema" in cmd
    assert cmd[-2] == "--"
    assert cmd[-1] == "classify"
    # the schema blob never precedes the model flag chaos — it's a single argv token.
    schema_idx = cmd.index("--json-schema") + 1
    assert cmd[schema_idx].startswith("{") and "domain" in cmd[schema_idx]


@pytest.mark.asyncio
async def test_json_schema_ndjson_last_result_wins(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """NDJSON stream: the last type==result object provides the structured answer."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    ndjson = (
        b'{"type":"system","subtype":"init"}\n'
        b'{"type":"assistant","message":"thinking"}\n'
        + _ENVELOPE_OK
    )

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        return _fake_proc(stdout=ndjson, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)
    assert resp.structured == {"domain": "visa", "confidence": 0.95}


@pytest.mark.asyncio
async def test_json_schema_is_error_envelope_falls_through(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """is_error:true (even on exit 0) is treated as empty → retry next token."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    counter = {"n": 0}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        counter["n"] += 1
        if counter["n"] == 1:
            return _fake_proc(
                stdout=b'{"type":"result","is_error":true,"result":"Overloaded"}',
                returncode=0,
            )
        return _fake_proc(stdout=_ENVELOPE_OK, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)
    assert resp.structured == {"domain": "visa", "confidence": 0.95}
    assert resp.attempts == 2


@pytest.mark.asyncio
async def test_json_schema_unsupported_cli_degrades_to_text(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_unsupported: None,
) -> None:
    """A CLI without the flag drops the schema and runs the plain text path (D4)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"plain answer", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)

    assert resp.text == "plain answer"
    assert resp.structured is None
    assert "--json-schema" not in captured["cmd"]


@pytest.mark.asyncio
async def test_json_schema_oversize_drops_to_text(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """A schema over the argv cap is dropped; the text path runs (D6 size-cap)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"text fallback", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    huge_schema = {"type": "object", "properties": {f"f{i}": {"type": "string"} for i in range(5000)}}
    resp = await mod.complete_async("classify", json_schema=huge_schema)

    assert resp.text == "text fallback"
    assert "--json-schema" not in captured["cmd"]


@pytest.mark.asyncio
async def test_json_schema_rate_limit_on_exit_nonzero_scans_stdout(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """In schema mode, a rate-limit error on STDOUT with exit!=0 must still be
    caught (panel fix: isolate-to-stderr only on exit 0)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "t2")
    counter = {"n": 0}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        counter["n"] += 1
        if counter["n"] == 1:
            # rate-limit reported on stdout, empty stderr, non-zero exit.
            return _fake_proc(
                stdout=b'{"error":"rate limit exceeded"}', stderr=b"", returncode=1
            )
        return _fake_proc(stdout=_ENVELOPE_OK, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)
    assert resp.token_label == "token_2"
    assert resp.structured == {"domain": "visa", "confidence": 0.95}


def test_parse_json_envelope_unit() -> None:
    """Direct unit coverage of the envelope parser's return contract."""
    from backend.llm.claude_oauth_client import _parse_json_envelope

    text, structured, usage = _parse_json_envelope(_ENVELOPE_OK.decode())
    assert text == "The domain is visa."
    assert structured == {"domain": "visa", "confidence": 0.95}
    assert usage == {"input_tokens": 120, "output_tokens": 18}

    # empty / unparseable → all-None contract
    assert _parse_json_envelope("") == ("", None, None)
    assert _parse_json_envelope("not json at all") == ("", None, None)

    # envelope without structured_output → text+usage but structured None
    no_struct = '{"type":"result","is_error":false,"result":"hi","usage":{"input_tokens":3,"output_tokens":1}}'
    t, s, u = _parse_json_envelope(no_struct)
    assert t == "hi" and s is None and u == {"input_tokens": 3, "output_tokens": 1}


def test_serialize_schema_compact_and_capped() -> None:
    from backend.llm.claude_oauth_client import _MAX_SCHEMA_BYTES, _serialize_schema

    blob = _serialize_schema({"a": 1, "b": 2})
    assert blob == '{"a":1,"b":2}'  # compact separators (no spaces)

    with pytest.raises(ValueError):
        _serialize_schema({"x": "y" * (_MAX_SCHEMA_BYTES + 100)})
