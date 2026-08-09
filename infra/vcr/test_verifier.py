"""Tests for infra/vcr/verifier.py — verifier auditability (R5/§5.3).

Guilt: hash drift, missing prober, and a failing selftest must each yield a
non-HEALTHY verdict — even when the OTHER checks would have passed (verifies
the short-circuit order doesn't hide a real problem behind an earlier check).
Innocence: matching hash + passing selftest -> HEALTHY.
"""

from __future__ import annotations

from infra.vcr.records import DRIFTED, FAILED, HEALTHY
from infra.vcr.verifier import check_verifier, compute_hash


def _passing_selftest(_path):
    return 0, "SELFTEST OK — 42 checks"


def _failing_selftest(_path):
    return 2, "SELFTEST FAIL:\n  some check: got X, want Y"


def test_innocence_matching_hash_and_passing_selftest_is_healthy(tmp_path):
    prober = tmp_path / "fake_prober.py"
    prober.write_text("print('hi')\n")
    good_hash = compute_hash(prober)
    state, detail = check_verifier(prober, good_hash, run_selftest_fn=_passing_selftest)
    assert state == HEALTHY
    assert "certified" in detail


def test_guilt_hash_mismatch_is_drifted_even_if_selftest_would_pass(tmp_path):
    prober = tmp_path / "fake_prober.py"
    prober.write_text("print('hi')\n")
    wrong_hash = "0" * 64
    state, detail = check_verifier(prober, wrong_hash, run_selftest_fn=_passing_selftest)
    assert state == DRIFTED
    assert "mismatch" in detail


def test_guilt_failing_selftest_is_failed_even_with_matching_hash(tmp_path):
    prober = tmp_path / "fake_prober.py"
    prober.write_text("print('hi')\n")
    good_hash = compute_hash(prober)
    state, detail = check_verifier(prober, good_hash, run_selftest_fn=_failing_selftest)
    assert state == FAILED
    assert "selftest exit 2" in detail


def test_guilt_missing_prober_is_failed(tmp_path):
    missing = tmp_path / "does_not_exist.py"
    state, detail = check_verifier(missing, None, run_selftest_fn=_passing_selftest)
    assert state == FAILED
    assert "not found" in detail


def test_innocence_no_certified_hash_skips_hash_check(tmp_path):
    """A not-yet-certified entry (certified_hash=None) still gets a real
    selftest run — it degrades the hash check, never skips verification
    entirely."""
    prober = tmp_path / "fake_prober.py"
    prober.write_text("print('hi')\n")
    state, _ = check_verifier(prober, None, run_selftest_fn=_passing_selftest)
    assert state == HEALTHY


def test_certified_hash_none_message_never_claims_hash_was_certified(tmp_path):
    """GLM red-team, 2026-08-03: the old detail string said 'hash certified,
    selftest passed' even when certified_hash=None — a literal lie, since
    the comparison was skipped, not performed. This is the guilt case: every
    current test_accessor.py fixture uses certified_hash=None, so if this
    regresses, the DRIFTED-detection path's messaging silently lies again
    on the exact path every accessor test exercises."""
    prober = tmp_path / "fake_prober.py"
    prober.write_text("print('hi')\n")
    state, detail = check_verifier(prober, None, run_selftest_fn=_passing_selftest)
    assert state == HEALTHY
    assert "SKIPPED" in detail
    assert "hash certified" not in detail


def test_innocence_a_real_certified_hash_still_says_certified(tmp_path):
    """Mirror of the guilt case above: when a real certified_hash IS
    registered and matches, the message must still say so — the fix must
    not just delete the claim everywhere."""
    prober = tmp_path / "fake_prober.py"
    prober.write_text("print('hi')\n")
    good_hash = compute_hash(prober)
    state, detail = check_verifier(prober, good_hash, run_selftest_fn=_passing_selftest)
    assert state == HEALTHY
    assert "hash certified" in detail
    assert "SKIPPED" not in detail


def test_real_arsenal_probe_hash_is_stable_across_two_reads(tmp_path):
    """Sanity: compute_hash is deterministic (guards against an accidental
    dependency on file mtime/encoding instead of content)."""
    p = tmp_path / "x.py"
    p.write_text("same content\n")
    first = compute_hash(p)
    second = compute_hash(p)
    assert first == second
