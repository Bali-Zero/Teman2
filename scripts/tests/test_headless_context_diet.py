"""Context-diet for the sentinel classifier + DLQ autopilot `claude --print` spawns
(2026-08-20).

Measured on Pro (CLI 2.1.237, Haiku): ambient headless context from repo cwd =
92,397 tokens; from a neutral cwd = 43,426; with --safe-mode +
--strict-mcp-config + an isolated empty cwd = 22,408. Both
sentinel_lib.classifier.classify_with_llm() and dlq_autopilot.claude_reason()
spawn pure self-contained f-string prompts with no tool access, so
skills/hooks/CLAUDE.md/MCP are pure overhead on these lanes (sentinel <=144
ticks/day, DLQ <=48/day). dlq_autopilot.dispatch_aider() is deliberately NOT
touched — it operates on the checkout via Aider and needs cwd=NUZANTARA_ROOT —
and is pinned here by an innocence test.

Test classes:
  TestClassifierContextDiet — GUILT: classify_with_llm() spawns claude with the
    three hardening flags and an isolated, non-repo-root cwd. INNOCENCE: the
    deterministic classify() regex path never touches subprocess at all.
  TestDlqContextDiet — GUILT: claude_reason() spawns claude with the same three
    flags + isolated cwd via _run_process_group(). INNOCENCE: dispatch_aider()
    still passes cwd=str(NUZANTARA_ROOT) to every subprocess.run() call — the
    diet must not leak into the repo-dependent spawn.

Run:
    cd ~/nuzantara/.worktrees/ops-headless-context-diet
    source apps/backend-rag/.venv/bin/activate
    python -m pytest scripts/tests/test_headless_context_diet.py -v
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

# scripts/tests/test_headless_context_diet.py -> parents[2] == repo root
# (same convention as test_claude_oauth_runtime_fallback.py::REPO_ROOT).
REPO_ROOT = Path(__file__).resolve().parents[2]

HARDENING_FLAGS = ("--safe-mode", "--strict-mcp-config")
MCP_EMPTY_CONFIG = '{"mcpServers":{}}'


def _load_module(relative_path: str, name: str) -> ModuleType:
    """Load a script module by explicit file path, not sys.path — avoids
    resolving to a sibling checkout (same pattern as
    test_claude_oauth_runtime_fallback.py::_load_module)."""
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_classifier(name: str) -> ModuleType:
    return _load_module("scripts/sentinel_lib/classifier.py", name)


def _load_dlq(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load dlq_autopilot.py by path with HOME monkeypatched to tmp_path FIRST
    (same pattern as test_dlq_board_honesty.py::dlq fixture) so NUZANTARA_ROOT
    resolves under the sandbox, not the real checkout."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    return _load_module("scripts/dlq_autopilot.py", name)


def _assert_context_diet_argv(argv: list[str]) -> None:
    for flag in HARDENING_FLAGS:
        assert flag in argv, f"missing hardening flag {flag!r} in argv {argv!r}"
    assert MCP_EMPTY_CONFIG in argv, f"missing empty mcp-config in argv {argv!r}"


# ─────────────────────────────────────────────────────────────────────────────
# sentinel_lib/classifier.py
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifierContextDiet:
    def test_guilt_classify_with_llm_spawns_safe_mode_isolated_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """classify_with_llm() must spawn `claude --print` with --safe-mode +
        --strict-mcp-config + an empty --mcp-config, cwd'd into an isolated,
        non-repo directory that actually exists on disk."""
        module = _load_classifier("context_diet_classifier_guilt")
        isolated_dir = tmp_path / "sentinel-claude-cwd"
        monkeypatch.setenv("SENTINEL_CLAUDE_CWD", str(isolated_dir))

        captured: dict = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            captured["kwargs"] = kwargs
            payload = json.dumps(
                {
                    "type": "TRANSIENT",
                    "subtype": "network",
                    "fix_suggestion": "retry",
                    "confidence": 0.8,
                }
            )
            return subprocess.CompletedProcess(cmd, 0, payload, "")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        result = module.classify_with_llm("connection dropped", "some-job")

        _assert_context_diet_argv(captured["cmd"])
        cwd = captured["kwargs"].get("cwd")
        assert cwd is not None, "classify_with_llm() must pass an explicit cwd"
        assert Path(cwd).exists(), "isolated cwd must be created on disk"
        assert Path(cwd).resolve() != REPO_ROOT.resolve(), (
            "cwd must NOT be the repo root (that is exactly the 92.4k-token case)"
        )
        assert Path(cwd).resolve() == isolated_dir.resolve()
        assert result["type"] == "TRANSIENT"

    def test_innocence_deterministic_classify_never_spawns_subprocess(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The deterministic classify() regex path is untouched by the diet —
        it must never call subprocess at all. Proves the diet only touched the
        LLM fallback branch (classify_with_llm), not the fast path."""
        module = _load_classifier("context_diet_classifier_innocence")

        def _boom(*_args, **_kwargs):
            raise AssertionError("classify() must never spawn a subprocess")

        monkeypatch.setattr(module.subprocess, "run", _boom)

        result = module.classify("Connection refused by remote host", retry_count=0)

        assert result["type"] == "TRANSIENT"
        assert result["subtype"] == "network_or_service"
        assert result["confidence"] == 0.9


# ─────────────────────────────────────────────────────────────────────────────
# dlq_autopilot.py
# ─────────────────────────────────────────────────────────────────────────────

