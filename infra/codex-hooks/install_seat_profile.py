#!/usr/bin/env python3
"""Install the reviewed Codex seat profile: root developer instructions + routine roles.

Sources live in seat/ and are the M5 seat's reviewed bytes. Per item: absent ->
installed; identical -> untouched; different -> left alone and reported as
operator-owned drift, never overwritten. Every write is preceded by a private
backup. The root key is validated absent in ONE user-layer snapshot from Codex's
own config/read and written with config/batchWrite pinned to that snapshot's
version, so changes arriving before Codex's version check are refused. This is
not a cross-process lock; installation requires an otherwise idle seat. The binary
must first reject a stale version on a scratch seat, and the result is checked
semantically afterwards. --check is read-only. There is deliberately no automatic removal: rollback is a
manual step with an exclusive writer (README). No auth or other config is copied.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import tempfile
import time
import tomllib
from pathlib import Path

from context_bridge import digest, save
from rpc import RPC

SOURCE = Path(__file__).resolve().parent / "seat"
ROLES = ("routine-explorer", "routine-worker", "mechanical", "code-reviewer")
KEY = "developer_instructions"
SKILL_BUDGET = 3000
NOTEBOOKLM = "notebooklm-mcp"
RESEARCH_READ_TOOLS = frozenset({
    "notebook_list", "notebook_get", "notebook_describe", "source_describe",
    "source_get_content", "notebook_query", "notebook_query_start",
    "notebook_query_status", "cross_notebook_query", "collection_list",
})


def expected() -> tuple[str, dict[str, bytes]]:
    text = (SOURCE / "developer_instructions.txt").read_text(encoding="utf-8")
    return text, {r: (SOURCE / "agents" / f"{r}.toml").read_bytes() for r in ROLES}


def read_config(config_file: Path) -> dict:
    if not config_file.exists():
        return {}
    return tomllib.loads(config_file.read_text(encoding="utf-8"))


def status(seat: Path) -> dict:
    text, roles = expected()
    current = read_config(seat / "config.toml").get(KEY)
    result = {
        KEY: "absent" if current is None else "match" if current == text else "drift",
        KEY + "_sha256": digest(text.encode()),
        "roles": {},
    }
    for role, data in roles.items():
        path = seat / "agents" / f"{role}.toml"
        if path.is_symlink() or (path.exists() and not path.is_file()):
            state = "drift"  # a link, directory or FIFO is never ours to replace
        elif not path.exists():
            state = "absent"
        else:
            state = "match" if path.read_bytes() == data else "drift"
        result["roles"][role] = state
    result["installed"] = result[KEY] == "match" and all(
        v == "match" for v in result["roles"].values()
    )
    return result


def create_exclusive(path: Path, data: bytes) -> bool:
    """Create path only if nobody else has; a concurrent writer's file wins."""
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with open(temp, "wb", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        stream.write(data)
    try:
        os.link(temp, path)
        return True
    except FileExistsError:
        return False
    finally:
        temp.unlink(missing_ok=True)


def rpc_call(seat: Path, method: str, params: dict) -> dict:
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(seat)
    rpc = None
    try:
        rpc = RPC()
        return rpc.call(method, params)
    finally:
        try:
            if rpc is not None:
                rpc.close()
        finally:
            if previous is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = previous


def user_layer(seat: Path, config_file: Path) -> tuple[dict, str]:
    """The seat's user-layer config and its opaque version, from one snapshot."""
    out = rpc_call(seat, "config/read", {"includeLayers": True})
    for layer in out.get("layers") or []:
        name = layer.get("name") or {}
        if (
            name.get("type") == "user"
            and name.get("profile") is None
            and Path(str(name.get("file"))).resolve() == config_file.resolve()
        ):
            return layer.get("config") or {}, layer["version"]
    raise RuntimeError(f"Codex reports no user layer for {config_file}")


def pinned_write(seat: Path, edits: list[dict], version: str) -> None:
    rpc_call(seat, "config/batchWrite", {"edits": edits, "expectedVersion": version})


def conditional_write_proven() -> bool:
    """True only if this Codex refuses a write pinned to a superseded version."""
    with tempfile.TemporaryDirectory(prefix="seat-profile-cas-") as tmp:
        scratch = Path(tmp)
        config_file = scratch / "config.toml"
        config_file.write_text('probe = "a"\n', encoding="utf-8")
        _, version = user_layer(scratch, config_file)
        config_file.write_text('probe = "b"\n', encoding="utf-8")
        edit = {"keyPath": "probe", "value": "c", "mergeStrategy": "replace"}
        try:
            pinned_write(scratch, [edit], version)
        except RuntimeError as exc:
            return "configVersionConflict" in str(exc)
        return False


def prepare(seat: Path) -> tuple[Path, Path]:
    seat = seat.expanduser().resolve()
    config_file = seat / "config.toml"
    if config_file.is_symlink():
        raise ValueError("refusing to replace a symlinked Codex config")
    if not config_file.is_file():
        raise ValueError("seat has no config.toml")
    return seat, config_file


def backup_seat(seat: Path, config_file: Path) -> Path:
    backup = seat / "state" / "nuzantara-seat-profile-backups" / str(time.time_ns())
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(config_file, backup / "config.toml")
    (backup / "config.toml").chmod(0o600)
    for role in ROLES:
        path = seat / "agents" / f"{role}.toml"
        if path.is_file() and not path.is_symlink():
            shutil.copy2(path, backup / path.name)
            (backup / path.name).chmod(0o600)
    return backup


def install(seat: Path) -> dict:
    seat, config_file = prepare(seat)
    before = status(seat)
    text, roles = expected()
    result = {"seat": str(seat), "before": before, "backup": None}
    if before["installed"] or (
        before[KEY] != "absent" and "absent" not in before["roles"].values()
    ):
        result.update(status(seat))
        return result
    if before[KEY] == "absent" and not conditional_write_proven():
        raise RuntimeError(
            "this Codex does not refuse a stale config version; seat config unchanged"
        )
    result["backup"] = str(backup_seat(seat, config_file))
    (seat / "agents").mkdir(mode=0o700, exist_ok=True)
    for role, data in roles.items():
        if before["roles"][role] == "absent":
            create_exclusive(seat / "agents" / f"{role}.toml", data)
    if before[KEY] == "absent":
        mode = config_file.stat().st_mode & 0o777
        snapshot, version = user_layer(seat, config_file)
        try:
            if KEY in snapshot:
                raise RuntimeError(
                    "developer_instructions appeared concurrently; config not written; backup/role files may exist"
                )
            edit = {"keyPath": KEY, "value": text, "mergeStrategy": "replace"}
            try:
                pinned_write(seat, [edit], version)
            except RuntimeError as exc:
                if "configVersionConflict" in str(exc):
                    raise RuntimeError(
                        "config.toml changed since it was validated; config not written; backup/role files may exist"
                    ) from exc
                raise
            after, _ = user_layer(seat, config_file)
            if (
                after.get(KEY) != text
                or {k: v for k, v in after.items() if k != KEY} != snapshot
            ):
                # Not restored automatically: a concurrent writer's edit would be lost.
                raise RuntimeError(
                    "developer_instructions write was not exact; backup at "
                    + result["backup"]
                )
        finally:
            if config_file.exists() and config_file.stat().st_mode & 0o777 != mode:
                config_file.chmod(mode)
    result.update(status(seat))
    save(seat / "state" / "nuzantara-seat-profile-install.json", result)
    return result


def notebook_tools(seat: Path) -> set[str]:
    """Discover effective tools from this seat; no notebook content is requested."""
    cursor = None
    seen = set()
    for _ in range(20):
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = rpc_call(seat, "mcpServerStatus/list", params)
        for server in page.get("data") or []:
            if server.get("name") == NOTEBOOKLM:
                tools = server.get("tools")
                if server.get("toolsError") or not isinstance(tools, dict) or not tools:
                    raise RuntimeError("NotebookLM tool discovery unavailable; no config changes")
                return set(tools)
        cursor = page.get("nextCursor")
        if not cursor or cursor in seen:
            break
        seen.add(cursor)
    raise RuntimeError("NotebookLM server not observed; no config changes")


def loadout_plan(config: dict, tools: set[str] | None, *, notebooklm: bool = True) -> tuple[dict, list[dict]]:
    """Per item: absent -> install, match -> noop, different -> report drift."""
    edits = []

    def item(path: str, current, wanted) -> str:
        if current is None:
            edits.append({"keyPath": path, "value": wanted, "mergeStrategy": "replace"})
            return "absent"
        return "match" if current == wanted else "drift"

    result = {"skills.max_context_tokens": item(
        "skills.max_context_tokens", config.get("skills", {}).get("max_context_tokens"), SKILL_BUDGET)}
    server = config.get("mcp_servers", {}).get(NOTEBOOKLM)
    if not notebooklm:
        result[NOTEBOOKLM] = "unchanged"
    elif server is None:
        result[NOTEBOOKLM] = "not_configured"
    elif server.get("enabled") is False:
        result[NOTEBOOKLM] = "disabled_by_operator"
    elif "enabled_tools" in server:
        result[NOTEBOOKLM] = "drift"  # an operator's allowlist remains authoritative
    else:
        current = server.get("disabled_tools")
        if current is not None and (not isinstance(current, list) or not all(isinstance(t, str) for t in current)):
            raise ValueError("invalid NotebookLM disabled_tools")
        # The native list omits disabled names. Combine its observation with the
        # existing filter for repeat checks; never hard-code a server inventory.
        known = (tools or set()) | set(current or [])
        if not RESEARCH_READ_TOOLS.issubset(tools or set()):
            result[NOTEBOOKLM] = "drift" if current is not None else "unavailable"
        else:
            wanted = sorted(known - RESEARCH_READ_TOOLS)
            normalized = sorted(set(current)) if current is not None else None
            result[NOTEBOOKLM] = item(f"mcp_servers.{NOTEBOOKLM}.disabled_tools", normalized, wanted)
        result["exposed_tools"] = len(tools or [])
    result["installed"] = (result["skills.max_context_tokens"] == "match"
                           and result[NOTEBOOKLM] in ("match", "not_configured", "disabled_by_operator", "unchanged"))
    return result, edits


def loadout(seat: Path, *, check: bool = False, notebooklm: bool = True) -> dict:
    seat, config_file = prepare(seat)
    # Pin the snapshot BEFORE discovery so a concurrent server/config change
    # cannot apply a filter derived from a different configuration.
    snapshot, version = user_layer(seat, config_file)
    server = snapshot.get("mcp_servers", {}).get(NOTEBOOKLM)
    tools = (notebook_tools(seat) if notebooklm and server is not None and server.get("enabled") is not False
             and "enabled_tools" not in server else None)
    before, edits = loadout_plan(snapshot, tools, notebooklm=notebooklm)
    result = {"seat": str(seat), "before": before, "backup": None, **before}
    if check or not edits:
        return result
    if not conditional_write_proven():
        raise RuntimeError("this Codex does not refuse a stale config version; seat config unchanged")
    result["backup"] = str(backup_seat(seat, config_file))
    expected_config = copy.deepcopy(snapshot)
    for edit in edits:
        target = expected_config
        parts = edit["keyPath"].split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = edit["value"]
    mode = config_file.stat().st_mode & 0o777
    try:
        pinned_write(seat, edits, version)
        after, _ = user_layer(seat, config_file)
        if after != expected_config:
            raise RuntimeError("loadout write was not exact; retain backup and inspect concurrent changes")
    finally:
        if config_file.is_file() and not config_file.is_symlink() and config_file.stat().st_mode & 0o777 != mode:
            config_file.chmod(mode)
    observed = notebook_tools(seat) if tools is not None else None
    result.update(loadout_plan(after, observed, notebooklm=notebooklm)[0])
    save(seat / "state" / "nuzantara-seat-loadout-install.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seat", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--loadout", action="store_true", help="opt in to bounded skills and NotebookLM read/query tools")
    scope.add_argument("--skills-only", action="store_true", help="bound skills without changing or querying MCP servers")
    args = parser.parse_args()
    if args.loadout or args.skills_only:
        result = loadout(args.seat, check=args.check, notebooklm=args.loadout)
    elif args.check:
        result = status(args.seat.expanduser().resolve())
    else:
        result = install(args.seat)
    print(json.dumps(result, indent=2))
    if args.check and not result["installed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
