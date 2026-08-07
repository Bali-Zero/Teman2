"""Guilt and innocence for the 47222 TERTUTUP -> TERBATAS one-shot.

The dangerous failure here is not the number (pma_max_asing stays 0 either
way) — it is the STATUS label. `TERTUTUP` says "closed to everyone";
`TERBATAS`/0 says "closed to foreign capital, open to domestic entities,
including Koperasi/UMKM". Getting this wrong in the other direction (writing
TERBATAS on a code that really is closed to everyone) would tell a client an
activity is reachable through an Indonesian partner when it is not. So this
file spends most of its weight on refusals: the compiler must recognise
exactly the one state it is licensed to touch, and refuse anything else.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_canonical_47222_reservation as mod  # noqa: E402

VALID_BASIS = (
    "Perpres 10/2021 Lampiran II, line 3731 '- Minuman Tidak Beralkohol 47222 V', "
    "V in DIALOKASIKAN-UNTUK-KOPERASI-DAN-UMKM column"
)


def _rec(code="47222", status="TERTUTUP", cap=0, verified=True, basis=VALID_BASIS,
         kondisi=None, **extra):
    return {
        "kode_kbli_2025": code,
        "judul": "x",
        "pma_status": status,
        "pma_max_asing": cap,
        "pma_cap_verified": verified,
        "pma_official_basis": basis,
        "pma_kondisi": kondisi,
        **extra,
    }


def _dataset(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


# --- the real dataset, post-cure -------------------------------------------


def test_the_real_canonical_47222_is_terbatas_with_zero_cap():
    records = json.loads(mod.CANONICAL.read_text(encoding="utf-8"))["data"]
    rec = {str(r["kode_kbli_2025"]): r for r in records}["47222"]
    assert rec["pma_status"] == "TERBATAS"
    assert rec["pma_max_asing"] == 0
    assert rec["pma_cap_verified"] is True
    assert "Lampiran II" in rec["pma_official_basis"]


# --- guilt: the patch itself -------------------------------------------------


def test_apply_flips_status_and_fills_an_absent_kondisi(tmp_path):
    path = _dataset(tmp_path, [_rec(kondisi=None)])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_max_asing"] == 0
    assert after["pma_kondisi"] == mod.KONDISI_IF_ABSENT


def test_apply_never_overwrites_an_existing_kondisi(tmp_path):
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_kondisi"] == "Kemitraan dengan UMKM/Koperasi"


def test_second_run_is_a_no_op(tmp_path, capsys):
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    capsys.readouterr()
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert "idempotent" in capsys.readouterr().out


def test_official_basis_is_left_byte_unchanged(tmp_path):
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_official_basis"] == VALID_BASIS


# --- guilt: refusals ---------------------------------------------------------


def test_refuses_when_the_code_is_missing(tmp_path):
    path = _dataset(tmp_path, [_rec(code="99999")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_cap_is_not_zero(tmp_path):
    path = _dataset(tmp_path, [_rec(cap=49)])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_on_an_unexpected_status(tmp_path):
    """Neither TERTUTUP (what it expects to cure) nor TERBATAS (already cured) —
    e.g. TERBUKA. The world moved under the adjudication; do not guess."""
    path = _dataset(tmp_path, [_rec(status="TERBUKA")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_cap_is_not_verified(tmp_path):
    path = _dataset(tmp_path, [_rec(verified=False)])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_basis_no_longer_cites_lampiran_ii(tmp_path):
    path = _dataset(tmp_path, [_rec(basis="some other note entirely")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- innocence ----------------------------------------------------------------


def test_a_neighbor_record_is_never_touched(tmp_path):
    neighbor = _rec(code="47111", status="TERBATAS", cap=0, kondisi="UMKM only")
    path = _dataset(tmp_path, [_rec(), neighbor])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = {str(r["kode_kbli_2025"]): r for r in json.loads(path.read_text(encoding="utf-8"))["data"]}
    assert after["47111"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    path = _dataset(tmp_path, [_rec()])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path)]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_already_cured_record_is_left_byte_identical(tmp_path):
    """A no-op run must not reformat the file — the real canonical is 540k
    lines and a spurious diff would make a one-code cure unreviewable."""
    path = _dataset(tmp_path, [_rec(status="TERBATAS", kondisi="Kemitraan dengan UMKM/Koperasi")])
    before = path.read_bytes()
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert path.read_bytes() == before


def test_applying_to_a_fixture_never_touches_the_repos_sidecar(tmp_path):
    """W96: a test that rewrites production state is its own defect."""
    sidecar_before = mod.SIDECAR_VERSION.read_bytes()
    copy_before = mod.SIDECAR_DATASET.stat().st_mtime_ns
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert mod.SIDECAR_VERSION.read_bytes() == sidecar_before
    assert mod.SIDECAR_DATASET.stat().st_mtime_ns == copy_before
