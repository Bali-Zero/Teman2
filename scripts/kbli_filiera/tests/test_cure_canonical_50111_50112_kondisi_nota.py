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
claiming the record is cured.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_canonical_47222_nota_kondisi as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
_SPEC_DIR = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs"
REAL_SPEC_50111 = json.loads(
    (_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json").read_text(
        encoding="utf-8"
    )
)
REAL_SPEC_50112 = json.loads(
    (_SPEC_DIR / "canonical_50112_kondisi_nota_2026_09_16.json").read_text(
        encoding="utf-8"
    )
)


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


# --- the real records, post-cure ----------------------------------------------


def test_the_real_50111_is_cured():
    _, records, _ = mod.load(mod.CANONICAL)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    rec = by_code["50111"]
    assert "PMDN" not in (rec.get("pma_kondisi") or "")
    assert rec.get("pma_kondisi") == "Modal asing maksimal 49%"
    assert rec.get("pma_status") == "TERBATAS"
    assert rec.get("pma_max_asing") == 49
    assert rec.get("pma_cap_verified") is True
    assert "no. 9" in (rec.get("pma_nota") or "")
    assert "Modal Asing Maksimal 49%" in (rec.get("pma_official_basis") or "")


def test_the_real_50112_is_cured():
    _, records, _ = mod.load(mod.CANONICAL)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    rec = by_code["50112"]
    assert "PMDN" not in (rec.get("pma_kondisi") or "")
    assert rec.get("pma_kondisi") == "Modal asing maksimal 49%"
    assert rec.get("pma_status") == "TERBATAS"
    assert rec.get("pma_max_asing") == 49
    assert rec.get("pma_cap_verified") is True
    # The copy-paste residue named goods transport ("barang") on a
    # passenger code — must be gone, replaced by the passenger title.
    assert "barang" not in (rec.get("pma_nota") or "")
    assert "penumpang" in (rec.get("pma_nota") or "")
    assert "no. 11" in (rec.get("pma_nota") or "")
    assert "Modal Asing Maksimal 49%" in (rec.get("pma_official_basis") or "")


def test_the_real_50111_cure_is_a_clean_noop_without_writing():
    """W96: never risk writing production state, even a believed no-op."""
    _, records, _ = mod.load(mod.CANONICAL)
    verdicts = mod.plan(REAL_SPEC_50111, records)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())


def test_the_real_50112_cure_is_a_clean_noop_without_writing():
    _, records, _ = mod.load(mod.CANONICAL)
    verdicts = mod.plan(REAL_SPEC_50112, records)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())


# --- guilt ----------------------------------------------------------------


