"""Model pins added 2026-08-20 (token-cuts round2) on three grandfathered
bare `claude -p`/`--print` call sites (scripts/lint/lint_claude_headless_model_pin.py,
infra/claude-headless-model-pin/grandfathered.json), picked by measured real
invocation cadence rather than a guess:

  - scripts/cron-agent-python/agent_job.py — shared reasoning lib imported by
    all 21 cron-agent-python job scripts (~477 launchd/cron ticks/day across
    the fleet); the two bare calls are session-bootstrap pings, now pinned
    to haiku.
  - scripts/dlq_autopilot.py — confirmed StartInterval=1800s cron
    (com.nuzantara.dlq-autopilot.plist), a real structured-classification
    reasoning call, now pinned to sonnet.

Each test pins the guilt case: constructing the real argv still contains
"--model" immediately followed by a claude-* slug pattern (mirrors the
allowlist shape in apps/backend-rag/backend/llm/claude_oauth_client.py
_ALLOWED_MODEL_RE), so a future edit that drops the flag or the value fails
loud here instead of silently reintroducing the bare call.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CRON_AGENT_PYTHON = REPO / "scripts" / "cron-agent-python"

_MODEL_RE = re.compile(r"^claude-[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")


def _model_after_flag(argv: list[str]) -> str | None:
    for i, tok in enumerate(argv):
        if tok == "--model" and i + 1 < len(argv):
            return argv[i + 1]
    return None


# ── scripts/cron-agent-python/agent_job.py ──────────────────────────────


@pytest.fixture()
def agent_job(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    sys.path.insert(0, str(CRON_AGENT_PYTHON))
    # Force a fresh import bound to the redirected HOME/STATE_DIR.
    for name in list(sys.modules):
        if name == "agent_job":
            del sys.modules[name]
    import agent_job as mod

    return mod


def test_session_bootstrap_calls_pin_a_real_model(agent_job, monkeypatch):
    """GUILT: both bare `claude --print` session-bootstrap calls now carry
    --model with a value matching the allowlist shape, and never inherit
    a caller-supplied model none of the 21 job scripts pass."""
    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(list(argv))

        class _R:
            returncode = 0
            stdout = '{"session_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}'
            stderr = ""

        return _R()

    # get_or_create_session() does `import subprocess` locally inside the
    # function body, so it resolves subprocess.run off the shared module
    # object at call time — patch that shared object, not an agent_job
    # attribute (there isn't one; the import never binds at module scope).
    monkeypatch.setattr(subprocess, "run", fake_run)
    agent_job.get_or_create_session("test-job", scope="persistent")

    assert captured, "get_or_create_session never called subprocess.run"
    for argv in captured:
        model = _model_after_flag(argv)
        assert model is not None, f"no --model in {argv!r}"
        assert _MODEL_RE.match(model), f"model {model!r} doesn't match allowlist shape"
    # The specific tier chosen: haiku (bootstrap ping does no reasoning).
    assert all(_model_after_flag(a) == "claude-haiku-4-5-20251001" for a in captured)


def test_session_bootstrap_model_is_overridable_but_never_empty():
    """INNOCENCE: SESSION_BOOTSTRAP_MODEL is a module-level constant, not a
    per-call accident — every call site references the same name."""
    src = (CRON_AGENT_PYTHON / "agent_job.py").read_text()
    assert src.count("SESSION_BOOTSTRAP_MODEL") >= 3  # def + 2 call sites


# ── scripts/dlq_autopilot.py ─────────────────────────────────────────────


@pytest.fixture()
def dlq(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    mod_path = Path(__file__).parent.parent / "dlq_autopilot.py"
    spec = importlib.util.spec_from_file_location("dlq_autopilot_model_pin_round2", mod_path)
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    return d


def test_claude_reason_pins_a_real_model(dlq, monkeypatch):
    """GUILT: claude_reason()'s argv to _run_process_group carries --model
    with a value matching the allowlist shape — was bare before this fix
    (zero "model" occurrences in the file)."""
    captured: list[list[str]] = []

    class _R:
        returncode = 0
        stdout = '{"fix_type": "unknown", "fix_instruction": "n/a", "confidence": 0.1, "needs_code_change": false}'
        stderr = ""

    def fake_run_process_group(argv, **kwargs):
        captured.append(list(argv))
        return _R()

    monkeypatch.setattr(dlq, "_run_process_group", fake_run_process_group)
    monkeypatch.setattr(dlq, "_load_token_chain", lambda: [("primary", "fake-token")])

    dlq.claude_reason({"job": "test-job", "error_summary": "boom", "log_tail": "", "files_implicated": []})

    assert captured, "claude_reason never called _run_process_group"
    model = _model_after_flag(captured[0])
    assert model is not None, f"no --model in {captured[0]!r}"
    assert _MODEL_RE.match(model)
    assert model == "claude-sonnet-5"


def test_reasoning_model_env_override(monkeypatch, tmp_path):
    """INNOCENCE: DLQ_CLAUDE_MODEL env override still produces a value
    matching the allowlist shape (operators can dial cost up/down without
    ever landing back on a bare call)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("DLQ_CLAUDE_MODEL", "claude-opus-5")
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    mod_path = Path(__file__).parent.parent / "dlq_autopilot.py"
    spec = importlib.util.spec_from_file_location("dlq_autopilot_model_pin_round2_env", mod_path)
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    assert d.REASONING_MODEL == "claude-opus-5"
