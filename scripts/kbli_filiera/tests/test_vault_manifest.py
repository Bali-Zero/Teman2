"""Unit tests for scripts/kbli_filiera/vault_manifest.py — pure filesystem
walk + hashing, no network."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402
from kbli_filiera import vault_manifest as manifest  # noqa: E402


def _make_tree(root):
    (root / "pp28").mkdir(parents=True)
    (root / "pp28" / "394930__a.pdf").write_bytes(b"pdf-a")
    (root / "pp28" / "394931__b.pdf").write_bytes(b"pdf-b")
    common.append_jsonl(root / "pp28" / "fetch-log.jsonl", {
        "id": 394930, "url": "https://example/394930", "rel_path": "pp28/394930__a.pdf",
        "http_status": 200, "fetched_at": "2026-07-16T00:00:00Z",
    })
    common.append_jsonl(root / "pp28" / "fetch-log.jsonl", {
        "id": 394931, "url": "https://example/394931", "rel_path": "pp28/394931__b.pdf",
        "http_status": 200, "fetched_at": "2026-07-16T00:01:00Z",
    })
    (root / "oss" / "47111").mkdir(parents=True)
    (root / "oss" / "47111" / "detail.json").write_bytes(b'{"detail": true}')
    common.append_jsonl(root / "oss" / "fetch-log.jsonl", {
        "code": "47111", "endpoint": "detail", "url": "https://oss/47111",
        "rel_path": "oss/47111/detail.json", "http_status": 200,
        "fetched_at": "2026-07-16T02:00:00Z",
    })
    common.append_jsonl(root / "oss" / "absences.jsonl", {
        "code": "47111", "endpoint": "ruang_lingkup", "status": 404, "recorded_as": "absent",
    })


class TestBuildManifest:
    def test_entries_sorted_by_rel_path(self, tmp_path):
        _make_tree(tmp_path)
        entries = manifest.build_manifest(tmp_path)
        rel_paths = [e["rel_path"] for e in entries]
        assert rel_paths == sorted(rel_paths)

    def test_log_files_excluded_from_manifest(self, tmp_path):
        _make_tree(tmp_path)
        entries = manifest.build_manifest(tmp_path)
        names = {e["rel_path"] for e in entries}
        assert "pp28/fetch-log.jsonl" not in names
        assert "oss/fetch-log.jsonl" not in names
        assert "oss/absences.jsonl" not in names

    def test_absences_never_produce_manifest_entries(self, tmp_path):
        _make_tree(tmp_path)
        entries = manifest.build_manifest(tmp_path)
        # ruang_lingkup was recorded absent (404) -> no file, no entry
        assert not any("ruang_lingkup" in e["rel_path"] for e in entries)

    def test_provenance_merged_by_exact_rel_path(self, tmp_path):
        _make_tree(tmp_path)
        entries = {e["rel_path"]: e for e in manifest.build_manifest(tmp_path)}
        pp28_a = entries["pp28/394930__a.pdf"]
        assert pp28_a["source_url"] == "https://example/394930"
        assert pp28_a["fetched_at"] == "2026-07-16T00:00:00Z"
        assert pp28_a["sha256"] == common.sha256_bytes(b"pdf-a")
        assert pp28_a["bytes"] == len(b"pdf-a")

    def test_file_with_no_provenance_still_included(self, tmp_path):
        tmp_path.joinpath("orphan.txt").write_bytes(b"no log entry for this")
        entries = manifest.build_manifest(tmp_path)
        orphan = next(e for e in entries if e["rel_path"] == "orphan.txt")
        assert "source_url" not in orphan
        assert "fetched_at" not in orphan
        assert orphan["sha256"] == common.sha256_bytes(b"no log entry for this")


class TestDeterminism:
    def test_same_tree_produces_byte_identical_output(self, tmp_path):
        _make_tree(tmp_path)
        first = manifest.render_manifest(manifest.build_manifest(tmp_path))
        second = manifest.render_manifest(manifest.build_manifest(tmp_path))
        assert first == second

    def test_rebuild_after_touching_provenance_order_is_still_deterministic(self, tmp_path):
        # Re-append the SAME log lines in a different insertion order for a
        # third file — output must not depend on jsonl iteration order.
        _make_tree(tmp_path)
        (tmp_path / "oss" / "68112").mkdir(parents=True)
        (tmp_path / "oss" / "68112" / "detail.json").write_bytes(b'{"x": 1}')
        common.append_jsonl(tmp_path / "oss" / "fetch-log.jsonl", {
            "code": "68112", "endpoint": "detail", "url": "https://oss/68112",
            "rel_path": "oss/68112/detail.json", "http_status": 200,
            "fetched_at": "2026-07-16T03:00:00Z",
        })
        run_a = manifest.render_manifest(manifest.build_manifest(tmp_path))
        run_b = manifest.render_manifest(manifest.build_manifest(tmp_path))
        assert run_a == run_b