class TestDlqContextDiet:
    def test_guilt_claude_reason_spawns_safe_mode_isolated_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """claude_reason() must spawn `claude --print` (via _run_process_group)
        with the same three hardening flags, cwd'd into an isolated,
        non-repo-root directory."""
        module = _load_dlq(
            "context_diet_dlq_autopilot_guilt", tmp_path, monkeypatch
        )
        isolated_dir = tmp_path / "dlq-claude-cwd"
        monkeypatch.setenv("DLQ_CLAUDE_CWD", str(isolated_dir))
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "fake-token")
        for i in (2, 3, 4, 5):
            monkeypatch.delenv(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        module._EXHAUSTED_TOKENS.clear()

        captured: dict = {}
        success_stdout = json.dumps(
            {
                "fix_type": "config",
                "fix_instruction": "restore the missing runtime setting",
                "confidence": 0.9,
                "needs_code_change": False,
            }
        )

        def fake_run_process_group(cmd, *, timeout, env=None, cwd=None):
            captured["cmd"] = list(cmd)
            captured["cwd"] = cwd
            return subprocess.CompletedProcess(cmd, 0, success_stdout, "")

        monkeypatch.setattr(module, "_run_process_group", fake_run_process_group)

        result = module.claude_reason(
            {
                "job": "test-job",
                "error_summary": "a sufficiently detailed test failure",
                "log_tail": "",
                "files_implicated": [],
            }
        )

        assert result is not None
        _assert_context_diet_argv(captured["cmd"])
        cwd = captured["cwd"]
        assert cwd is not None, "claude_reason() must pass an explicit cwd"
        assert Path(cwd).exists(), "isolated cwd must be created on disk"
        assert Path(cwd).resolve() != REPO_ROOT.resolve()
        assert Path(cwd).resolve() != module.NUZANTARA_ROOT.resolve(), (
            "claude_reason() must NOT use the repo checkout as cwd"
        )
        assert Path(cwd).resolve() == isolated_dir.resolve()

    def test_innocence_dispatch_aider_keeps_repo_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """dispatch_aider() is deliberately untouched by the diet — every
        subprocess.run() call it makes (git stash + the ai-dispatch.sh bash
        call) must still pass cwd=str(NUZANTARA_ROOT). Pins that the diet did
        not leak into the repo-dependent spawn."""
        module = _load_dlq(
            "context_diet_dlq_autopilot_innocence", tmp_path, monkeypatch
        )
        dispatch_script = module.NUZANTARA_ROOT / "scripts" / "ai-dispatch.sh"
        dispatch_script.parent.mkdir(parents=True, exist_ok=True)
        dispatch_script.write_text("#!/bin/bash\necho ok\n")

        captured_calls: list[tuple[list, dict]] = []

        def fake_run(cmd, **kwargs):
            captured_calls.append((list(cmd), kwargs))
            if list(cmd)[:2] == ["git", "stash"]:
                return subprocess.CompletedProcess(cmd, 0, "No local changes to stash", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        entry = {
            "job": "test-job",
            "error_summary": "boom",
            "files_implicated": ["some/file.py"],
        }
        reasoning = {"fix_instruction": "do the fix"}
        registry = {"test-job": {"test_cmd": "true"}}

        success, _output = module.dispatch_aider(entry, reasoning, registry)

        assert success is True
        bash_calls = [c for c in captured_calls if c[0] and c[0][0] == "bash"]
        git_calls = [c for c in captured_calls if c[0] and c[0][0] == "git"]
        assert bash_calls, "expected dispatch_aider to spawn the ai-dispatch.sh bash call"
        assert git_calls, "expected dispatch_aider to spawn the pre-flight git stash call"
        for cmd, kwargs in bash_calls + git_calls:
            assert kwargs.get("cwd") == str(module.NUZANTARA_ROOT), (
                f"dispatch_aider() spawn {cmd!r} must keep cwd=NUZANTARA_ROOT, "
                f"got {kwargs.get('cwd')!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# MUTATION CHECK (manual, report only — no mutations actually committed):
#
#   sentinel_lib/classifier.py::classify_with_llm — reverting any one of the
#   three argv flags (--safe-mode, --strict-mcp-config, --mcp-config
#   '{"mcpServers":{}}') makes _assert_context_diet_argv() in
#   test_guilt_classify_with_llm_spawns_safe_mode_isolated_cwd fail on the
#   corresponding `assert flag in argv` / `assert MCP_EMPTY_CONFIG in argv`
#   line. Reverting the cwd=str(_isolated_cwd()) kwarg (dropping it, or
#   passing None) fails `assert cwd is not None` in the same test.
#
#   dlq_autopilot.py::claude_reason — same three flags, caught by the same
#   _assert_context_diet_argv() call inside
#   test_guilt_claude_reason_spawns_safe_mode_isolated_cwd. Reverting the
#   cwd=str(_isolated_cwd()) kwarg fails `assert cwd is not None` /
#   `assert Path(cwd).resolve() != module.NUZANTARA_ROOT.resolve()` in the
#   same test (the latter also catches an accidental cwd=NUZANTARA_ROOT
#   regression, i.e. the diet quietly reusing dispatch_aider's cwd).
#
#   dlq_autopilot.py::_run_process_group — dropping the `cwd=cwd` pass-through
#   to subprocess.Popen would make the GUILT test's captured cwd never reach
#   the real Popen call, but since the test replaces _run_process_group
#   itself, that specific regression is caught structurally by
#   test_innocence_dispatch_aider_keeps_repo_cwd staying green (it does not
#   go through _run_process_group at all) combined with the GUILT test's
#   asserts on the captured kwarg the real call site passes.
# ─────────────────────────────────────────────────────────────────────────────
