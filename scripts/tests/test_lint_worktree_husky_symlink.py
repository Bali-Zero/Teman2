"""Tests for scripts/lint_worktree_husky_symlink.py (superscar #2 detector).

W82 discipline applied to the detector itself: every health state gets a GUILT case
(missing/dangling .husky/_ IS caught) and an INNOCENCE case (a healthy .husky/_ --
either a real directory or a symlink to a real target -- is NOT caught). Also covers
the porcelain parser against a real-shaped fixture (verified live on M5, 2026-07-26),
origin classification for every worktree location this repo actually uses, and the
blind-scan guard (W84: zero worktrees traversed must not report clean).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_worktree_husky_symlink.py"
_spec = importlib.util.spec_from_file_location("lint_worktree_husky_symlink", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
lwhs = importlib.util.module_from_spec(_spec)
# Register in sys.modules BEFORE exec_module: dataclasses' type-annotation
# resolution (_is_type) looks the module up via sys.modules[cls.__module__],
# and a dynamically-loaded module that isn't registered yet resolves to None
# there, crashing @dataclass at class-definition time. Same fix as the sibling
# test for pending_arms_report.py (which also dataclasses).
sys.modules[_spec.name] = lwhs
_spec.loader.exec_module(lwhs)


# --------------------------------------------------- check_husky_health (guilt/innocence)


def test_guilt_missing_husky_dir_is_a_finding(tmp_path: Path) -> None:
    wt = tmp_path / "some-worktree"
    wt.mkdir()
    health, is_symlink = lwhs.check_husky_health(wt)
    assert health == lwhs.HEALTH_MISSING
    assert is_symlink is False


def test_guilt_dangling_symlink_is_a_finding(tmp_path: Path) -> None:
    wt = tmp_path / "some-worktree"
    (wt / ".husky").mkdir(parents=True)
    (wt / ".husky" / "_").symlink_to(tmp_path / "nonexistent-target")
    health, is_symlink = lwhs.check_husky_health(wt)
    assert health == lwhs.HEALTH_DANGLING
    assert is_symlink is True


def test_innocence_real_directory_is_healthy(tmp_path: Path) -> None:
    wt = tmp_path / "some-worktree"
    husky = wt / ".husky" / "_"
    husky.mkdir(parents=True)
    (husky / "pre-push").write_text("#!/bin/sh\n")
    health, is_symlink = lwhs.check_husky_health(wt)
    assert health == lwhs.HEALTH_OK
    assert is_symlink is False


def test_innocence_symlink_to_real_target_is_healthy(tmp_path: Path) -> None:
    real_target = tmp_path / "main-checkout" / ".husky" / "_"
    real_target.mkdir(parents=True)
    (real_target / "pre-push").write_text("#!/bin/sh\n")

    wt = tmp_path / "broker-worktree"
    (wt / ".husky").mkdir(parents=True)
    (wt / ".husky" / "_").symlink_to(real_target)

    health, is_symlink = lwhs.check_husky_health(wt)
    assert health == lwhs.HEALTH_OK
    assert is_symlink is True


def test_worktree_record_is_finding_property() -> None:
    def mk(health: str) -> lwhs.WorktreeRecord:
        return lwhs.WorktreeRecord(
            path=Path("/x"),
            head="abc",
            branch=None,
            detached=True,
            locked_reason=None,
            origin=lwhs.ORIGIN_EXTERNAL,
            origin_detail="",
            health=health,
            is_symlink=False,
        )

    assert mk(lwhs.HEALTH_OK).is_finding is False
    assert mk(lwhs.HEALTH_MISSING).is_finding is True
    assert mk(lwhs.HEALTH_DANGLING).is_finding is True
    # GONE is informational (nothing can push from a nonexistent directory) --
    # explicitly NOT a finding, per the module docstring's design decision.
    assert mk(lwhs.HEALTH_GONE).is_finding is False


# --------------------------------------------------------------- parse_porcelain

# Shape verified live via `git worktree list --porcelain` on M5, 2026-07-26.
REAL_SHAPED_FIXTURE = """worktree /repo
HEAD 5fb81e45409e7ee546860065a6416192eebcbd3d
branch refs/heads/main

