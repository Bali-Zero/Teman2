"""Tests for infra/claude-plugins/install_local_marketplace.py. Hermetic (no
network): vendored files are faked via a tiny local "upstream" tree + a temp
vendor.lock.json (--lock/--vendor-dir); AUTHORED files come from the real repo
tree (static, on disk, no network). W82: every check arm gets guilt + innocence.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "infra" / "claude-plugins" / "install_local_marketplace.py"
_spec = importlib.util.spec_from_file_location("install_local_marketplace", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
ilm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ilm)

MARKETPLACE_SRC = _MODULE_PATH.parent / "local-marketplace"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_fake_vendor(tmp_path: Path) -> tuple[Path, Path]:
    vendor_dir = tmp_path / "vendor"
    plugin_dir = vendor_dir / "fakeplugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "a.txt").write_bytes(b"hello fake plugin\n")
    (plugin_dir / "sub").mkdir()
    (plugin_dir / "sub" / "b.txt").write_bytes(b"nested\n")

    lock = {
        "plugins": {
            "fakeplugin": {
                "upstream_url": "https://example.invalid/fakeplugin.git",
                "upstream_commit": "0" * 40,
                "files": {"a.txt": _sha(b"hello fake plugin\n"), "sub/b.txt": _sha(b"nested\n")},
            }
        }
    }
    lock_path = tmp_path / "vendor.lock.json"
    lock_path.write_text(json.dumps(lock))
    return vendor_dir, lock_path


def install(tmp_path: Path, vendor_dir: Path, lock_path: Path, machine: str = "m5") -> tuple[int, Path]:
    home = tmp_path / "home"
    rc = ilm.main(["--home", str(home), "--vendor-dir", str(vendor_dir), "--lock", str(lock_path), "--machine", machine])
    return rc, home


def check(home: Path, lock_path: Path, machine: str = "m5") -> int:
    return ilm.main(["--check", "--home", str(home), "--lock", str(lock_path), "--machine", machine])


# ---------------------------------------------------------------- innocence


def test_exact_tree_checks_clean(tmp_path: Path) -> None:
    vendor_dir, lock_path = make_fake_vendor(tmp_path)
    rc, home = install(tmp_path, vendor_dir, lock_path)
    assert rc == 0
    assert check(home, lock_path) == 0


# ---------------------------------------------------------------- guilt


def test_modified_vendored_byte_is_drift(tmp_path: Path) -> None:
    vendor_dir, lock_path = make_fake_vendor(tmp_path)
    rc, home = install(tmp_path, vendor_dir, lock_path)
    assert rc == 0
    live = home / ".claude" / "local-marketplace" / "plugins" / "fakeplugin" / "a.txt"
    live.write_bytes(b"tampered\n")
    assert check(home, lock_path) == 1


def test_extra_file_is_drift(tmp_path: Path) -> None:
    vendor_dir, lock_path = make_fake_vendor(tmp_path)
    rc, home = install(tmp_path, vendor_dir, lock_path)
    assert rc == 0
    extra = home / ".claude" / "local-marketplace" / "plugins" / "fakeplugin" / "unexpected.txt"
    extra.write_bytes(b"not declared anywhere\n")
    assert check(home, lock_path) == 1


def test_missing_file_is_drift(tmp_path: Path) -> None:
    vendor_dir, lock_path = make_fake_vendor(tmp_path)
    rc, home = install(tmp_path, vendor_dir, lock_path)
    assert rc == 0
    (home / ".claude" / "local-marketplace" / "plugins" / "fakeplugin" / "sub" / "b.txt").unlink()
    assert check(home, lock_path) == 1


def test_wrong_machine_fallback_path_is_drift(tmp_path: Path) -> None:
    vendor_dir, lock_path = make_fake_vendor(tmp_path)
    rc, home = install(tmp_path, vendor_dir, lock_path, machine="m5")
    assert rc == 0
    # Same tree, checked as if it were pro's — fallbackPath differs, byte mismatch.
    assert check(home, lock_path, machine="pro") == 1


# ---------------------------------------------------------------- install + backup


def test_reinstall_backs_up_previous_and_checks_clean(tmp_path: Path) -> None:
    vendor_dir, lock_path = make_fake_vendor(tmp_path)
    rc, home = install(tmp_path, vendor_dir, lock_path)
    assert rc == 0
    live_root = home / ".claude" / "local-marketplace"
    (live_root / "plugins" / "fakeplugin" / "a.txt").write_bytes(b"will be backed up\n")

    rc2, _ = install(tmp_path, vendor_dir, lock_path)
    assert rc2 == 0

    backups = list((home / ".claude").glob("local-marketplace.bak-*"))
    assert len(backups) == 1, f"expected exactly one backup dir, found {backups}"
    assert (backups[0] / "plugins" / "fakeplugin" / "a.txt").read_bytes() == b"will be backed up\n"
    assert check(home, lock_path) == 0


def test_vendor_hash_mismatch_aborts_before_touching_live(tmp_path: Path) -> None:
    vendor_dir, lock_path = make_fake_vendor(tmp_path)
    (vendor_dir / "fakeplugin" / "a.txt").write_bytes(b"corrupted at the source\n")
    rc, home = install(tmp_path, vendor_dir, lock_path)
    assert rc == 1
    assert not (home / ".claude" / "local-marketplace").exists()


# ---------------------------------------------------------------- static, real-repo


def test_real_lock_hashes_are_64_hex() -> None:
    lock = json.loads((MARKETPLACE_SRC / "vendor.lock.json").read_text())
    hex64 = re.compile(r"^[0-9a-f]{64}$")
    checked = 0
    for plugin, meta in lock["plugins"].items():
        assert re.match(r"^[0-9a-f]{40}$", meta["upstream_commit"]), plugin
        for relpath, digest in meta["files"].items():
            assert hex64.match(digest), f"{plugin}/{relpath}: {digest!r}"
            checked += 1
    assert checked > 0


def test_real_machine_files_differ_only_in_fallback_path() -> None:
    texts = {m: (MARKETPLACE_SRC / "machines" / m / "typescript-lsp.plugin.json").read_text() for m in ("m5", "pro", "mini")}

    def strip_fallback(s: str) -> str:
        return re.sub(r'"fallbackPath":\s*"[^"]*"', '"fallbackPath": ""', s)

    stripped = {m: strip_fallback(t) for m, t in texts.items()}
    assert stripped["m5"] == stripped["pro"] == stripped["mini"]
    assert len(set(texts.values())) == 3  # else the test above is vacuous


def test_real_marketplace_json_has_no_lsp_servers() -> None:
    marketplace = json.loads((MARKETPLACE_SRC / ".claude-plugin" / "marketplace.json").read_text())
    for plugin in marketplace["plugins"]:
        assert "lspServers" not in plugin, plugin["name"]
