"""Tests for the GARUDA-FILIERA per-ancestor RESTORE compiler (2026-07-18).

49213 "Angkutan Perkotaan" graduates from detach (cure_canonical_collisions.py,
per_skala -> []) to RESTORE (per_skala <- the per-ancestor merged PP28 rows),
per the signed conductor adjudication research/operations/2026-07-18-kbli-
batch-a-plan.md §A-6(b)-RESOLVED (PR #2721/#2740). This compiler is the
opposite operation from the detach compiler — these unit tests use fabricated
in-memory records (never the live 30MB dataset) to pin the plan/apply logic
in isolation; scripts/tests/test_kbli_false_friend_registry.py covers the
real served dataset after --apply (guilt: restored content correct; innocence:
no other record / no other Fase-1 code touched).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import cure_restore_per_ancestor as cure  # noqa: E402

DISPUTED_KEY = "per_skala_disputed_pp28_collision"

RESTORED_ROWS = [
    {"skala_usaha": ["Mikro"], "kategori_risiko": "Menengah Tinggi", "jangka_waktu": "5 Hari",
     "scope_index": 0, "scope_uraian": "Angkutan Bus Kota",
     "perizinan": ["NIB dan Sertifikat Standar"], "persyaratan": [], "kewajiban": [],
     "kewenangan": ["Bupati/Wali Kota"], "jangka_waktu_source": "pp28_lampiran_image_verified",
     "fiktif_positif": True},
]

SPEC = {
    "action": "restore_per_skala_per_ancestor",
    "code": "49213",
    "disputed_key": DISPUTED_KEY,
    "pp28_sources": ["49214", "49219", "49413"],
    "per_skala": RESTORED_ROWS,
    "data_note": "restored from per-ancestor PP28 rows image-verified ...",
}


def _record(*, per_skala, pp28_sources=("49213", "49413"), data_note="old note", disputed=True):
    rec = {
        "kode_kbli_2025": "49213",
        "judul": "Angkutan Perkotaan",
        "per_skala": per_skala,
        "pp28_sources": list(pp28_sources),
        "pma_status": "TERBUKA",
        "_data_note": data_note,
        "intel_2026": {"whatYouNeed": "unrelated to this compiler"},
    }
    if disputed:
        rec[DISPUTED_KEY] = {
            "per_skala": [{"kategori_risiko": "Menengah Tinggi", "kewenangan": ["Gubernur"]}],
            "per_skala_legacy": [{"kewenangan": "Gubernur"}],
        }
    return rec


# ---------------------------------------------------------------------------
# load_spec — action/required-key validation.
# ---------------------------------------------------------------------------

def test_load_spec_ships_expected_action_and_shape():
    spec = cure.load_spec(cure.DEFAULT_SPEC)
    assert spec["action"] == "restore_per_skala_per_ancestor"
    assert spec["code"] == "49213"
    assert spec["disputed_key"] == "per_skala_disputed_pp28_collision"
    assert spec["pp28_sources"] == ["49214", "49219", "49413"]
    assert len(spec["per_skala"]) == 12
    for row in spec["per_skala"]:
        assert row["kategori_risiko"] == "Menengah Tinggi"
        assert row["kewenangan"] in (["Bupati/Wali Kota"], ["Wali Kota"])
        assert "Gubernur" not in row["kewenangan"]


def test_load_spec_rejects_wrong_action(tmp_path):
    import json

    bad = dict(SPEC)
    bad["action"] = "detach"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(cure.CureError):
        cure.load_spec(path)


def test_load_spec_rejects_missing_keys(tmp_path):
    import json

    bad = {"action": "restore_per_skala_per_ancestor", "code": "49213"}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(cure.CureError):
        cure.load_spec(path)


# ---------------------------------------------------------------------------
# plan_restore — GUILT: the expected pre-restore state (per_skala==[], disputed
# key present) plans "apply". INNOCENCE: guard rails refuse ungated/ambiguous
# states rather than clobbering them.
# ---------------------------------------------------------------------------

def test_plan_apply_when_detached_with_disputed_key():
    rec = _record(per_skala=[], disputed=True)
    plan = cure.plan_restore(rec, SPEC)
    assert plan.status == "apply"
    assert plan.needs_apply is True


def test_plan_no_disputed_refuses_ungated_restore():
    """INNOCENCE guard: a restore must only ever happen as a follow-up to an
    existing detach/quarantine — never on a record with no disputed key at
    all (that would be an ungated, unaudited data change)."""
    rec = _record(per_skala=[], disputed=False)
    plan = cure.plan_restore(rec, SPEC)
    assert plan.status == "no-disputed"


def test_plan_unexpected_state_refuses_to_clobber_nonempty_non_target_per_skala():
    """INNOCENCE guard: per_skala already holds SOME non-empty content that is
    neither [] nor the spec's target rows — refuse (no-clobber), do not
    silently overwrite an unrecognised prior state."""
    rec = _record(per_skala=[{"kategori_risiko": "Rendah"}], disputed=True)
    plan = cure.plan_restore(rec, SPEC)
    assert plan.status == "unexpected-state"


def test_plan_already_cured_when_all_three_fields_match_spec():
    rec = _record(
        per_skala=copy.deepcopy(SPEC["per_skala"]),
        pp28_sources=SPEC["pp28_sources"],
        data_note=SPEC["data_note"],
        disputed=True,
    )
    plan = cure.plan_restore(rec, SPEC)
    assert plan.status == "already-cured"


def test_plan_apply_when_per_skala_already_target_but_data_note_stale():
    """Partial-apply case (e.g. a manual mid-migration state): per_skala
    already matches the target but pp28_sources/_data_note don't yet — this
    must still plan 'apply' (idempotent re-apply completes the other fields),
    never 'unexpected-state' (the target rows ARE a recognised state)."""
    rec = _record(
        per_skala=copy.deepcopy(SPEC["per_skala"]),
        pp28_sources=("49213", "49413"),
        data_note="stale note",
        disputed=True,
    )
    plan = cure.plan_restore(rec, SPEC)
    assert plan.status == "apply"


# ---------------------------------------------------------------------------
# apply_restore — GUILT: exactly 3 fields change. INNOCENCE: the disputed key
# and every other field are byte-identical before/after.
# ---------------------------------------------------------------------------

def test_apply_restore_sets_exactly_three_fields():
    rec = _record(per_skala=[], disputed=True)
    original_disputed = copy.deepcopy(rec[DISPUTED_KEY])
    out = cure.apply_restore(rec, SPEC)

    assert out["per_skala"] == SPEC["per_skala"]
    assert out["pp28_sources"] == SPEC["pp28_sources"]
    assert out["_data_note"] == SPEC["data_note"]

    # INNOCENCE: disputed key untouched (never re-derived, never re-detached).
    assert out[DISPUTED_KEY] == original_disputed

    # INNOCENCE: every other field byte-identical to the input record.
    for key in ("kode_kbli_2025", "judul", "pma_status", "intel_2026"):
        assert out[key] == rec[key], f"{key} was unexpectedly changed by apply_restore"


def test_apply_restore_does_not_mutate_the_input_record_in_place():
    """apply_restore must return a NEW dict — the caller's original record
    object must be untouched (deepcopy discipline, matches
    cure_canonical_collisions.apply_cure's own contract)."""
    rec = _record(per_skala=[], disputed=True)
    original = copy.deepcopy(rec)
    cure.apply_restore(rec, SPEC)
    assert rec == original, "apply_restore mutated its input record in place"


def test_apply_restore_is_idempotent_on_content():
    rec = _record(per_skala=[], disputed=True)
    once = cure.apply_restore(rec, SPEC)
    twice = cure.apply_restore(once, SPEC)
    assert once == twice


# ---------------------------------------------------------------------------
# End-to-end dry-run / apply against a throwaway on-disk fixture (mirrors the
# CLI contract, never the live 30MB dataset).
# ---------------------------------------------------------------------------

def _write_fixture_dataset(tmp_path: Path, record: dict) -> Path:
    import json

    path = tmp_path / "fixture_dataset.json"
    path.write_text(
        json.dumps({"metadata": {}, "data": [record]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _write_fixture_spec(tmp_path: Path) -> Path:
    import json

    path = tmp_path / "fixture_spec.json"
    path.write_text(json.dumps(SPEC, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_cli_dry_run_writes_nothing(tmp_path, monkeypatch):
    rec = _record(per_skala=[], disputed=True)
    dataset_path = _write_fixture_dataset(tmp_path, rec)
    spec_path = _write_fixture_spec(tmp_path)
    before = dataset_path.read_text(encoding="utf-8")

    rc = cure.main(["--spec", str(spec_path), "--canonical", str(dataset_path)])

    assert rc == 0
    assert dataset_path.read_text(encoding="utf-8") == before, "dry-run must never write"


def test_cli_apply_then_second_apply_is_noop(tmp_path, monkeypatch):
    import json

    # Fixture-only test: stub out the real sync script / sidecar writer so
    # this never touches the live repo's consumer copies or sidecar file.
    monkeypatch.setattr(cure.base, "run_sync_script", lambda: None)
    monkeypatch.setattr(cure.base, "update_sidecar", lambda: None)

    rec = _record(per_skala=[], disputed=True)
    dataset_path = _write_fixture_dataset(tmp_path, rec)
    spec_path = _write_fixture_spec(tmp_path)

    rc1 = cure.main(["--spec", str(spec_path), "--canonical", str(dataset_path), "--apply"])
    assert rc1 == 0
    applied = json.loads(dataset_path.read_text(encoding="utf-8"))["data"][0]
    assert applied["per_skala"] == SPEC["per_skala"]
    assert applied["pp28_sources"] == SPEC["pp28_sources"]
    assert applied["_data_note"] == SPEC["data_note"]
    assert applied[DISPUTED_KEY] == rec[DISPUTED_KEY], "disputed key must survive apply unchanged"

    after_first = dataset_path.read_text(encoding="utf-8")
    rc2 = cure.main(["--spec", str(spec_path), "--canonical", str(dataset_path), "--apply"])
    assert rc2 == 0
    assert dataset_path.read_text(encoding="utf-8") == after_first, "second apply must be a no-op"


def test_cli_refuses_code_missing_from_canonical(tmp_path):
    other_rec = {"kode_kbli_2025": "00000", "per_skala": []}
    dataset_path = _write_fixture_dataset(tmp_path, other_rec)
    spec_path = _write_fixture_spec(tmp_path)

    rc = cure.main(["--spec", str(spec_path), "--canonical", str(dataset_path)])
    assert rc == 1


def test_cli_refuses_ungated_restore_with_no_disputed_key(tmp_path):
    rec = _record(per_skala=[], disputed=False)
    dataset_path = _write_fixture_dataset(tmp_path, rec)
    spec_path = _write_fixture_spec(tmp_path)

    rc = cure.main(["--spec", str(spec_path), "--canonical", str(dataset_path)])
    assert rc == 1
