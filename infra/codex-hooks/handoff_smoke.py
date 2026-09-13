"""Exercise two native continuations and a failed launch in the isolated probe only."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import context_bridge as bridge


def main() -> None:
    report = bridge.load(bridge.codex_home() / "state" / "nuzantara-context-smoke.json")
    if not report.get("passed"):
        raise ValueError("run the lifecycle probe first")
    sid = report["thread_id"]
    root = str((bridge.codex_home() / "worktrees" / "codex-context-smoke").resolve())
    first = bridge.load(bridge.state_path(sid))
    if first.get("cwd") != root or first.get("hops", 0):
        raise ValueError("probe source must be an isolated original session")
    chain = [sid]
    for hop in (1, 2):
        bridge.checkpoint(
            sid,
            {
                "objective": "Complete the isolated lifecycle probe",
                "next_action": "Run exactly true, then reply CODEX_BRIDGE_SMOKE_OK",
                "remaining": ["Run the one shell command"],
                "risks": [],
            },
        )
        with bridge.locked(sid) as (path, state):
            state["rollover"] = "requested"
            bridge.save(path, state)
        outcome = bridge.launch(sid, 3)
        if outcome.get("continue") is not False:
            raise RuntimeError("destination did not acknowledge source")
        until = time.monotonic() + 60
        while time.monotonic() < until:
            state = bridge.load(bridge.state_path(sid))
            if state.get("destination_status"):
                break
            time.sleep(0.2)
        if state.get("destination_status") != "completed":
            raise RuntimeError("destination did not complete")
        target = state["to_session"]
        child = bridge.load(bridge.state_path(target))
        assert child["from_session"] == sid and child["hops"] == hop
        assert child["model"] == first["model"] and child["effort"] == first["effort"]
        assert child["sandbox_policy"] == first["sandbox_policy"]
        assert child["approval_policy"] == first["approval_policy"]
        assert child["event_counts"].get("PreToolUse") and child["event_counts"].get(
            "Stop"
        )
        chain.append(target)
        sid = target
    bridge.checkpoint(
        sid,
        {"objective": "Test failed launch retention", "next_action": "No further work"},
    )
    with bridge.locked(sid) as (path, state):
        state["rollover"] = "requested"
        bridge.save(path, state)
    old = os.environ.get("CODEX_CONTEXT_BINARY")
    os.environ["CODEX_CONTEXT_BINARY"] = "/usr/bin/false"
    try:
        failed = bridge.launch(sid, 3)
    finally:
        if old is None:
            os.environ.pop("CODEX_CONTEXT_BINARY", None)
        else:
            os.environ["CODEX_CONTEXT_BINARY"] = old
    state = bridge.load(bridge.state_path(sid))
    preserved = (
        failed.get("continue") is not False
        and state["rollover"] == "needs_attention"
        and "to_session" not in state
        and Path(state["transcript"]).is_file()
    )
    result = {
        "passed": preserved,
        "chain": chain,
        "model": first["model"],
        "completed_hops": 2,
        "exact_source_binding": True,
        "permission_policy_preserved": True,
        "failed_launch_preserves_source": preserved,
    }
    bridge.save(
        bridge.codex_home() / "state" / "nuzantara-context-handoff-smoke.json", result
    )
    print(json.dumps(result, indent=2))
    if not preserved:
        raise RuntimeError("failed launch did not preserve source")


if __name__ == "__main__":
    main()
