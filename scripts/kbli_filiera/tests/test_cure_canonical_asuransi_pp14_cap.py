"""Guilt and innocence for the asuransi/reasuransi PP 14/2018 80% cap cure.

The dangerous failure here is not "wrong number" — it's leaking the cap onto
a neighbour the sector law does NOT reach: 65123 (LPS, a state deposit-
insurance body), 65131/65132/65203/65204 (the penjaminan/guarantee family,
UU 1/2016, a DIFFERENT sector law), or any of the 1,553 other codes in the
dataset. Perpres 10/2021 Pasal 11(2) carves finance/banking OUT to sector
law; that carve-out is real for the six insurance/reinsurance codes named in
UU 40/2014 Pasal 1 angka 14, and it is NOT a license to touch anything that
merely sits in the same KBLI section.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402
import cure_canonical_asuransi_pp14_cap as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "canonical_asuransi_pp14_cap_2026_08_08.json"
    ).read_text(encoding="utf-8")
)

SIX_CODES = ["65111", "65112", "65121", "65122", "65201", "65202"]
EXCLUDED_NEIGHBORS = ["65123", "65131", "65132", "65203", "65204"]


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _open_record(code, **overrides):
    rec = {
        "kode_kbli_2025": code,
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_source": "Perpres 10/2021, 49/2021",
    }
    rec.update(overrides)
    return rec


def _one_code_spec(code, patch=None):
    rec = _open_record(code)
    patch = patch or {
        "pma_status": "TERBATAS",
        "pma_max_asing": 80,
        "pma_cap_verified": True,
        "pma_official_basis": "PP 14/2018 Pasal 5(1)",
        "pma_kondisi": "Foreign ownership max 80% of paid-up capital.",
        "pma_nota": "Sector-law regime.",
        "pma_source": "PP 14/2018, PP 3/2020",
    }
    return {
        "codes": {
            code: {
                "old_sha256": H.sha256_of(rec),
                "expect": {"pma_status": "TERBUKA", "pma_max_asing": 100},
                "patch": patch,
            }
        }
    }


# --- the real six codes, post-cure ---------------------------------------------


def test_the_real_six_codes_are_cured():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    for code in SIX_CODES:
        rec = by_code[code]
        assert rec.get("pma_status") == "TERBATAS", code
        assert rec.get("pma_max_asing") == 80, code
        assert rec.get("pma_cap_verified") is True, code
        assert "PP 14/2018" in (rec.get("pma_official_basis") or ""), code
        assert "80%" in (rec.get("pma_kondisi") or ""), code


def test_excluded_neighbors_are_byte_untouched():
    """65123 (LPS) and the penjaminan family (UU 1/2016) sit in the same KBLI
    section as the six cured codes and must not have moved at all."""
    _, records, _ = H.load_dataset(mod.CANONICAL)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    for code in EXCLUDED_NEIGHBORS:
        rec = by_code[code]
        assert rec.get("pma_status") == "TERBUKA", code
        assert rec.get("pma_max_asing") == 100, code
        assert rec.get("pma_cap_verified") is not True, code


def test_the_real_cure_is_a_clean_noop_without_writing():
    """W96: never risk writing production state, even a believed no-op."""
    _, records, _ = H.load_dataset(mod.CANONICAL)
    verdicts = mod.plan(REAL_SPEC, records)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())
    assert set(verdicts) == set(SIX_CODES)


# --- guilt ----------------------------------------------------------------------


def test_apply_patches_all_seven_fields(tmp_path):
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111")])
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(tmp_path / "spec.json")]) == 0
    _, records, _ = H.load_dataset(path)
    rec = records[0]
    for key, value in spec["codes"]["65111"]["patch"].items():
        assert rec[key] == value


def test_second_run_without_a_backfilled_new_sha256_refuses(tmp_path, capsys):
    """ITEM J, guilt: the blind spot this hardening closes was a per-key value
    guess that read a hash-mismatched-but-value-matching record as noop.
    `judge_patch` requires an EXPLICIT `new_sha256` pin before it will ever
    call a hash-mismatched record cured — without one, a second run must
    REFUSE, not silently succeed. This is the behaviour change from the old
    `already_patched` heuristic, and it deserves its own test rather than
    being buried inside the noop path.
    """
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111")])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0
    before = path.read_text(encoding="utf-8")
    capsys.readouterr()
    assert mod.main(argv) == 2, "no new_sha256 pin yet — must refuse, not noop"
    assert "REFUSED" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == before


def test_second_run_is_a_noop_after_new_sha256_is_backfilled(tmp_path, capsys):
    """The intended two-step resume path: apply, THEN an explicit backfill of
    `new_sha256` (this test does it inline; the real tool is `backfill_new_
    sha256.py`), THEN a second run recognizes the record as already cured.
    """
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111")])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0

    _, records, _ = H.load_dataset(path)
    patched_rec = {str(r.get(mod.CODE_FIELD)): r for r in records}["65111"]
    spec["codes"]["65111"]["new_sha256"] = H.sha256_of(patched_rec)
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    capsys.readouterr()
    assert mod.main(argv) == 0
    assert "already cured" in capsys.readouterr().out


def test_unrelated_field_drift_after_backfill_is_refused_not_noop(tmp_path, capsys):
    """ITEM J's exact ask: a record whose PATCHED fields still read correctly
    but whose UNRELATED fields moved after `new_sha256` was pinned (a later
    cure touching the same record, or a hand-edit) must be refused — the
    whole-record hash can no longer match either pin, so `judge_patch` cannot
    mistake this for "already cured". This is the scenario the old per-key
    `already_patched` guess was blind to by construction.
    """
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111")])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0

    _, records, _ = H.load_dataset(path)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    spec["codes"]["65111"]["new_sha256"] = H.sha256_of(by_code["65111"])
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    # A field OUTSIDE the patch drifts — e.g. a later, unrelated cure edits
    # `judul`. Every patched key still reads exactly as the patch left it.
    by_code["65111"]["judul"] = "mutated by a different cure entirely"
    body = json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n"
    path.write_text(body, encoding="utf-8")

    before = path.read_text(encoding="utf-8")
    capsys.readouterr()
    assert mod.main(argv) == 2, "unrelated drift must refuse, never read as noop"
    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert path.read_text(encoding="utf-8") == before, "a refusal must never write"


def test_untouched_fields_survive(tmp_path):
    spec = _one_code_spec("65111")
    rec = _open_record("65111", judul="Asuransi Jiwa Konvensional")
    spec["codes"]["65111"]["old_sha256"] = H.sha256_of(rec)
    path = _canonical_file(tmp_path, [rec])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    assert records[0]["judul"] == "Asuransi Jiwa Konvensional"


def test_a_neighbor_record_in_a_fixture_is_never_touched(tmp_path):
    neighbor = _open_record("65123")
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111"), dict(neighbor)])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    assert by_code["65123"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111")])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path), "--spec", str(spec_path)]) == 0
    assert path.read_text(encoding="utf-8") == before


# --- guilt: refusals -------------------------------------------------------------


def test_refuses_when_the_code_is_missing(tmp_path):
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [{"kode_kbli_2025": "99999"}])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_record_has_drifted(tmp_path):
    """Live status is neither the pinned pre-image nor the already-patched
    state — a third state, and the compiler must refuse rather than guess."""
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111", pma_status="TERTUTUP")])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_cap_has_already_diverged(tmp_path):
    spec = _one_code_spec("65111")
    path = _canonical_file(tmp_path, [_open_record("65111", pma_max_asing=49)])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before
