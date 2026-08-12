"""Population, guilt, innocence, guard, and idempotence for Bali four-state cure."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from pytest import MonkeyPatch

FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if FILIERA_DIR not in sys.path:
    sys.path.insert(0, FILIERA_DIR)

import _l4bali_basis as basis  # noqa: E402
import cure_l4bali_verdict_state as cure  # noqa: E402
import emit_l4bali_verdict_state_spec as emitter  # noqa: E402


def _row(scales: list[str], tier: str) -> dict:
    return {"skala_usaha": scales, "kategori_risiko": tier}


def _record(
    code: str,
    *,
    status: str = "APERTO_BALI_RISCHIO_ALTO",
    blocked: bool = False,
    confidence: str = "HIGH",
    needs_review: bool = False,
    rows: list[dict] | None = None,
    verdict_state: str | None = None,
) -> dict:
    l4 = {
        "status": status,
        "blocked": blocked,
        "confidence": confidence,
        "needs_review": needs_review,
        "reason": "fixture",
    }
    if verdict_state is not None:
        l4["verdict_state"] = verdict_state
    return {
        "kode_kbli_2025": code,
        "per_skala": rows if rows is not None else [_row(["Besar"], "Tinggi")],
        "l4_bali": l4,
    }


def _write(path: Path, payload: object) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def _fixture_files(tmp_path: Path, records: list[dict]) -> tuple[Path, Path]:
    canonical = _write(tmp_path / "canonical.json", {"data": records})
    spec, _ = emitter.build_spec(records, canonical)
    spec_path = _write(tmp_path / "spec.json", spec)
    return canonical, spec_path


def _run(canonical: Path, spec: Path, *, apply: bool = False) -> int:
    argv = ["--canonical", str(canonical), "--spec", str(spec)]
    if apply:
        argv.append("--apply")
    return cure.main(argv)


def test_emitter_population_pins_measured_live_canonical_counts() -> None:
    records = emitter.load_records(emitter.DEFAULT_CANONICAL)
    spec, stats = emitter.build_spec(records, emitter.DEFAULT_CANONICAL)

    assert len(records) == len(spec["codes"]) == 1559
    assert stats["status:NON_CLASSIFICABILE"] == 25
    assert stats["unknown_blocked_true_preserved"] == 17
    assert stats["open_supporting_tier_absent:APERTO_BALI_RISCHIO_ALTO"] == 11
    assert stats["open_supporting_tier_absent:OK_or_HIGHER_RISK"] == 90
    assert stats["open_supporting_tier_absent"] == 101
    assert {
        state: stats[f"verdict_state:{state}"]
        for state in ("blocked", "open", "unknown", "provisional")
    } == {"blocked": 95, "open": 3, "unknown": 25, "provisional": 1436}


def test_checked_in_spec_matches_fresh_live_state_emission() -> None:
    records = emitter.load_records(emitter.DEFAULT_CANONICAL)
    fresh, _ = emitter.build_spec(records, emitter.DEFAULT_CANONICAL)
    checked_in = cure.load_spec(cure.DEFAULT_SPEC)

    assert checked_in["codes"] == fresh["codes"]
    assert checked_in["_meta"]["measured_counts"] == fresh["_meta"]["measured_counts"]


def test_93114_is_guilty_by_live_rows_not_a_code_list() -> None:
    records = emitter.load_records(emitter.DEFAULT_CANONICAL)
    record = next(r for r in records if r[basis.CODE_FIELD] == "93114")

    assert basis.besar_risks(record) == ()
    assert basis.open_supporting_tier_absent(record) is True
    assert basis.derive_verdict_state(record) == "provisional"


def test_restricted_and_proposed_closed_live_statuses_are_provisional() -> None:
    records = emitter.load_records(emitter.DEFAULT_CANONICAL)
    by_code = {record[basis.CODE_FIELD]: record for record in records}

    assert (by_code["86102"].get("l4_bali") or {}).get("status") == "TERBATAS"
    assert basis.derive_verdict_state(by_code["86102"]) == "provisional"
    assert (by_code["68111"].get("l4_bali") or {}).get("status") == (
        "CHIUSO_BALI_PROPOSTO"
    )
    assert basis.derive_verdict_state(by_code["68111"]) == "provisional"


def test_01112_open_family_with_live_support_is_innocent() -> None:
    records = emitter.load_records(emitter.DEFAULT_CANONICAL)
    record = next(r for r in records if r[basis.CODE_FIELD] == "01112")

    assert (record.get("l4_bali") or {}).get("status") == "OK_or_HIGHER_RISK"
    assert basis.besar_risks(record) == ("Menengah Tinggi", "Menengah Tinggi")
    assert basis.open_supporting_tier_absent(record) is False
    assert basis.derive_verdict_state(record) == "open"


def test_healthy_aperto_with_own_besar_high_tier_is_innocent() -> None:
    healthy = _record("99991", rows=[_row(["Besar"], "Menengah Tinggi")])

    assert basis.besar_risks(healthy) == ("Menengah Tinggi",)
    assert basis.open_supporting_tier_absent(healthy) is False
    assert basis.derive_verdict_state(healthy) == "open"


def test_compiler_applies_guilt_and_innocence_without_flipping_blocked(
    tmp_path: Path,
) -> None:
    unknown = _record(
        "99992",
        status="NON_CLASSIFICABILE",
        blocked=True,
        confidence="MEDIUM",
        needs_review=True,
        rows=[],
    )
    guilty = _record(
        "99993",
        confidence="LOW",
        needs_review=True,
        rows=[_row(["Mikro", "Kecil", "Menengah"], "Menengah Rendah")],
    )
    innocent = _record("99994")
    canonical, spec = _fixture_files(tmp_path, [unknown, guilty, innocent])

    assert _run(canonical, spec, apply=True) == 0
    records = json.loads(canonical.read_text(encoding="utf-8"))["data"]
    by_code = {record[basis.CODE_FIELD]: record for record in records}
    assert by_code["99992"]["l4_bali"]["verdict_state"] == "unknown"
    assert by_code["99992"]["l4_bali"]["blocked"] is True
    assert by_code["99993"]["l4_bali"]["verdict_state"] == "provisional"
    assert by_code["99994"]["l4_bali"]["verdict_state"] == "open"


def test_compiler_is_idempotent_and_second_apply_preserves_bytes(tmp_path: Path) -> None:
    canonical, spec = _fixture_files(tmp_path, [_record("99995")])
    assert _run(canonical, spec, apply=True) == 0
    after_first = canonical.read_bytes()
    assert _run(canonical, spec, apply=True) == 0
    assert canonical.read_bytes() == after_first


def test_noop_apply_skips_consumer_sync_and_sidecar(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    canonical, spec = _fixture_files(tmp_path, [_record("99988")])
    assert _run(canonical, spec, apply=True) == 0

    monkeypatch.setattr(cure, "DEFAULT_CANONICAL", canonical)

    def fail_if_called() -> None:
        raise AssertionError("pure-noop apply must not reconcile consumers")

    monkeypatch.setattr(cure, "run_sync_script", fail_if_called)
    monkeypatch.setattr(cure, "update_sidecar", fail_if_called)

    assert _run(canonical, spec, apply=True) == 0


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    canonical, spec = _fixture_files(tmp_path, [_record("99996")])
    before = canonical.read_bytes()
    assert _run(canonical, spec) == 0
    assert canonical.read_bytes() == before


def test_refuses_spec_entry_that_would_flip_blocked_true_to_false(
    tmp_path: Path,
) -> None:
    record = _record(
        "99997", status="NON_CLASSIFICABILE", blocked=True, rows=[]
    )
    canonical, spec_path = _fixture_files(tmp_path, [record])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["codes"]["99997"]["patch"]["blocked"] = False
    _write(spec_path, spec)
    before = canonical.read_bytes()

    assert _run(canonical, spec_path, apply=True) == cure.EXIT_REFUSED
    assert canonical.read_bytes() == before


def test_refuses_existing_verdict_blocked_to_open(tmp_path: Path) -> None:
    record = _record("99998", verdict_state="blocked")
    canonical, spec = _fixture_files(tmp_path, [record])
    before = canonical.read_bytes()

    assert _run(canonical, spec, apply=True) == cure.EXIT_REFUSED
    assert canonical.read_bytes() == before


def test_facts_basis_guard_refuses_licensing_tier_mutation(tmp_path: Path) -> None:
    original = _record("99999")
    canonical, spec = _fixture_files(tmp_path, [original])
    mutated = copy.deepcopy(original)
    mutated["per_skala"] = [_row(["Mikro", "Kecil", "Menengah"], "Tinggi")]
    _write(canonical, {"data": [mutated]})
    before = canonical.read_bytes()

    assert _run(canonical, spec, apply=True) == cure.EXIT_REFUSED
    assert canonical.read_bytes() == before


def test_facts_basis_guard_refuses_duplicate_besar_row_deletion(
    tmp_path: Path,
) -> None:
    duplicate = _row(["Besar"], "Tinggi")
    original = _record("99990", rows=[duplicate, copy.deepcopy(duplicate)])
    canonical, spec = _fixture_files(tmp_path, [original])
    mutated = copy.deepcopy(original)
    mutated["per_skala"] = [duplicate]
    _write(canonical, {"data": [mutated]})
    before = canonical.read_bytes()

    assert _run(canonical, spec, apply=True) == cure.EXIT_REFUSED
    assert canonical.read_bytes() == before


def test_empty_tier_besar_row_is_provisional() -> None:
    record = _record("99989", rows=[_row(["Besar"], "")])

    assert basis.besar_risks(record) == ("",)
    assert basis.open_supporting_tier_absent(record) is True
    assert basis.derive_verdict_state(record) == "provisional"