worktree /repo/.claude/worktrees/ops-wr2-deploy-test-fixture
HEAD 34e8b03ee62cb4c7f7a86e63fcd264c383b1bcba
branch refs/heads/worktree-ops-wr2-deploy-test-fixture
locked claude session ops-wr2-deploy-test-fixture (pid 20787 start Sat Jul 25 10:12:50 2026)

worktree /repo/.claude/worktrees/wf_4398a7e7-a91-4
HEAD 0c51947550f58fea50616cbfb0dbead738ac4c44
branch refs/heads/agent/air-m5/backend-rag/e33-guard-arm

worktree /repo/.worktrees/detached-example
HEAD deadbeef00000000000000000000000000000000
detached
"""


def test_parse_porcelain_real_shaped_fixture() -> None:
    blocks = lwhs.parse_porcelain(REAL_SHAPED_FIXTURE)
    assert len(blocks) == 4

    main_block = blocks[0]
    assert main_block["path"] == "/repo"
    assert main_block["branch"] == "refs/heads/main"
    assert main_block["detached"] is False
    assert main_block["locked_reason"] is None

    locked_block = blocks[1]
    assert locked_block["path"] == "/repo/.claude/worktrees/ops-wr2-deploy-test-fixture"
    assert locked_block["locked_reason"] == (
        "claude session ops-wr2-deploy-test-fixture (pid 20787 start Sat Jul 25 10:12:50 2026)"
    )

    detached_block = blocks[3]
    assert detached_block["detached"] is True
    assert detached_block["branch"] is None


def test_parse_porcelain_empty_output_is_zero_blocks() -> None:
    assert lwhs.parse_porcelain("") == []


# ----------------------------------------------------------------- classify_origin


def test_classify_origin_main(tmp_path: Path) -> None:
    origin, _ = lwhs.classify_origin(tmp_path, tmp_path)
    assert origin == lwhs.ORIGIN_MAIN


def test_classify_origin_broker_with_metadata(tmp_path: Path) -> None:
    wt = tmp_path / ".worktrees" / "ops-example"
    wt.mkdir(parents=True)
    (wt / ".agent-task.json").write_text("{}")
    origin, _ = lwhs.classify_origin(wt, tmp_path)
    assert origin == lwhs.ORIGIN_BROKER


def test_classify_origin_broker_path_no_metadata(tmp_path: Path) -> None:
    wt = tmp_path / ".worktrees" / "bare-add-example"
    wt.mkdir(parents=True)
    # deliberately no .agent-task.json -- imitates a bare `git worktree add`
    origin, detail = lwhs.classify_origin(wt, tmp_path)
    assert origin == lwhs.ORIGIN_BROKER_NO_METADATA
    assert "bare" in detail.lower()


def test_classify_origin_claude_harness_workflow_tool(tmp_path: Path) -> None:
    wt = tmp_path / ".claude" / "worktrees" / "wf_abc123-1"
    wt.mkdir(parents=True)
    origin, detail = lwhs.classify_origin(wt, tmp_path)
    assert origin == lwhs.ORIGIN_CLAUDE_HARNESS
    assert "Workflow-tool" in detail


def test_classify_origin_claude_harness_named_session(tmp_path: Path) -> None:
    wt = tmp_path / ".claude" / "worktrees" / "ops-named-session"
    wt.mkdir(parents=True)
    origin, detail = lwhs.classify_origin(wt, tmp_path)
    assert origin == lwhs.ORIGIN_CLAUDE_HARNESS
    assert "named Claude Code session" in detail


def test_classify_origin_external(tmp_path: Path) -> None:
    outside = tmp_path.parent / "totally-elsewhere-not-a-child-of-repo"
    origin, _ = lwhs.classify_origin(outside, tmp_path)
    assert origin == lwhs.ORIGIN_EXTERNAL


def test_classify_origin_other(tmp_path: Path) -> None:
    wt = tmp_path / "some-random-subdir-not-a-worktree-location"
    wt.mkdir()
    origin, _ = lwhs.classify_origin(wt, tmp_path)
    assert origin == lwhs.ORIGIN_OTHER


# ----------------------------------------------------- scan() end-to-end (injected porcelain)


def _mk_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".husky" / "_").mkdir(parents=True)
    return repo


def test_scan_end_to_end_mixed_fleet(tmp_path: Path) -> None:
    repo = _mk_repo(tmp_path)

    # Healthy broker worktree: properly symlinked .husky/_ (what agent_start.py produces).
    healthy_wt = repo / ".worktrees" / "ops-healthy"
    healthy_wt.mkdir(parents=True)
    (healthy_wt / ".agent-task.json").write_text("{}")
    (healthy_wt / ".husky").mkdir()
    (healthy_wt / ".husky" / "_").symlink_to(repo / ".husky" / "_")

    # Broker-path-no-metadata worktree, .husky/_ missing entirely -- the exact bug
    # this detector exists to catch (a bare `git worktree add` into .worktrees/).
    bare_wt = repo / ".worktrees" / "bare-add"
    bare_wt.mkdir(parents=True)

    # claude-harness worktree with a dangling symlink.
    harness_wt = repo / ".claude" / "worktrees" / "wf_xyz-1"
    harness_wt.mkdir(parents=True)
    (harness_wt / ".husky").mkdir()
    (harness_wt / ".husky" / "_").symlink_to(repo / "nonexistent")

    porcelain = (
        f"worktree {repo}\nHEAD aaa\nbranch refs/heads/main\n\n"
        f"worktree {healthy_wt}\nHEAD bbb\nbranch refs/heads/agent/x/ops/healthy\n\n"
        f"worktree {bare_wt}\nHEAD ccc\nbranch refs/heads/agent/x/ops/bare\n\n"
        f"worktree {harness_wt}\nHEAD ddd\nbranch refs/heads/agent/x/whatever\n"
    )

    records = lwhs.scan(repo, porcelain_output=porcelain)
    assert len(records) == 4

    by_path = {r.path: r for r in records}
    assert by_path[repo].origin == lwhs.ORIGIN_MAIN
    assert by_path[repo].health == lwhs.HEALTH_OK

    assert by_path[healthy_wt].origin == lwhs.ORIGIN_BROKER
    assert by_path[healthy_wt].health == lwhs.HEALTH_OK

    assert by_path[bare_wt].origin == lwhs.ORIGIN_BROKER_NO_METADATA
    assert by_path[bare_wt].health == lwhs.HEALTH_MISSING

    assert by_path[harness_wt].origin == lwhs.ORIGIN_CLAUDE_HARNESS
    assert by_path[harness_wt].health == lwhs.HEALTH_DANGLING

    findings = [r for r in records if r.is_finding]
    assert len(findings) == 2
    assert {r.origin for r in findings} == {
        lwhs.ORIGIN_BROKER_NO_METADATA,
        lwhs.ORIGIN_CLAUDE_HARNESS,
    }


def test_scan_gone_worktree_not_counted_as_finding(tmp_path: Path) -> None:
    repo = _mk_repo(tmp_path)
    gone_path = repo / ".worktrees" / "deleted-but-still-registered"
    # deliberately never created on disk -- simulates `rm -rf` instead of
    # `git worktree remove`.

    porcelain = (
        f"worktree {repo}\nHEAD aaa\nbranch refs/heads/main\n\n"
        f"worktree {gone_path}\nHEAD bbb\nbranch refs/heads/agent/x/ops/gone\n"
    )
    records = lwhs.scan(repo, porcelain_output=porcelain)
    assert len(records) == 2
    gone_record = next(r for r in records if r.path == gone_path)
    assert gone_record.health == lwhs.HEALTH_GONE
    assert gone_record.is_finding is False


# --------------------------------------------------- blind-scan guard (W84) + exit codes


def test_main_blind_scan_guard_on_empty_porcelain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo = _mk_repo(tmp_path)
    monkeypatch.setattr(lwhs, "_run_git_worktree_list", lambda repo_root: "")
    exit_code = lwhs.main(["--repo-root", str(repo)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "blind" in captured.err.lower()


def test_main_blind_scan_guard_on_git_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _mk_repo(tmp_path)

    def _boom(repo_root: Path) -> str:
        raise RuntimeError("git worktree list --porcelain failed (exit 128): fatal: not a git repository")

    monkeypatch.setattr(lwhs, "_run_git_worktree_list", _boom)
    exit_code = lwhs.main(["--repo-root", str(repo)])
    assert exit_code == 2


def test_main_exit_0_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _mk_repo(tmp_path)
    porcelain = f"worktree {repo}\nHEAD aaa\nbranch refs/heads/main\n"
    monkeypatch.setattr(lwhs, "_run_git_worktree_list", lambda repo_root: porcelain)
    exit_code = lwhs.main(["--repo-root", str(repo)])
    assert exit_code == 0


def test_main_exit_1_when_findings_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _mk_repo(tmp_path)
    missing_wt = repo / ".worktrees" / "bare"
    missing_wt.mkdir(parents=True)
    porcelain = (
        f"worktree {repo}\nHEAD aaa\nbranch refs/heads/main\n\n"
        f"worktree {missing_wt}\nHEAD bbb\nbranch refs/heads/agent/x/ops/bare\n"
    )
    monkeypatch.setattr(lwhs, "_run_git_worktree_list", lambda repo_root: porcelain)
    exit_code = lwhs.main(["--repo-root", str(repo)])
    assert exit_code == 1


def test_main_json_output_is_valid_and_matches_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo = _mk_repo(tmp_path)
    missing_wt = repo / ".worktrees" / "bare"
    missing_wt.mkdir(parents=True)
    porcelain = (
        f"worktree {repo}\nHEAD aaa\nbranch refs/heads/main\n\n"
        f"worktree {missing_wt}\nHEAD bbb\nbranch refs/heads/agent/x/ops/bare\n"
    )
    monkeypatch.setattr(lwhs, "_run_git_worktree_list", lambda repo_root: porcelain)
    exit_code = lwhs.main(["--repo-root", str(repo), "--json"])
    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["traversed"] == 2
    assert payload["findings_count"] == 1
    assert payload["gone_count"] == 0


def test_default_repo_root_uses_git_common_dir_not_file_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression test for the bug caught while dogfooding this script (2026-07-26,
    before it ever shipped): a file-path heuristic
    (`Path(__file__).resolve().parent.parent`) is only correct when the script
    happens to run from the main checkout -- it silently resolves to the
    WORKTREE's own root when this script runs from inside one, which it is
    designed to (per the "own worktree, created via agent_start.py"
    discipline), making every real worktree misclassify as `external` relative
    to itself. The fix derives repo_root from `git rev-parse
    --git-common-dir`, the one `.git` directory every worktree shares
    regardless of which worktree invoked git. This test is hermetic (mocks
    subprocess) so it holds identically whether the suite itself happens to
    run from a worktree or a plain checkout.
    """
    fake_common_dir = tmp_path / "shared-repo-root" / ".git"

    class _FakeResult:
        returncode = 0
        stdout = str(fake_common_dir) + "\n"

    def _fake_run(cmd, **kwargs):
        assert cmd[:2] == ["git", "rev-parse"]
        assert "--git-common-dir" in cmd
        return _FakeResult()

    monkeypatch.setattr(lwhs.subprocess, "run", _fake_run)
    resolved = lwhs._default_repo_root()
    assert resolved == fake_common_dir.parent
    assert resolved == tmp_path / "shared-repo-root"


def test_default_repo_root_falls_back_to_file_path_on_git_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResult:
        returncode = 128
        stdout = ""

    def _fake_run(cmd, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(lwhs.subprocess, "run", _fake_run)
    resolved = lwhs._default_repo_root()
    # Falls back to the file-path heuristic only when git itself is
    # unavailable -- a real git failure re-surfaces as the blind-scan guard
    # the moment scan() calls git itself, so this fallback is a courtesy, not
    # a silent wrong-answer path.
    assert resolved == _MODULE_PATH.resolve().parent.parent
