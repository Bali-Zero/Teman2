"""Bounded real Codex hook consumer probe; no production edits or sends."""

from __future__ import annotations

import argparse
import json
import subprocess

from context_bridge import codex_home, load, save, state_path
from rpc import RPC, binary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    args = parser.parse_args()
    root = codex_home() / "worktrees" / "codex-context-smoke"
    root.mkdir(parents=True, exist_ok=True)
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Bridge probe",
                "-c",
                "user.email=probe@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "probe",
            ],
            check=True,
        )
    rpc = RPC()
    try:
        entries = rpc.call("hooks/list", {"cwds": [str(root)]})["data"][0]
        hooks = [
            h
            for h in entries["hooks"]
            if "nuzantara-context/context_bridge.py" in h.get("command", "")
        ]
        if len(hooks) != 6 or any(
            h["trustStatus"] != "trusted" or not h["enabled"] for h in hooks
        ):
            raise RuntimeError("bridge hooks not trusted and enabled")
    finally:
        rpc.close()
    command = [
        binary_path(),
        "-a",
        "never",
        "--sandbox",
        "read-only",
        "-c",
        'model_reasoning_effort="low"',
        "exec",
        "--json",
    ]
    if args.model:
        command += ["--model", args.model]
    command += [
        "This is a bounded Codex lifecycle smoke test, not project work. Run exactly one shell "
        "command: true. Then reply CODEX_BRIDGE_SMOKE_OK. Do not read or edit files, do not "
        "write memories, do not use MCP/browser/network tools, and do not perform other work."
    ]
    run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=150)
    events = [
        json.loads(line) for line in run.stdout.splitlines() if line.startswith("{")
    ]
    sid = next(
        (e["thread_id"] for e in events if e.get("type") == "thread.started"), None
    )
    completed = run.returncode == 0 and any(
        e.get("type") == "turn.completed" for e in events
    )
    state = load(state_path(sid)) if sid else {}
    result = {
        "thread_id": sid,
        "turn_status": "completed" if completed else "failed",
        "model": state.get("model"),
        "trusted_hooks": len(hooks),
        "event_counts": state.get("event_counts", {}),
        "used_tokens": state.get("used"),
        "context_window": state.get("window"),
        "binary": binary_path(),
    }
    required = ("SessionStart", "PreToolUse", "PostToolUse", "Stop")
    result["passed"] = completed and all(
        result["event_counts"].get(e, 0) for e in required
    )
    save(codex_home() / "state" / "nuzantara-context-smoke.json", result)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise RuntimeError("actual hook execution unverified")


if __name__ == "__main__":
    main()
