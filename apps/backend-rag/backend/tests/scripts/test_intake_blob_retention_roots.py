"""Defence-in-depth tests for the intake-blob retention managed-root set.

Regression guard for the WhatsApp-blob leak (2026-06-27): wa-mirror-media
blobs lived OUTSIDE the single managed root, so the retention job skipped them
forever and the dir grew unbounded (2.0 GB / 5.6k files). The fix turns the
single root into a managed SET that includes ~/wa-mirror-media while keeping
the same "never unlink outside a managed root" guarantee.

These tests load the script by path (it lives under scripts/, not a package)
and exercise the pure helpers only — no DB, no filesystem mutation.
"""

import importlib.util
import os
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[5] / "scripts" / "intake_blob_retention.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("intake_blob_retention", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_roots_include_intake_blobs_and_wa_mirror(monkeypatch):
    monkeypatch.delenv("INTAKE_BLOB_ROOTS", raising=False)
    monkeypatch.delenv("INTAKE_BLOB_ROOT", raising=False)
    m = _load()
    roots = m._blob_roots()
    names = {r.name for r in roots}
    assert "intake-blobs" in names
    assert "wa-mirror-media" in names


def test_wa_mirror_blob_is_now_under_a_managed_root(monkeypatch):
    monkeypatch.delenv("INTAKE_BLOB_ROOTS", raising=False)
    monkeypatch.delenv("INTAKE_BLOB_ROOT", raising=False)
    m = _load()
    roots = m._blob_roots()
    wa = Path(os.path.expanduser("~/wa-mirror-media/groups/x/abc.jpg"))
    # the leak: this used to be skipped; it must now be eligible
    assert m._is_under_any_root(wa, roots) is True


def test_drive_intake_blob_still_under_a_managed_root(monkeypatch):
    monkeypatch.delenv("INTAKE_BLOB_ROOTS", raising=False)
    monkeypatch.delenv("INTAKE_BLOB_ROOT", raising=False)
    m = _load()
    roots = m._blob_roots()
    ib = Path(os.path.expanduser("~/.nuzantara/intake-blobs/drive/1x/FILE__n.pdf"))
    assert m._is_under_any_root(ib, roots) is True


def test_arbitrary_path_is_never_under_a_managed_root(monkeypatch):
    """Innocence: a path outside every managed root must never be unlinked."""
    monkeypatch.delenv("INTAKE_BLOB_ROOTS", raising=False)
    monkeypatch.delenv("INTAKE_BLOB_ROOT", raising=False)
    m = _load()
    roots = m._blob_roots()
    for danger in ("/etc/passwd", "/", os.path.expanduser("~/.ssh/id_ed25519")):
        assert m._is_under_any_root(Path(danger), roots) is False, danger


def test_env_override_replaces_the_whole_set(monkeypatch):
    monkeypatch.setenv("INTAKE_BLOB_ROOTS", os.pathsep.join(["/tmp/a", "/tmp/b"]))
    m = _load()
    roots = {r.name for r in m._blob_roots()}
    assert roots == {"a", "b"}
    # and a wa-mirror path is NOT matched once the set is overridden
    wa = Path(os.path.expanduser("~/wa-mirror-media/x.jpg"))
    assert m._is_under_any_root(wa, m._blob_roots()) is False


def test_legacy_singular_env_still_overrides_first_root(monkeypatch):
    monkeypatch.delenv("INTAKE_BLOB_ROOTS", raising=False)
    monkeypatch.setenv("INTAKE_BLOB_ROOT", "/tmp/custom-intake")
    m = _load()
    names = {r.name for r in m._blob_roots()}
    # custom intake root replaces the default intake-blobs; wa-mirror stays
    assert "custom-intake" in names
    assert "wa-mirror-media" in names
