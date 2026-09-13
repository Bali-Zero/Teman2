"""Offline release validation. No database, authentication, or model calls."""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def manifest(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("release_symlink_forbidden")
        relative = path.relative_to(root).as_posix()
        if not re.fullmatch(r"[A-Za-z0-9_./+\-]+", relative):
            raise ValueError("release_filename_invalid")
        if path.is_file() and relative != "SHA256SUMS":
            rows.append(f"{sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    if not rows:
        raise ValueError("release_empty")
    return "".join(rows)


def native_references_allowed(
    text: str, binary: Path, root: Path, *, install_name: str | None = None
) -> bool:
    for index, line in enumerate(text.splitlines()[1:]):
        reference = line.strip().split(" (", 1)[0]
        if not reference:
            continue
        # otool -L also lists a dylib's own LC_ID_DYLIB first. This identifier
        # is not a path it loads; real LC_LOAD_* dependencies remain checked.
        if index == 0 and reference == install_name:
            continue
        if reference.startswith(("/usr/lib/", "/System/Library/")):
            continue
        if reference.startswith("@rpath/"):
            if ".." in Path(reference).parts:
                return False
            continue
        if reference.startswith("@executable_path/"):
            target = (
                root / "python/bin" / reference.removeprefix("@executable_path/")
            ).resolve()
            if target.is_relative_to(root):
                continue
        if reference.startswith("@loader_path/"):
            target = (binary.parent / reference.removeprefix("@loader_path/")).resolve()
            if target.is_relative_to(root):
                continue
        return False
    return True


def verify(root: Path, *, immutable: bool = False, native: bool = True) -> None:
    root = root.resolve()
    if (root / "SHA256SUMS").read_text() != manifest(root):
        raise ValueError("release_manifest_mismatch")
    if immutable and sys.platform == "darwin":
        for option in ("-lde", "-leR"):
            listing = subprocess.run(
                ["/bin/ls", option, str(root)],
                capture_output=True,
                text=True,
                check=True,
            )
            if re.search(r"^\s*\d+:", listing.stdout, re.MULTILINE):
                raise ValueError("release_acl_forbidden")
    for path in [root, *root.rglob("*")]:
        status = path.lstat()
        if not (stat.S_ISREG(status.st_mode) or stat.S_ISDIR(status.st_mode)):
            raise ValueError("release_special_file_forbidden")
        if immutable and (status.st_uid != 0 or status.st_mode & 0o6022):
            raise ValueError("release_not_root_protected")
        if not native or not path.is_file():
            continue
        with path.open("rb") as handle:
            magic = handle.read(4)
        if magic not in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe"):
            continue
        linked = subprocess.run(
            ["/usr/bin/otool", "-L", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        load = subprocess.run(
            ["/usr/bin/otool", "-l", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        identity = re.search(
            r"cmd LC_ID_DYLIB\n.*?\n\s*name (.*?) \(offset", load.stdout
        )
        if not native_references_allowed(
            linked.stdout,
            path,
            root,
            install_name=identity.group(1) if identity else None,
        ):
            raise ValueError("external_runtime_library")
        for value in re.findall(
            r"cmd LC_RPATH\n.*?\n\s*path (.*?) \(offset", load.stdout
        ):
            if value.startswith(("@loader_path", "@executable_path")):
                relative = value.split("/", 1)[1] if "/" in value else "."
                origin = (
                    path.parent
                    if value.startswith("@loader_path")
                    else root / "python/bin"
                )
                if (origin / relative).resolve().is_relative_to(root):
                    continue
            raise ValueError("external_runtime_search_path")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--immutable", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    try:
        verify(root, immutable=args.immutable)
        if not Path(sys.base_prefix).resolve().is_relative_to(root / "python"):
            raise ValueError("interpreter_outside_release")
        sys.path[:0] = [
            str(root / "site-packages"),
            str(root / "src"),
            str(root / "src/apps/backend-rag"),
            str(root / "src/packages/research-os-core"),
        ]
        for module in (
            "scripts.consul_broker",
            "asyncpg",
            "backend.core.pg_json_codec",
            "backend.services.autonomous_lab.consul_native_broker",
        ):
            importlib.import_module(module)
    except (ValueError, OSError, ImportError, subprocess.SubprocessError):
        print(json.dumps({"status": "release_rejected"}))
        return 1
    print(json.dumps({"status": "release_verified", "uid": os.getuid()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
