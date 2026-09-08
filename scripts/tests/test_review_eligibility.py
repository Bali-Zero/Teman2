"""Guilt+innocence corpus for scripts/conductor/review_eligibility.py.

One test per reason code, plus the positive controls from the acceptance
spec: a distinct-reviewer ALLOW, the A17 "rank confers no exemption" four-way
matrix (opus/sol, in/out of contributors), and a same-family-but-not-a-
contributor ALLOW proving family membership alone never disqualifies.
"""

from __future__ import annotations

from scripts.conductor.contracts import Decision
from scripts.conductor.review_eligibility import SCHEMA_VERSION, evaluate


def _valid_record(**overrides) -> dict:
    record = {
        "schema_version": SCHEMA_VERSION,
        "artifact_hash": "sha256:abc123",
        "contributors": ("alice", "bob"),
        "reviewer": "charlie",
        "reviewed_hash": "sha256:abc123",
        "reviewer_family": "fam-charlie",
        "contributor_families": ("fam-alice", "fam-bob"),
    }
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_distinct_reviewer_with_matching_hashes_allows_with_no_reasons():
    result = evaluate(_valid_record())
    assert result.decision is Decision.ALLOW
    assert result.reason_codes == ()


def test_rank_confers_no_exemption_opus_in_contributors_blocks():
    record = _valid_record(reviewer="opus", contributors=("opus", "bob"))
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "reviewer_is_contributor" in result.reason_codes


def test_rank_confers_no_exemption_opus_not_in_contributors_allows():
    record = _valid_record(reviewer="opus", contributors=("alice", "bob"))
    result = evaluate(record)
    assert result.decision is Decision.ALLOW
    assert result.reason_codes == ()


def test_rank_confers_no_exemption_sol_in_contributors_blocks():
    record = _valid_record(reviewer="sol", contributors=("sol", "bob"))
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "reviewer_is_contributor" in result.reason_codes


def test_rank_confers_no_exemption_sol_not_in_contributors_allows():
    record = _valid_record(reviewer="sol", contributors=("alice", "bob"))
    result = evaluate(record)
    assert result.decision is Decision.ALLOW
    assert result.reason_codes == ()


def test_same_family_non_contributor_reviewer_is_allowed():
    """Family membership alone is never disqualifying — only actual

    contribution is. `charlie` shares `fam-alice` with contributor `alice`
    but never contributed, so this must ALLOW. Family diversity is a separate
    existing build-lane concern (`evidence_pack_lint.py`) and is not
    re-implemented here.
    """
    record = _valid_record(
        reviewer="charlie",
        reviewer_family="fam-alice",
        contributors=("alice", "bob"),
        contributor_families=("fam-alice", "fam-bob"),
    )
    result = evaluate(record)
    assert result.decision is Decision.ALLOW
    assert result.reason_codes == ()


# ---------------------------------------------------------------------------
# Rejection rules — one isolated test per reason code
# ---------------------------------------------------------------------------


def test_unknown_schema_version_missing():
    record = _valid_record()
    del record["schema_version"]
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "unknown_schema_version" in result.reason_codes


def test_unknown_schema_version_wrong_value():
    record = _valid_record(schema_version="review-eligibility/0")
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "unknown_schema_version" in result.reason_codes


def test_missing_required_field_when_reviewer_absent():
    record = _valid_record()
    del record["reviewer"]
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes


def test_missing_required_field_when_artifact_hash_empty_string():
    record = _valid_record(artifact_hash="")
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes


def test_missing_required_field_when_reviewer_family_none():
    record = _valid_record(reviewer_family=None)
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes


def test_missing_required_field_when_contributor_families_absent():
    record = _valid_record()
    del record["contributor_families"]
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes


def test_reviewer_is_contributor_exact_match():
    record = _valid_record(reviewer="alice", contributors=("alice", "bob"))
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "reviewer_is_contributor" in result.reason_codes


def test_reviewer_is_contributor_case_and_whitespace_folded_match():
    record = _valid_record(reviewer="  Alice  ", contributors=("alice", "bob"))
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "reviewer_is_contributor" in result.reason_codes


def test_stale_review_hash():
    record = _valid_record(reviewed_hash="sha256:different")
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "stale_review_hash" in result.reason_codes


def test_no_contributor_recorded():
    record = _valid_record(contributors=())
    result = evaluate(record)
    assert result.decision is Decision.BLOCK
    assert "no_contributor_recorded" in result.reason_codes


def test_non_dict_record_returns_structured_block():
    result = evaluate(["not", "a", "dict"])
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes


def test_evaluate_is_deterministic_across_repeated_calls():
    record = _valid_record(reviewer="alice", contributors=("alice", "bob"))
    first = evaluate(record)
    second = evaluate(record)
    assert first == second
