"""Tests for scripts/ops/orchestrator_live_map.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "ops" / "orchestrator_live_map.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "orchestrator_live_map_under_test", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


olm = _load_module()


def test_parse_worktree_porcelain_extracts_agent_lane_and_task() -> None:
    text = """worktree /repo
HEAD abc
branch refs/heads/main

worktree /repo/.worktrees/ops-live-map
HEAD def
branch refs/heads/agent/nuzantara/ops/live-map

worktree /repo/.worktrees/wr2-active
HEAD 123
detached
"""
    worktrees = olm.parse_worktree_porcelain(text)
    assert len(worktrees) == 3
    assert worktrees[1].branch == "agent/nuzantara/ops/live-map"
    assert worktrees[1].lane == "ops"
    assert worktrees[1].task_id == "live-map"
    assert worktrees[2].detached is True
    assert worktrees[2].lane == "wr2"


def test_parse_remote_target_supports_default_and_explicit() -> None:
    default = olm.parse_remote_target("m5")
    assert default.name == "m5"
    assert default.host == "m5"
    assert default.repo_root == "/Users/balizero/Desktop/nuzantara"

    explicit = olm.parse_remote_target(
        "staging=mini:/Users/nuzantara/Desktop/nuzantara"
    )
    assert explicit.name == "staging"
    assert explicit.host == "mini"
    assert explicit.repo_root == "/Users/nuzantara/Desktop/nuzantara"


def test_parse_worktree_porcelain_tags_machine() -> None:
    text = """worktree /repo/.worktrees/backend-rag-wire-orphan-routers
