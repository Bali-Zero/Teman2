"""Tests for the Batch A CALIBRATION REGISTRY v2 compiler (plan §8 A-6(c)).

Mirrors `test_emit_batch_calibration.py` (v1)'s pattern, adapted to v2's
shape: extended gold sets (21 NEGATIVE / 8 POSITIVE-after-exclusion, new
salts "v2"/"v2-lot2"), the m1-m5 registry with Lot-1 declared-BREACH state,
the m3 category rename, and plaintext-never-leaks for BOTH gold classes
(v2's NEGATIVE set is no longer blind-to-conductor only — 13 of its 21
codes were REVEALED as Lot-1's quarantine outcome in the conductor gate
report, but they must still never appear in the v2 artifact itself, since
the artifact commits digests only, per plan §5).
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
import emit_batch_calibration_v2 as c  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _rec(code, *, l2_source=None, per_skala=None):
    r = {"kode_kbli_2025": code}
    if l2_source is not None:
        r["_l2_source"] = l2_source
    if per_skala is not None:
        r["per_skala"] = per_skala
    return r


# --- (a) eligibility predicate v2: guilt + innocence + Lot-1-reveal exclusion


def test_eligible_v2_requires_both_l2_source_and_per_skala():
    guilty = _rec("11111", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
    assert c.eligible_positive_codes_v2([guilty]) == ["11111"]


def test_eligible_v2_ineligible_missing_l2_source():
    innocent = _rec("22222", l2_source=None, per_skala=[{"x": 1}])
    assert c.eligible_positive_codes_v2([innocent]) == []


def test_eligible_v2_ineligible_empty_per_skala():
    innocent = _rec("33333", l2_source="OSS_RBA_resiko_2025", per_skala=[])
    assert c.eligible_positive_codes_v2([innocent]) == []


def test_eligible_v2_excludes_lot1_revealed_positive_controls():
    """A code otherwise eligible but already burned as a Lot-1 POSITIVE
    reveal must NOT reappear as a v2-eligible candidate."""
    burned_code = c.LOT1_POSITIVE_REVEALED[0]
    r = _rec(burned_code, l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
    assert c.eligible_positive_codes_v2([r]) == []


def test_eligible_v2_keeps_non_burned_eligible_code():
    r = _rec("99999", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
    assert "99999" not in c.LOT1_POSITIVE_REVEALED
    assert c.eligible_positive_codes_v2([r]) == ["99999"]


# --- (b) deterministic selection: same inputs => same digests -------------


def test_positive_v2_selection_deterministic_across_runs():
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 40)
    ]
    manifest_digest = "a" * 64
    first = c.select_positive_digests_v2(records, manifest_digest)
    second = c.select_positive_digests_v2(records, manifest_digest)
    assert first == second
    assert first == sorted(first)


def test_artifact_v2_byte_identical_on_double_render():
    ctx1 = _synthetic_ctx()
    ctx2 = _synthetic_ctx()
    assert c.render_markdown(ctx1) == c.render_markdown(ctx2)
    assert c.render_json(ctx1) == c.render_json(ctx2)


# --- (c) negative-list correctness: recompute independently, salt "v2" ----


def test_negative_v2_digest_matches_recomputed_phase1_code_68112():
    manifest_digest = "deadbeef" * 8
    digests = c.negative_digests_v2(manifest_digest)
    expected = hashlib.sha256(f"68112|{manifest_digest}|v2".encode()).hexdigest()
    assert expected in digests


def test_negative_v2_digest_matches_recomputed_lot1_code_01700():
    manifest_digest = "deadbeef" * 8
    digests = c.negative_digests_v2(manifest_digest)
    expected = hashlib.sha256(f"01700|{manifest_digest}|v2".encode()).hexdigest()
    assert expected in digests


def test_negative_v2_digests_match_all_recomputed_codes():
    manifest_digest = "cafef00d" * 8
    digests = set(c.negative_digests_v2(manifest_digest))
    all_codes = set(v1.NEGATIVE_CONTROL_CODES) | set(c.LOT1_QUARANTINED_CODES)
    for code in all_codes:
        assert hashlib.sha256(f"{code}|{manifest_digest}|v2".encode()).hexdigest() in digests


def test_negative_v2_uses_v2_salt_not_v1_salt():
    """A v2 NEGATIVE digest must NOT collide with the corresponding v1
    (unsalted) digest for the same code — new salt, new digest space."""
    manifest_digest = "1234abcd" * 8
    v1_digest_68112 = hashlib.sha256(f"68112|{manifest_digest}".encode()).hexdigest()
    v2_digests = set(c.negative_digests_v2(manifest_digest))
    assert v1_digest_68112 not in v2_digests


# --- (d) gold set v2 shape: 21 NEGATIVE + 8 POSITIVE, all 64-hex ----------


def test_negative_control_v2_pin_is_8_plus_13_equals_21_unique_codes():
    phase1 = set(v1.NEGATIVE_CONTROL_CODES)
    lot1 = set(c.LOT1_QUARANTINED_CODES)
    assert len(phase1) == 8
    assert len(lot1) == 13
    assert phase1.isdisjoint(lot1)
    assert len(phase1 | lot1) == 21


def test_lot1_positive_revealed_pin_is_exactly_8_burned_codes():
    assert c.LOT1_POSITIVE_REVEALED == (
        "47401", "32902", "46737", "28262", "36002", "47732", "50121", "46204",
    )


def test_gold_sets_v2_are_21_and_8_valid_hex():
    manifest_digest = "0123456789abcdef" * 4
    neg = c.negative_digests_v2(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos = c.select_positive_digests_v2(records, manifest_digest)
    assert len(neg) == 21
    assert len(pos) == 8
    for d in neg + pos:
        assert HEX64.match(d), f"not 64-hex: {d}"


def test_too_few_eligible_v2_codes_raises():
    manifest_digest = "b" * 64
    records = [_rec("11111", l2_source="OSS_X", per_skala=[{"x": 1}])]  # only 1, need 8
    with pytest.raises(c.CalibrationError):
        c.select_positive_digests_v2(records, manifest_digest)


def test_too_few_eligible_v2_after_all_candidates_burned_raises():
    manifest_digest = "b" * 64
    # 8 eligible candidates, but all 8 are the exact Lot-1 burned codes -> 0 left
    records = [
        _rec(code, l2_source="OSS_X", per_skala=[{"x": 1}])
        for code in c.LOT1_POSITIVE_REVEALED
    ]
    with pytest.raises(c.CalibrationError):
        c.select_positive_digests_v2(records, manifest_digest)


# --- (e) m1-m5 v2 registry: exact numeric/state values ---------------------


def test_control_limits_v2_exact_values():
    cl = _synthetic_ctx()["control_limits"]
    assert cl["m1_blind_concordance"]["floor"] == 0.75
    assert cl["m1_blind_concordance"]["lot1_reading"] == 0.385
    assert cl["m1_blind_concordance"]["state"] == "declared-breach"
    assert cl["m2_certification_rate"]["floor"] == 0.20
    assert cl["m2_certification_rate"]["ceiling"] == 0.85
    assert cl["m2_certification_rate"]["lot1_reading"] == 0.000
    assert cl["m2_certification_rate"]["state"] == "declared-breach"
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
    assert cl["m4_tokens_per_dossier"]["ceiling"] == 400000
    # m4 pilot baseline is INVARIANT from v1 — same object, never re-derived.
    assert cl["m4_tokens_per_dossier"]["pilot_avg"] == v1.PILOT_A1["avg_tokens_per_code"]
    assert cl["m4_tokens_per_dossier"]["pilot_max"] == v1.PILOT_A1["max_tokens_per_code"]
    assert cl["m5_gold_set_hit_rate"]["required"] == 1.00
    assert "per-ancestor image-grade" in cl["m5_gold_set_hit_rate"]["neg_miss_ruling"]


def test_m3_categories_v2_is_superset_minus_rename_of_v1():
    v1_cats = set(v1.REFUTATION_CATEGORIES)
    v2_cats = set(c.REFUTATION_CATEGORIES_V2)
    # phantom_source_pointer dropped (renamed), 2 new categories added
    assert "phantom_source_pointer" not in v2_cats
    assert "unresolvable_source_pointer" in v2_cats
    assert v2_cats - v1_cats == {"payload_cross_contamination", "unresolvable_source_pointer", "mapping_metadata_false"}
    assert len(v2_cats) == 7


def test_control_limits_v2_exact_strings_in_rendered_output():
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
            assert needle in text, f"{needle!r} missing from rendered v2 artifact"
        assert "phantom_source_pointer" in text  # only via the 'renamed.from' note
    assert "unresolvable_source_pointer" in md.split("## m3 category rename")[1]


def test_lot1_outcome_block_pinned_in_rendered_output():
    ctx = _synthetic_ctx()
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for text in (md, js):
        assert "13" in text  # quarantined count
        assert "7/8" in text  # m5 NEG hit rate
        assert "A-6(b)-RESOLVED" in text or "halt lifted" in text
        assert c.CONDUCTOR_GATE_REPORT_PATH in text
        assert c.LOT1_PR_REFS in text


def test_sign_off_v2_pinned_literal():
    assert c.CONDUCTOR_SIGN_OFF == "SIGNED — Fable conductor session (MANDATO S2, post-GO), 2026-07-18"
    assert c.PINNED_DATE == "2026-07-18"


# --- (f) plaintext gold codes never leak into the rendered artifact --------


def test_negative_plaintext_never_appears_in_rendered_v2_artifact():
    """The committed gold DIGEST list must never spell out the NEGATIVE
    plaintext codes. ONE deliberate, spec-mandated exception: '49213' is
    cited BY NAME in the m5 neg_miss_ruling prose as the historical
    precedent for the per-ancestor image-grade adjudication rule (plan
    A-6(b)-RESOLVED) — it is not a gold-list leak, since 49213's phase-1
    NEG membership was ALREADY publicly revealed post-lot-close in the
    conductor gate report (plan §5 reveal rule), and the citation is prose
    about a resolved precedent, not the digest-list section itself."""
    manifest_digest = "5" * 64
    neg_digests = c.negative_digests_v2(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos_digests = c.select_positive_digests_v2(records, manifest_digest)
    ctx = c.build_context(
        canonical_revision="0" * 40,
        manifest_digest=manifest_digest,
        membership_sha256="2" * 64,
        eligible_population_before_exclusion=len(records),
        eligible_population_after_exclusion=len(records),
        positive_digests=pos_digests,
        neg_digests=neg_digests,
    )
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    all_neg_plaintext = list(v1.NEGATIVE_CONTROL_CODES) + list(c.LOT1_QUARANTINED_CODES)
    deliberate_precedent_citation = {"49213"}
    for code in all_neg_plaintext:
        if code in deliberate_precedent_citation:
            continue
        assert code not in md, f"NEGATIVE control {code!r} leaked into v2 markdown"
        assert code not in js, f"NEGATIVE control {code!r} leaked into v2 json"
    # 49213 IS expected, but ONLY inside the m5 ruling prose, never inside
    # the gold_sets.negative_control digest-list section itself.
    assert "49213" in md and "49213" in js
    gold_section_md = md.split("## Gold sets v2")[1].split("## Lot 1 outcome")[0]
    assert "49213" not in gold_section_md, "49213 leaked into the v2 gold digest-list section"
    gold_section_json_neg = json.dumps(json.loads(js)["gold_sets"]["negative_control"])
    assert "49213" not in gold_section_json_neg


def test_positive_plaintext_never_appears_in_rendered_v2_artifact():
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    records = _load_real_canonical()
    eligible = c.eligible_positive_codes_v2(records)
    pairs = sorted((c._digest_v2(code, manifest_digest, c.POSITIVE_SALT), code) for code in eligible)
    plaintext_positive_codes = [code for _, code in pairs[:8]]

    membership_sha256 = c._sha256_file(c.MEMBERSHIP_PATH)
    positive_digests = c.select_positive_digests_v2(records, manifest_digest)
    neg_digests = c.negative_digests_v2(manifest_digest)
    ctx = c.build_context(
        canonical_revision="0" * 40,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population_before_exclusion=len(v1.eligible_positive_codes(records)),
        eligible_population_after_exclusion=len(eligible),
        positive_digests=positive_digests,
        neg_digests=neg_digests,
    )
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for code in plaintext_positive_codes:
        assert code not in md, f"positive control {code!r} leaked into v2 markdown"
        assert code not in js, f"positive control {code!r} leaked into v2 json"
    # and none of the plaintext positives selected are among the burned Lot-1 reveals
    assert set(plaintext_positive_codes).isdisjoint(c.LOT1_POSITIVE_REVEALED)


# --- (g) fencing: reused verbatim from v1, sanity-checked here -------------


def test_fencing_reused_from_v1_aborts_on_mutated_canonical(tmp_path, monkeypatch):
    mutated = tmp_path / "mutated-canonical.json"
    mutated.write_text('{"data": [{"kode_kbli_2025": "00000"}]}', encoding="utf-8")
    monkeypatch.setattr(v1, "CANONICAL", mutated)
    with pytest.raises(v1.CalibrationError):
        v1._canonical_revision()


def test_v2_reuses_v1_calibration_error_class():
    assert c.CalibrationError is v1.CalibrationError


# --- integration: real repo inputs -----------------------------------------
#
# NOTE (known pre-existing branch state, verified 2026-07-18): on THIS
# branch (kbli/lot1-data-apply), the Lot-1 data-apply commit (48b823364)
# already cured the canonical (detached 13 codes) but data/kbli-filiera/
# membership/batch-a-members.json (the P0 artifact) has NOT been re-emitted
# against the post-cure canonical yet. Running v1's OWN unmodified test
# suite on this branch shows the identical failure
# (test_end_to_end_against_real_repo_inputs FAILS the same way, plus 2 more
# membership-pin tests) — this is a real, pre-existing repo-state gap, not a
# defect introduced by this v2 compiler. v2 reuses v1's fencing/pin logic
# verbatim (plan §4 reuse), so it fails identically and fail-visibly rather
# than silently — which is the correct, intended behavior (never a silent
# pass on stale evidence). This test is therefore EXPECTED TO FAIL on this
# branch today; it will pass once membership is re-emitted against the
# cured canonical (a separate, already-tracked follow-up).


def test_end_to_end_against_real_repo_inputs():
    canonical_revision = v1._canonical_revision()
    fenced_blob = v1._fenced_canonical_blob()
    membership = v1._load_membership()
    v1._validate_membership_pin(membership, fenced_blob)  # may raise — see NOTE above
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    membership_sha256 = c._sha256_file(c.MEMBERSHIP_PATH)
    records = _load_real_canonical()
    eligible_before = v1.eligible_positive_codes(records)
    eligible_after = c.eligible_positive_codes_v2(records)
    assert len(eligible_after) >= 8
    pos = c.select_positive_digests_v2(records, manifest_digest)
    neg = c.negative_digests_v2(manifest_digest)
    ctx = c.build_context(
        canonical_revision=canonical_revision,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population_before_exclusion=len(eligible_before),
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
    import json

    return json.loads(c.CANONICAL.read_text(encoding="utf-8"))["data"]


def _synthetic_ctx():
    manifest_digest = "1" * 64
    neg = c.negative_digests_v2(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos = c.select_positive_digests_v2(records, manifest_digest)
    return c.build_context(
        canonical_revision="0" * 40,
        manifest_digest=manifest_digest,
        membership_sha256="2" * 64,
        eligible_population_before_exclusion=len(records),
        eligible_population_after_exclusion=len(records),
        positive_digests=pos,
        neg_digests=neg,
    )
