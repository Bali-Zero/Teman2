"""One real read-only Claude child, with metadata-only hook evidence."""

from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "claude-hooks"))
import child_context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("haiku", "sonnet", "opus"), default="haiku")
    parser.add_argument(
        "--parent-model",
        default="claude-haiku-4-5",
        help="Parent dispatcher model; override only with an explicitly chosen model",
    )
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="No-tool child; calibrates without needing a successful guarded tool",
    )
    parser.add_argument("--children", type=int, choices=range(1, 5), default=1)
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="Use branch adapter in this invocation only; preserve normal recovery settings",
    )
    args = parser.parse_args()
    seat = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    root = seat / "state" / "worktrees" / ("claude-child-probe-" + str(time.time_ns()))
    root.mkdir(parents=True, exist_ok=True)
    (root / "fixture.txt").write_text("native child fixture 42\n")
    run_cwd = Path(os.environ.get("CLAUDE_CHILD_PROBE_CWD") or root)
    log = root / "payloads.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("")
    capture = Path(__file__)
    command = shlex.join([sys.executable, str(capture), "capture", str(log)])
    settings = root / "settings.json"
    config = {}
    if args.candidate:
        from install_claude_children import route_settings

        hooks = root / "hooks"
        hooks.mkdir()
        # Copy existing legacy dependencies; never rewrite HOME hooks or settings.
        for source in (Path.home() / ".claude" / "hooks").glob("*.py"):
            shutil.copy2(source, hooks / source.name)
        for source in (
            Path(__file__).with_name("mandate_budget.py"),
            Path(child_context.__file__),
            Path(child_context.__file__).with_name("child_workflow.py"),
        ):
            shutil.copy2(source, hooks / source.name)
        config = route_settings(json.loads((seat / "settings.json").read_text()), hooks)
    for event in (
        "SessionStart",
        "PreToolUse",
        "PostToolUse",
        "SubagentStart",
        "SubagentStop",
        "Stop",
    ):
        config.setdefault("hooks", {}).setdefault(event, []).append(
            {"hooks": [{"type": "command", "command": command, "timeout": 30}]}
        )
    settings.write_text(json.dumps(config))
    settings.chmod(0o600)
    assignment = (
        "Return the number 42 without any tools."
        if args.warmup
        else f"Read {root / 'fixture.txt'} twice sequentially (second Read after the first result), report its number."
    )
    role = "Explore"
    prompt = f"Bounded native child probe, explicitly authorized delegation. Use Agent exactly {args.children} time(s), all in ONE parallel dispatch message, subagent_type {role} and model {args.model} explicitly. Give each only this assignment: {assignment} Read-only, no edits, no network, no replacements, no memories, expected result42. Wait for every result then independently Read the same fixture yourself, compare42 and return CLAUDE_CHILD_PROBE_OK. No other work."
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY",)}
    env["CONTEXT_JUMP_NO_SPAWN"] = "1"
    outpath = root / "probe.jsonl"
    executable = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    with outpath.open("w") as out, outpath.with_suffix(".stderr").open("w") as err:
        run = subprocess.run(
            [
                executable,
                "-p",
                "--model",
                args.parent_model,
                "--permission-mode",
                "plan",
                "--tools",
                "Agent,Read",
                "--allowedTools",
                "Agent,Read",
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--settings",
                str(settings),
                *(["--setting-sources", "project,local"] if args.candidate else []),
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
    dispatch_groups: dict[str, set[str]] = {}
    for row in rows:
        if row.get("type") == "assistant" and not row.get("parent_tool_use_id"):
            message = row.get("message", {})
            for item in message.get("content", []):
                if item.get("type") == "tool_use" and item.get("name") == "Agent":
                    dispatch_groups.setdefault(message.get("id", "UNKNOWN"), set()).add(
                        item["id"]
                    )
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
                    "denials",
                    "budget_elapsed",
                    "budget_started_at",
                    "time_budget_exceeded",
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
        "requested_model": args.model,
        "phase": "capacity_warmup" if args.warmup else "calibrated_consumer",
        "evidence_directory": str(root),
        "candidate": args.candidate,
        "parallel_dispatch_counts": [len(ids) for ids in dispatch_groups.values()],
        "observed_events": sorted({r["hook_event_name"] for r in metadata}),
    }
    # A successful transport with UNKNOWN usage is not a measured-budget proof.
    child_observations = [
        o
        for o in observations
        if str(o.get("model") or "").startswith("claude-" + args.model + "-")
    ]
    evidence["transport_passed"] = (
        run.returncode == 0
        and evidence["success"]
        and len(states) == args.children
        and len(child_observations) == args.children
        and evidence["parallel_dispatch_counts"] == [args.children]
    )
    evidence["passed"] = evidence["transport_passed"] and (
        args.warmup
        or (
            len(states) == args.children
            and all(
                s.get("pretool_count", 0) > 0
                and s.get("status") == "returned_unverified"
                and not s.get("stop_reminded")
                and s.get("measurement") in ("calibrated", "observed")
                and s.get("used") is not None
                and str(s.get("model") or "").startswith("claude-" + args.model + "-")
                and s.get("window")
                and not s.get("denials")
                for s in states
            )
        )
    )
    evidence["capacities"] = (
        child_context.calibrate(result, observations, str(run_cwd))
        if evidence["transport_passed"]
        else []
    )
    if args.warmup:
        evidence["passed"] = (
            evidence["transport_passed"]
            and bool(child_observations)
            and all(
                any(
                    c["model"] == o["model"] and c["scope"] == o["capacity_scope"]
                    for c in evidence["capacities"]
                )
                for o in child_observations
            )
        )
    (root / "result.json").write_text(json.dumps(evidence, indent=2))
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
