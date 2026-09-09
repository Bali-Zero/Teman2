#!/usr/bin/env python3
"""Install the reviewed bridge on this host using Codex's own hook hashes.

No existing hook is removed/reordered, no security setting is weakened, and
no auth/config file is copied between machines. Each seat remains independent.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
import time
from pathlib import Path

import mandate_budget
from context_bridge import EVENTS, VERSION, digest, load, save
from rpc import RPC


def install(seat: Path, roots: list[str], trust: bool = False) -> dict:
    seat = seat.expanduser().resolve()
    seat.mkdir(parents=True, exist_ok=True)
    roots = list(dict.fromkeys([*roots, str(seat / "worktrees")]))
    dest = seat / "hooks" / "nuzantara-context"
    dest.mkdir(parents=True, exist_ok=True)
    backup = seat / "state" / "nuzantara-context-backups" / str(time.time_ns())
    backup.mkdir(parents=True, mode=0o700)
    hooks_file = seat / "hooks.json"
    # Preserve exact originals before the narrowly scoped configuration changes.
    for old in (
        hooks_file,
        seat / "config.toml",
        seat / "nuzantara-context-policy.json",
    ):
        if old.exists():
            shutil.copy2(old, backup / old.name)
            (backup / old.name).chmod(0o600)
    hashes = {}
    for name in ("context_bridge.py", "rpc.py", "mandate_budget.py"):
        source = Path(__file__).parent / name
        if (dest / name).exists():
            shutil.copy2(dest / name, backup / name)
        shutil.copy2(source, dest / name)
        (dest / name).chmod(0o700)
        hashes[name] = digest(source.read_bytes())
    command = shlex.join([sys.executable, str(dest / "context_bridge.py"), "hook"])
    config = load(hooks_file)
    events = config.setdefault("hooks", {})
    for event in EVENTS:
        groups = events.setdefault(event, [])
        ours = [
            h
            for group in groups
            for h in group.get("hooks", [])
            if "nuzantara-context/context_bridge.py" in h.get("command", "")
        ]
        if len(ours) > 1:
            raise ValueError("duplicate bridge hook")
        handler = {
            "type": "command",
            "command": command,
            "timeout": 60,
            "statusMessage": "Nuzantara Codex context and verification",
        }
        if ours:
            ours[0].update(handler)
        else:
            groups.append({"hooks": [handler]})
    save(hooks_file, config)
    policy = load(seat / "nuzantara-context-policy.json")
    policy.update(version=VERSION, enabled=True, roots=roots)
    policy.setdefault("thresholds", {"imperator": 0.2, "builder": 0.4})
    policy.setdefault("max_hops", 3)
    policy.setdefault(
        "child_limits",
        {
            "max_attempts": 24,
            "max_active": 3,
            "max_depth": 1,
            "max_seconds": 3600,
            # Declared, not inherited: the Claude adapter passes the same value and
            # the asymmetry was silent until the council named it.
            "active_ttl": mandate_budget.ACTIVE_TTL_SECONDS,
        },
    )
    save(seat / "nuzantara-context-policy.json", policy)
    # Only the current seat is selected for this subprocess. Credentials stay put.
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(seat)
    rpc = RPC()
    try:
        response = rpc.call("hooks/list", {"cwds": roots[:1]})
        items = response["data"][0]
        if items.get("errors"):
            raise RuntimeError("Codex rejected hook configuration")
        hooks = [h for h in items["hooks"] if h.get("command") == command]
        if len(hooks) != len(EVENTS):
            raise RuntimeError("Codex did not discover all bridge events")
        if trust:
            edits = [
                {"keyPath": "features.hooks", "value": True, "mergeStrategy": "replace"}
            ]
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
        result = {
            "seat": str(seat),
            "version": VERSION,
            "backup": str(backup),
            "events": len(hooks),
            "source_sha256": hashes,
            "trust_requested": trust,
        }
        previous_install = load(seat / "state" / "nuzantara-context-install.json")
        result["original_backup"] = previous_install.get("original_backup") or str(
            min(backup.parent.iterdir(), key=lambda p: p.name)
        )
        save(seat / "state" / "nuzantara-context-install.json", result)
        return result
    finally:
        rpc.close()
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seat", type=Path, required=True)
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--trust-reviewed-hooks", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(install(args.seat, args.root, args.trust_reviewed_hooks), indent=2)
    )


if __name__ == "__main__":
    main()
