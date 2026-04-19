import sys
from pathlib import Path

import pytest

# Add scripts dir to import path
# parents[6] = repo root (worktree root), scripts/ lives there
# depth: test_file → scripts/ → unit/ → tests/ → backend/ → backend-rag/ → apps/ → repo-root
_SCRIPTS_DIR = Path(__file__).resolve().parents[6] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from check_llm_cost_tracking import (  # noqa: E402
    is_paid_client,
    tracks_cost,
    scan_files,
    WHITELIST_SUBSTRINGS,
)


def test_detects_paid_client_without_tracking(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(
        "from openai import AsyncOpenAI\n"
        "client = AsyncOpenAI()\n"
        "async def call():\n"
        "    return await client.chat.completions.create(model='gpt-4', messages=[])\n",
    )
    assert is_paid_client(f) is True
    assert tracks_cost(f) is False


def test_whitelist_includes_ollama_files():
    assert any("ollama_client.py" in s for s in WHITELIST_SUBSTRINGS)
    assert any("llm/providers/ollama" in s for s in WHITELIST_SUBSTRINGS)


def test_tracked_file_passes(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text(
        "from backend.services.observability import llm_cost_tracked\n"
        "from openai import AsyncOpenAI\n"
        "@llm_cost_tracked(provider='openai', static_model='x')\n"
        "async def call(): ...\n",
    )
    assert is_paid_client(f) is True
    assert tracks_cost(f) is True


def test_scan_returns_violations(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from openai import AsyncOpenAI\n"
        "AsyncOpenAI().chat.completions.create()\n",
    )
    good = tmp_path / "good.py"
    good.write_text(
        "from openai import AsyncOpenAI\n"
        "record_llm_call()\n",
    )

    violations = scan_files([tmp_path])
    assert str(bad) in violations
    assert str(good) not in violations


def test_scan_respects_whitelist(tmp_path, monkeypatch):
    # Simulate a whitelisted file
    f = tmp_path / "ollama_client.py"
    f.write_text("from openai import AsyncOpenAI\nAsyncOpenAI()\n")

    # Inject our test path substring into the whitelist
    import check_llm_cost_tracking as mod
    original = list(mod.WHITELIST_SUBSTRINGS)
    try:
        mod.WHITELIST_SUBSTRINGS.append("ollama_client.py")
        violations = scan_files([tmp_path])
        assert str(f) not in violations
    finally:
        mod.WHITELIST_SUBSTRINGS.clear()
        mod.WHITELIST_SUBSTRINGS.extend(original)