def test_apply_50111_patches_kondisi_and_nota(tmp_path):
    path = _canonical_file(tmp_path, [_base_50111()])
    assert (
        mod.main(
            [
                "--apply",
                "--dataset",
                str(path),
                "--spec",
                str(_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json"),
            ]
        )
        == 0
    )
    _, records, _ = mod.load(path)
    rec = records[0]
    assert rec["pma_kondisi"] == "Modal asing maksimal 49%"
    assert "PMDN" not in rec["pma_kondisi"]
    assert "no. 9" in rec["pma_nota"]


def test_apply_50112_patches_kondisi_and_nota(tmp_path):
    path = _canonical_file(tmp_path, [_base_50112()])
    assert (
        mod.main(
            [
                "--apply",
                "--dataset",
                str(path),
                "--spec",
                str(_SPEC_DIR / "canonical_50112_kondisi_nota_2026_09_16.json"),
            ]
        )
        == 0
    )
    _, records, _ = mod.load(path)
    rec = records[0]
    assert rec["pma_kondisi"] == "Modal asing maksimal 49%"
    assert "PMDN" not in rec["pma_kondisi"]
    assert "barang" not in rec["pma_nota"]
    assert "penumpang" in rec["pma_nota"]


def test_untouched_fields_survive_50111(tmp_path):
    path = _canonical_file(tmp_path, [_base_50111()])
    assert (
        mod.main(
            [
                "--apply",
                "--dataset",
                str(path),
                "--spec",
                str(_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json"),
            ]
        )
        == 0
    )
    _, records, _ = mod.load(path)
    after = records[0]
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_max_asing"] == 49
    assert after["pma_cap_verified"] is True


def test_untouched_fields_survive_50112(tmp_path):
    path = _canonical_file(tmp_path, [_base_50112()])
    assert (
        mod.main(
            [
                "--apply",
                "--dataset",
                str(path),
                "--spec",
                str(_SPEC_DIR / "canonical_50112_kondisi_nota_2026_09_16.json"),
            ]
        )
        == 0
    )
    _, records, _ = mod.load(path)
    after = records[0]
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_max_asing"] == 49
    assert after["pma_cap_verified"] is True


def test_second_run_of_each_is_a_no_op(tmp_path, capsys):
    path111 = _canonical_file(tmp_path, [_base_50111()])
    spec111 = str(_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json")
    assert mod.main(["--apply", "--dataset", str(path111), "--spec", spec111]) == 0
    capsys.readouterr()
    assert mod.main(["--apply", "--dataset", str(path111), "--spec", spec111]) == 0
    assert "already cured" in capsys.readouterr().out


# --- guilt: refusals --------------------------------------------------------


def test_refuses_when_50111_cap_has_drifted(tmp_path):
    path = _canonical_file(tmp_path, [_base_50111(pma_max_asing=100)])
    spec = str(_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", spec]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_50112_status_has_drifted(tmp_path):
    path = _canonical_file(tmp_path, [_base_50112(pma_status="TERBUKA")])
    spec = str(_SPEC_DIR / "canonical_50112_kondisi_nota_2026_09_16.json")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", spec]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_50111_live_kondisi_has_drifted(tmp_path):
    path = _canonical_file(
        tmp_path, [_base_50111(pma_kondisi="a human already fixed this differently")]
    )
    spec = str(_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", spec]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- innocence ---------------------------------------------------------------


def test_curing_50111_never_touches_its_50112_sibling(tmp_path):
    path = _canonical_file(tmp_path, [_base_50111(), _base_50112()])
    spec = str(_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", spec]) == 0
    _, records, _ = mod.load(path)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    assert by_code["50112"] == _base_50112()


def test_curing_50112_never_touches_its_50111_sibling(tmp_path):
    path = _canonical_file(tmp_path, [_base_50111(), _base_50112()])
    spec = str(_SPEC_DIR / "canonical_50112_kondisi_nota_2026_09_16.json")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", spec]) == 0
    _, records, _ = mod.load(path)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    assert by_code["50111"] == _base_50111()


def test_dry_run_writes_nothing_50111(tmp_path):
    path = _canonical_file(tmp_path, [_base_50111()])
    spec = str(_SPEC_DIR / "canonical_50111_kondisi_nota_2026_09_16.json")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path), "--spec", spec]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_dry_run_writes_nothing_50112(tmp_path):
    path = _canonical_file(tmp_path, [_base_50112()])
    spec = str(_SPEC_DIR / "canonical_50112_kondisi_nota_2026_09_16.json")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path), "--spec", spec]) == 0
    assert path.read_text(encoding="utf-8") == before


# --- population pin: the named PR-3e scope, and only that scope -------------


def test_50111_and_50112_no_longer_carry_pmdn_while_keeping_the_49_cap():
    """The exact contradiction W-H PR-3e resolves — TERBATAS + 49% cap next to
    a PMDN-only condition string — is gone on both named codes, and the cap
    itself never moved.

    Scoped to 50111/50112 only (this PR's adjudicated pair, Perpres 49/2021
    Lampiran III rows 9 and 11): a repo-wide scan for the same shape turns up
    at least one more offender (50121) that this PR was never adjudicated to
    touch — that is a future cure's scope, not a reason to widen this one or
    to skip this pin.
    """
    _, records, _ = mod.load(mod.CANONICAL)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    for code in ("50111", "50112"):
        rec = by_code[code]
        assert rec.get("pma_status") == "TERBATAS"
        assert rec.get("pma_max_asing") == 49
        assert "PMDN" not in (rec.get("pma_kondisi") or ""), code
