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


# ---------------------------------------------------------------------------
# ARMED-CHECK (added 2026-07-27). The detector above was complete, tested and
# CI-verified from the day it merged -- and had never once run against a real
# machine. Its only caller in the tree was immune-enforcement.yml, and what that
# workflow runs is THIS FILE, not the detector: a GitHub runner cannot see a
# worktree on M5. Measured by hand that day: 15 of 115 worktrees on M5 had no
# `.husky/_` at all, so every push from them invoked no hook and exited 0 in
# silence. Family #2 one level up -- not a missing detector, a detector nobody
# asks. The cure is the proprioception registry entry these tests pin, because
# that organ runs per-machine at SessionStart and its report is read.
#
# Pinned here rather than in a new file precisely because a new file under
# scripts/ would itself need a workflow to name it -- which is the disease.
# ---------------------------------------------------------------------------

_PROPRIO_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"


def _proprioception_module():
    spec = importlib.util.spec_from_file_location("proprioception", _PROPRIO_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _gate_entry():
    entries = [e for e in _proprioception_module().DEFAULT_REGISTRY
               if e.get("id") == "worktree_gate_shim"]
    assert len(entries) == 1, (
        "proprioception must carry exactly one worktree_gate_shim entry — without it "
        "lint_worktree_husky_symlink.py runs on no machine and this whole file guards "
        "a tool that is never invoked."
    )
    return entries[0]


def test_proprioception_actually_invokes_this_detector() -> None:
    """The entry must point at THIS script — the arming, not a re-implementation."""
    entry = _gate_entry()
    assert entry["type"] == "wrap", "must wrap the real tool, never re-implement it as a builtin twin"
    target = entry["target"]
    assert target[-1] == "--json", f"the parser needs JSON, got {target}"
    assert target[-2].endswith("/scripts/lint_worktree_husky_symlink.py"), \
        f"proprioception points at the wrong script: {target}"


def test_the_registry_and_the_tool_agree_on_what_counts_as_a_finding() -> None:
    """Two graders of one signal need one rule (else the organ and the tool disagree).

    `ok_values` is proprioception's copy of the tool's FINDING_HEALTHS. Drift here
    is silent in both directions: a health state added to the tool and not here
    would be graded a finding by the organ and not by the tool, or vice versa.
    """
    ok = set(_gate_entry()["ok_values"])
    all_healths = {lwhs.HEALTH_OK, lwhs.HEALTH_MISSING, lwhs.HEALTH_DANGLING, lwhs.HEALTH_GONE}
    assert ok | set(lwhs.FINDING_HEALTHS) == all_healths, (
        "every health state the tool can emit must be classified by the registry: "
        f"ok={sorted(ok)} findings={sorted(lwhs.FINDING_HEALTHS)} all={sorted(all_healths)}"
    )
    assert not (ok & set(lwhs.FINDING_HEALTHS)), (
        f"the registry calls {sorted(ok & set(lwhs.FINDING_HEALTHS))} acceptable while the tool "
        "scores it a finding — the organ would report calm over a blind gate"
    )
    assert lwhs.HEALTH_GONE in ok, (
        "GONE (the worktree directory itself is absent) is stale-registry hygiene for "
        "`git worktree prune`, not a worktree pushing without a gate — deliberately not a finding"
    )


def test_the_parser_contract_matches_the_tools_json_shape() -> None:
    """`unwrap_key`/`verdict_key` are strings resolved at runtime: a rename in the
    tool's JSON would make run_wrap return UNPROBEABLE forever, which reads as
    'not applicable here' rather than as a break. Pin them against real output."""
    entry = _gate_entry()
    payload = json.loads(json.dumps({  # shape mirrored from the tool's own emit path
        "traversed": 1, "healthy": 1, "findings_count": 0, "gone_count": 0,
        "origin_counts": {"main": 1},
        "worktrees": [{"path": "/x", "origin": "main", "health": lwhs.HEALTH_OK,
                       "is_symlink": False, "is_finding": False}],
    }))
    assert entry["unwrap_key"] in payload, f"unwrap_key {entry['unwrap_key']!r} absent from the tool's JSON"
    assert entry["verdict_key"] in payload[entry["unwrap_key"]][0], \
        f"verdict_key {entry['verdict_key']!r} absent from a worktree record"
