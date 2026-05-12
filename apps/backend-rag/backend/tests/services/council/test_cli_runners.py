"""Unit tests for CLI runners + JSON extractor."""

from __future__ import annotations

import pytest

from backend.services.council.cli_runners import (
    ClaudeCLIRunner,
    CLIRunnerError,
    DeepSeekHTTPRunner,
    GeminiCLIRunner,
    _extract_json,
)

# ── JSON extractor ─────────────────────────────────────────────────────


def test_extract_json_from_bare_json():
    out = '{"register": "analitico", "rationale": "x"}'
    parsed = _extract_json(out)
    assert parsed == {"register": "analitico", "rationale": "x"}


def test_extract_json_from_markdown_fence():
    out = 'preamble\n```json\n{"chosen_register": "tecnico"}\n```\ntrailing'
    parsed = _extract_json(out)
    assert parsed == {"chosen_register": "tecnico"}


def test_extract_json_from_generic_fence():
    out = '```\n{"a": 1}\n```'
    parsed = _extract_json(out)
    assert parsed == {"a": 1}


def test_extract_json_with_prose_around():
    out = (
        "Sure, here's my choice.\n"
        '{"register": "ironico", "example_headline": "hi"}\n'
        "Hope it helps."
    )
    parsed = _extract_json(out)
    assert parsed == {"register": "ironico", "example_headline": "hi"}


def test_extract_json_returns_none_on_garbage():
    assert _extract_json("no json here") is None
    assert _extract_json("") is None


def test_extract_json_returns_none_if_all_candidates_invalid():
    """Extractor must not raise and must return None on malformed input."""
    out = "```\nnot { valid json\n```"
    parsed = _extract_json(out)
    assert parsed is None


# ── ClaudeCLIRunner config ────────────────────────────────────────────


def test_claude_runner_default_binary_path():
    r = ClaudeCLIRunner(binary_path="/fake/claude")
    assert r.binary_path == "/fake/claude"
    assert r.name == "claude"


def test_gemini_runner_default():
    r = GeminiCLIRunner(binary_path="/fake/gemini")
    assert r.binary_path == "/fake/gemini"


def test_deepseek_requires_api_key():
    with pytest.raises(CLIRunnerError):
        DeepSeekHTTPRunner(api_key="")


def test_deepseek_runner_default_model():
    r = DeepSeekHTTPRunner(api_key="sk-test")
    assert r.model == "deepseek-v4-pro"


# ── ClaudeCLIRunner subprocess errors ──────────────────────────────────


@pytest.mark.asyncio
async def test_claude_runner_missing_binary_raises():
    r = ClaudeCLIRunner(binary_path="/does/not/exist/claude_xyz_9999")
    with pytest.raises(CLIRunnerError):
        await r.run("hello", timeout=2)


@pytest.mark.asyncio
async def test_gemini_runner_missing_binary_raises():
    r = GeminiCLIRunner(binary_path="/does/not/exist/gemini_xyz_9999")
    with pytest.raises(CLIRunnerError):
        await r.run("hello", timeout=2)


# ── Echo test: use `echo` as a stand-in binary to exercise subprocess path ──


@pytest.mark.asyncio
async def test_subprocess_runner_success_with_echo(tmp_path):
    """Spin up ClaudeCLIRunner with binary=/bin/echo to verify the async
    subprocess path works end-to-end without needing claude installed."""
    runner = ClaudeCLIRunner(binary_path="/bin/echo", extra_args=["--"])
    result = await runner.run("hello world", timeout=5)
    assert result.ok is True
    assert "hello world" in result.output
    assert result.returncode == 0


@pytest.mark.asyncio
async def test_subprocess_runner_timeout_kills_process(tmp_path):
    """Use a tiny sleeper script to verify timeout cleanly kills the subprocess."""
    sleeper = tmp_path / "sleeper.sh"
    sleeper.write_text("#!/bin/sh\nsleep 5\n")
    sleeper.chmod(0o755)
    runner = ClaudeCLIRunner(binary_path=str(sleeper))
    result = await runner.run("whatever", timeout=1)
    assert result.ok is False
    assert "timeout" in (result.error or "").lower()
