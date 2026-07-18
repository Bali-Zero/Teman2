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
import subprocess
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
    """CURRENT (post plan §8 A-3, 2026-07-18) active limits — these are the
    values the drift test (test_lot_runner_contract.py::
    test_m1_m2_m4_literals_match_calibration_artifact) cross-checks against
    infra/workflows/kbli-batch-a-lot.js's CALIBRATION literal. m1/m2 were
    recalibrated for remaining A-serving lots; m3/m4/m5 are UNCHANGED."""
    cl = _synthetic_ctx()["control_limits"]
    assert cl["m1_blind_concordance"]["floor"] == 0.45
    assert cl["m1_blind_concordance"]["pilot_baseline"] == 0.917
    assert cl["m2_certification_rate"]["floor"] == 0.05
    assert cl["m2_certification_rate"]["ceiling"] == 0.60
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


def test_control_limits_original_values_preserved_in_revisions():
    """ORIGINAL (pilot-derived, pre-A-3) values must remain visible under
    revisions.original — recalibration is auditable history, never a silent
    overwrite (plan §8 A-3, explicit requirement)."""
    cl = _synthetic_ctx()["control_limits"]
    m1_orig = cl["m1_blind_concordance"]["revisions"]["original"]
    m2_orig = cl["m2_certification_rate"]["revisions"]["original"]
    assert m1_orig["floor"] == 0.75
    assert m2_orig["floor"] == 0.20
    assert m2_orig["ceiling"] == 0.85

    m1_cur = cl["m1_blind_concordance"]["revisions"]["current"]
    m2_cur = cl["m2_certification_rate"]["revisions"]["current"]
    assert m1_cur["floor"] == cl["m1_blind_concordance"]["floor"] == 0.45
    assert m2_cur["floor"] == cl["m2_certification_rate"]["floor"] == 0.05
    assert m2_cur["ceiling"] == cl["m2_certification_rate"]["ceiling"] == 0.60
    for entry in (m1_cur, m2_cur):
        assert entry["amendment"] == "plan §8 amendment A-3 (2026-07-18)"
        assert entry["scope"] == "remaining A-serving lots only"


def test_control_limits_exact_strings_in_rendered_output():
    ctx = _synthetic_ctx()
    md = c.render_markdown(ctx)
    js = c.render_json(ctx)
    for text in (md, js):
        # current (active) values
        for needle in ("0.45", "0.05", "0.60", "0.917", "400000", "225008", "357453", "1.00"):
            assert needle in text, f"{needle!r} missing from rendered artifact"
        # original (pre-A-3) values must ALSO still be visible — history, not overwrite
        for needle in ("0.75", "0.20", "0.85", "0.417"):
            assert needle in text, f"original value {needle!r} missing from rendered artifact"


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
    # legacy shape: no canonical_sha256 -> exercises the git-blob FALLBACK path
    with pytest.raises(c.CalibrationError):
        c._validate_membership_pin({"canonical_revision": "deadbeef" * 5}, fenced_blob="x" * 40)


def test_validate_membership_pin_requires_canonical_revision_field():
    with pytest.raises(c.CalibrationError):
        c._validate_membership_pin({}, fenced_blob="x" * 40)


# --- content-addressed pin (shallow-clone-safe, zero git) ------------------
#
# CI runs on a SHALLOW checkout (depth=1): historical commit objects for an
# arbitrary `canonical_revision` SHA are absent, so resolving them via git
# 128's (observed live: PR #2665 FAIL 1). The content-addressed path below
# must never invoke git at all when `canonical_sha256` is present.


def test_validate_membership_pin_content_path_never_calls_git(monkeypatch):
    real_sha256 = c._sha256_file(c.CANONICAL)
    membership = {"canonical_sha256": real_sha256, "canonical_revision": "irrelevant-in-content-path"}
    git_calls: list[tuple] = []

    def _boom(*args, **kwargs):
        git_calls.append(args)
        raise AssertionError("content-addressed path must not call git")

    monkeypatch.setattr(c, "_git", _boom)
    c._validate_membership_pin(membership, fenced_blob="unused")  # must not raise
    assert git_calls == [], f"content-addressed path called git: {git_calls}"


def test_validate_membership_pin_content_path_mismatch_never_calls_git(monkeypatch):
    membership = {"canonical_sha256": "0" * 64, "canonical_revision": "irrelevant-in-content-path"}

    def _boom(*args, **kwargs):
        raise AssertionError("content-addressed path must not call git")

    monkeypatch.setattr(c, "_git", _boom)
    with pytest.raises(c.CalibrationError):
        c._validate_membership_pin(membership, fenced_blob="unused")


def test_validate_membership_pin_fallback_wraps_shallow_clone_128(monkeypatch):
    """Legacy membership (no canonical_sha256): simulates the exact CI
    failure — resolving an arbitrary historical commit's tree entry 128's
    under a shallow checkout. The error must be wrapped with a clear
    're-emit membership' pointer, never a bare git CalledProcessError."""
    membership = {"canonical_revision": "4328b1bbd604a0934680be9d0a416075fd8d5c44"}

    def _boom(*args, **kwargs):
        raise subprocess.CalledProcessError(
            128, ["git", "rev-parse"], output="", stderr="fatal: Not a valid object name"
        )

    monkeypatch.setattr(c, "_git", _boom)
    with pytest.raises(c.CalibrationError, match="shallow"):
        c._validate_membership_pin(membership, fenced_blob="unused")


def test_membership_artifact_carries_content_addressed_pin():
    """The real, committed membership artifact must carry canonical_sha256
    (re-emitted alongside this fix) — this is what makes the content path
    the PRIMARY path rather than dead code."""
    membership = c._load_membership()
    assert "canonical_sha256" in membership
    assert re.match(r"^[0-9a-f]{64}$", membership["canonical_sha256"])
    assert membership["canonical_sha256"] == c._sha256_file(c.CANONICAL)


