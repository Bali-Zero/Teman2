"""Guilt and innocence for the 47221 pma_kondisi cure (item 4 of the
2026-08-08 sector-law brief): the "Kemitraan dengan UMKM/Koperasi" phrasing
was copy-paste residue from 47222 (non-alcoholic beverage retail, genuinely
Lampiran-II-allocated) bleeding onto 47221 (alcoholic beverage retail,
which has zero rows in Lampiran II and a different official_basis entirely).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402
import cure_canonical_47221_kondisi as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "canonical_47221_kondisi_2026_08_08.json"
    ).read_text(encoding="utf-8")
)


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _base_record(**overrides):
    rec = {
        "kode_kbli_2025": "47221",
        "pma_status": "TERBATAS",
        "pma_max_asing": "special",
        "pma_cap_verified": True,
        "pma_official_basis": "Perpres 10/2021 Lampiran III ... Jaringan distribusi dan tempatnya khusus ...",
        "pma_kondisi": "Kemitraan dengan UMKM/Koperasi",
        "pma_nota": "Perdagangan eceran minuman beralkohol",
    }
    rec.update(overrides)
    return rec


def _spec(**overrides):
    rec = _base_record()
    spec = {
        "code": "47221",
        "old_sha256": H.sha256_of(rec),
        "expect": {"pma_status": "TERBATAS", "pma_cap_verified": True},
        "patch": {
            "pma_kondisi": "Jaringan distribusi dan tempatnya khusus — a special distribution-network/location requirement, not a UMKM/Koperasi partnership duty."
        },
    }
    spec.update(overrides)
    return spec


def test_the_real_47221_is_cured():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    rec = by_code["47221"]
    assert "Kemitraan dengan UMKM/Koperasi" not in (rec.get("pma_kondisi") or "")
    assert "Jaringan distribusi" in (rec.get("pma_kondisi") or "")
    assert rec.get("pma_nota") == "Perdagangan eceran minuman beralkohol"
    assert rec.get("pma_status") == "TERBATAS"


def test_47222_neighbor_is_byte_untouched():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    rec = by_code["47222"]
    assert "beralkohol" not in (rec.get("pma_nota") or "")


def test_the_real_cure_is_a_clean_noop_without_writing():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    verdict = mod.plan(REAL_SPEC, records)
    assert verdict["action"] == "noop"


def test_apply_patches_the_field(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    assert "Jaringan distribusi" in records[0]["pma_kondisi"]


def test_second_run_is_a_noop(tmp_path, capsys):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0
    capsys.readouterr()
    assert mod.main(argv) == 0
    assert "already cured" in capsys.readouterr().out


def test_untouched_fields_survive(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    after = records[0]
    assert after["pma_nota"] == "Perdagangan eceran minuman beralkohol"
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_max_asing"] == "special"


def test_a_neighbor_record_in_a_fixture_is_never_touched(tmp_path):
    neighbor = {
        "kode_kbli_2025": "47222",
        "pma_kondisi": "Kemitraan dengan UMKM/Koperasi",
        "pma_nota": "Perdagangan eceran minuman tidak beralkohol",
    }
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record(), dict(neighbor)])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    assert by_code["47222"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path), "--spec", str(spec_path)]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_code_is_missing(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [{"kode_kbli_2025": "99999"}])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_status_has_drifted(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record(pma_status="TERBUKA")])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before
