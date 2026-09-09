"""One real read-only Claude child, with metadata-only hook evidence."""

from __future__ import annotations
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "claude-hooks"))
import child_context


def main() -> None:
    seat = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    root = seat / "state" / "worktrees" / "claude-child-probe"
    root.mkdir(parents=True, exist_ok=True)
    (root / "fixture.txt").write_text("native child fixture 42\n")
    run_cwd = Path(os.environ.get("CLAUDE_CHILD_PROBE_CWD") or root)
    log = seat / "state" / "native-child-payloads.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("")
    capture = Path(__file__)
    command = shlex.join([sys.executable, str(capture), "capture", str(log)])
    settings = seat / "state" / "native-child-probe-settings.json"
    settings.write_text(
        json.dumps(
            {
                # Project settings may reintroduce recovery switches after env
                # sanitization. Enable the actual guards in this probe only.
                "env": {
                    key: "0"
                    for key in (
                        "SUBAGENT_STOP_VERIFY_OFF",
                        "STOP_VERIFY_ALLOW_DIRTY",
                        "CONTEXT_GUARD_OFF",
                        "MANDATE_BUDGET_OFF",
                    )
                },
                "hooks": {
                    e: [{"hooks": [{"type": "command", "command": command}]}]
                    for e in (
                        "SessionStart",
                        "PreToolUse",
                        "PostToolUse",
                        "SubagentStart",
                        "SubagentStop",
                        "Stop",
                    )
                },
            }
        )
    )
    prompt = f"Bounded native child probe, explicitly authorized delegation. Use Agent exactly once, subagent_type Explore and model haiku explicitly. Give only this assignment: Read {root / 'fixture.txt'} with one Read tool, report its number. Read-only, no edits, no network, no replacements, no memories, expected result42. Wait for its result then independently Read the same fixture yourself, compare42 and return CLAUDE_CHILD_PROBE_OK. No other work."
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in (
            "ANTHROPIC_API_KEY",
            "SUBAGENT_STOP_VERIFY_OFF",
            "STOP_VERIFY_ALLOW_DIRTY",
            "CONTEXT_GUARD_OFF",
            "MANDATE_BUDGET_OFF",
        )
    }
    env["CONTEXT_JUMP_NO_SPAWN"] = "1"
    outpath = seat / "state" / "native-child-probe.jsonl"
    executable = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    with outpath.open("w") as out, outpath.with_suffix(".stderr").open("w") as err:
        run = subprocess.run(
            [
                executable,
                "-p",
                "--model",
                "claude-fable-5-1",
                "--effort",
                "xhigh",
                "--permission-mode",
                "plan",
                "--tools",
                "Agent,Read",
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--settings",
                str(settings),
                "--output-format",
                "stream-json",
                "--verbose",
                prompt,
            ],
            cwd=run_cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            timeout=480,
        )
    rows = [
        json.loads(s) for s in outpath.read_text().splitlines() if s.startswith("{")
    ]
    result = next((r for r in reversed(rows) if r.get("type") == "result"), {})
    metadata = [json.loads(s) for s in log.read_text().splitlines()]
    starts = [r for r in metadata if r.get("hook_event_name") == "SubagentStart"]
    states = []
    observations = []
    for event in metadata:
        if event.get("hook_event_name") in ("SubagentStop", "SessionStart"):
            path = Path(
                event.get(
                    "agent_transcript_path"
                    if event["hook_event_name"] == "SubagentStop"
                    else "transcript_path"
                )
                or ""
            )
            if path.is_file():
                observations.append(
                    {
                        **child_context.snapshot(path.read_text()),
                        "capacity_scope": event.get("capacity_scope"),
                    }
                )
    for r in starts:
        key = hashlib.sha256(
            (r["session_id"] + ":" + r["agent_id"]).encode()
        ).hexdigest()
        path = seat / "state" / "child-workflow" / (key + ".json")
        state = json.loads(path.read_text()) if path.exists() else {}
        states.append(
            {
                k: state.get(k)
                for k in (
                    "parent_session",
                    "agent_id",
                    "role",
                    "model",
                    "measurement",
                    "status",
                    "pretool_count",
                    "stop_reminded",
                    "used",
                    "window",
                    "token_limit",
                    "version",
                )
            }
        )
    evidence = {
        "exit_code": run.returncode,
        "cwd": str(run_cwd),
        "session_id": result.get("session_id"),
        "success": not result.get("is_error", True)
        and "CLAUDE_CHILD_PROBE_OK" in result.get("result", ""),
        "children": states,
        "observed_events": sorted({r["hook_event_name"] for r in metadata}),
    }
    evidence["passed"] = (
        run.returncode == 0
        and evidence["success"]
        and len(states) == 1
        and all(
            s.get("pretool_count", 0) > 0
            and s.get("status") == "returned_unverified"
            and not s.get("stop_reminded")
            for s in states
        )
    )
    evidence["capacities"] = (
        child_context.calibrate(result, observations, str(run_cwd))
        if evidence["passed"]
        else []
    )
    (seat / "state" / "native-child-probe-result.json").write_text(
        json.dumps(evidence, indent=2)
    )
    print(json.dumps(evidence))
    if not evidence["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "capture":
        from native_child_probe import capture

        payload = json.load(sys.stdin)
        sys.stdin = io.StringIO(json.dumps(payload))
        capture(
            sys.argv[2],
            {"capacity_scope": child_context.scope(payload.get("cwd", os.getcwd()))},
        )
    else:
        main()
