"""Unit tests for scripts/kbli_filiera/vault_fetch_pp28.py — no network:
common.http_get is monkeypatched wherever a fetch would otherwise fire."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402
from kbli_filiera import vault_fetch_pp28 as pp28  # noqa: E402


def _fake_result(status=200, headers=None, body=b"", error=None):
    return common.FetchResult(status=status, headers=headers or {}, body=body, error=error)


class TestTargetPath:
    def test_builds_id_dunder_filename(self, tmp_path):
        target = pp28.target_path(tmp_path, 394930, "2.1 Lampiran I.A (I.A.1-500).pdf")
        assert target.parent == tmp_path / "pp28"
        assert target.name == "394930__2.1 Lampiran I.A (I.A.1-500).pdf"


class TestFetchOneResume:
    def test_verified_prior_skips_without_network(self, tmp_path, monkeypatch):
        data = b"pdf bytes"
        filename = "2.1 Lampiran I.A (I.A.1-500).pdf"
        target = pp28.target_path(tmp_path, 394930, filename)
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        prior = {
            "id": 394930, "url": "x", "filename": filename,
            "bytes": len(data), "sha256": common.sha256_bytes(data),
            "fetched_at": "2026-07-16T00:00:00Z", "http_status": 200,
            "rel_path": target.relative_to(tmp_path).as_posix(),
        }

        called = {"n": 0}

        def _boom(*a, **k):
            called["n"] += 1
            raise AssertionError("http_get must not be called on a verified skip")

        monkeypatch.setattr(common, "http_get", _boom)
        rec = pp28.fetch_one(tmp_path, 394930, prior, sleep_s=0)
        assert rec is prior
        assert called["n"] == 0

    def test_corrupted_prior_triggers_refetch(self, tmp_path, monkeypatch):
        filename = "2.1 Lampiran I.A (I.A.1-500).pdf"
        target = pp28.target_path(tmp_path, 394930, filename)
        target.parent.mkdir(parents=True)
        target.write_bytes(b"CORRUPTED")
        prior = {
            "id": 394930, "url": "x", "filename": filename,
            "bytes": 9, "sha256": common.sha256_bytes(b"original bytes"),
            "fetched_at": "2026-07-16T00:00:00Z", "http_status": 200,
            "rel_path": target.relative_to(tmp_path).as_posix(),
        }
        new_body = b"fresh download"
        monkeypatch.setattr(
            common, "http_get",
            lambda *a, **k: _fake_result(
                200,
                {"Content-Disposition": f'attachment; filename="{filename}"',
                 "Content-Length": str(len(new_body))},
                new_body,
            ),
        )
        rec = pp28.fetch_one(tmp_path, 394930, prior, sleep_s=0)
        assert rec["sha256"] == common.sha256_bytes(new_body)
        assert target.read_bytes() == new_body


class TestFetchOneFreshFetch:
    def test_ok_fetch_writes_file_and_parses_structure(self, tmp_path, monkeypatch):
        filename = "2.6g Lampiran I.F (I.F.4501-5248).pdf"
        body = b"%PDF-1.4 fake content"
        monkeypatch.setattr(
            common, "http_get",
            lambda *a, **k: _fake_result(
                200,
                {"Content-Disposition": f'attachment; filename="{filename}"',
                 "Content-Length": str(len(body))},
                body,
            ),
        )
        rec = pp28.fetch_one(tmp_path, 394941, None, sleep_s=0)
        assert rec["http_status"] == 200
        assert rec["sha256"] == common.sha256_bytes(body)
        assert rec["fragment"] == "2.6g"
        assert rec["letter"] == "I.F"
        assert rec["range"] == "4501-5248"
        written = tmp_path / rec["rel_path"]
        assert written.read_bytes() == body

    def test_non_200_status_records_error_and_writes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common, "http_get", lambda *a, **k: _fake_result(500, {}, b"", "HTTP 500"))
        rec = pp28.fetch_one(tmp_path, 394930, None, sleep_s=0)
        assert rec["http_status"] == 500
        assert rec["error"]
        assert not (tmp_path / "pp28").exists() or not any((tmp_path / "pp28").iterdir())

    def test_content_length_mismatch_is_fail_visible(self, tmp_path, monkeypatch):
        body = b"short"
        monkeypatch.setattr(
            common, "http_get",
            lambda *a, **k: _fake_result(
                200,
                {"Content-Disposition": 'attachment; filename="x.pdf"', "Content-Length": "99999"},
                body,
            ),
        )
        rec = pp28.fetch_one(tmp_path, 394930, None, sleep_s=0)
        assert rec["rel_path"] is None
        assert "mismatch" in rec["error"]


class TestRun:
    def test_run_returns_zero_when_all_ok(self, tmp_path, monkeypatch):
        body = b"ok"
        monkeypatch.setattr(
            common, "http_get",
            lambda *a, **k: _fake_result(
                200, {"Content-Disposition": 'attachment; filename="x.pdf"'}, body,
            ),
        )
        rc = pp28.run(tmp_path, ids=(1, 2, 3), sleep_s=0)
        assert rc == 0
        records = common.read_jsonl(pp28.fetch_log_path(tmp_path))
        assert len(records) == 3

    def test_run_finishes_full_sweep_and_returns_one_on_any_failure(self, tmp_path, monkeypatch):
        calls = []

        def _fake_http(url, **k):
            calls.append(url)
            if url.endswith("2"):
                return _fake_result(500, {}, b"", "HTTP 500")
            return _fake_result(200, {"Content-Disposition": 'attachment; filename="x.pdf"'}, b"ok")

        monkeypatch.setattr(common, "http_get", _fake_http)
        rc = pp28.run(tmp_path, ids=(1, 2, 3), sleep_s=0)
        assert rc == 1
        # the sweep must not stop early at the failing id — all 3 attempted
        assert len(calls) == 3
