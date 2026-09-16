"""Guilt and innocence for W-H PR-3e — 50111/50112's pma_kondisi contradicted
their own 49% foreign cap.

Both codes carried `pma_status`/`pma_max_asing`=49 (TERBATAS, cap_verified)
next to `pma_kondisi` = "Hanya PMDN (100% domestik)" — two incompatible
answers on the same page for a foreign investor: the record's own adjudicated
cap says 49% is allowed, the condition string says only 100% domestic capital
is allowed. Perpres 49/2021 Lampiran III rows 9 (50111) and 11 (50112, BPS
ancestor 50114) both say "Modal asing maksimal 49%" — that is the condition,
not a PMDN-only reservation.

50112 additionally carried `pma_nota` naming goods transport ("barang") on a
passenger code — copy-paste residue from the neighbouring row, corrected to
name passenger pioneer transport per its own title and BPS ancestor 50114.

Same shared compiler as cure G (47222) —
`cure_canonical_47222_nota_kondisi.py` — driven by a per-code `--spec`; the
dangerous failure here is the same class as that cure's own docstring names:
bleeding one code's fix onto its sibling, or leaving "PMDN" behind while
claiming the record is cured. 50121 carries the same contradiction and is
left to the prose lot: this PR is adjudicated for Lampiran III rows 9 and 11 only.
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
_SPEC_DIR = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs"


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _base_50111(**overrides):
    rec = {
        "kode_kbli_2025": "50111",
        "pma_status": "TERBATAS",
        "pma_max_asing": 49,
        "pma_cap_verified": True,
        "pma_official_basis": "Perpres 49/2021 Lampiran III no. 9 — Modal Asing Maksimal 49%",
        "pma_kondisi": "Hanya PMDN (100% domestik)",
        "pma_nota": "Angkutan laut dalam negeri penumpang",
    }
    rec.update(overrides)
    return rec


def _base_50112(**overrides):
    rec = {
        "kode_kbli_2025": "50112",
        "pma_status": "TERBATAS",
        "pma_max_asing": 49,
        "pma_cap_verified": True,
        "pma_official_basis": "Perpres 49/2021 Lampiran III no. 11 — Modal Asing Maksimal 49%",
        "pma_kondisi": "Hanya PMDN (100% domestik)",
        "pma_nota": "Angkutan laut dalam negeri barang",
    }
    rec.update(overrides)
    return rec


_SPECS = {
    "50111": _SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json",
    "50112": _SPEC_DIR / "canonical_50112_kondisi_nota_2026_09_16.json",
}
_BASES = {"50111": _base_50111, "50112": _base_50112}
_NOTA_ROW = {"50111": "no. 9", "50112": "no. 11"}
_SIBLING = {"50111": "50112", "50112": "50111"}
_CODES = pytest.mark.parametrize("code", ["50111", "50112"])


def _apply(path, code, *, apply=True):
    args = ["--dataset", str(path), "--spec", str(_SPECS[code])]
    return mod.main((["--apply"] if apply else []) + args)


def _real(code):
    _, records, _ = mod.load(mod.CANONICAL)
    return {str(r.get("kode_kbli_2025")): r for r in records}[code]


# --- the real records, post-cure ----------------------------------------------


@_CODES
def test_the_real_record_is_cured_and_its_cap_never_moved(code):
    rec = _real(code)
    assert rec.get("pma_kondisi") == "Modal asing maksimal 49%"
    assert "PMDN" not in rec["pma_kondisi"]
    assert rec.get("pma_status") == "TERBATAS"
    assert rec.get("pma_max_asing") == 49
    assert rec.get("pma_cap_verified") is True
    assert _NOTA_ROW[code] in (rec.get("pma_nota") or "")
    assert "Modal Asing Maksimal 49%" in (rec.get("pma_official_basis") or "")
    if code == "50112":
        # Copy-paste residue named goods transport on a passenger code.
        assert "barang" not in rec["pma_nota"]
        assert "penumpang" in rec["pma_nota"]


@_CODES
def test_the_real_cure_is_a_clean_noop_without_writing(code):
    """W96: never risk writing production state, even a believed no-op."""
    _, records, _ = mod.load(mod.CANONICAL)
    spec = json.loads(_SPECS[code].read_text(encoding="utf-8"))
    verdicts = mod.plan(spec, records)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())


# --- guilt ----------------------------------------------------------------


@_CODES
def test_apply_patches_both_fields_and_leaves_the_cap(tmp_path, code):
    path = _canonical_file(tmp_path, [_BASES[code]()])
    assert _apply(path, code) == 0
    _, records, _ = mod.load(path)
    rec = records[0]
    assert rec["pma_kondisi"] == "Modal asing maksimal 49%"
    assert _NOTA_ROW[code] in rec["pma_nota"]
    assert (rec["pma_status"], rec["pma_max_asing"], rec["pma_cap_verified"]) == (
        "TERBATAS",
        49,
        True,
    )


def test_second_run_is_a_no_op(tmp_path, capsys):
    path = _canonical_file(tmp_path, [_base_50111()])
    assert _apply(path, "50111") == 0
    capsys.readouterr()
    assert _apply(path, "50111") == 0
    assert "already cured" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("code", "drift"),
    [
        ("50111", {"pma_max_asing": 100}),
        ("50112", {"pma_status": "TERBUKA"}),
        ("50111", {"pma_kondisi": "a human already fixed this differently"}),
    ],
)
def test_refuses_a_record_the_spec_no_longer_describes(tmp_path, code, drift):
    path = _canonical_file(tmp_path, [_BASES[code](**drift)])
    before = path.read_text(encoding="utf-8")
    assert _apply(path, code) == 2
    assert path.read_text(encoding="utf-8") == before


# --- innocence ---------------------------------------------------------------


@_CODES
def test_curing_one_code_never_touches_its_sibling(tmp_path, code):
    path = _canonical_file(tmp_path, [_base_50111(), _base_50112()])
    assert _apply(path, code) == 0
    _, records, _ = mod.load(path)
    sibling = _SIBLING[code]
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    assert by_code[sibling] == _BASES[sibling]()


@_CODES
def test_dry_run_writes_nothing(tmp_path, code):
    path = _canonical_file(tmp_path, [_BASES[code]()])
    before = path.read_text(encoding="utf-8")
    assert _apply(path, code, apply=False) == 0
    assert path.read_text(encoding="utf-8") == before
