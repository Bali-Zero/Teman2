"""Tests for the Batch A CALIBRATION compiler (plan §5 gate).

Pins: the eligibility predicate for POSITIVE gold-set controls (guilt +
innocence), deterministic digest selection (byte-identical on double run),
the negative-control digest correctness (recomputed independently), the
digest-count/format shape (8+8, 64-hex), the m1-m5 numeric control limits
exactly as pre-registered in the plan, plaintext-never-leaks for the
positive control class, and canonical fencing on a mutated on-disk file.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import pytest

import emit_batch_calibration as c  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _rec(code, *, l2_source=None, per_skala=None):
    r = {"kode_kbli_2025": code}
    if l2_source is not None:
        r["_l2_source"] = l2_source
    if per_skala is not None:
        r["per_skala"] = per_skala
    return r


# --- (a) eligibility predicate: guilt + innocence -------------------------


def test_eligible_requires_both_l2_source_and_per_skala():
    guilty = _rec("11111", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
    assert c.eligible_positive_codes([guilty]) == ["11111"]


def test_ineligible_missing_l2_source():
    innocent = _rec("22222", l2_source=None, per_skala=[{"x": 1}])
    assert c.eligible_positive_codes([innocent]) == []


def test_ineligible_empty_per_skala():
    innocent = _rec("33333", l2_source="OSS_RBA_resiko_2025", per_skala=[])
    assert c.eligible_positive_codes([innocent]) == []


def test_ineligible_missing_per_skala_key():
    innocent = _rec("44444", l2_source="OSS_RBA_resiko_2025")
    assert c.eligible_positive_codes([innocent]) == []


def test_ineligible_no_code():
    r = {"_l2_source": "OSS_RBA_resiko_2025", "per_skala": [{"x": 1}]}
    assert c.eligible_positive_codes([r]) == []


# --- (b) deterministic selection: same inputs => same digests -------------


def test_positive_selection_deterministic_across_runs():
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 40)
    ]
    manifest_digest = "a" * 64
    first = c.select_positive_digests(records, manifest_digest)
    second = c.select_positive_digests(records, manifest_digest)
    assert first == second
    assert first == sorted(first)


def test_artifact_byte_identical_on_double_render():
    ctx1 = _synthetic_ctx()
    ctx2 = _synthetic_ctx()
    assert c.render_markdown(ctx1) == c.render_markdown(ctx2)
    assert c.render_json(ctx1) == c.render_json(ctx2)


# --- (c) negative-list correctness: recompute independently ---------------


def test_negative_digest_matches_recomputed_68112():
    manifest_digest = "deadbeef" * 8
    digests = c.negative_digests(manifest_digest)
    expected = hashlib.sha256(f"68112|{manifest_digest}".encode()).hexdigest()
    assert expected in digests


def test_negative_digests_match_all_recomputed_codes():
    manifest_digest = "cafef00d" * 8
    digests = set(c.negative_digests(manifest_digest))
    for code in c.NEGATIVE_CONTROL_CODES:
        assert hashlib.sha256(f"{code}|{manifest_digest}".encode()).hexdigest() in digests


# --- (d) exactly 8+8 digests, all 64-hex -----------------------------------


def test_gold_sets_are_exactly_8_and_8_valid_hex():
    manifest_digest = "0123456789abcdef" * 4
    neg = c.negative_digests(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos = c.select_positive_digests(records, manifest_digest)
    assert len(neg) == 8
    assert len(pos) == 8
    for d in neg + pos:
        assert HEX64.match(d), f"not 64-hex: {d}"


def test_too_few_eligible_codes_raises():
    manifest_digest = "b" * 64
    records = [_rec("11111", l2_source="OSS_X", per_skala=[{"x": 1}])]  # only 1, need 8
    with pytest.raises(c.CalibrationError):
        c.select_positive_digests(records, manifest_digest)


# --- (f) m1-m5 limits present with exact numeric values --------------------


def test_control_limits_exact_values():
    cl = _synthetic_ctx()["control_limits"]
    assert cl["m1_blind_concordance"]["floor"] == 0.75
    assert cl["m1_blind_concordance"]["pilot_baseline"] == 0.917
    assert cl["m2_certification_rate"]["floor"] == 0.20
    assert cl["m2_certification_rate"]["ceiling"] == 0.85
    assert cl["m2_certification_rate"]["pilot_baseline"] == 0.417
    assert cl["m3_refutation_categories"]["categories"] == [
        "code_collision",
        "illegitimate_inheritance",
        "wrong_authority_level",
        "phantom_source_pointer",
        "source_absent_in_vault",
    ]
    assert cl["m4_tokens_per_dossier"]["ceiling"] == 400000
    assert cl["m4_tokens_per_dossier"]["pilot_avg"] == 225008
    assert cl["m4_tokens_per_dossier"]["pilot_max"] == 357453
    assert cl["m5_gold_set_hit_rate"]["required"] == 1.00


def test_control_limits_exact_strings_in_rendered_output():
    ctx = _synthetic_ctx()
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for text in (md, js):
        for needle in ("0.75", "0.917", "0.20", "0.85", "0.417", "400000", "225008", "357453", "1.00"):
            assert needle in text, f"{needle!r} missing from rendered artifact"


def test_pilot_a1_values_pinned_exactly():
    assert c.PILOT_A1["total_sonnet_tokens"] == 3375127
    assert c.PILOT_A1["avg_tokens_per_code"] == 225008
    assert c.PILOT_A1["max_tokens_per_code"] == 357453
    assert c.PILOT_A1["adjudicated"] == 12
    assert c.PILOT_A1["certified_clean"] == 5
    assert c.PILOT_A1["quarantined"] == 7
    assert c.PILOT_A1["innocence_untouched"] == 3
    assert c.PILOT_A1["d1_d5_dossier_concordance"] == "11/12"


# --- (e) plaintext positive codes never leak -------------------------------


def test_positive_plaintext_never_appears_in_rendered_artifact():
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    records = _load_real_canonical()
    eligible = c.eligible_positive_codes(records)
    pairs = sorted((c._digest(code, manifest_digest), code) for code in eligible)
    plaintext_positive_codes = [code for _, code in pairs[:8]]

    membership = c._load_membership()
    membership_sha256 = c._sha256_file(c.MEMBERSHIP_PATH)
    positive_digests = c.select_positive_digests(records, manifest_digest)
    neg_digests = c.negative_digests(manifest_digest)
    ctx = c.build_context(
        canonical_revision=membership["canonical_revision"],
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population=len(eligible),
        positive_digests=positive_digests,
        neg_digests=neg_digests,
    )
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for code in plaintext_positive_codes:
        assert code not in md, f"positive control {code!r} leaked into markdown"
        assert code not in js, f"positive control {code!r} leaked into json"


# --- (g) fencing: mutated canonical on disk aborts -------------------------


def test_fencing_aborts_on_mutated_canonical(tmp_path, monkeypatch):
    mutated = tmp_path / "mutated-canonical.json"
    mutated.write_text('{"data": [{"kode_kbli_2025": "00000"}]}', encoding="utf-8")
    monkeypatch.setattr(c, "CANONICAL", mutated)
    with pytest.raises(c.CalibrationError):
        c._canonical_revision()


def test_validate_membership_pin_rejects_mismatched_blob():
    with pytest.raises(c.CalibrationError):
        c._validate_membership_pin({"canonical_revision": "deadbeef" * 5}, fenced_blob="x" * 40)


def test_validate_membership_pin_requires_canonical_revision_field():
    with pytest.raises(c.CalibrationError):
        c._validate_membership_pin({}, fenced_blob="x" * 40)


# --- integration: real repo inputs -----------------------------------------


def test_end_to_end_against_real_repo_inputs():
    canonical_revision = c._canonical_revision()
    fenced_blob = c._fenced_canonical_blob()
    membership = c._load_membership()
    c._validate_membership_pin(membership, fenced_blob)  # must not raise
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    membership_sha256 = c._sha256_file(c.MEMBERSHIP_PATH)
    records = _load_real_canonical()
    eligible = c.eligible_positive_codes(records)
    assert len(eligible) >= 8
    pos = c.select_positive_digests(records, manifest_digest)
    neg = c.negative_digests(manifest_digest)
    ctx = c.build_context(
        canonical_revision=canonical_revision,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population=len(eligible),
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
    neg = c.negative_digests(manifest_digest)
    records = [
        _rec(f"{n:05d}", l2_source="OSS_RBA_resiko_2025", per_skala=[{"x": 1}])
        for n in range(1, 20)
    ]
    pos = c.select_positive_digests(records, manifest_digest)
    return c.build_context(
        canonical_revision="0" * 40,
        manifest_digest=manifest_digest,
        membership_sha256="2" * 64,
        eligible_population=len(records),
        positive_digests=pos,
        neg_digests=neg,
    )
