"""Unit tests for scripts/kbli_filiera/vault_to_risk_jsonl.py — pure
filesystem read, no network."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402
from kbli_filiera import vault_to_risk_jsonl as adapter  # noqa: E402


def _make_ground_truth(tmp_path, codes):
    gt = tmp_path / "gt.json"
    gt.write_text(json.dumps({
        "_meta": {},
        "data": [{"kode": c, "uuid": f"u-{c}", "digits": 5} for c in codes]
                + [{"kode": "123", "uuid": "u-not-5", "digits": 3}],
    }), encoding="utf-8")
    return gt


def _write_data(vault_root, code, payload):
    d = vault_root / "oss" / code
    d.mkdir(parents=True, exist_ok=True)
    (d / "ruang_lingkup.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_absence(vault_root, code, endpoint="ruang_lingkup", status=404, recorded_as="absent"):
    common.append_jsonl(vault_root / "oss" / "absences.jsonl", {
        "code": code, "endpoint": endpoint, "status": status, "recorded_as": recorded_as,
    })


class TestLoadFiveDigitCodes:
    def test_filters_and_sorts_ascending(self, tmp_path):
        gt = _make_ground_truth(tmp_path, ["68112", "47111"])
        pairs = adapter.load_five_digit_codes(gt)
        assert pairs == [("47111", "u-47111"), ("68112", "u-68112")]

    def test_non_5digit_kode_raises_invalid_code(self, tmp_path):
        """codex round 1, F5: a kode like "../escape" that carries digits==5
        in its metadata but is NOT actually a 5-digit string must be
        rejected before it is ever used to build a filesystem path."""
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({
            "_meta": {},
            "data": [{"kode": "../escape", "uuid": "u-evil", "digits": 5}],
        }), encoding="utf-8")
        with pytest.raises(adapter.InvalidCode) as exc_info:
            adapter.load_five_digit_codes(gt)
        assert "../escape" in str(exc_info.value)


class TestBuildRecord:
    def test_200_reads_raw_data_file(self, tmp_path):
        _write_data(tmp_path, "47111", {"success": True, "data": [1, 2]})
        rec = adapter.build_record(tmp_path, "47111", "u-47111")
        assert rec == {"kode": "47111", "uuid": "u-47111", "status": 200,
                        "data": {"success": True, "data": [1, 2]}}

    def test_404_shape_when_absence_recorded_and_no_data_file(self, tmp_path):
        _write_absence(tmp_path, "68112")
        rec = adapter.build_record(tmp_path, "68112", "u-68112")
        assert rec == {"kode": "68112", "uuid": "u-68112", "status": 404,
                        "data": {"success": False, "code": 404}}

    def test_data_file_wins_over_a_stray_absence_record(self, tmp_path):
        _write_data(tmp_path, "99999", {"success": True, "data": []})
        _write_absence(tmp_path, "99999")
        rec = adapter.build_record(tmp_path, "99999", "u-99999")
        assert rec["status"] == 200

    def test_neither_data_nor_absence_raises_missing_evidence(self, tmp_path):
        with pytest.raises(adapter.MissingEvidence):
            adapter.build_record(tmp_path, "00001", "u-00001")

    def test_absence_for_a_different_endpoint_does_not_count(self, tmp_path):
        _write_absence(tmp_path, "55555", endpoint="umku")
        with pytest.raises(adapter.MissingEvidence):
            adapter.build_record(tmp_path, "55555", "u-55555")

    def test_status_500_record_is_not_an_absence(self, tmp_path):
        """codex round 1, F4: has_absence must require status == 404 (and
        recorded_as == "absent") — a transient-error probe is not a
        confirmed no-scope signal."""
        _write_absence(tmp_path, "77777", status=500, recorded_as="error")
        with pytest.raises(adapter.MissingEvidence):
            adapter.build_record(tmp_path, "77777", "u-77777")
        assert adapter.has_absence(tmp_path, "77777") is False


class TestMain:
    def _vault(self, tmp_path):
        vault_root = tmp_path / "vault"
        _write_data(vault_root, "10215", {"success": True, "data": [{"a": 1}]})
        _write_data(vault_root, "47111", {"success": True, "data": []})
        _write_absence(vault_root, "56101")
        gt = _make_ground_truth(tmp_path, ["56101", "10215", "47111"])
        return vault_root, gt

    def test_output_is_ascending_kode_order(self, tmp_path):
        vault_root, gt = self._vault(tmp_path)
        out = tmp_path / "out.jsonl"
        rc = adapter.main(["--vault-root", str(vault_root), "--ground-truth", str(gt), "--out", str(out)])
        assert rc == 0
        lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        assert [r["kode"] for r in lines] == ["10215", "47111", "56101"]
        assert lines[2]["status"] == 404

    def test_deterministic_byte_identical_on_rerun(self, tmp_path):
        vault_root, gt = self._vault(tmp_path)
        out1 = tmp_path / "out1.jsonl"
        out2 = tmp_path / "out2.jsonl"
        adapter.main(["--vault-root", str(vault_root), "--ground-truth", str(gt), "--out", str(out1)])
        adapter.main(["--vault-root", str(vault_root), "--ground-truth", str(gt), "--out", str(out2)])
        assert out1.read_bytes() == out2.read_bytes()

    def test_missing_evidence_exits_2_and_names_the_code(self, tmp_path, capsys):
        vault_root = tmp_path / "vault"
        vault_root.mkdir()
        gt = _make_ground_truth(tmp_path, ["00001"])
        out = tmp_path / "out.jsonl"
        rc = adapter.main(["--vault-root", str(vault_root), "--ground-truth", str(gt), "--out", str(out)])
        assert rc == 2
        assert "00001" in capsys.readouterr().err
        assert not out.exists()

    def test_invalid_kode_exits_2_and_names_the_value(self, tmp_path, capsys):
        """codex round 1, F5."""
        vault_root = tmp_path / "vault"
        vault_root.mkdir()
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({
            "_meta": {}, "data": [{"kode": "../escape", "uuid": "u-evil", "digits": 5}],
        }), encoding="utf-8")
        out = tmp_path / "out.jsonl"
        rc = adapter.main(["--vault-root", str(vault_root), "--ground-truth", str(gt), "--out", str(out)])
        assert rc == 2
        assert "../escape" in capsys.readouterr().err
        assert not out.exists()
