"""Tests for the SOTA M13 self-commit promotion helper (cure-A, PR #7 mandate).

promote_research_output() copies caller-written research/ files into an
ephemeral worktree and commits+pushes+opens an auto-merge PR there — the
main checkout is never touched by git. Every git/gh/agent_start.py call is
subprocess-mocked; no real git repo, network, or gh CLI is exercised.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

from backend.services.sota_loop._promote import promote_research_output

_REL = "research/sota-social-2026-v1/weekly_report_2026-08-08.md"


def _find_repo_root() -> Path:
    """Walk up from this file until scripts/check_adversarial_review.py is
    found — mirrors scripts/tests/test_adversarial_review_gate.py's own
    loader convention (scripts/ is a flat bag, not a package)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "scripts" / "check_adversarial_review.py").is_file():
            return parent
    raise RuntimeError("could not locate repo root from test_promote.py")


def _load_r1_gate() -> ModuleType:
    module_path = _find_repo_root() / "scripts" / "check_adversarial_review.py"
    spec = importlib.util.spec_from_file_location("check_adversarial_review", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r1_gate = _load_r1_gate()


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


# --------------------------------------------------------------------------- #
# R1 generator!=grader compliance (cure-B, follow-up to PR #4581): every
# research/**/*.md this module promotes must pass scripts/check_adversarial_
# review.py by construction, never born red on the R1 gate.
# --------------------------------------------------------------------------- #


def test_promoted_md_passes_r1_gate_when_refuter_reachable(tmp_path, monkeypatch):
    """INNOCENCE: kimi reachable and returns findings -> real seat + section,
    and the resulting file PASSES the actual R1 gate (not a re-implementation
    of its rule)."""
    target = _write_target(tmp_path)
    wt = tmp_path / ".worktrees" / "wr2-sota-weekly-5"
    wt.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "--lane" in cmd:
            return _cp(stdout=f"WORKTREE_READY {wt}\n")
        if cmd[:1] == ["kimi"]:
            return _cp(stdout="NONE — deltas reconcile with kpi_timeline.csv.\n")
        if cmd[:2] == ["git", "status"]:
            return _cp(stdout=f" M {_REL}\n")
        if cmd[:2] == ["git", "branch"]:
            return _cp(stdout="agent/host/wr2/sota-weekly-5\n")
        if cmd[:2] == ["git", "push"]:
            return _cp()
        if cmd[:3] == ["gh", "pr", "create"]:
            return _cp(stdout="https://github.com/org/repo/pull/1001\n")
        if cmd[:3] == ["gh", "pr", "merge"]:
            return _cp()
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is True

    promoted = wt / _REL
    verdict = r1_gate.evaluate_file(promoted)
    assert verdict.ok is True, verdict.reason
    assert "kimi" in promoted.read_text()
    assert target.read_text() == "content"  # source file untouched


def test_promoted_md_passes_r1_gate_when_refuter_unreachable(tmp_path, monkeypatch):
    """GUILT-adjacent INNOCENCE: kimi missing/times out -> the promoter must
    NOT fabricate a `kimi-k3` claim for a review that never ran. It falls
    back to an honest `exempt-` marker, which the real R1 gate accepts."""
    _write_target(tmp_path)
    wt = tmp_path / ".worktrees" / "wr2-sota-weekly-6"
    wt.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "--lane" in cmd:
            return _cp(stdout=f"WORKTREE_READY {wt}\n")
        if cmd[:1] == ["kimi"]:
            raise FileNotFoundError("kimi not on PATH")
        if cmd[:2] == ["git", "status"]:
            return _cp(stdout=f" M {_REL}\n")
        if cmd[:2] == ["git", "branch"]:
            return _cp(stdout="agent/host/wr2/sota-weekly-6\n")
        if cmd[:2] == ["git", "push"]:
            return _cp()
        if cmd[:3] == ["gh", "pr", "create"]:
            return _cp(stdout="https://github.com/org/repo/pull/1002\n")
        if cmd[:3] == ["gh", "pr", "merge"]:
            return _cp()
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [_REL], commit_subject="x", commit_body="y")
    assert ok is True

    promoted = wt / _REL
    verdict = r1_gate.evaluate_file(promoted)
    assert verdict.ok is True, verdict.reason
    assert "exempt-" in promoted.read_text()
    assert "kimi-k3" not in promoted.read_text().split("---", 2)[1]  # not in frontmatter


def test_existing_frontmatter_is_never_clobbered(tmp_path, monkeypatch):
    """A future hand-authored report that already opens with frontmatter
    must pass through untouched — the promoter never overwrites a real
    human/seat review with its own automated one."""
    rel = "research/sota-social-2026-v1/checkpoint_day_30.md"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    original = "---\nadversarial_review: human-zero\n---\n\n# Title\n\n### Adversarial review\n\nReviewed live.\n"
    p.write_text(original)

    wt = tmp_path / ".worktrees" / "wr2-sota-checkpoint-1"
    wt.mkdir(parents=True)
    kimi_called: list = []

    def fake_run(cmd, **kwargs):
        if "--lane" in cmd:
            return _cp(stdout=f"WORKTREE_READY {wt}\n")
        if cmd[:1] == ["kimi"]:
            kimi_called.append(cmd)
            return _cp(stdout="NONE\n")
        if cmd[:2] == ["git", "status"]:
            return _cp(stdout=f" M {rel}\n")
        if cmd[:2] == ["git", "branch"]:
            return _cp(stdout="agent/host/wr2/sota-checkpoint-1\n")
        if cmd[:2] == ["git", "push"]:
            return _cp()
        if cmd[:3] == ["gh", "pr", "create"]:
            return _cp(stdout="https://github.com/org/repo/pull/1003\n")
        if cmd[:3] == ["gh", "pr", "merge"]:
            return _cp()
        return _cp()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok = promote_research_output(tmp_path, [rel], commit_subject="x", commit_body="y")
    assert ok is True
    assert kimi_called == [], "must not dispatch a review over an already-reviewed file"
    assert (wt / rel).read_text() == original
