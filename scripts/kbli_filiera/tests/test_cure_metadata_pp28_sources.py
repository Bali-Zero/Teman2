"""Tests for the GARUDA-FILIERA metadata-only cure compiler
(cure_metadata_pp28_sources.py), Batch A Lot 2's 56101 innocence-violation
finding (2026-07-18).

Unlike cure_canonical_collisions.py (detach) and cure_restore_per_ancestor.py
(restore-from-detach), this compiler NEVER touches per_skala or
per_skala_legacy — it corrects exactly three fields (pp28_sources,
aggregation_note, intel_2026.whatChanged) plus _data_note. Fabricated
fixtures throughout (guilt + innocence, scar #3 discipline); no dependency
on the real canonical dataset except the two sanity checks at the bottom
that load the committed spec/compiler pairing.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
REPO_ROOT = FILIERA.parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import cure_metadata_pp28_sources as cure  # noqa: E402

SPEC = {
    "action": "correct_pp28_sources_metadata",
    "code": "56101",
    "pp28_sources": ["56101", "56102", "56109"],
    "aggregation_note": "Dati da 56101 + 2 codici figli PP28 (56102, 56109)",
    "whatChanged": "corrected merge list text",
    "data_note": "corrected provenance note",
}


def _record(
    *,
    pp28_sources=("56101", "56104", "56103", "56109"),
    aggregation_note="Dati da 56101 + 3 codici figli PP28",
    what_changed="stale merge list text",
    data_note=None,
    disputed=False,
    per_skala=None,
    per_skala_legacy=None,
    has_intel=True,
):
    rec: dict = {
        "kode_kbli_2025": "56101",
        "judul": "Aktivitas Penyediaan Makanan di Bangunan Tetap",
        "pp28_sources": list(pp28_sources),
        "aggregation_note": aggregation_note,
    }
    if per_skala is not None:
        rec["per_skala"] = per_skala
    if per_skala_legacy is not None:
        rec["per_skala_legacy"] = per_skala_legacy
    if has_intel:
        rec["intel_2026"] = {
            "whatItMeans": "keep me untouched",
            "whatYouNeed": "keep me untouched too",
            "whatChanged": what_changed,
        }
    if data_note is not None:
        rec["_data_note"] = data_note
    if disputed:
        rec["per_skala_disputed_pp28_collision"] = [{"kategori_risiko": "Tinggi"}]
    return rec


# ---------------------------------------------------------------------------
# load_spec
# ---------------------------------------------------------------------------


def test_load_spec_valid(tmp_path: Path):
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(SPEC), encoding="utf-8")
    spec = cure.load_spec(p)
    assert spec["code"] == "56101"


def test_load_spec_missing_keys_rejected(tmp_path: Path):
    p = tmp_path / "spec.json"
    bad = {k: v for k, v in SPEC.items() if k != "aggregation_note"}
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(cure.CureError, match="missing required keys"):
        cure.load_spec(p)


def test_load_spec_wrong_action_rejected(tmp_path: Path):
    p = tmp_path / "spec.json"
    bad = dict(SPEC, action="restore_per_skala_per_ancestor")
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(cure.CureError, match="unsupported action"):
        cure.load_spec(p)


def test_load_spec_empty_pp28_sources_rejected(tmp_path: Path):
    p = tmp_path / "spec.json"
    bad = dict(SPEC, pp28_sources=[])
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(cure.CureError, match="pp28_sources"):
        cure.load_spec(p)


# ---------------------------------------------------------------------------
# plan_metadata_cure
# ---------------------------------------------------------------------------


def test_plan_apply_when_metadata_differs():
    rec = _record()
    plan = cure.plan_metadata_cure(rec, SPEC)
    assert plan.status == "apply"


def test_plan_already_cured_when_metadata_matches():
    rec = _record(
        pp28_sources=SPEC["pp28_sources"],
        aggregation_note=SPEC["aggregation_note"],
        what_changed=SPEC["whatChanged"],
        data_note=SPEC["data_note"],
    )
    plan = cure.plan_metadata_cure(rec, SPEC)
    assert plan.status == "already-cured"


def test_plan_detached_guard_refuses_quarantined_record():
    """GUILT: a record already carrying a per_skala_disputed_* key is refused
    — a metadata-only cure is only sound on an un-quarantined record."""
    rec = _record(disputed=True)
    plan = cure.plan_metadata_cure(rec, SPEC)
    assert plan.status == "detached-guard"


def test_plan_no_intel_guard():
    rec = _record(has_intel=False)
    plan = cure.plan_metadata_cure(rec, SPEC)
    assert plan.status == "no-intel"


def test_plan_innocence_untouched_neighbor_not_flagged():
    """INNOCENCE (scar #3): a legitimate, already-correct neighbor record
    (matches the spec's target shape exactly) reads as already-cured, never
    as apply/guard — the compiler must not false-positive on a clean record."""
    rec = _record(
        pp28_sources=SPEC["pp28_sources"],
        aggregation_note=SPEC["aggregation_note"],
        what_changed=SPEC["whatChanged"],
        data_note=SPEC["data_note"],
        disputed=False,
    )
    plan = cure.plan_metadata_cure(rec, SPEC)
    assert plan.status == "already-cured"


# ---------------------------------------------------------------------------
# apply_metadata_cure
# ---------------------------------------------------------------------------


def test_apply_sets_three_fields_and_data_note():
    rec = _record()
    out = cure.apply_metadata_cure(rec, SPEC)
    assert out["pp28_sources"] == SPEC["pp28_sources"]
    assert out["aggregation_note"] == SPEC["aggregation_note"]
    assert out["intel_2026"]["whatChanged"] == SPEC["whatChanged"]
    assert out["_data_note"] == SPEC["data_note"]


def test_apply_preserves_other_intel_fields():
    rec = _record()
    out = cure.apply_metadata_cure(rec, SPEC)
    assert out["intel_2026"]["whatItMeans"] == "keep me untouched"
    assert out["intel_2026"]["whatYouNeed"] == "keep me untouched too"


def test_apply_never_touches_per_skala():
    original_per_skala = [{"skala_usaha": ["Mikro"], "kategori_risiko": "Menengah Rendah"}]
    rec = _record(per_skala=copy.deepcopy(original_per_skala))
    out = cure.apply_metadata_cure(rec, SPEC)
    assert out["per_skala"] == original_per_skala, "per_skala must be byte-identical, never touched"


def test_apply_never_touches_per_skala_legacy():
    original_legacy = [{"skala_usaha": ["Mikro"], "perizinan": "NIB dan Sertifikat Standar"}]
    rec = _record(per_skala_legacy=copy.deepcopy(original_legacy))
    out = cure.apply_metadata_cure(rec, SPEC)
    assert out["per_skala_legacy"] == original_legacy, "per_skala_legacy must be byte-identical, never touched"


def test_apply_does_not_mutate_input_record_in_place():
    rec = _record()
    original = copy.deepcopy(rec)
    cure.apply_metadata_cure(rec, SPEC)
    assert rec == original, "apply_metadata_cure must return a NEW dict, never mutate the input"


def test_apply_idempotent():
    rec = _record()
    once = cure.apply_metadata_cure(rec, SPEC)
    twice = cure.apply_metadata_cure(once, SPEC)
    assert once == twice


# ---------------------------------------------------------------------------
# CLI end-to-end against a throwaway fixture file
# ---------------------------------------------------------------------------


def _write_fixture_canonical(tmp_path: Path) -> Path:
    canonical = {
        "data": [
            _record(),
            {"kode_kbli_2025": "99999", "judul": "unrelated innocence neighbor", "pp28_sources": ["99999"]},
        ]
    }
    p = tmp_path / "canonical.json"
    p.write_text(json.dumps(canonical, indent=2), encoding="utf-8")
    return p


def _write_spec_file(tmp_path: Path) -> Path:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(SPEC), encoding="utf-8")
    return p


def test_cli_dry_run_does_not_write(tmp_path: Path):
    canonical_path = _write_fixture_canonical(tmp_path)
    spec_path = _write_spec_file(tmp_path)
    before = canonical_path.read_text(encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(FILIERA / "cure_metadata_pp28_sources.py"), "--spec", str(spec_path), "--canonical", str(canonical_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout
    assert canonical_path.read_text(encoding="utf-8") == before, "dry-run must not write the fixture file"


def test_cli_apply_mutates_target_and_leaves_neighbor_untouched(tmp_path: Path, monkeypatch):
    canonical_path = _write_fixture_canonical(tmp_path)
    spec_path = _write_spec_file(tmp_path)

    # neutralize the sync/sidecar side effects (they target the real repo
    # paths) — the CLI-apply contract under test here is the canonical
    # mutation itself, not the sync pipeline (covered elsewhere).
    monkeypatch.setattr(cure.base, "run_sync_script", lambda: None)
    monkeypatch.setattr(cure.base, "update_sidecar", lambda: None)

    result = cure.main(["--spec", str(spec_path), "--canonical", str(canonical_path), "--apply"])
    assert result == 0

    out = json.loads(canonical_path.read_text(encoding="utf-8"))
    by_code = {r["kode_kbli_2025"]: r for r in out["data"]}
    cured = by_code["56101"]
    assert cured["pp28_sources"] == SPEC["pp28_sources"]
    assert cured["aggregation_note"] == SPEC["aggregation_note"]
    assert cured["intel_2026"]["whatChanged"] == SPEC["whatChanged"]
    assert cured["_data_note"] == SPEC["data_note"]

    neighbor = by_code["99999"]
    assert neighbor == {"kode_kbli_2025": "99999", "judul": "unrelated innocence neighbor", "pp28_sources": ["99999"]}, (
        "innocence: the unrelated neighbor record must be byte-identical after apply"
    )


def test_cli_apply_then_dry_run_reports_already_cured(tmp_path: Path, monkeypatch):
    canonical_path = _write_fixture_canonical(tmp_path)
    spec_path = _write_spec_file(tmp_path)
    monkeypatch.setattr(cure.base, "run_sync_script", lambda: None)
    monkeypatch.setattr(cure.base, "update_sidecar", lambda: None)

    assert cure.main(["--spec", str(spec_path), "--canonical", str(canonical_path), "--apply"]) == 0
    result = subprocess.run(
        [sys.executable, str(FILIERA / "cure_metadata_pp28_sources.py"), "--spec", str(spec_path), "--canonical", str(canonical_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ALREADY CURED" in result.stdout


def test_cli_missing_code_exits_nonzero(tmp_path: Path):
    canonical_path = tmp_path / "canonical.json"
    canonical_path.write_text(json.dumps({"data": [{"kode_kbli_2025": "00000"}]}), encoding="utf-8")
    spec_path = _write_spec_file(tmp_path)
    result = cure.main(["--spec", str(spec_path), "--canonical", str(canonical_path)])
    assert result == 1


def test_cli_detached_guard_exits_nonzero(tmp_path: Path):
    canonical = {"data": [_record(disputed=True)]}
    canonical_path = tmp_path / "canonical.json"
    canonical_path.write_text(json.dumps(canonical), encoding="utf-8")
    spec_path = _write_spec_file(tmp_path)
    result = cure.main(["--spec", str(spec_path), "--canonical", str(canonical_path)])
    assert result == 1


# ---------------------------------------------------------------------------
# Sanity check against the real committed spec (2026-07-18 Lot 2)
# ---------------------------------------------------------------------------


def test_real_metadata_56101_spec_loads_and_matches_target_shape():
    spec = cure.load_spec(cure.DEFAULT_SPEC)
    assert spec["code"] == "56101"
    assert spec["pp28_sources"] == ["56101", "56102", "56109"]
    assert "56102" in spec["aggregation_note"]
    assert "56109" in spec["aggregation_note"]
    # the corrected whatChanged must still name 56103/56104 (so former operators
    # recognize themselves) but redirect them to 56102, not claim them for 56101
    assert "56103" in spec["whatChanged"]
    assert "56104" in spec["whatChanged"]
    assert "56102" in spec["whatChanged"]
