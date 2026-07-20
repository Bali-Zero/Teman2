"""Tests for the Batch A CALIBRATION REGISTRY v3 compiler (Lot 3 gate
sign-off condition (3) — the v3 registry re-salt).

Mirrors `test_emit_batch_calibration_v2.py` (v2)'s pattern, adapted to v3's
shape: extended gold sets (47 NEGATIVE / 8 POSITIVE-after-double-exclusion,
new salt "v3" for BOTH classes), the m1-m5 registry now carrying THREE lot
readings (Lot 1/2/3), the m3 category registry INVARIANT (zero new
categories since v2), and plaintext-never-leaks for BOTH gold classes (v3's
NEGATIVE set is no longer blind-to-conductor only — all 47 of its codes were
REVEALED as Lot-1/2/3's quarantine outcomes in their respective conductor
gate reports, but they must still never appear in the v3 artifact itself,
since the artifact commits digests only, per plan §5).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import pytest

import emit_batch_calibration as v1  # noqa: E402
import emit_batch_calibration_v2 as v2  # noqa: E402
import emit_batch_calibration_v3 as c  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _rec(code, *, l2_source=None, per_skala=None):
    r = {"kode_kbli_2025": code}
    if l2_source is not None:
        r["_l2_source"] = l2_source
    if per_skala is not None:
        r["per_skala"] = per_skala
    return r


# --- (a) eligibility predicate v3: guilt + innocence + Lot-1+Lot-2 exclusion


def test_eligible_v3_requires_both_l2_source_and_per_skala():
    guilty = _rec("11111", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
    assert c.eligible_positive_codes_v3([guilty]) == ["11111"]


def test_eligible_v3_ineligible_missing_l2_source():
    innocent = _rec("22222", l2_source=None, per_skala=[{"x": 1}])
    assert c.eligible_positive_codes_v3([innocent]) == []


def test_eligible_v3_ineligible_empty_per_skala():
    innocent = _rec("33333", l2_source="OSS_RBA_resiko_2025", per_skala=[])
    assert c.eligible_positive_codes_v3([innocent]) == []


def test_eligible_v3_excludes_lot1_revealed_positive_controls():
    """A code otherwise eligible but already burned as a Lot-1 POSITIVE
    reveal must NOT reappear as a v3-eligible candidate."""
    burned_code = v2.LOT1_POSITIVE_REVEALED[0]
    r = _rec(burned_code, l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
    assert c.eligible_positive_codes_v3([r]) == []


def test_eligible_v3_excludes_lot2_revealed_positive_controls():
    """A code otherwise eligible but already burned as a Lot-2 POSITIVE
    reveal (Appendix A) must NOT reappear as a v3-eligible candidate —
    including 10433, which is ADDITIONALLY a disqualified true finding."""
    for burned_code in c.LOT2_POSITIVE_REVEALED:
        r = _rec(burned_code, l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        assert c.eligible_positive_codes_v3([r]) == [], f"{burned_code} leaked into v3 eligible pool"


def test_eligible_v3_keeps_non_burned_eligible_code():
    r = _rec("99999", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
    assert "99999" not in v2.LOT1_POSITIVE_REVEALED
    assert "99999" not in c.LOT2_POSITIVE_REVEALED
    assert c.eligible_positive_codes_v3([r]) == ["99999"]


def test_lot1_and_lot2_positive_revealed_are_disjoint():
    assert set(v2.LOT1_POSITIVE_REVEALED).isdisjoint(set(c.LOT2_POSITIVE_REVEALED))


# --- (b) deterministic selection: same inputs => same digests -------------


def test_positive_v3_selection_deterministic_across_runs():
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 40)
    ]
    manifest_digest = "a" * 64
    first = c.select_positive_digests_v3(records, manifest_digest)
    second = c.select_positive_digests_v3(records, manifest_digest)
    assert first == second
    assert first == sorted(first)


def test_artifact_v3_byte_identical_on_double_render():
    ctx1 = _synthetic_ctx()
    ctx2 = _synthetic_ctx()
    assert c.render_markdown(ctx1) == c.render_markdown(ctx2)
    assert c.render_json(ctx1) == c.render_json(ctx2)


# --- (c) negative-list correctness: recompute independently, salt "v3" ----


def test_negative_v3_digest_matches_recomputed_phase1_code_68112():
    manifest_digest = "deadbeef" * 8
    digests = c.negative_digests_v3(manifest_digest)
    expected = hashlib.sha256(f"68112|{manifest_digest}|v3".encode()).hexdigest()
    assert expected in digests


def test_negative_v3_digest_matches_recomputed_lot1_code_01700():
    manifest_digest = "deadbeef" * 8
    digests = c.negative_digests_v3(manifest_digest)
    expected = hashlib.sha256(f"01700|{manifest_digest}|v3".encode()).hexdigest()
    assert expected in digests


def test_negative_v3_digest_matches_recomputed_lot2_code_47771():
    manifest_digest = "deadbeef" * 8
    digests = c.negative_digests_v3(manifest_digest)
    expected = hashlib.sha256(f"47771|{manifest_digest}|v3".encode()).hexdigest()
    assert expected in digests


def test_negative_v3_digest_matches_recomputed_lot3_code_64940():
    manifest_digest = "deadbeef" * 8
    digests = c.negative_digests_v3(manifest_digest)
    expected = hashlib.sha256(f"64940|{manifest_digest}|v3".encode()).hexdigest()
    assert expected in digests


def test_negative_v3_digests_match_all_recomputed_codes():
    manifest_digest = "cafef00d" * 8
    digests = set(c.negative_digests_v3(manifest_digest))
    all_codes = (
        set(v1.NEGATIVE_CONTROL_CODES)
        | set(v2.LOT1_QUARANTINED_CODES)
        | set(c.LOT2_QUARANTINED_CODES)
        | set(c.LOT3_QUARANTINED_CODES)
    )
    for code in all_codes:
        assert hashlib.sha256(f"{code}|{manifest_digest}|v3".encode()).hexdigest() in digests


def test_negative_v3_uses_v3_salt_not_v2_salt():
    """A v3 NEGATIVE digest must NOT collide with the corresponding v2
    (salt="v2") digest for the same code — new salt, new digest space."""
    manifest_digest = "1234abcd" * 8
    v2_digest_68112 = hashlib.sha256(f"68112|{manifest_digest}|v2".encode()).hexdigest()
    v3_digests = set(c.negative_digests_v3(manifest_digest))
    assert v2_digest_68112 not in v3_digests


# --- (d) gold set v3 shape: 47 NEGATIVE + 8 POSITIVE, all 64-hex ----------


def test_negative_control_v3_pin_is_8_plus_13_plus_13_plus_13_equals_47_unique_codes():
    phase1 = set(v1.NEGATIVE_CONTROL_CODES)
    lot1 = set(v2.LOT1_QUARANTINED_CODES)
    lot2 = set(c.LOT2_QUARANTINED_CODES)
    lot3 = set(c.LOT3_QUARANTINED_CODES)
    assert len(phase1) == 8
    assert len(lot1) == 13
    assert len(lot2) == 13
    assert len(lot3) == 13
    assert phase1.isdisjoint(lot1)
    assert phase1.isdisjoint(lot2)
    assert phase1.isdisjoint(lot3)
    assert lot1.isdisjoint(lot2)
    assert lot1.isdisjoint(lot3)
    assert lot2.isdisjoint(lot3)
    assert len(phase1 | lot1 | lot2 | lot3) == 47


def test_lot2_quarantined_pin_is_exactly_13_codes():
    assert c.LOT2_QUARANTINED_CODES == (
        "42999", "47771", "49233", "49296", "50113",
        "52103", "52105", "52211", "52219", "52232",
        "52239", "52299", "59131",
    )


def test_lot3_quarantined_pin_is_exactly_13_codes():
    assert c.LOT3_QUARANTINED_CODES == (
        "60101", "60103", "60201", "60203", "60311",
        "61905", "61909", "64110", "64220", "64320",
        "64330", "64920", "64940",
    )


def test_lot2_positive_revealed_pin_is_exactly_8_burned_codes():
    assert c.LOT2_POSITIVE_REVEALED == (
        "10433", "46329", "46631", "42204", "06202", "23129", "01285", "47711",
    )


def test_gold_sets_v3_are_47_and_8_valid_hex():
    manifest_digest = "0123456789abcdef" * 4
    neg = c.negative_digests_v3(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos = c.select_positive_digests_v3(records, manifest_digest)
    assert len(neg) == 47
    assert len(pos) == 8
    for d in neg + pos:
        assert HEX64.match(d), f"not 64-hex: {d}"


def test_too_few_eligible_v3_codes_raises():
    manifest_digest = "b" * 64
    records = [_rec("11111", l2_source="OSS_X", per_skala=[{"x": 1}])]  # only 1, need 8
    with pytest.raises(c.CalibrationError):
        c.select_positive_digests_v3(records, manifest_digest)


def test_too_few_eligible_v3_after_all_candidates_burned_raises():
    manifest_digest = "b" * 64
    # 8 eligible candidates, but all 8 are the exact Lot-2 burned codes -> 0 left
    records = [
        _rec(code, l2_source="OSS_X", per_skala=[{"x": 1}])
        for code in c.LOT2_POSITIVE_REVEALED
    ]
    with pytest.raises(c.CalibrationError):
        c.select_positive_digests_v3(records, manifest_digest)


# --- (e) m1-m5 v3 registry: exact numeric/state values, 3-lot readings ----


def test_control_limits_v3_m1_three_lot_readings():
    cl = _synthetic_ctx()["control_limits"]
    m1 = cl["m1_blind_concordance"]
    assert m1["floor"] == 0.75
    assert m1["lot1_reading"] == 0.385
    assert m1["lot1_state"] == "declared-breach"
    assert m1["lot2_reading"] == 1.00
    assert m1["lot2_state"] == "measured, no breach"
    assert m1["lot3_reading"] == 1.00
    assert m1["lot3_state"] == "measured, no breach"
    assert "cross-family" in m1["principle"]
    assert "scar W100" in m1["principle"]


def test_control_limits_v3_m2_three_lot_readings_all_declared_breach():
    cl = _synthetic_ctx()["control_limits"]
    m2 = cl["m2_certification_rate"]
    assert m2["floor"] == 0.20
    assert m2["ceiling"] == 0.85
    assert m2["lot1_reading"] == 0.000
    assert m2["lot2_reading"] == 0.000
    assert m2["lot3_reading"] == 0.000
    assert m2["state"] == "declared-breach"


def test_control_limits_v3_m3_categories_invariant_from_v2():
    cl = _synthetic_ctx()["control_limits"]
    assert cl["m3_refutation_categories"]["categories"] == list(v2.REFUTATION_CATEGORIES_V2)
    assert cl["m3_refutation_categories"]["categories"] == [
        "code_collision",
        "illegitimate_inheritance",
        "wrong_authority_level",
        "source_absent_in_vault",
        "payload_cross_contamination",
        "unresolvable_source_pointer",
        "mapping_metadata_false",
    ]
    assert cl["m3_refutation_categories"]["renamed"] == {
        "from": "phantom_source_pointer",
        "to": "unresolvable_source_pointer",
        "note": "text-hunt evidence cannot establish nonexistence (plan A-5 terminology note)",
    }


def test_control_limits_v3_m4_invariant_from_v1():
    cl = _synthetic_ctx()["control_limits"]
    assert cl["m4_tokens_per_dossier"]["ceiling"] == 400000
    assert cl["m4_tokens_per_dossier"]["pilot_avg"] == v1.PILOT_A1["avg_tokens_per_code"]
    assert cl["m4_tokens_per_dossier"]["pilot_max"] == v1.PILOT_A1["max_tokens_per_code"]


def test_control_limits_v3_m5_neg_and_pos_disqualified_rulings():
    cl = _synthetic_ctx()["control_limits"]
    m5 = cl["m5_gold_set_hit_rate"]
    assert m5["required"] == 1.00
    assert "per-ancestor image-grade" in m5["neg_miss_ruling"]
    assert "49213" in m5["neg_miss_ruling"]
    assert "DISQUALIFIED" in m5["pos_disqualified_ruling"]
    assert "10433" in m5["pos_disqualified_ruling"]


def test_m3_categories_v3_is_identical_set_to_v2_zero_new():
    v2_cats = set(v2.REFUTATION_CATEGORIES_V2)
    v3_cats = set(c.REFUTATION_CATEGORIES_V3)
    assert v2_cats == v3_cats
    assert len(v3_cats) == 7


def test_control_limits_v3_exact_strings_in_rendered_output():
    ctx = _synthetic_ctx()
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for text in (md, js):
        for needle in (
            "0.75", "0.385", "0.20", "0.85", "0.000", "400000", "1.00",
            "declared-breach",
            "code_collision", "illegitimate_inheritance", "wrong_authority_level",
            "source_absent_in_vault", "payload_cross_contamination",
            "unresolvable_source_pointer", "mapping_metadata_false",
        ):
            assert needle in text, f"{needle!r} missing from rendered v3 artifact"
        assert "phantom_source_pointer" in text  # only via the 'renamed.from' note


def test_pos_preverification_required_field_present_and_true():
    ctx = _synthetic_ctx()
    pos = ctx["gold_sets"]["positive_control"]
    assert pos["pos_preverification_required"] is True
    assert "BOTH crosswalk directions" in pos["pos_preverification_rule"]
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    assert "pos_preverification_required" in js
    assert "pos_preverification_required" in md
    assert "BOTH crosswalk directions" in md


def test_lot_outcome_blocks_pinned_in_rendered_output():
    ctx = _synthetic_ctx()
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for text in (md, js):
        assert c.CONDUCTOR_GATE_REPORT_PATH in text  # Lot 1
        assert c.LOT2_GATE_REPORT_PATH in text
        assert c.LOT3_GATE_REPORT_PATH in text
        assert "#2753" in text
        assert "#2768" in text


def test_sign_off_v3_pinned_literal():
    assert c.CONDUCTOR_SIGN_OFF == "SIGNED — Fable conductor session (MANDATO S2, post-Lot-3-GO), 2026-07-19"
    assert c.PINNED_DATE == "2026-07-19"


# --- (f) plaintext gold codes never leak into the rendered artifact --------


def test_negative_plaintext_never_appears_in_rendered_v3_artifact():
    """The committed gold DIGEST list must never spell out the NEGATIVE
    plaintext codes. THREE deliberate, spec-mandated exceptions, each
    already publicly revealed post-lot-close in its own SIGNED conductor
    gate report (plan §5 reveal rule) and cited by name only in prose,
    never inside the gold-list section itself:
      - '49213' in the m5 neg_miss_ruling prose (carried verbatim from v2)
        as the per-ancestor-restore historical precedent.
      - '10433' in the m5 pos_disqualified_ruling prose (it is a POSITIVE
        control precedent, not a member of the NEGATIVE digest list at all).
      - '64940' in the m1 Lot-3 note prose, naming the flagship wrong-parent
        case (true ancestor 64992 independently re-derived cross-family) —
        it IS also a NEGATIVE-list member (Lot-3 quarantine), so it is
        checked for gold-section leakage same as the others."""
    manifest_digest = "5" * 64
    neg_digests = c.negative_digests_v3(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos_digests = c.select_positive_digests_v3(records, manifest_digest)
    ctx = c.build_context(
        canonical_revision="0" * 40,
        manifest_digest=manifest_digest,
        membership_sha256="2" * 64,
        eligible_population_before_exclusion=len(records),
        eligible_population_after_lot1_exclusion=len(records),
        eligible_population_after_exclusion=len(records),
        positive_digests=pos_digests,
        neg_digests=neg_digests,
    )
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    all_neg_plaintext = (
        list(v1.NEGATIVE_CONTROL_CODES)
        + list(v2.LOT1_QUARANTINED_CODES)
        + list(c.LOT2_QUARANTINED_CODES)
        + list(c.LOT3_QUARANTINED_CODES)
    )
    assert "10433" not in all_neg_plaintext, "10433 is a POS-burned code, not a NEG-list member"
    # 49213 and 64940 ARE genuine NEG-list members (phase-1 and Lot-3
    # respectively) deliberately cited by name in control_limits prose
    # (m5 neg_miss_ruling / m1 Lot-3 note) — they must never appear inside
    # the gold_sets digest-list section itself, only in that prose.
    deliberate_neg_precedent_citations = {"49213", "64940"}
    for code in all_neg_plaintext:
        if code in deliberate_neg_precedent_citations:
            continue
        assert code not in md, f"NEGATIVE control {code!r} leaked into v3 markdown"
        assert code not in js, f"NEGATIVE control {code!r} leaked into v3 json"
    assert "49213" in md and "49213" in js
    assert "64940" in md and "64940" in js
    gold_section_md = md.split("## Gold sets v3")[1].split("## Lot 1 outcome")[0]
    assert "49213" not in gold_section_md, "49213 leaked into the v3 gold digest-list section"
    assert "64940" not in gold_section_md, "64940 leaked into the v3 gold digest-list section"
    gold_section_json = json.dumps(json.loads(js)["gold_sets"])
    assert "49213" not in gold_section_json
    assert "64940" not in gold_section_json
    # 10433 IS expected inside the gold_sets section (POS burn-note prose,
    # documenting its disqualification) but must NEVER appear inside the
    # negative_control subsection (it is not a NEG code) nor as a fabricated
    # entry in either digest LIST (both digest lists are 64-hex only).
    gs = json.loads(js)["gold_sets"]
    assert "10433" in gold_section_md, "10433 (POS burn-note) unexpectedly absent from gold_sets section"
    assert "10433" not in json.dumps(gs["negative_control"]), "10433 leaked into the NEGATIVE control subsection"
    assert "10433" not in gs["positive_control"]["digests"] and all(
        "10433" not in d for d in gs["positive_control"]["digests"]
    ), "10433 leaked into the POSITIVE digest list itself"


def test_positive_plaintext_never_appears_in_rendered_v3_artifact():
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    records = _load_real_canonical()
    eligible = c.eligible_positive_codes_v3(records)
    pairs = sorted((c._digest_v3(code, manifest_digest, c.POSITIVE_SALT), code) for code in eligible)
    plaintext_positive_codes = [code for _, code in pairs[:8]]

    membership_sha256 = c._sha256_file(c.MEMBERSHIP_PATH)
    positive_digests = c.select_positive_digests_v3(records, manifest_digest)
    neg_digests = c.negative_digests_v3(manifest_digest)
    ctx = c.build_context(
        canonical_revision="0" * 40,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population_before_exclusion=len(v1.eligible_positive_codes(records)),
        eligible_population_after_lot1_exclusion=len(v2.eligible_positive_codes_v2(records)),
        eligible_population_after_exclusion=len(eligible),
        positive_digests=positive_digests,
        neg_digests=neg_digests,
    )
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for code in plaintext_positive_codes:
        assert code not in md, f"positive control {code!r} leaked into v3 markdown"
        assert code not in js, f"positive control {code!r} leaked into v3 json"
    # and none of the plaintext positives selected are among the burned reveals
    assert set(plaintext_positive_codes).isdisjoint(v2.LOT1_POSITIVE_REVEALED)
    assert set(plaintext_positive_codes).isdisjoint(c.LOT2_POSITIVE_REVEALED)


# --- (g) fencing: reused verbatim from v1/v2, sanity-checked here ----------


def test_fencing_reused_from_v1_aborts_on_mutated_canonical(tmp_path, monkeypatch):
    mutated = tmp_path / "mutated-canonical.json"
    mutated.write_text('{"data": [{"kode_kbli_2025": "00000"}]}', encoding="utf-8")
    monkeypatch.setattr(v1, "CANONICAL", mutated)
    with pytest.raises(v1.CalibrationError):
        v1._canonical_revision()


def test_v3_reuses_v2_and_v1_calibration_error_class():
    assert c.CalibrationError is v2.CalibrationError
    assert c.CalibrationError is v1.CalibrationError


# --- integration: real repo inputs -----------------------------------------


def test_end_to_end_against_real_repo_inputs():
    canonical_revision = v1._canonical_revision()
    fenced_blob = v1._fenced_canonical_blob()
    membership = v1._load_membership()
    v1._validate_membership_pin(membership, fenced_blob)
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    membership_sha256 = c._sha256_file(c.MEMBERSHIP_PATH)
    records = _load_real_canonical()
    eligible_before = v1.eligible_positive_codes(records)
    eligible_after_lot1 = v2.eligible_positive_codes_v2(records)
    eligible_after = c.eligible_positive_codes_v3(records)
    assert len(eligible_after) >= 8
    pos = c.select_positive_digests_v3(records, manifest_digest)
    neg = c.negative_digests_v3(manifest_digest)
    ctx = c.build_context(
        canonical_revision=canonical_revision,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population_before_exclusion=len(eligible_before),
        eligible_population_after_lot1_exclusion=len(eligible_after_lot1),
        eligible_population_after_exclusion=len(eligible_after),
        positive_digests=pos,
        neg_digests=neg,
    )
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    assert md.endswith("\n") and not md.endswith("\n\n")
    assert js.endswith("\n") and not js.endswith("\n\n")
    assert c.CONDUCTOR_SIGN_OFF in md
    assert c.CONDUCTOR_SIGN_OFF in js


# --- helpers -----------------------------------------------------------


def _load_real_canonical():
    return json.loads(c.CANONICAL.read_text(encoding="utf-8"))["data"]


def _synthetic_ctx():
    manifest_digest = "1" * 64
    neg = c.negative_digests_v3(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos = c.select_positive_digests_v3(records, manifest_digest)
    return c.build_context(
        canonical_revision="0" * 40,
        manifest_digest=manifest_digest,
        membership_sha256="2" * 64,
        eligible_population_before_exclusion=len(records),
        eligible_population_after_lot1_exclusion=len(records),
        eligible_population_after_exclusion=len(records),
        positive_digests=pos,
        neg_digests=neg,
    )
