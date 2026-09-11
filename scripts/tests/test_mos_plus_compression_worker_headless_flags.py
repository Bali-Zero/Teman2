"""mos-plus-compression-worker.py — headless claude invocation (D-006, 2026-09-01).

The claude_haiku tier call must run with `--setting-sources "" --strict-mcp-config`
so it skips SessionStart hooks + CLAUDE.md + MCP schema injection — measured
~350K -> ~13K input tokens/call (tokenaudit 2026-09-01,
~/.tokenaudit/reports/04-rightsizing.md). `-p prompt` must stay the LAST two argv
elements: a list-valued flag placed AFTER `-p` would swallow the prompt as its
own value instead of leaving it as `-p`'s positional argument.

Same import shape as test_mos_plus_compression_worker.py (W96 class): the module
does real work at import (os.path.expanduser("~/.claude/...") evaluated at load),
so HOME is redirected to a throwaway tmp_path BEFORE import, and the module is
loaded by path (hyphenated filename, not a valid Python identifier). `main()` is
guarded by `if __name__ == "__main__":` (verified: only that guarded call site
invokes it), so importing this module never executes the worker loop.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "mos-plus-compression-worker.py"


@pytest.fixture()
def worker(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("MOS_PLUS_OLLAMA_URL", raising=False)

    spec = importlib.util.spec_from_file_location(
        "mos_plus_compression_worker_headless", SRC
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mos_plus_compression_worker_headless"] = mod
    spec.loader.exec_module(mod)
    try:
        yield mod
    finally:
        sys.modules.pop("mos_plus_compression_worker_headless", None)


def test_claude_haiku_call_runs_headless_without_harness_bootstrap(worker, monkeypatch):
    captured = {}

    class FakeResult:
        returncode = 0
        stdout = "synthesized"
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return FakeResult()

    monkeypatch.setattr(worker.subprocess, "run", fake_run)

    out = worker.call_claude_haiku("compress these observations")

    assert out == "synthesized"
    argv = captured["argv"]

    assert "--setting-sources" in argv, "must skip global/project/local settings load"
    idx = argv.index("--setting-sources")
    assert argv[idx + 1] == "", (
        "--setting-sources must be given the empty string (no settings sources), "
        f"got {argv[idx + 1]!r}"
    )
    assert "--strict-mcp-config" in argv, "must not load any ambient MCP server config"

    # `-p prompt` must be the LAST two argv elements — a list-valued flag placed
    # after `-p` would swallow the prompt as its own value instead of leaving it
    # as -p's positional argument (the exact agy-cli trap this repo already hit,
    # cf. the call_agy_gemini comment in this same file).
    assert argv[-2:] == ["-p", "compress these observations"], (
        f"-p <prompt> must be the trailing pair of argv, got tail={argv[-3:]}"
    )


def test_claude_haiku_argv_flags_precede_the_prompt(worker, monkeypatch):
    """Guilt: a flag reordering that put --setting-sources/--strict-mcp-config
    AFTER -p would silently break the prompt delivery (agy-cli class of bug) —
    this pins the ordering, not just the presence of each flag."""
    captured = {}

    class FakeResult:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(
        worker.subprocess, "run",
        lambda argv, **kwargs: captured.setdefault("argv", argv) or FakeResult(),
    )

    worker.call_claude_haiku("hello")
    argv = captured["argv"]

    p_idx = argv.index("-p")
    setting_idx = argv.index("--setting-sources")
    strict_idx = argv.index("--strict-mcp-config")

    assert setting_idx < p_idx and strict_idx < p_idx, (
        "both flags must precede -p so the prompt stays -p's own trailing value"
    )