def test_end_to_end_membership_pin_survives_shallow_clone_simulation(monkeypatch):
    """The full main()-shaped flow (fence canonical -> load membership ->
    validate pin) must succeed even when git cannot resolve ANY historical
    revision — the exact shallow-CI shape that broke PR #2665. `_git` is
    only allowed to answer HEAD-relative queries (which a depth=1 checkout
    CAN resolve); anything else 128's, matching real shallow-clone behavior."""
    real_git = c._git

    def _shallow_git(*args: str) -> str:
        joined = " ".join(args)
        if "HEAD" in joined and "4328b1bb" not in joined:
            return real_git(*args)
        raise subprocess.CalledProcessError(128, ["git", *args], output="", stderr="fatal: shallow")

    monkeypatch.setattr(c, "_git", _shallow_git)
    canonical_revision = c._canonical_revision()
    assert len(canonical_revision) == 40
    fenced_blob = c._fenced_canonical_blob()
    membership = c._load_membership()
    c._validate_membership_pin(membership, fenced_blob)  # must not raise: content path, zero git


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


# --- Part 4 (plan §8 A-3): recalibration must not touch gold-set selection -


# Regression pin: the EXACT 8+8 digests + pinned-revisions as committed in
# data/kbli-filiera/batch-reports/batchA-calibration.json BEFORE this
# recalibration (Part 4) landed. Gold-set digests are a pure function of
# (canonical, manifest_digest) — control_limits changes must never move them.
_PRE_A3_NEGATIVE_DIGESTS = [
    "0be62853bc799751a2c1fdf3d35f2b4ca6f42f87bdfdd04c182ab64c07563160",
    "148e8314ff7d55fe6acef963d0e51b4d83b92bd44e568da405c45452dcbca6bb",
    "34ad28116dea958b6481af2155ebd20cbbd7ef807178a7fee49b45e48f5a5402",
    "40bb04a7514c53133acf4d979def4d8d667accb5ea9c1f12f9853364c4148e5b",
    "5fbb35d093c960a1cfe9166d1419a1e3853eec0a82d3fd4dd880bc817729dd97",
    "cce4f93a7687b6c201c046fc55af2fe9659db7857b84cb33e839681b0ec3293f",
    "d279d2b5cf9396272bced8d09a19aa3005150155240433a32a6751b89973ce92",
    "fb5df44ffe81b6af8ac36fb6a666243f815c84e8a02c8d0de223223e77aa4a1e",
]
_PRE_A3_POSITIVE_DIGESTS = [
    "002b2f50370eeb36d78030d3a0137997571b9535954f34c595f032d7d5abcd0b",
    "0090e8cc839d35a849b789fcd4c15816c0c72de46a5a02191abca0f938b6fb24",
    "00bcc0ba8e78902530873e111ffa57b7f86685acbbe26bddad1d43cf36bfd5fd",
    "00c324c333f44f347349f475b9f084f55dd1a7249acf6495f468becaafc5b6d1",
    "00c4757efbe09c7b0f764078d7732b47b557f9ad204fd70cd46fd86d5b5f3c8a",
    "00f964023ee65e7bb184d770624485b8eec6057e78624ef5d6bd187e5ddfa048",
    "011b8eecc4a165dd230b1e25d8fb1e898e9e75a2c55b02889b9f4c813c18204b",
    "0181b72ccb224bd7d53017f67be1e7c9ba6d3e8efbef3524c0a6d4f3f37335df",
]


def test_a3_recalibration_does_not_change_gold_digests():
    """Part 4 regression pin: recalibrating m1/m2 (plan §8 A-3) must NEVER
    touch gold-set selection. Compares against the real repo's canonical +
    manifest + membership inputs — same fixtures as
    test_end_to_end_against_real_repo_inputs — asserting the negative/positive
    digest lists are byte-identical to what was committed before this Part-4
    recalibration landed."""
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    records = _load_real_canonical()
    pos = c.select_positive_digests(records, manifest_digest)
    neg = c.negative_digests(manifest_digest)
    assert neg == _PRE_A3_NEGATIVE_DIGESTS
    assert pos == _PRE_A3_POSITIVE_DIGESTS


def test_a3_recalibration_pinned_revisions_unchanged():
    """The pinned-revisions block (canonical/manifest/membership pins) is
    orthogonal to control_limits — recalibrating m1/m2 must not touch it.

    NOTE (scar W88 — verify by CONTENT, never by a SHA/ancestor/timestamp
    proxy): canonical_git_revision is `git rev-parse HEAD`, which advances on
    EVERY commit regardless of whether the canonical file changed — pinning
    that here would break on the very next unrelated commit. manifest_sha256
    and membership_sha256, and the canonical FILE's own content sha256, are
    content-addressed and genuinely stable across commits that don't touch
    those files — those are the load-bearing assertions."""
    manifest_digest = c._sha256_file(c.MANIFEST_PATH)
    membership_sha256 = c._sha256_file(c.MEMBERSHIP_PATH)
    canonical_content_sha256 = c._sha256_file(c.CANONICAL)
    assert manifest_digest == "e7d25a377b717ed76efd1c7c806fe74b45067321629c5ed77655aeea9375db9d"
    assert membership_sha256 == "aa0a0a6980117d57321e625fdad4e1a89f19f5b34125614d8d9921fb50f60497"
    assert canonical_content_sha256 == "659dc7a71b360e16fbdb7bac5cbc0fe1831f33a994785185b56fe66e73fb04b5"


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
