"""Model pin added 2026-08-20 (token-cuts round2) on a grandfathered bare
`claude --print` call site (scripts/lint/lint_claude_headless_model_pin.py,
infra/claude-headless-model-pin/grandfathered.json), picked by measured real
invocation cadence rather than a guess:

  - scripts/cron-agent-python/agent_job.py — shared reasoning lib imported by
    all 21 cron-agent-python job scripts (~477 launchd/cron ticks/day across
    the fleet); the two bare calls are session-bootstrap pings, now pinned
    to haiku.

NOTE: scripts/dlq_autopilot.py was ALSO measured as genuinely bare in this
same pass, but PR #4430 (team-lead's, armed first) already pins it — same
insertion point after REASONING_TIMEOUT_S = 90, same --model addition inside
claude_reason()'s argv, just haiku instead of sonnet. Dropped here to avoid
a textual merge conflict on the same lines; #4430 owns that file.

The test pins the guilt case: constructing the real argv still contains
"--model" immediately followed by a claude-* slug pattern (mirrors the
allowlist shape in apps/backend-rag/backend/llm/claude_oauth_client.py
_ALLOWED_MODEL_RE), so a future edit that drops the flag or the value fails
loud here instead of silently reintroducing the bare call.
"""

from __future__ import annotations

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
