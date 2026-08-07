"""Guilt and innocence for the sector-law prose-fixpack cure (item G/A/B/C/D
of the 2026-08-08 fix-pack): nine codes whose SIBLING prose fields kept
asserting a pre-adjudication figure after another cure in the same PR had
already corrected the record's own governing field.

This is the compiler that introduced INDEXED patch-path support to
`_hardened_cure_io` (`editorial.byTheNumbers[2].value`) and is the first to
combine an indexed and a non-indexed dotted patch on the SAME code in one
spec entry — both are exercised here, not just the plain-dict paths the
sibling compilers already covered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402
import cure_canonical_sector_law_prosepack as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "canonical_sector_law_prosepack_2026_08_08.json"
    ).read_text(encoding="utf-8")
)

REAL_CODES = ["41011", "47221", "90200", "65111", "65112", "65121", "65122", "65201", "65202"]


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _base_record(**overrides):
    rec = {
        "kode_kbli_2025": "65112",
        "pma_status": "TERBATAS",
        "pma_max_asing": 80,
        "intel_2026": {
            "zantaraOpener": "Nationally this carries PMA status: Open.",
            "editorial": {
                "body": "... the Perpres's annexes never actually governed this activity ...",
                "byTheNumbers": [
                    {"label": "Something", "value": "X"},
                    {"label": "Something else", "value": "Y"},
                    {"label": "PMA source", "value": "Perpres 10/2021, 49/2021"},
                ],
            },
        },
    }
    rec.update(overrides)
    return rec


def _spec(code="65112", **overrides):
    rec = _base_record()
    spec = {
        "codes": {
            code: {
                "old_sha256": H.sha256_of(rec),
                "expect": {"pma_status": "TERBATAS", "pma_max_asing": 80},
                "patch": {
                    "intel_2026.editorial.byTheNumbers[2].value": "PP 14/2018 Pasal 5(1) jo. PP 3/2020 (Perpres 10/2021 Pasal 11(2))",
                    "intel_2026.zantaraOpener": "Nationally this carries PMA status: Restricted — capped at 80% foreign ownership.",
                    "intel_2026.editorial.body": "... so the residual-open default cannot ground an ownership verdict here ...",
                },
            }
        }
    }
    spec.update(overrides)
    return spec


# --- the real nine codes, post-cure ------------------------------------------


def test_the_real_nine_codes_are_cured():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    for code, entry in REAL_SPEC["codes"].items():
        rec = by_code[code]
        for path, want in entry["patch"].items():
            assert H.read_field(rec, path) == want, f"{code}.{path}"


def test_the_real_cure_is_a_clean_noop_without_writing():
    """W96: never risk writing production state, even a believed no-op."""
    _, records, _ = H.load_dataset(mod.CANONICAL)
    verdicts = mod.plan(REAL_SPEC, records)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())
    assert set(verdicts) == set(REAL_CODES) == set(REAL_SPEC["codes"])


# --- guilt: apply, indexed AND non-indexed paths in one patch ---------------


def test_apply_patches_the_indexed_list_cell(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    rec = records[0]
    assert rec["intel_2026"]["editorial"]["byTheNumbers"][2]["value"] == (
        "PP 14/2018 Pasal 5(1) jo. PP 3/2020 (Perpres 10/2021 Pasal 11(2))"
    )


def test_apply_patches_the_plain_dotted_fields_in_the_same_code(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    rec = records[0]
    assert "Restricted" in rec["intel_2026"]["zantaraOpener"]
    assert "residual-open default cannot ground" in rec["intel_2026"]["editorial"]["body"]


def test_untouched_list_cells_and_sibling_fields_survive(tmp_path):
    """The indexed patch touches ONLY byTheNumbers[2] — [0] and [1] must be
    byte-identical, and this codes's non-editorial fields must not move.
    """
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    rec = records[0]
    cells = rec["intel_2026"]["editorial"]["byTheNumbers"]
    assert cells[0] == {"label": "Something", "value": "X"}
    assert cells[1] == {"label": "Something else", "value": "Y"}
    assert rec["pma_status"] == "TERBATAS"
    assert rec["pma_max_asing"] == 80


def test_a_neighbor_record_in_a_fixture_is_never_touched(tmp_path):
    neighbor = {"kode_kbli_2025": "65123", "pma_status": "TERBUKA"}
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record(), dict(neighbor)])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    assert by_code["65123"] == neighbor


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


def test_refuses_when_the_record_has_drifted(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record(pma_status="TERTUTUP")])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- item J: resume hardening, same two-step contract as the sibling cures --


def test_second_run_without_a_backfilled_new_sha256_refuses(tmp_path, capsys):
    """ITEM J, guilt: without an explicit `new_sha256` pin, `judge_patch`
    never mistakes a hash-mismatched record for "already cured".
    """
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
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
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0

    _, records, _ = H.load_dataset(path)
    patched_rec = {str(r.get(mod.CODE_FIELD)): r for r in records}["65112"]
    spec["codes"]["65112"]["new_sha256"] = H.sha256_of(patched_rec)
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    capsys.readouterr()
    assert mod.main(argv) == 0
    assert "already cured" in capsys.readouterr().out


def test_unrelated_field_drift_after_backfill_is_refused_not_noop(tmp_path, capsys):
    """ITEM J's exact ask: every patched key (including the indexed list
    cell) still reads exactly as patched, but an UNRELATED field moved after
    `new_sha256` was pinned — must refuse, not noop.
    """
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0

    _, records, _ = H.load_dataset(path)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    spec["codes"]["65112"]["new_sha256"] = H.sha256_of(by_code["65112"])
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    # An UNTOUCHED list cell drifts — every declared patch key still matches.
    by_code["65112"]["intel_2026"]["editorial"]["byTheNumbers"][0]["value"] = "mutated"
    body = json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n"
    path.write_text(body, encoding="utf-8")

    before = path.read_text(encoding="utf-8")
    capsys.readouterr()
    assert mod.main(argv) == 2, "unrelated drift must refuse, never read as noop"
    assert "REFUSED" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == before
