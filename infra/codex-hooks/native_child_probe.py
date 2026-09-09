"""Bounded native payload capture; persist metadata only, never tool arguments."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from context_bridge import codex_home, save, load, state_dir
from rpc import RPC, binary_path


def capture(destination: str, extra: dict | None = None) -> None:
    payload = json.load(sys.stdin)
    keep = (
        "hook_event_name",
        "session_id",
        "agent_id",
        "agent_type",
        "cwd",
        "transcript_path",
        "agent_transcript_path",
        "model",
        "tool_name",
        "stop_hook_active",
    )
    record = {k: payload[k] for k in keep if k in payload}
    record.update(extra or {})
    record["keys"] = sorted(payload)
    record["continuation_env_present"] = bool(
        os.environ.get("CODEX_CONTEXT_FROM_SESSION")
    )
    with open(
        destination, "a", opener=lambda p, flags: os.open(p, flags, 0o600)
    ) as stream:
        stream.write(json.dumps(record) + "\n")
    print("{}")


def main() -> None:
    root = codex_home() / "worktrees" / "codex-child-probe"
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    if subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True
    ).returncode:
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Probe",
                "-c",
                "user.email=probe@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "fixture",
            ],
            check=True,
        )
    (root / "fixture.txt").write_text("native child fixture 42\n")
    log = codex_home() / "state" / "native-child-payloads.jsonl"
    log.write_text("")
    config_dir = root / ".codex"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.toml").touch()
    command = shlex.join(
        [sys.executable, str(Path(__file__).resolve()), "capture", str(log)]
    )
    events = (
        "SessionStart",
        "PreToolUse",
        "PostToolUse",
        "SubagentStart",
        "SubagentStop",
        "Stop",
    )
    save(
        config_dir / "hooks.json",
        {
            "hooks": {
                e: [{"hooks": [{"type": "command", "command": command}]}]
                for e in events
            }
        },
    )
    rpc = RPC()
    try:
        config = rpc.call("config/read", {"includeLayers": False})["config"]
        rpc.call(
            "config/batchWrite",
            {
                "edits": [
                    {
                        "keyPath": "projects." + json.dumps(str(root)) + ".trust_level",
                        "value": "trusted",
                        "mergeStrategy": "replace",
                    }
                ]
            },
        )
    finally:
        rpc.close()
    rpc = RPC()
    try:
        found = rpc.call("hooks/list", {"cwds": [str(root)]})["data"][0]
        hooks = [h for h in found["hooks"] if h.get("command") == command]
        assert len(hooks) == len(events), found.get("errors")
        edits = []
        for h in hooks:
            base = "hooks.state." + json.dumps(h["key"])
            edits.extend(
                [
                    {
                        "keyPath": base + ".trusted_hash",
                        "value": h["currentHash"],
                        "mergeStrategy": "replace",
                    },
                    {
                        "keyPath": base + ".enabled",
                        "value": True,
                        "mergeStrategy": "replace",
                    },
                ]
            )
        rpc.call("config/batchWrite", {"edits": edits})
    finally:
        rpc.close()
    prompt = (
        "Bounded native subagent probe, explicitly authorized delegation: spawn exactly one read-only child. "
        "Assign it only to read fixture.txt using one shell tool and report its number. "
        "Do not edit files, launch replacements, use network/MCP/browser, or write memories. "
        "Wait for that child. Independently read fixture.txt yourself using one shell tool, "
        "compare the number, send one followup_task to the SAME child asking it to confirm the number with one shell read, wait for it, close the child, and return NATIVE_CHILD_PROBE_OK. Do no other work."
    )
    flags = ["-c", "project_doc_max_bytes=0"]
    for name in config.get("mcp_servers", {}):
        flags += ["-c", "mcp_servers." + name + ".enabled=false"]
    run = subprocess.run(
        [
            binary_path(),
            *flags,
            "-a",
            "never",
            "--sandbox",
            "read-only",
            "-c",
            'model_reasoning_effort="low"',
            "exec",
            "--model",
            "gpt-6-astra",
            "--json",
            prompt,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=480,
    )
    records = [json.loads(s) for s in run.stdout.splitlines() if s.startswith("{")]
    result = {
        "exit_code": run.returncode,
        "thread_id": next(
            (r["thread_id"] for r in records if r.get("type") == "thread.started"), None
        ),
        "turn_completed": any(r.get("type") == "turn.completed" for r in records),
        "payloads": str(log),
        "expected_result": any(
            r.get("type") == "item.completed"
            and r.get("item", {}).get("type") == "agent_message"
            and "NATIVE_CHILD_PROBE_OK" in r["item"].get("text", "")
            for r in records
        ),
    }
    if run.returncode:
        # Private local diagnostic, never a shared artifact or auth/config dump.
        diagnostic = codex_home() / "state" / "native-child-probe.stderr"
        diagnostic.write_text(run.stderr)
        diagnostic.chmod(0o600)
    save(codex_home() / "state" / "native-child-probe.json", result)
    print(json.dumps(result))
    states = [
        s
        for p in state_dir().glob("*.json")
        if (s := load(p)).get("parent_session") == result["thread_id"]
    ]
    result["children"] = [
        {
            k: s.get(k)
            for k in (
                "session_id",
                "role",
                "measurement",
                "event_counts",
                "completion_status",
                "stop_reminded",
                "acceptance_status",
            )
        }
        for s in states
    ]
    result["passed"] = (
        result["exit_code"] == 0
        and result["turn_completed"]
        and result["expected_result"]
        and len(states) == 1
        and all(
            s.get("completion_status") == "returned_unverified"
            and not s.get("stop_reminded")
            and s.get("event_counts", {}).get("SubagentStop", 0) >= 2
            for s in states
        )
    )
    save(codex_home() / "state" / "native-child-probe.json", result)
    print(json.dumps(result))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "capture":
        capture(sys.argv[2])
    else:
        main()
