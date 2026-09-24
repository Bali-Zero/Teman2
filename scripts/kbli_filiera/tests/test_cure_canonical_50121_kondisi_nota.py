"""Guilt and innocence for 50121's PMA condition and note (W-H lot remainder).

50121 (Angkutan Laut Dalam Negeri untuk Barang Umum) is TERBATAS with a
verified 49% cap, and its `pma_official_basis` quotes the annex condition
"Modal Asing Maksimal 49%". Its `pma_kondisi` said "Kemitraan dengan PMDN" —
a partnership condition the annex row does not state — and the page's FAQ and
FAQPage JSON-LD repeated it as "Condition: Kemitraan dengan PMDN". Its
`pma_nota` said "Angkutan laut luar negeri" (INTERNATIONAL sea transport) on a
DOMESTIC code, and that note reaches the chat channel's PMA block.

Same shared compiler and same shape as PR-3e's 50111/50112 cure. Both fields
feed the certified PMA fingerprint, so the code is de-certified: no compiler
re-certifies a moved fingerprint, and a stale certificate would keep serving
an Intelligence section reviewed against the old PMA facts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_canonical_47222_nota_kondisi as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "canonical_50121_kondisi_nota_2026_09_25.json"
REGISTRY = REPO_ROOT / "data" / "kbli-filiera" / "pma-editorial-certifications.json"
CURED_KONDISI = "Modal asing maksimal 49%"


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _base(**overrides):
    rec = {
        "kode_kbli_2025": "50121",
        "pma_status": "TERBATAS",
        "pma_max_asing": 49,
        "pma_cap_verified": True,
        "pma_official_basis": "Perpres 10/2021 Lampiran III 'Modal Asing Maksimal 49%' — matched by activity name",
        "pma_kondisi": "Kemitraan dengan PMDN",
        "pma_nota": "Angkutan laut luar negeri",
    }
    rec.update(overrides)
    return rec


def _apply(path, *, apply=True):
    args = ["--dataset", str(path), "--spec", str(SPEC)]
    return mod.main((["--apply"] if apply else []) + args)


def _real():
    _, records, _ = mod.load(mod.CANONICAL)
    return {str(r.get("kode_kbli_2025")): r for r in records}


# --- guilt: the real record ------------------------------------------------------


def test_guilt_the_real_condition_is_the_annex_condition_not_a_pmdn_partnership():
    rec = _real()["50121"]
    assert rec.get("pma_kondisi") == CURED_KONDISI
    assert "PMDN" not in rec["pma_kondisi"]


def test_guilt_the_real_note_names_the_domestic_activity():
    nota = _real()["50121"].get("pma_nota") or ""
    assert "luar negeri" not in nota.lower()
    assert "dalam negeri" in nota.lower()
    assert "50131" in nota


def test_guilt_50121_is_no_longer_certified_against_the_old_pma_facts():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert "50121" not in registry["canonicalIntel"]


def test_the_real_cure_is_a_clean_noop_without_writing():
    _, records, _ = mod.load(mod.CANONICAL)
    verdicts = mod.plan(json.loads(SPEC.read_text(encoding="utf-8")), records)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())


# --- guilt: the compiler on a pre-cure fixture ------------------------------------


def test_apply_patches_both_fields_and_leaves_the_cap(tmp_path):
    path = _canonical_file(tmp_path, [_base()])
    assert _apply(path) == 0
    rec = mod.load(path)[1][0]
    assert rec["pma_kondisi"] == CURED_KONDISI
    assert "dalam negeri" in rec["pma_nota"]
    assert (rec["pma_status"], rec["pma_max_asing"], rec["pma_cap_verified"]) == ("TERBATAS", 49, True)


@pytest.mark.parametrize(
    "drift",
    [{"pma_max_asing": 100}, {"pma_status": "TERBUKA"}, {"pma_kondisi": "a human already fixed this differently"}],
)
def test_refuses_a_record_the_spec_no_longer_describes(tmp_path, drift):
    path = _canonical_file(tmp_path, [_base(**drift)])
    before = path.read_text(encoding="utf-8")
    assert _apply(path) == 2
    assert path.read_text(encoding="utf-8") == before


# --- innocence ----------------------------------------------------------------------


def test_innocence_the_cap_and_its_basis_never_moved():
    rec = _real()["50121"]
    assert (rec["pma_status"], rec["pma_max_asing"], rec["pma_cap_verified"]) == ("TERBATAS", 49, True)
    assert "Modal Asing Maksimal 49%" in rec["pma_official_basis"]


def test_innocence_the_pr3e_siblings_keep_their_own_cure():
    by_code = _real()
    for code, row in (("50111", "no. 9"), ("50112", "no. 11")):
        assert by_code[code]["pma_kondisi"] == CURED_KONDISI
        assert row in by_code[code]["pma_nota"]


def test_innocence_other_49_percent_sea_codes_carry_no_condition_and_stay_certified():
    by_code = _real()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["canonicalIntel"]
    for code in ("50122", "50123", "50124", "50125", "50126"):
        assert by_code[code].get("pma_kondisi") is None
        assert code in registry


def test_innocence_curing_50121_never_touches_its_neighbour(tmp_path):
    neighbour = _base(kode_kbli_2025="50122", pma_kondisi=None, pma_nota=None)
    path = _canonical_file(tmp_path, [_base(), neighbour])
    assert _apply(path) == 0
    by_code = {str(r["kode_kbli_2025"]): r for r in mod.load(path)[1]}
    assert by_code["50122"] == neighbour


def test_dry_run_writes_nothing(tmp_path):
    path = _canonical_file(tmp_path, [_base()])
    before = path.read_text(encoding="utf-8")
    assert _apply(path, apply=False) == 0
    assert path.read_text(encoding="utf-8") == before
