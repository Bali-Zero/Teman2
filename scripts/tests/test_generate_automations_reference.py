"""Tests for scripts/generate_automations_reference.py's prettier call.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package (mirrors scripts/tests/test_adversarial_review_gate.py convention).

Pins the defect measured on Pro's first live run of
scripts/automations-reference-cron-wrapper.sh (2026-09-1x): the generator
wrote docs/AUTOMATIONS_REFERENCE.md inside an isolated worktree, then ran
`npx prettier --write <absolute worktree path>` with the CALLER's cwd — the
main checkout, where `.worktrees/` is gitignored. Prettier honours
.gitignore, so it matched ZERO files and reported success in ~1s while the
file itself, from the worktree's own cwd, showed real style warnings. The
husky pre-commit hook in the worktree then failed on the unformatted file,
and the wrapper (fixed separately) ignored that non-zero commit rc.

Fix pinned here: run prettier with `cwd=NUZANTARA_ROOT` explicitly and a path
RELATIVE to it, so the caller's cwd cannot make prettier silently skip the
file, and surface rc/stderr instead of swallowing them into /dev/null.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parent.parent / "generate_automations_reference.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_automations_reference", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gen = _load_module()


def _fake_completed(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["npx", "prettier"], returncode=returncode, stdout="", stderr=stderr)


def test_run_prettier_uses_nuzantara_root_cwd_and_relative_path(capsys):
    with mock.patch("subprocess.run", return_value=_fake_completed(0)) as mock_run:
        gen._run_prettier("docs/AUTOMATIONS_REFERENCE.md", cwd=gen.NUZANTARA_ROOT)

    mock_run.assert_called_once()
    _args, kwargs = mock_run.call_args
    called_cmd = _args[0] if _args else kwargs.get("args")
    assert called_cmd == ["npx", "prettier", "--write", "docs/AUTOMATIONS_REFERENCE.md"]
    assert kwargs["cwd"] == gen.NUZANTARA_ROOT
    # No absolute path anywhere in the invoked command — that is precisely the
    # shape that let prettier's own .gitignore matching silently no-op.
    assert not any(str(gen.NUZANTARA_ROOT) in str(a) for a in called_cmd)
    out = capsys.readouterr().out
    assert "prettier rc=" not in out  # success path prints nothing


def test_run_prettier_prints_rc_and_stderr_on_failure(capsys):
    with mock.patch("subprocess.run", return_value=_fake_completed(2, "some style error\n")):
        gen._run_prettier("docs/AUTOMATIONS_REFERENCE.md", cwd=gen.NUZANTARA_ROOT)

    out = capsys.readouterr().out
    assert "prettier rc=2" in out
    assert "some style error" in out


def test_run_prettier_timeout_does_not_raise(capsys):
    with mock.patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["npx", "prettier"], timeout=30),
    ):
        gen._run_prettier("docs/AUTOMATIONS_REFERENCE.md", cwd=gen.NUZANTARA_ROOT, timeout=30)

    out = capsys.readouterr().out
    assert "prettier rc=timeout" in out


def test_generate_calls_run_prettier_with_relative_path_from_nuzantara_root(tmp_path, monkeypatch):
    """`generate()` must hand _run_prettier a path relative to NUZANTARA_ROOT,
    not the caller's cwd — this is the exact call site the live-run defect
    was found in."""
    fake_root = tmp_path / "worktree-checkout"
    (fake_root / "docs").mkdir(parents=True)
    monkeypatch.setattr(gen, "NUZANTARA_ROOT", fake_root)
    monkeypatch.setattr(gen, "OUTPUT_FILE", fake_root / "docs" / "AUTOMATIONS_REFERENCE.md")
    monkeypatch.setattr(gen, "_check_output_safety", lambda path: None)
    # Every external state source degrades to empty/graceful, so generate()
    # runs end to end without touching the real machine.
    monkeypatch.setattr(gen, "_run", lambda *a, **k: "")
    monkeypatch.setattr(gen, "_ssh_mini", lambda *a, **k: "")
    monkeypatch.setattr(gen, "_load_registry", lambda *a, **k: {})
    monkeypatch.setattr(gen, "_load_sentinel_state", lambda *a, **k: ({}, {}))

    captured: dict = {}

    def fake_run_prettier(relative_path, cwd=gen.NUZANTARA_ROOT, timeout=30):
        captured["relative_path"] = relative_path
        captured["cwd"] = cwd

    monkeypatch.setattr(gen, "_run_prettier", fake_run_prettier)

    gen.generate(dry_run=False)

    assert captured["cwd"] == fake_root
    assert captured["relative_path"] == "docs/AUTOMATIONS_REFERENCE.md"
    assert not Path(captured["relative_path"]).is_absolute()