HEAD abc
branch refs/heads/agent/air-m5/backend-rag/wire-orphan-routers
"""
    worktrees = olm.parse_worktree_porcelain(text, machine="m5")
    assert worktrees[0].machine == "m5"
    assert worktrees[0].lane == "backend-rag"


def test_parse_pr_json_infers_lanes() -> None:
    payload = [
        {
            "number": 1124,
            "title": "feat(routers): wire orphan routers",
            "headRefName": "agent/air-m5/backend-rag/wire-orphan-routers",
            "baseRefName": "main",
            "state": "OPEN",
            "isDraft": False,
            "mergeStateStatus": "DIRTY",
            "updatedAt": "2026-06-04T16:24:39Z",
            "author": {"login": "Balizero1987"},
        },
        {
            "number": 1125,
            "title": "fix(wr2): autopsy remediation",
            "headRefName": "agent/nuzantara/wr2/autopsy-fixes",
            "baseRefName": "main",
            "state": "OPEN",
            "isDraft": False,
            "mergeStateStatus": "UNKNOWN",
            "updatedAt": "2026-06-04T16:23:20Z",
            "author": {"login": "Balizero1987"},
        },
        {
            "number": 1116,
            "title": "Palette: MessageBubble UX and Accessibility Improvements",
            "headRefName": "palette/message-bubble-ux-a11y",
            "baseRefName": "main",
            "state": "OPEN",
            "isDraft": False,
            "mergeStateStatus": "UNKNOWN",
            "updatedAt": "2026-06-04T02:51:35Z",
            "author": {"login": "Balizero1987"},
        },
    ]
    prs = olm.parse_pr_json(json.dumps(payload))
    assert [pr.lane for pr in prs] == ["backend-router", "wr2", "mouth"]
    assert [pr.machine for pr in prs] == ["m5", "pro", None]


def test_derive_no_touch_lanes_uses_prs_worktrees_and_processes() -> None:
    worktrees = [
        olm.WorktreeInfo(
            path="/repo/.worktrees/doc-intake-dossier",
            branch="agent/pro/research/doc-intake-dossier",
            lane="doc-intake",
        ),
    ]
    prs = [
        olm.PullRequestInfo(
            number=1124,
            title="feat(routers): wire orphan routers",
            head_ref="agent/air-m5/backend-rag/wire-orphan-routers",
            base_ref="main",
            state="OPEN",
            is_draft=False,
            merge_state_status="DIRTY",
            updated_at=None,
            author="Balizero1987",
            lane="backend-router",
        )
    ]
    processes = [
        olm.ProcessSignal(
            pid=100,
            category="flowkit",
            command="/Users/nuzantara/flowkit/venv/bin/python",
        ),
        olm.ProcessSignal(
            pid=101,
            category="flowkit",
            command="/Users/nuzantara/flowkit/venv/bin/python -m agent.main",
        ),
    ]
    lanes = olm.derive_no_touch_lanes(worktrees, prs, processes)
    lane_names = {lane.lane for lane in lanes}
    assert lane_names == {"backend-rag", "backend-router", "doc-intake", "flowkit"}
    assert len([lane for lane in lanes if lane.lane == "flowkit"]) == 1


def test_parse_ps_aux_ignores_apple_workflowkit_false_positive() -> None:
    text = (
        "user 10 0.0 0.0 /System/Library/PrivateFrameworks/WorkflowKit.framework/XPCServices/ShortcutsViewService\n"
        "user 11 0.0 0.0 /Users/nuzantara/flowkit/venv/bin/python -m agent.main\n"
    )
    signals = olm.parse_ps_aux(text)
    assert [(signal.pid, signal.category) for signal in signals] == [(11, "flowkit")]


def test_flowkit_no_touch_blocks_wr3_candidates() -> None:
    findings = [
        olm.ComponentFinding(
            component_id="wr3",
            area="wr3",
            path="scripts/wr3_flowkit_client.py",
            line=1,
            marker="placeholder_text",
            severity="medium",
            evidence="placeholder",
        ),
        olm.ComponentFinding(
            component_id="admin-dashboard",
            area="admin-dashboard",
            path="apps/admin-dashboard/app/legal/page.tsx",
            line=1,
            marker="placeholder_text",
            severity="medium",
            evidence="placeholder",
        ),
    ]
    no_touch = [
        olm.NoTouchLane(
            lane="flowkit", reason="running", source="process", reference="flowkit"
        )
    ]
    candidates = olm.derive_candidate_workstreams(findings, no_touch)
    assert [candidate.area for candidate in candidates] == ["admin-dashboard"]


def test_remote_no_touch_blocks_local_candidate() -> None:
    findings = [
        olm.ComponentFinding(
            component_id="backend-rag",
            area="backend-rag",
            path="apps/backend-rag/backend/services/naga.py",
            line=1,
            marker="placeholder_text",
            severity="medium",
            evidence="placeholder",
        )
    ]
    no_touch = [
        olm.NoTouchLane(
            lane="backend-rag",
            reason="active remote worktree exists",
            source="worktree",
            reference="agent/air-m5/backend-rag/wire-orphan-routers",
            machine="m5",
        )
    ]
    assert olm.derive_candidate_workstreams(findings, no_touch) == []


def test_scan_incomplete_markers_and_candidates_skip_no_touch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    backend = repo / "apps" / "backend-rag" / "backend" / "app" / "routers"
    mouth = repo / "apps" / "mouth"
    backend.mkdir(parents=True)
    mouth.mkdir(parents=True)
    (backend / "intel.py").write_text(
        "from fastapi import HTTPException\n"
        "async def revalidate():\n"
        "    raise HTTPException(status_code=501, detail='not implemented')\n"
    )
    (mouth / "settings.tsx").write_text("export const value = 'placeholder result';\n")

    findings = olm.scan_incomplete_markers(
        repo, ["apps/backend-rag/backend", "apps/mouth"], limit=20
    )
    assert {finding.area for finding in findings} == {"backend-router", "mouth"}
    no_touch = [
        olm.NoTouchLane(
            lane="backend-rag", reason="active PR", source="test", reference="pr"
        )
    ]
    candidates = olm.derive_candidate_workstreams(findings, no_touch)
    assert [candidate.area for candidate in candidates] == ["mouth"]
    assert candidates[0].task_id == "audit-mouth-incomplete"


def test_render_markdown_includes_no_touch_and_candidates() -> None:
    report = olm.OrchestratorMap(
        generated_at="2026-06-04T16:00:00Z",
        repo_root="/repo",
        current_branch="agent/nuzantara/ops/live-map",
        machines=[
            olm.MachineStatus(
                name="m5",
                host="m5",
                repo_root="/Users/balizero/Desktop/nuzantara",
                reachable=True,
                current_branch="HEAD",
                head="40b28a2",
                origin_main="36fb513",
                identity="balizero@Air-M5",
            )
        ],
        no_touch_lanes=[
            olm.NoTouchLane(
                lane="wr2",
                reason="active git worktree exists",
                source="worktree",
                reference="agent/wr2",
                machine="m5",
            )
        ],
        candidate_workstreams=[
            olm.CandidateWorkstream(
                lane="mouth",
                task_id="audit-mouth-incomplete",
                area="mouth",
                finding_count=2,
                top_severity="medium",
                sample_paths=["apps/mouth/settings.tsx"],
                rationale="test",
            )
        ],
    )
    rendered = olm.render_markdown(report)
    assert "## Machines" in rendered
    assert "`m5` via `m5`" in rendered
    assert "## No-Touch Lanes" in rendered
    assert "[m5]" in rendered
    assert "`wr2`" in rendered
    assert "`audit-mouth-incomplete`" in rendered
