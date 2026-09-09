"""Read-only proof of the installed artifact, trust and prior consumer probes."""

from __future__ import annotations

import json
from pathlib import Path

from context_bridge import codex_home, digest, load
from rpc import RPC, binary_path


def main() -> None:
    seat = codex_home()
    manifest = load(seat / "state" / "nuzantara-context-install.json")
    policy = load(seat / "nuzantara-context-policy.json")
    rpc = RPC()
    try:
        entries = rpc.call("hooks/list", {"cwds": policy["roots"][:1]})["data"][0]
    finally:
        rpc.close()
    hooks = [
        h
        for h in entries["hooks"]
        if "nuzantara-context/context_bridge.py" in h.get("command", "")
    ]
    hashes = {
        name: digest((seat / "hooks" / "nuzantara-context" / name).read_bytes())
        for name in manifest["source_sha256"]
    }
    old = load(Path(manifest["original_backup"]) / "hooks.json")
    current = load(seat / "hooks.json")
    for event in list(current.get("hooks", {})):
        groups = current["hooks"][event]
        groups[:] = [
            g
            for g in groups
            if not any(
                "nuzantara-context/context_bridge.py" in h.get("command", "")
                for h in g.get("hooks", [])
            )
        ]
        if not groups and event not in old.get("hooks", {}):
            del current["hooks"][event]
    if not current.get("hooks") and not old:
        current = {}
    result = {
        "seat": str(seat),
        "binary": binary_path(),
        "enabled": policy.get("enabled"),
        "trusted_events": [
            h["eventName"]
            for h in hooks
            if h["trustStatus"] == "trusted" and h["enabled"]
        ],
        "artifact_matches_manifest": hashes == manifest["source_sha256"],
        "existing_hooks_preserved": current == old,
        "thresholds": policy["thresholds"],
        "source_sha256": hashes,
        "original_backup": manifest["original_backup"],
        "lifecycle_probe": load(seat / "state" / "nuzantara-context-smoke.json"),
        "handoff_probe": load(seat / "state" / "nuzantara-context-handoff-smoke.json"),
    }
    result["installed"] = (
        len(result["trusted_events"]) == 6
        and result["enabled"]
        and result["artifact_matches_manifest"]
        and result["existing_hooks_preserved"]
    )
    print(json.dumps(result, indent=2))
    if not result["installed"]:
        raise RuntimeError("installation proof failed")


if __name__ == "__main__":
    main()
