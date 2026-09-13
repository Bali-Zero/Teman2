"""Build a disposable Pro-only, wheel-only release; never install or activate it."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import tarfile
import tempfile

from verify import manifest

PYTHON_URL = "https://github.com/astral-sh/python-build-standalone/releases/download/20260807/cpython-3.11.15%2B20260807-aarch64-apple-darwin-install_only_stripped.tar.gz"
PYTHON_SHA256 = "76b27e15a5be9539b830fc698e2646d001b84a66500eeb5228cee46909d6f2cf"
UV = "/opt/homebrew/bin/uv"
SOURCE_ROOTS = ("", "apps/backend-rag", "packages/research-os-core")


def source_closure(repo: Path) -> list[Path]:
    """Copy only statically imported internal Python sources, including inits."""
    pending = ["scripts.consul_broker"]
    visited: set[str] = set()
    files: set[Path] = set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        candidates = [
            repo / prefix / (module.replace(".", "/") + suffix)
            for prefix in SOURCE_ROOTS
            for suffix in (".py", "/__init__.py")
        ]
        path = next((path for path in candidates if path.is_file()), None)
        if path is None:
            continue
        if not path.resolve().is_relative_to(repo.resolve()) or path.is_symlink():
            raise ValueError("source_outside_repository")
        files.add(path)
        pieces = module.split(".")
        pending.extend(".".join(pieces[:n]) for n in range(1, len(pieces)))
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package = (
                        module
                        if path.name == "__init__.py"
                        else module.rpartition(".")[0]
                    )
                    base = importlib.util.resolve_name("." * node.level + base, package)
                pending.append(base)
                pending.extend(
                    base + "." + alias.name for alias in node.names if alias.name != "*"
                )
    if repo / "scripts/consul_broker.py" not in files:
        raise ValueError("broker_entry_missing")
    return sorted(files)


def copy_runtime(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if path.is_symlink() and not path.resolve(strict=True).is_relative_to(
            source.resolve()
        ):
            raise ValueError("runtime_symlink_escape")
    # Internal interpreter/library links become regular files before provisioning.
    shutil.copytree(source, destination, symlinks=False)
    # -S ignores PBS's bundled pip/setuptools. Ship only explicitly locked wheels.
    for site in destination.glob("lib/python*/site-packages"):
        shutil.rmtree(site)


def snapshot(paths: list[Path]) -> dict[Path, str]:
    return {path: sha256(path.read_bytes()).hexdigest() for path in paths}


def checked_copy(source: Path, destination: Path, expected: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if sha256(destination.read_bytes()).hexdigest() != expected:
        raise ValueError("bundle_source_changed")


def build(repo: Path, output: Path) -> str:
    if (
        platform.system() != "Darwin"
        or socket.gethostname().split(".")[0] != "Nuzantara"
        or platform.machine() != "arm64"
    ):
        raise PermissionError("bundle_build_pro_required")
    if os.geteuid() == 0 or output.exists():
        raise PermissionError("unprivileged_fresh_output_required")
    version = subprocess.check_output([UV, "--version"], text=True)
    if not version.startswith("uv 0.12.3 "):
        raise ValueError("uv_version_unqualified")
    controls = Path(__file__).resolve().parent
    files = source_closure(repo)
    lock = controls / "dependencies.lock"
    control_names = ("entry.py", "verify.py", "wrapper.sh", "sudoers")
    original = snapshot(files + [controls / name for name in control_names] + [lock])
    with tempfile.TemporaryDirectory(prefix="consul-bundle-") as temporary:
        work = Path(temporary)
        archive = work / "python.tar.gz"
        subprocess.run(
            [
                "/usr/bin/curl",
                "--proto",
                "=https",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "10",
                "--max-time",
                "180",
                PYTHON_URL,
                "--output",
                str(archive),
            ],
            check=True,
        )
        if sha256(archive.read_bytes()).hexdigest() != PYTHON_SHA256:
            raise ValueError("python_asset_digest_mismatch")
        unpacked = work / "unpacked"
        unpacked.mkdir()
        with tarfile.open(archive) as handle:
            handle.extractall(unpacked, filter="data")
        stage = work / "release"
        stage.mkdir()
        copy_runtime(unpacked / "python", stage / "python")
        for path in files:
            target = stage / "src" / path.relative_to(repo)
            checked_copy(path, target, original[path])
        for name in ("entry.py", "verify.py"):
            checked_copy(controls / name, stage / name, original[controls / name])
        (stage / "control").mkdir()
        for name in ("wrapper.sh", "sudoers"):
            checked_copy(
                controls / name, stage / "control" / name, original[controls / name]
            )
        pinned_lock = work / "dependencies.lock"
        checked_copy(lock, pinned_lock, original[lock])
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(work),
            "UV_CACHE_DIR": str(work / "cache"),
            "UV_NO_CONFIG": "1",
        }
        subprocess.run(
            [
                UV,
                "pip",
                "install",
                "--python",
                str(stage / "python/bin/python3"),
                "--target",
                str(stage / "site-packages"),
                "--only-binary",
                ":all:",
                "--require-hashes",
                "--no-deps",
                "-r",
                str(pinned_lock),
            ],
            check=True,
            env=env,
        )
        metadata = {
            "python_asset_url": PYTHON_URL,
            "python_asset_sha256": PYTHON_SHA256,
            "uv_version": version.strip(),
            "dependency_lock_sha256": original[lock],
            "sources": {str(p.relative_to(repo)): original[p] for p in files},
        }
        if snapshot(list(original)) != original or source_closure(repo) != files:
            raise ValueError("bundle_source_changed")
        (stage / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
        (stage / "SHA256SUMS").write_text(manifest(stage))
        # Moving before import checks catches relocation failures; nothing installs.
        shutil.move(str(stage), output)
    subprocess.run(
        [
            str(output / "python/bin/python3"),
            "-I",
            "-S",
            "-B",
            str(output / "verify.py"),
        ],
        check=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/var/empty"},
    )
    return sha256((output / "SHA256SUMS").read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            {"release_sha256": build(args.repo.resolve(), args.output.resolve())}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
