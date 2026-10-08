"""kbli_dataset_anchor: the D2 anchor must equal the canonical dataset's hash."""
import hashlib
import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)

_DATA = json.dumps({"data": [{"kode": "1"}, {"kode": "2"}]}).encode()
_SHA = hashlib.sha256(_DATA).hexdigest()


def _tree(tmp_path: Path, anchor_sha: str, records: int = 2) -> Path:
    (tmp_path / "data/source_documents").mkdir(parents=True)
    (tmp_path / "data/source_documents/KBLI_2025_FINAL_CLEAN.json").write_bytes(_DATA)
    (tmp_path / "apps/kbli-navigator-macos/Resources").mkdir(parents=True)
    (tmp_path / "apps/kbli-navigator-macos/Resources/DATASET_MANIFEST.json").write_text(
        json.dumps({"sha256": anchor_sha, "records": records}))
    return tmp_path


def _run(root: Path):
    # tmp_path is not a git repo: git show fails, so the LOCAL fallback is what is measured.
    return prop.probe_kbli_dataset_anchor(root, {"no_fetch": True}, 10)


def test_innocence_matching_anchor_is_reconciled(tmp_path):
    verdict, n, ev = _run(_tree(tmp_path, _SHA))
    assert (verdict, n) == (prop.RECONCILED, 0)
    assert _SHA[:12] in ev[0]
    assert "LOCAL" in ev[0]


def test_guilt_differing_anchor_is_diverged_naming_both_shas(tmp_path):
    bad = ("0" if _SHA[0] != "0" else "1") + _SHA[1:]
    verdict, n, ev = _run(_tree(tmp_path, bad))
    text = " ".join(ev)
    assert verdict == prop.DIVERGED and n >= 1
    assert bad[:12] in text and _SHA[:12] in text
    assert "DATASET_MANIFEST.json" in text and "exit 4" in text and "re-anchor deliberately" in text
    assert "refreshes and re-stamps" not in text


def test_guilt_record_count_mismatch(tmp_path):
    verdict, _, ev = _run(_tree(tmp_path, _SHA, records=3))
    assert verdict == prop.DIVERGED
    assert "records 3 != canonical records 2" in " ".join(ev)


def test_unreadable_manifest_is_unprobeable(tmp_path):
    verdict, _, _ = _run(tmp_path)
    assert verdict == prop.UNPROBEABLE


def test_registry_fix_hint_is_the_same_true_remedy():
    entry = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "kbli_dataset_anchor")
    assert "DATASET_MANIFEST.json" in entry["fix_hint"] and "exit 4" in entry["fix_hint"]
    assert "refreshes and re-stamps" not in entry["fix_hint"]


def test_manifest_is_read_from_origin_main_not_the_checkout(tmp_path):
    import subprocess

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    _tree(tmp_path, _SHA)
    git("add", "-A")
    git("commit", "-qm", "anchor")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    # a never-pulled checkout: the working-tree manifest is stale, origin/main's is right
    (tmp_path / "apps/kbli-navigator-macos/Resources/DATASET_MANIFEST.json").write_text(
        json.dumps({"sha256": "0" * 64, "records": 2}))
    verdict, _, ev = _run(tmp_path)
    assert verdict == prop.RECONCILED
    assert "LOCAL" not in ev[0] and "origin/main:apps/kbli-navigator-macos" in ev[0]
