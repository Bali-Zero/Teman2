#!/usr/bin/env python3
"""Install/verify the `nuzantara-local` plugin marketplace (infra/claude-plugins/
local-marketplace/) into `<home>/.claude/local-marketplace`.

AUTHORED files (marketplace.json, README.md, superpowers/caveman plugin.json,
machines/<m>/typescript-lsp.plugin.json) are compared BYTE-EQUAL to the repo.
VENDORED files (everything else under plugins/superpowers/, plugins/caveman/)
are compared by sha256 against vendor.lock.json, which pins the upstream
commit each hash came from.

--check: read-only, no network, live vs expected. --machine auto|m5|pro|mini
(auto = scripts/lint_home_fork.machine_label). Default: install — fetches/
copies vendored files, verifies against the lock, backs up the existing live
dir, swaps in. Never touches ~/.claude/settings.json or plugin enabled-state.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
MARKETPLACE_SRC = SCRIPT_DIR / "local-marketplace"
DEFAULT_LOCK = MARKETPLACE_SRC / "vendor.lock.json"

# (repo path relative to MARKETPLACE_SRC, live path relative to local-marketplace/)
AUTHORED_FILES = [
    (".claude-plugin/marketplace.json", ".claude-plugin/marketplace.json"),
    ("README.md", "README.md"),
    ("plugins/superpowers/.claude-plugin/plugin.json", "plugins/superpowers/.claude-plugin/plugin.json"),
    ("plugins/caveman/.claude-plugin/plugin.json", "plugins/caveman/.claude-plugin/plugin.json"),
]


def typescript_lsp_authored(machine: str) -> tuple[str, str]:
    return (f"machines/{machine}/typescript-lsp.plugin.json", "plugins/typescript-lsp/.claude-plugin/plugin.json")


def machine_label() -> str:
    """Delegates to scripts/lint_home_fork.machine_label — this installer lives
    in the same repo, so there is no standalone-script case to replicate for."""
    repo_root = SCRIPT_DIR.parent.parent
    if ".worktrees" in repo_root.parts:
        repo_root = Path(*repo_root.parts[: repo_root.parts.index(".worktrees")])
    sys.path.insert(0, str(repo_root / "scripts"))
    from lint_home_fork import machine_label as _ml  # type: ignore

    return _ml()


def sha256_file(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def do_check(home: Path, machine: str, lock: dict) -> int:
    live_root = home / ".claude" / "local-marketplace"
    drift: list[str] = []
    expected_live_paths: set[str] = set()

    authored = list(AUTHORED_FILES) + [typescript_lsp_authored(machine)]
    for repo_rel, live_rel in authored:
        expected_live_paths.add(live_rel)
        repo_path = MARKETPLACE_SRC / repo_rel
        live_path = live_root / live_rel
        if not repo_path.exists():
            drift.append(f"MISSING-IN-REPO {repo_rel}")
            continue
        if not live_path.exists():
            drift.append(f"MISSING-LIVE {live_rel}")
            continue
        if repo_path.read_bytes() != live_path.read_bytes():
            drift.append(f"DRIFT {live_rel} (byte mismatch vs repo {repo_rel})")

    for plugin, meta in lock["plugins"].items():
        for relpath, expected_hash in meta["files"].items():
            live_rel = f"plugins/{plugin}/{relpath}"
            expected_live_paths.add(live_rel)
            live_path = live_root / live_rel
            if not live_path.exists():
                drift.append(f"MISSING-LIVE {live_rel}")
                continue
            actual_hash = sha256_file(live_path)
            if actual_hash != expected_hash:
                drift.append(f"DRIFT {live_rel} (sha256 {actual_hash} != lock {expected_hash})")

    if live_root.exists():
        for p in sorted(live_root.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(live_root).as_posix()
            if rel not in expected_live_paths:
                drift.append(f"EXTRA {rel}")
    else:
        drift.append(f"MISSING-LIVE-DIR {live_root}")

    for line in drift:
        print(line)
    if drift:
        print(f"FAIL: {len(drift)} drift line(s) — {live_root} vs {MARKETPLACE_SRC} (machine={machine})")
        return 1
    print(f"OK: {live_root} matches {MARKETPLACE_SRC} exactly ({len(expected_live_paths)} files, machine={machine})")
    return 0


def _fetch_upstream_plugin(tmp_root: Path, plugin: str, meta: dict) -> Path:
    checkout = tmp_root / f"_upstream_{plugin}"
    checkout.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(checkout), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(checkout), "fetch", "--depth", "1", meta["upstream_url"], meta["upstream_commit"]], check=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "-q", "FETCH_HEAD"], check=True)
    return checkout


def _register_claude_marketplace(live_root: Path) -> None:
    for verb, arg in (("update", "nuzantara-local"), ("add", str(live_root))):
        result = subprocess.run(["claude", "plugin", "marketplace", verb, arg], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout.strip() or f"marketplace {verb}: ok")
            return
        print(f"marketplace {verb} failed ({result.returncode}): {result.stderr.strip()}", file=sys.stderr)
    print("WARNING: could not register the marketplace via update or add", file=sys.stderr)


def do_install(home: Path, machine: str, lock: dict, vendor_dir: Optional[Path]) -> int:
    if machine not in ("m5", "pro", "mini"):
        print(f"FAIL: unknown machine '{machine}' — pass --machine m5|pro|mini", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="local-marketplace-install-") as tmp:
        tmp_root = Path(tmp)
        new_tree = tmp_root / "local-marketplace"
        new_tree.mkdir()

        authored = list(AUTHORED_FILES) + [typescript_lsp_authored(machine)]
        for repo_rel, live_rel in authored:
            dst = new_tree / live_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(MARKETPLACE_SRC / repo_rel, dst)

        for plugin, meta in lock["plugins"].items():
            src_root = (vendor_dir / plugin) if vendor_dir is not None else _fetch_upstream_plugin(tmp_root, plugin, meta)
            for relpath, expected_hash in meta["files"].items():
                src = src_root / relpath
                if not src.exists():
                    print(f"FAIL: vendored source missing: {plugin}/{relpath} (looked in {src_root})", file=sys.stderr)
                    return 1
                actual_hash = sha256_file(src)
                if actual_hash != expected_hash:
                    print(f"FAIL: vendored hash mismatch {plugin}/{relpath}: got {actual_hash}, lock says {expected_hash}", file=sys.stderr)
                    return 1
                dst = new_tree / "plugins" / plugin / relpath
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        live_root = home / ".claude" / "local-marketplace"
        live_root.parent.mkdir(parents=True, exist_ok=True)
        if live_root.exists():
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = home / ".claude" / f"local-marketplace.bak-{ts}"
            shutil.move(str(live_root), str(backup))
            print(f"backed up existing {live_root} -> {backup}")
        shutil.move(str(new_tree), str(live_root))
        print(f"installed {live_root} (machine={machine})")

    if home == Path.home():
        _register_claude_marketplace(live_root)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--machine", choices=["auto", "m5", "pro", "mini"], default="auto")
    parser.add_argument("--vendor-dir", default=None, help="dir holding <plugin>/ upstream checkouts (offline/tests)")
    parser.add_argument("--home", default=None, help="home dir to operate on (default: real $HOME)")
    parser.add_argument("--lock", default=None, help="path to vendor.lock.json (default: local-marketplace/vendor.lock.json)")
    parser.add_argument("--check", action="store_true", help="read-only: report drift, exit 1 if any")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    home = Path(args.home).expanduser() if args.home else Path.home()
    lock = json.loads((Path(args.lock) if args.lock else DEFAULT_LOCK).read_text())
    machine = machine_label() if args.machine == "auto" else args.machine

    if args.check:
        return do_check(home, machine, lock)
    return do_install(home, machine, lock, Path(args.vendor_dir) if args.vendor_dir else None)


if __name__ == "__main__":
    sys.exit(main())
