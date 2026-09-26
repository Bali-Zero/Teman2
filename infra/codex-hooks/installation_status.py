"""Read-only proof of the installed artifact, trust and prior consumer probes."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from context_bridge import EVENTS, codex_home, digest, load
from install import COMPACT_OVERRIDES, owns_guard
from rpc import RPC, binary_path

BRIDGE_MARK = "nuzantara-context/context_bridge.py"


def native_compact_defaults(config_file: Path) -> bool:
    config = tomllib.loads(config_file.read_text()) if config_file.exists() else {}
    active_profile = config.get("profiles", {}).get(config.get("profile"), {})
    return not any(key in config or key in active_profile for key in COMPACT_OVERRIDES)


def ours(command: str, seat: Path) -> bool:
    return BRIDGE_MARK in command or owns_guard(command, seat)


def foreign_hooks(config: dict, seat: Path) -> dict:
    """Every handler except ours, grouped as configured; empty groups dropped."""
    result = {}
    for event, groups in (config.get("hooks") or {}).items():
        kept = []
        for group in groups:
            handlers = [
                h
                for h in group.get("hooks", [])
                if not ours(h.get("command", ""), seat)
            ]
            if handlers:
                kept.append(dict(group, hooks=handlers))
        if kept:
            result[event] = kept
    return result


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
    guard = [h for h in entries["hooks"] if owns_guard(h.get("command", ""), seat)]
    hashes = {
        name: digest((seat / "hooks" / "nuzantara-context" / name).read_bytes())
        for name in manifest["source_sha256"]
    }
    # Preservation is judged against the snapshot taken just before THIS install,
    # handler by handler; original_backup stays the rollback point only.
    previous = manifest.get("backup") or manifest["original_backup"]
    old = foreign_hooks(load(Path(previous) / "hooks.json"), seat)
    current = foreign_hooks(load(seat / "hooks.json"), seat)
    result = {
        "seat": str(seat),
        "binary": binary_path(),
        "enabled": policy.get("enabled"),
        "parent_rollover_enabled": policy.get("parent_rollover_enabled", True),
        "native_compact_defaults": native_compact_defaults(seat / "config.toml"),
        "trusted_events": [
            h["eventName"]
            for h in hooks
            if h["trustStatus"] == "trusted" and h["enabled"]
        ],
        "output_guard_trusted": len(guard) == 1
        and guard[0]["trustStatus"] == "trusted"
        and guard[0]["enabled"]
        and guard[0].get("matcher") == "Bash"
        and str(guard[0].get("eventName", "")).lower() == "pretooluse",
        "artifact_matches_manifest": hashes == manifest["source_sha256"],
        "existing_hooks_preserved": current == old,
        "thresholds": policy["thresholds"],
        "source_sha256": hashes,
        "original_backup": manifest["original_backup"],
        "lifecycle_probe": load(seat / "state" / "nuzantara-context-smoke.json"),
        "handoff_probe": load(seat / "state" / "nuzantara-context-handoff-smoke.json"),
    }
    result["installed"] = (
        len(result["trusted_events"]) == len(EVENTS)
        and result["output_guard_trusted"]
        and result["enabled"]
        and result["artifact_matches_manifest"]
        and result["existing_hooks_preserved"]
        and not result["parent_rollover_enabled"]
        and result["native_compact_defaults"]
    )
    print(json.dumps(result, indent=2))
    if not result["installed"]:
        raise RuntimeError("installation proof failed")


if __name__ == "__main__":
    main()
