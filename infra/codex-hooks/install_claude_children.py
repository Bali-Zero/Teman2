"""Install a narrow child router; original Claude guards remain byte-identical."""

from __future__ import annotations
import argparse
import hashlib
import json
import shlex
import shutil
import sys
import time
from pathlib import Path


def route_settings(settings: dict, shared_hooks: Path) -> dict:
    """Preserve interpreter, arguments, timeout and unrelated hooks; fail before writes."""
    settings = json.loads(json.dumps(settings))
    for event, filename, mode in (
        ("PreToolUse", "context_window_guard.py", "context"),
        ("SubagentStop", "subagent_stop_verify.py", "stop"),
        ("SubagentStart", None, "start"),
    ):
        groups = settings.setdefault("hooks", {}).setdefault(event, [])
        matches = [
            h
            for g in groups
            for h in g.get("hooks", [])
            if (filename and filename in h.get("command", ""))
            or "child_workflow.py" in h.get("command", "")
        ]
        if len(matches) > 1:
            raise ValueError("Duplicate or ambiguous child adapter target: " + event)
        if matches:
            handler = matches[0]
            argv = shlex.split(handler["command"])
            if filename:
                positions = [
                    i for i, a in enumerate(argv) if a.endswith("/" + filename)
                ]
                if positions:
                    if len(positions) != 1 or positions[0] != len(argv) - 1:
                        raise ValueError(
                            "Unsupported legacy hook command; preserve it for review"
                        )
                    argv[positions[0] :] = [
                        str(shared_hooks / "child_workflow.py"),
                        mode,
                    ]
                    handler["command"] = shlex.join(argv)
        else:
            groups.append(
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": shlex.join(
                                [
                                    sys.executable,
                                    str(shared_hooks / "child_workflow.py"),
                                    mode,
                                ]
                            ),
                            "timeout": 30,
                        }
                    ]
                }
            )
    return settings


def install(seat: Path, shared_hooks: Path) -> dict:
    originals = (
        "context_window_guard.py",
        "subagent_stop_verify.py",
        "orchestrate_gate.py",
    )
    before = {
        n: hashlib.sha256((shared_hooks / n).read_bytes()).hexdigest()
        for n in originals
    }
    settings_path = seat / "settings.json"
    settings = route_settings(json.loads(settings_path.read_text()), shared_hooks)
    sources = {
        "child_workflow.py": Path(__file__).parents[1]
        / "claude-hooks"
        / "child_workflow.py",
        "mandate_budget.py": Path(__file__).parent / "mandate_budget.py",
    }
    for n, p in sources.items():
        compile(p.read_text(), n, "exec")
    backup = seat / "state" / "child-workflow-backups" / str(time.time_ns())
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(settings_path, backup / "settings.json")
    for n, p in sources.items():
        if (shared_hooks / n).exists():
            shutil.copy2(shared_hooks / n, backup / n)
        shutil.copy2(p, shared_hooks / n)
    # Symlinked account settings deliberately continue to point to the same file.
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    settings_path.chmod(0o600)
    after = {
        n: hashlib.sha256((shared_hooks / n).read_bytes()).hexdigest()
        for n in originals
    }
    assert before == after
    result = {
        "seat": str(seat),
        "hook_directory": str(shared_hooks),
        "backup": str(backup),
        "legacy_guards_byte_identical": True,
        "legacy_sha256": after,
        "sha256": {
            n: hashlib.sha256((shared_hooks / n).read_bytes()).hexdigest()
            for n in sources
        },
    }
    (seat / "state" / "child-workflow-install.json").write_text(
        json.dumps(result, indent=2)
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seat", type=Path, required=True)
    parser.add_argument("--hooks", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(install(args.seat.expanduser(), args.hooks.expanduser()), indent=2)
    )
