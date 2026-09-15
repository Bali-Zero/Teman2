"""Tests for cure_pr2b_source_rows_93114_43110.py (SAETTA-20260915 W-H PR-2b).

Fabricated in-memory records pin plan()'s logic: guilt (a malformed
precondition refuses) and innocence (the real shape produces the spec's
patch). TestRealCatalogue then checks the actually-applied canonical.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import cure_pr2b_source_rows_93114_43110 as cure  # noqa: E402
import _hardened_cure_io as H  # noqa: E402

SPEC = json.loads(cure.SPEC_PATH.read_text(encoding="utf-8"))
GOLF_ROW = {"skala_usaha": ["Menengah", "Besar"], "kategori_risiko": "Tinggi"}
LEGACY_3 = [
    {"skala_usaha": ["Mikro", "Kecil", "Menengah"], "parameter": "BUJKN"},
    {"skala_usaha": ["Besar"], "parameter": "BUJK dan Kantor Perwakilan BUJKA"},
    {"skala_usaha": ["Mikro"], "perizinan": "NIB dan Sertifikat Standar 1", "parameter": "Usaha Orang Perseorangan"},
]


def _rec93114(**overrides) -> dict:
    rec = {
        "kode_kbli_2025": "93114",
        "per_skala": [{"skala_usaha": ["Mikro", "Kecil", "Menengah"], "kategori_risiko": "Menengah Rendah"}],
        "per_skala_disputed_pp28_collision": [copy.deepcopy(GOLF_ROW)],
        "_data_note": "stale",
        "l4_bali": {"status": "APERTO_BALI_RISCHIO_ALTO", "blocked": False, "review_basis": "x"},
    }
    rec.update(overrides)
    return rec


def _rec43110(legacy=None, **overrides) -> dict:
    rec = {
        "kode_kbli_2025": "43110",
        "per_skala": [{"skala_usaha": ["Mikro"], "kategori_risiko": "Menengah Rendah"}],
        "per_skala_legacy": legacy if legacy is not None else copy.deepcopy(LEGACY_3),
        "l4_bali": {"status": "BLOCCATO_DIPENDE_SCOPE", "blocked": True, "verdict": "NO_BESAR", "rule": "x", "review_basis": "y"},
    }
    rec.update(overrides)
    return rec


class TestGuilt:
    def test_missing_disputed_key_raises(self):
        rec = _rec93114()
        del rec["per_skala_disputed_pp28_collision"]
        with pytest.raises(H.CureError, match="nothing to restore"):
            cure.plan([rec, _rec43110()], SPEC)

    def test_legacy_wrong_count_raises(self):
        rec = _rec43110(legacy=[copy.deepcopy(LEGACY_3[0])])
        with pytest.raises(H.CureError, match="exactly 3 rows"):
            cure.plan([_rec93114(), rec], SPEC)

    def test_code_missing_raises(self):
        with pytest.raises(H.CureError, match="93114: not in canonical"):
            cure.plan([_rec43110()], SPEC)


class TestInnocence:
    def test_93114_gains_golf_row_and_drops_stale_keys(self):
        items = cure.plan([_rec93114(), _rec43110()], SPEC)
        item = items["93114"]
        assert len(item["per_skala"]) == 2
        assert item["per_skala"][1] == GOLF_ROW
        assert set(item["drop_keys"]) == {"per_skala_disputed_pp28_collision", "_data_note"}

    def test_43110_keeps_all_three_legacy_rows(self):
        items = cure.plan([_rec93114(), _rec43110()], SPEC)
        assert len(items["43110"]["per_skala"]) == 3

    def test_43110_row3_perizinan_artifact_is_fixed(self):
        items = cure.plan([_rec93114(), _rec43110()], SPEC)
        assert items["43110"]["per_skala"][2]["perizinan"] == "NIB dan Sertifikat Standar"

    def test_apply_item_flips_43110_blocked_and_drops_no_besar_vocabulary(self):
        rec = _rec43110()
        items = cure.plan([_rec93114(), rec], SPEC)
        cure.apply_item(rec, items["43110"])
        assert rec["l4_bali"]["blocked"] is False
        for stale in ("verdict", "rule", "review_basis"):
            assert stale not in rec["l4_bali"]
        assert rec["l4_bali"]["verdict_state"] == "provisional"

    def test_apply_item_93114_drops_data_note(self):
        rec = _rec93114()
        items = cure.plan([rec, _rec43110()], SPEC)
        cure.apply_item(rec, items["93114"])
        assert "_data_note" not in rec
        assert rec["l4_bali"]["blocked"] is False


class TestRealCatalogue:
    @classmethod
    @pytest.fixture(scope="class")
    def records(cls):
        payload = json.loads(cure.CANONICAL.read_text(encoding="utf-8"))
        return {r["kode_kbli_2025"]: r for r in payload["data"]}

    def test_93114_two_rows_no_disputed_key_no_data_note(self, records):
        rec = records["93114"]
        assert len(rec["per_skala"]) == 2
        assert "per_skala_disputed_pp28_collision" not in rec
        assert "_data_note" not in rec

    def test_43110_three_rows_and_fixed_perizinan(self, records):
        rows = records["43110"]["per_skala"]
        assert len(rows) == 3
        assert rows[2]["perizinan"] == "NIB dan Sertifikat Standar"

    def test_43110_blocked_false(self, records):
        assert records["43110"]["l4_bali"]["blocked"] is False
