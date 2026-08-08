"""Tests for the SOTA M13 self-commit promotion helper (cure-A, PR #7 mandate).

promote_research_output() copies caller-written research/ files into an
ephemeral worktree and commits+pushes+opens an auto-merge PR there — the
main checkout is never touched by git. Every git/gh/agent_start.py call is
subprocess-mocked; no real git repo, network, or gh CLI is exercised.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

from backend.services.sota_loop._promote import promote_research_output

_REL = "research/sota-social-2026-v1/weekly_report_2026-08-08.md"


def _cp(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def _write_target(tmp_path, rel: str = _REL):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("content")
    return p


def test_nothing_to_promote_when_file_absent(tmp_path, monkeypatch):
    """INNOCENCE: the common case (nothing new written this run) makes ZERO
    subprocess calls — no worktree churn for a no-op."""
    calls: list = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (calls.append(a), _cp())[1])
    ok = promote_research_output(
        tmp_path, ["research/sota-social-2026-v1/does-not-exist.md"],
        commit_subject="x", commit_body="y",
    )
    assert ok is True
    assert calls == []


def test_kill_switch_skips_without_any_subprocess_call(tmp_path, monkeypatch):
    _write_target(tmp_path)
    monkeypatch.setenv("SOTA_PROMOTE_ENABLED", "false")
    calls: list = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (calls.append(a), _cp())[1])
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is True
    assert calls == []


def test_worktree_creation_failure_returns_false(tmp_path, monkeypatch):
    """GUILT: broker disabled / worktree creation error must fail loud, not
    silently pretend success."""
    _write_target(tmp_path)

    def fake_run(cmd, **kwargs):
        if "--lane" in cmd:
            return _cp(returncode=1, stderr="ERROR: broker disabled (AGENT_BROKER_ENABLED=false)")
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is False


def test_no_diff_after_copy_releases_worktree_and_returns_true(tmp_path, monkeypatch):
    """A same-day re-run that copies byte-identical content must not open a
    duplicate PR — it releases the worktree and reports success (no-op)."""
    _write_target(tmp_path)
    wt = tmp_path / ".worktrees" / "wr2-sota-weekly-1"
    wt.mkdir(parents=True)
    released: list = []

    def fake_run(cmd, **kwargs):
        if "--lane" in cmd:
            return _cp(stdout=f"WORKTREE_READY {wt}\n")
        if cmd[:2] == ["git", "status"]:
            return _cp(stdout="")  # no diff
        if "--release" in cmd:
            released.append(cmd)
            return _cp()
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is True
    assert released, "expected --release when the copy produced no diff"


def test_full_success_flow_calls_add_commit_push_pr_and_merge(tmp_path, monkeypatch):
    _write_target(tmp_path)
    wt = tmp_path / ".worktrees" / "wr2-sota-weekly-2"
    wt.mkdir(parents=True)
    seen: list = []

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        if "--lane" in cmd:
            return _cp(stdout=f"WORKTREE_READY {wt}\n")
        if cmd[:2] == ["git", "status"]:
            return _cp(stdout=f" M {_REL}\n")
        if cmd[:2] == ["git", "branch"]:
            return _cp(stdout="agent/host/wr2/sota-weekly-2\n")
        if cmd[:2] == ["git", "push"]:
            return _cp()
        if cmd[:3] == ["gh", "pr", "create"]:
            return _cp(stdout="https://github.com/org/repo/pull/999\n")
        if cmd[:3] == ["gh", "pr", "merge"]:
            return _cp()
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is True
    joined = [" ".join(c) for c in seen]
    assert any(c.startswith("git add") for c in joined)
    assert any(c.startswith("git commit") for c in joined)
    assert any(c.startswith("git push") for c in joined)
    assert any(c.startswith("gh pr create") for c in joined)
    assert any(c.startswith("gh pr merge 999") for c in joined)


def test_push_failure_returns_false_and_does_not_open_pr(tmp_path, monkeypatch):
    """GUILT: a failed push must never proceed to open a PR against a branch
    that never reached origin."""
    _write_target(tmp_path)
    wt = tmp_path / ".worktrees" / "wr2-sota-weekly-3"
    wt.mkdir(parents=True)
    pr_called: list = []

    def fake_run(cmd, **kwargs):
        if "--lane" in cmd:
            return _cp(stdout=f"WORKTREE_READY {wt}\n")
        if cmd[:2] == ["git", "status"]:
            return _cp(stdout=f" M {_REL}\n")
        if cmd[:2] == ["git", "branch"]:
            return _cp(stdout="agent/host/wr2/sota-weekly-3\n")
        if cmd[:2] == ["git", "push"]:
            return _cp(returncode=1, stderr="rejected")
        if cmd[:3] == ["gh", "pr", "create"]:
            pr_called.append(cmd)
            return _cp(stdout="https://github.com/org/repo/pull/1000\n")
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is False
    assert pr_called == []


def test_gh_pr_create_failure_returns_false_but_branch_stays_pushed(tmp_path, monkeypatch):
    _write_target(tmp_path)
    wt = tmp_path / ".worktrees" / "wr2-sota-weekly-4"
    wt.mkdir(parents=True)
    merge_called: list = []

    def fake_run(cmd, **kwargs):
        if "--lane" in cmd:
            return _cp(stdout=f"WORKTREE_READY {wt}\n")
        if cmd[:2] == ["git", "status"]:
            return _cp(stdout=f" M {_REL}\n")
        if cmd[:2] == ["git", "branch"]:
            return _cp(stdout="agent/host/wr2/sota-weekly-4\n")
        if cmd[:2] == ["git", "push"]:
            return _cp()
        if cmd[:3] == ["gh", "pr", "create"]:
            return _cp(returncode=1, stderr="already exists")
        if cmd[:3] == ["gh", "pr", "merge"]:
            merge_called.append(cmd)
            return _cp()
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is False
    assert merge_called == []
