#!/usr/bin/env python3
"""Install the reviewed bridge on this host using Codex's own hook hashes.

No existing hook is removed/reordered, no security setting is weakened, and
no auth/config file is copied between machines. Each seat remains independent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
import time
import tomllib
from pathlib import Path

import mandate_budget
from context_bridge import EVENTS, VERSION, digest, load, save
from rpc import RPC


THRESHOLD_DEFAULTS = {"imperator": 0.6, "builder": 0.6, "dux": 0.6}
# The reviewed Claude guard, unchanged. Codex reports shell calls to PreToolUse
# as tool_name "Bash" with tool_input.command (observed in this bridge's own
# state) and honours exit 2 + stderr as a deny. Whether every exec path emits
# PreToolUse is upstream- and version-dependent: the release proves it live.
GUARD_NAME = "output_hygiene_guard.py"
GUARD_SOURCE = Path(__file__).resolve().parent.parent / "claude-hooks" / GUARD_NAME
GUARD_MARK = "nuzantara-context/" + GUARD_NAME


def owns_guard(command: str, seat: Path) -> bool:
    """Ours only if the command runs this seat's installed copy, not a lookalike."""
    target = str(seat / "hooks" / "nuzantara-context" / GUARD_NAME)
    try:
        return target in shlex.split(command)
    except ValueError:
        return False


COMPACT_OVERRIDES = (
    "model_auto_compact_token_limit",
    "model_auto_compact_token_limit_scope",
)


def native_compact_config(source: str) -> str:
    """Drop only root compact overrides; reject any collateral TOML change."""
    expected = tomllib.loads(source)
    result = source
    for key in COMPACT_OVERRIDES:
        if key not in expected:
            continue
        del expected[key]
        result = re.sub(
            r"(?m)^[ \t]*" + re.escape(key) + r"[ \t]*=[^\n]*(?:\n|$)",
            "",
            result,
            count=1,
        )
    if tomllib.loads(result) != expected:
        raise ValueError("cannot safely remove root compaction overrides")
    return result


def merge_thresholds(policy: dict) -> dict:
    """Fill missing role thresholds per KEY, never per dict.

    `policy.setdefault("thresholds", {...})` added nothing to a host that had
    ever been installed, so a role introduced later could never reach an
    existing seat: the three live policies carried `imperator`/`builder` and
    would have carried no `dux` forever, and the seat would have silently used
    the conservative 0.4 fallback while the doctrine said 0.6. Each key is
    filled only when ABSENT, so an operator's tuned value survives every
    reinstall -- the same reason the imperator regression still pins 0.2.
    """
    thresholds = policy.setdefault("thresholds", {})
    for role, default in THRESHOLD_DEFAULTS.items():
        thresholds.setdefault(role, default)
    return thresholds


def install(seat: Path, roots: list[str], trust: bool = False) -> dict:
    seat = seat.expanduser().resolve()
    config_file = seat / "config.toml"
    if config_file.is_symlink():
        raise ValueError("refusing to replace a symlinked Codex config")
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
    if config_file.exists():
        original = config_file.read_bytes().decode("utf-8")
        migrated = native_compact_config(original)
        if migrated != original:
            staged = backup / "config.native.toml"
            staged.write_bytes(migrated.encode("utf-8"))
            staged.chmod(config_file.stat().st_mode & 0o777)
            os.replace(staged, config_file)
    hashes = {}
    sources = {
        name: Path(__file__).parent / name
        for name in ("context_bridge.py", "rpc.py", "mandate_budget.py")
    }
    sources[GUARD_NAME] = GUARD_SOURCE
    for name, source in sources.items():
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
    guard_command = shlex.join([sys.executable, str(dest / GUARD_NAME)])
    pre = events.setdefault("PreToolUse", [])
    owned = [
        (group, h)
        for group in pre
        for h in group.get("hooks", [])
        if owns_guard(h.get("command", ""), seat)
    ]
    if len(owned) > 1:
        raise ValueError("duplicate output guard hook")
    guard_group = {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "command": guard_command,
                "timeout": 10,
                "statusMessage": "Nuzantara output hygiene",
            }
        ],
    }
    if owned and len(owned[0][0].get("hooks", [])) == 1:
        owned[0][0].clear()
        owned[0][0].update(guard_group)
    else:
        # Only our handler moves: a foreign handler sharing its group stays put.
        if owned:
            owned[0][0]["hooks"].remove(owned[0][1])
        pre.append(guard_group)
    save(hooks_file, config)
    policy = load(seat / "nuzantara-context-policy.json")
    policy.update(
        version=VERSION, enabled=True, roots=roots, parent_rollover_enabled=False
    )
    merge_thresholds(policy)
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
        guard = [h for h in items["hooks"] if h.get("command") == guard_command]
        if len(guard) != 1:
            raise RuntimeError("Codex did not discover the output guard")
        if trust:
            edits = [
                {"keyPath": "features.hooks", "value": True, "mergeStrategy": "replace"}
            ]
            for h in hooks + guard:
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
