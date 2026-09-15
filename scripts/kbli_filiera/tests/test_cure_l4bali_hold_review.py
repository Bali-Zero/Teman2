"""TDD for cure_l4bali_hold_review.py — the 12 no-Besar-row hold codes.

Runs against the REAL canonical (read-only checks) and against synthetic
in-memory fixtures for the mutating checks (never writes the real file from
a test — the compiler's own --apply path is exercised via the CLI in the
lane's manual run, not from pytest).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = Path(__file__).resolve().parents[1]
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

import cure_l4bali_hold_review as cure  # noqa: E402

REPO_ROOT = _FILIERA_DIR.parents[1]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC_PATH = _FILIERA_DIR / "cure_specs" / "l4bali_hold_review_2026_09_15.json"

CODES = [
    "38110",
    "55202",
    "55300",
    "56102",
    "56304",
    "56306",
    "70201",
    "73300",
    "74199",
    "79901",
    "79902",
    "86995",
]


def _canonical_by_code() -> dict[str, dict]:
    data = json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]
    return {r["kode_kbli_2025"]: r for r in data}


def _spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def test_spec_names_exactly_the_12_codes():
    spec = _spec()
    assert sorted(spec["codes"].keys()) == sorted(CODES)


def test_format_scales_orders_by_business_size_not_alphabet():
    assert cure.format_scales({"Menengah", "Kecil", "Mikro"}) == "Mikro, Kecil and Menengah"
    assert cure.format_scales({"Kecil", "Mikro"}) == "Mikro and Kecil"
    assert cure.format_scales({"Mikro"}) == "Mikro"


def test_format_scales_rejects_unknown_value():
    with pytest.raises(cure.CureError):
        cure.format_scales({"Mikro", "Raksasa"})


@pytest.mark.parametrize(
    "code,expected_scales,expected_tier",
    [
        ("73300", "Mikro, Kecil and Menengah", "Rendah"),
        ("38110", "Mikro, Kecil and Menengah", "Menengah Rendah"),
        ("56102", "Mikro and Kecil", "Menengah Rendah"),
    ],
)
def test_measure_scales_and_tier_on_real_data(code, expected_scales, expected_tier):
    by_code = _canonical_by_code()
    scales, tier = cure.measure_scales_and_tier(code, by_code[code])
    assert scales == expected_scales
    assert tier == expected_tier


def test_measure_scales_and_tier_all_12_have_a_single_tier():
    """Guard precondition: Template H names ONE tier. If a future re-ingestion
    splits any of the 12 into multiple risk tiers, this must fail loudly."""
    by_code = _canonical_by_code()
    for code in CODES:
        scales, tier = cure.measure_scales_and_tier(code, by_code[code])
        assert scales, f"{code}: empty scales"
        assert tier, f"{code}: empty tier"
        assert "," not in tier, f"{code}: tier {tier!r} looks like more than one value"


def test_build_new_reason_never_matches_the_withdrawn_inference_ban():
    spec = _spec()
    template = spec["template"]
    by_code = _canonical_by_code()
    for code in CODES:
        scales, tier = cure.measure_scales_and_tier(code, by_code[code])
        sector = spec["codes"][code]["sector"]
        reason = cure.build_new_reason(template, sector, scales, tier)
        assert not cure.WITHDRAWN_CLAIM.search(reason), (code, reason)


def test_spec_pristine_expectations_match_current_canonical_before_cure():
    """The spec's `expected_*` fields were captured FROM this canonical. If this
    fails, the canonical has drifted since the spec was authored and the real
    --apply run would (correctly) refuse with a CureError — this test says so
    before that happens on the real file."""
    spec = _spec()
    by_code = _canonical_by_code()
    for code in CODES:
        entry = spec["codes"][code]
        plan = cure.evaluate_code(code, entry, spec["template"], by_code)
        assert plan.status in ("apply", "already_cured"), (code, plan.status, plan.detail)


def test_status_and_blocked_are_never_in_the_new_l4_keys_touched():
    """The plan only ever rewrites reason/confidence/needs_review; status and
    blocked must be byte-identical to what the record already carries."""
    spec = _spec()
    by_code = _canonical_by_code()
    for code in CODES:
        entry = spec["codes"][code]
        original_status = by_code[code]["l4_bali"]["status"]
        original_blocked = by_code[code]["l4_bali"]["blocked"]
        plan = cure.evaluate_code(code, entry, spec["template"], by_code)
        if plan.new_l4 is not None:
            assert plan.new_l4["status"] == original_status
            assert plan.new_l4["blocked"] == original_blocked


def test_evaluate_code_raises_on_status_or_blocked_drift():
    by_code = _canonical_by_code()
    record = copy.deepcopy(by_code["38110"])
    record["l4_bali"]["blocked"] = False  # simulate drift
    fake_by_code = {"38110": record}
    entry = _spec()["codes"]["38110"]
    with pytest.raises(cure.CureError):
        cure.evaluate_code("38110", entry, _spec()["template"], fake_by_code)


def test_evaluate_code_raises_on_unexpected_reason_drift():
    by_code = _canonical_by_code()
    record = copy.deepcopy(by_code["38110"])
    record["l4_bali"]["reason"] = "something nobody wrote"
    fake_by_code = {"38110": record}
    entry = _spec()["codes"]["38110"]
    with pytest.raises(cure.CureError):
        cure.evaluate_code("38110", entry, _spec()["template"], fake_by_code)


def test_evaluate_code_apply_sets_medium_confidence_and_needs_review():
    spec = _spec()
    by_code = _canonical_by_code()
    entry = spec["codes"]["73300"]
    plan = cure.evaluate_code("73300", entry, spec["template"], by_code)
    if plan.status == "already_cured":
        pytest.skip("already cured on this canonical")
    assert plan.status == "apply"
    new_l4 = plan.new_l4
    assert new_l4 is not None
    assert new_l4["confidence"] == "MEDIUM"
    assert new_l4["needs_review"] is True
    assert "Mikro, Kecil and Menengah scale" in new_l4["reason"]
    assert "(Rendah)" in new_l4["reason"]


def test_evaluate_code_is_idempotent_after_apply():
    """Re-running evaluate_code against an already-cured record is a no-op,
    never a CureError — the --apply CLI must be safely re-runnable."""
    spec = _spec()
    by_code = _canonical_by_code()
    entry = spec["codes"]["73300"]
    plan = cure.evaluate_code("73300", entry, spec["template"], by_code)
    cured_record = copy.deepcopy(by_code["73300"])
    if plan.new_l4 is not None:
        cured_record["l4_bali"] = plan.new_l4
    fake_by_code = {"73300": cured_record}
    plan2 = cure.evaluate_code("73300", entry, spec["template"], fake_by_code)
    assert plan2.status == "already_cured"


def test_apply_is_all_or_nothing_on_a_tmp_copy(tmp_path):
    """A run where ONE code has a problem must write NOTHING for the other 11
    — not a partial apply that then reports failure. Codex review finding:
    the first cut of this script wrote the valid subset, ran sync, updated
    the sidecar, and only THEN returned exit 1 — leaving a canonical whose
    content says success next to an exit code that says failure."""
    tmp_canonical = tmp_path / "KBLI_2025_FINAL_CLEAN.json"
    tmp_canonical.write_bytes(CANONICAL.read_bytes())
    spec = _spec()

    # This canonical may already be cured (the lane applies --apply for
    # real). Force a KNOWN state instead of assuming one: 73300 reset to the
    # spec's own pristine expectation (genuinely to_apply-eligible), 38110
    # sabotaged with an unrecognised reason (a CureError, not a no-op).
    dataset = json.loads(tmp_canonical.read_bytes())
    for record in dataset["data"]:
        code = record.get("kode_kbli_2025")
        if code == "73300":
            entry = spec["codes"]["73300"]
            record["l4_bali"]["reason"] = entry["expected_reason"]
            record["l4_bali"]["confidence"] = entry["expected_confidence"]
            record["l4_bali"]["needs_review"] = entry["expected_needs_review"]
        elif code == "38110":
            record["l4_bali"]["reason"] = "drifted — not the spec's pristine text"
    tmp_canonical.write_text(json.dumps(dataset, ensure_ascii=False, indent=2))
    sabotaged_bytes = tmp_canonical.read_bytes()

    exit_code = cure.main(
        ["--canonical", str(tmp_canonical), "--apply", "--only"] + CODES
    )
    assert exit_code == 1
    # The file on disk must be BYTE-IDENTICAL to the sabotaged input — the
    # run wrote nothing at all, for any of the 12 codes, even though 73300
    # was genuinely eligible to be cured on its own.
    assert tmp_canonical.read_bytes() == sabotaged_bytes
    reread = json.loads(tmp_canonical.read_text())
    by = {r["kode_kbli_2025"]: r for r in reread["data"]}
    assert by["73300"]["l4_bali"]["confidence"] == spec["codes"]["73300"]["expected_confidence"]
    assert by["73300"]["l4_bali"]["needs_review"] == spec["codes"]["73300"]["expected_needs_review"]


def test_check_flag_is_a_write_nothing_alias_for_dry_run(tmp_path):
    tmp_canonical = tmp_path / "KBLI_2025_FINAL_CLEAN.json"
    tmp_canonical.write_bytes(CANONICAL.read_bytes())
    before = tmp_canonical.read_bytes()
    exit_code = cure.main(["--canonical", str(tmp_canonical), "--check"])
    assert exit_code == 0
    assert tmp_canonical.read_bytes() == before


def test_check_and_apply_together_is_rejected():
    with pytest.raises(cure.CureError):
        cure.main(["--check", "--apply"])
