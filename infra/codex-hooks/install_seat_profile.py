#!/usr/bin/env python3
"""Install the reviewed Codex seat profile: root developer instructions + routine roles.

Sources live in seat/ and are the M5 seat's reviewed bytes. Per item: absent ->
installed; identical -> untouched; different -> left alone and reported as
operator-owned drift, never overwritten. Every write is preceded by a private
backup. The root key is written through Codex's own config API and then checked
semantically: only that key may change. --check is read-only; --remove deletes
only items still identical to these sources. No auth or other config is copied.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import tomllib
from pathlib import Path

from context_bridge import digest, save
from rpc import RPC

SOURCE = Path(__file__).resolve().parent / "seat"
ROLES = ("routine-explorer", "routine-worker", "mechanical", "code-reviewer")
KEY = "developer_instructions"


def expected() -> tuple[str, dict[str, bytes]]:
    text = (SOURCE / "developer_instructions.txt").read_text()
    return text, {r: (SOURCE / "agents" / f"{r}.toml").read_bytes() for r in ROLES}


def read_config(config_file: Path) -> dict:
    return tomllib.loads(config_file.read_text()) if config_file.exists() else {}


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
        result["roles"][role] = (
            "absent"
            if not path.exists()
            else "match"
            if path.read_bytes() == data
            else "drift"
        )
    result["installed"] = result[KEY] == "match" and all(
        v == "match" for v in result["roles"].values()
    )
    return result


def write_private(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with open(temp, "wb", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        stream.write(data)
    os.replace(temp, path)


def config_write(seat: Path, edits: list[dict]) -> None:
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(seat)
    rpc = RPC()
    try:
        rpc.call("config/batchWrite", {"edits": edits})
    finally:
        rpc.close()
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


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
        if path.exists():
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
    result["backup"] = str(backup_seat(seat, config_file))
    (seat / "agents").mkdir(mode=0o700, exist_ok=True)
    for role, data in roles.items():
        if before["roles"][role] == "absent":
            write_private(seat / "agents" / f"{role}.toml", data)
    if before[KEY] == "absent":
        original = read_config(config_file)
        mode = config_file.stat().st_mode & 0o777
        config_write(
            seat, [{"keyPath": KEY, "value": text, "mergeStrategy": "replace"}]
        )
        try:
            after = read_config(config_file)
        except tomllib.TOMLDecodeError:
            after = {}
        if (
            after.get(KEY) != text
            or {k: v for k, v in after.items() if k != KEY} != original
        ):
            # Not restored automatically: a concurrent writer's edit would be lost.
            raise RuntimeError(
                "developer_instructions write was not exact; backup at "
                + result["backup"]
            )
        if config_file.stat().st_mode & 0o777 != mode:
            config_file.chmod(mode)
    result.update(status(seat))
    save(seat / "state" / "nuzantara-seat-profile-install.json", result)
    return result


def remove(seat: Path) -> dict:
    seat, config_file = prepare(seat)
    before = status(seat)
    result = {
        "seat": str(seat),
        "before": before,
        "backup": str(backup_seat(seat, config_file)),
    }
    for role, state in before["roles"].items():
        if state == "match":
            (seat / "agents" / f"{role}.toml").unlink()
    if before[KEY] == "match":
        source = config_file.read_text()
        expected_config = tomllib.loads(source)
        del expected_config[KEY]
        stripped = re.sub(
            r"(?m)^[ \t]*" + KEY + r"[ \t]*=[^\n]*(?:\n|$)", "", source, count=1
        )
        if tomllib.loads(stripped) != expected_config:
            raise ValueError(
                "cannot safely remove developer_instructions; restore the backup"
            )
        mode = config_file.stat().st_mode & 0o777
        write_private(config_file, stripped.encode())
        config_file.chmod(mode)
    result.update(status(seat))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seat", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    if args.check:
        result = status(args.seat.expanduser().resolve())
    elif args.remove:
        result = remove(args.seat)
    else:
        result = install(args.seat)
    print(json.dumps(result, indent=2))
    if args.check and not result["installed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
