"""Unit tests for scripts/kbli_filiera/vault_fetch_oss.py — no network:
common.http_get is monkeypatched wherever a fetch would otherwise fire."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402
from kbli_filiera import vault_fetch_oss as oss  # noqa: E402


def _fake_result(status=200, headers=None, body=b"", error=None):
    return common.FetchResult(status=status, headers=headers or {}, body=body, error=error)


class TestEndpointUrl:
    def test_detail_has_no_prefix(self):
        assert oss.endpoint_url("detail", "abc-uuid") == "https://gw.oss.go.id/v2/portal/kbli/abc-uuid"

    def test_ruang_lingkup_prefix(self):
        assert oss.endpoint_url("ruang_lingkup", "abc-uuid") == (
            "https://gw.oss.go.id/v2/portal/kbli/ruang-lingkup/abc-uuid"
        )

    def test_relasi_and_umku_prefixes(self):
        assert oss.endpoint_url("relasi", "u") == "https://gw.oss.go.id/v2/portal/kbli/relasi/u"
        assert oss.endpoint_url("umku", "u") == "https://gw.oss.go.id/v2/portal/kbli/umku/u"


class TestLoadCodeUuidMap:
    def test_filters_to_5_digit_codes_only(self, tmp_path):
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({
            "_meta": {},
            "data": [
                {"kode": "47111", "uuid": "u1", "digits": 5},
                {"kode": "471", "uuid": "u2", "digits": 3},
                {"kode": "68112", "uuid": "u3", "digits": 5},
            ],
        }), encoding="utf-8")
        codes = oss.load_code_uuid_map(gt)
        assert codes == [("47111", "u1"), ("68112", "u3")]


class TestBuildAbsenceRecord:
    def test_shape_matches_spec(self):
        rec = oss.build_absence_record("47111", "ruang_lingkup", "http://x", "uuid-1", 404, "2026-07-16T00:00:00Z")
        assert rec == {
            "code": "47111",
            "endpoint": "ruang_lingkup",
            "url": "http://x",
            "uuid": "uuid-1",
            "status": 404,
            "recorded_as": "absent",
            "fetched_at": "2026-07-16T00:00:00Z",
        }


class TestFetchEndpoint:
    def test_200_writes_data_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common, "http_get", lambda *a, **k: _fake_result(200, {}, b'{"ok": true}'))
        rec = oss.fetch_endpoint(tmp_path, "47111", "uuid-1", "detail", None)
        assert rec["_kind"] == "data"
        assert rec["http_status"] == 200
        target = tmp_path / rec["rel_path"]
        assert target.read_bytes() == b'{"ok": true}'

    def test_404_returns_absence_kind_never_writes_a_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common, "http_get", lambda *a, **k: _fake_result(404, {}, b""))
        rec = oss.fetch_endpoint(tmp_path, "47111", "uuid-1", "ruang_lingkup", None)
        assert rec["_kind"] == "absence"
        assert rec["status"] == 404
        assert rec["recorded_as"] == "absent"
        data_file = oss.data_path(tmp_path, "47111", "ruang_lingkup")
        assert not data_file.exists()

    def test_non_200_non_404_records_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common, "http_get", lambda *a, **k: _fake_result(503, {}, b"", "HTTP 503"))
        rec = oss.fetch_endpoint(tmp_path, "47111", "uuid-1", "umku", None)
        assert rec["_kind"] == "data"
        assert rec["http_status"] == 503
        assert rec["error"]
        assert rec["rel_path"] is None

    def test_verified_prior_skips_without_network(self, tmp_path, monkeypatch):
        data = b'{"cached": true}'
        target = oss.data_path(tmp_path, "47111", "detail")
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        prior = {
            "code": "47111", "endpoint": "detail", "url": "x", "uuid": "uuid-1",
            "bytes": len(data), "sha256": common.sha256_bytes(data),
            "fetched_at": "2026-07-16T00:00:00Z", "http_status": 200,
            "rel_path": target.relative_to(tmp_path).as_posix(),
        }

        def _boom(*a, **k):
            raise AssertionError("http_get must not be called on a verified skip")

        monkeypatch.setattr(common, "http_get", _boom)
        result = oss.fetch_endpoint(tmp_path, "47111", "uuid-1", "detail", prior)
        assert result is None


class TestRun:
    def test_only_filters_to_requested_codes(self, tmp_path, monkeypatch):
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({
            "_meta": {},
            "data": [
                {"kode": "47111", "uuid": "u1", "digits": 5},
                {"kode": "68112", "uuid": "u2", "digits": 5},
                {"kode": "99999", "uuid": "u3", "digits": 5},
            ],
        }), encoding="utf-8")
        seen_codes = set()

        def _fake_http(url, **k):
            seen_codes.add(url.rsplit("/", 1)[-1])
            return _fake_result(200, {}, b"{}")

        monkeypatch.setattr(common, "http_get", _fake_http)
        rc = oss.run(tmp_path, gt, only={"47111"}, rate_s=0)
        assert rc == 0
        assert seen_codes == {"u1"}  # only the requested code's uuid was fetched

    def test_404_endpoints_do_not_cause_a_nonzero_exit(self, tmp_path, monkeypatch):
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({
            "_meta": {}, "data": [{"kode": "47111", "uuid": "u1", "digits": 5}],
        }), encoding="utf-8")
        monkeypatch.setattr(common, "http_get", lambda *a, **k: _fake_result(404, {}, b""))
        rc = oss.run(tmp_path, gt, rate_s=0)
        assert rc == 0
        absences = common.read_jsonl(oss.absences_path(tmp_path))
        assert len(absences) == 4  # detail + ruang_lingkup + relasi + umku, all absent
        assert all(a["recorded_as"] == "absent" for a in absences)

    def test_real_failure_causes_nonzero_exit(self, tmp_path, monkeypatch):
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({
            "_meta": {}, "data": [{"kode": "47111", "uuid": "u1", "digits": 5}],
        }), encoding="utf-8")
        monkeypatch.setattr(common, "http_get", lambda *a, **k: _fake_result(500, {}, b"", "HTTP 500"))
        rc = oss.run(tmp_path, gt, rate_s=0)
        assert rc == 1
