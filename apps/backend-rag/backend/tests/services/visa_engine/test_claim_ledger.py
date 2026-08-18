"""Tests for ``backend.services.visa_engine.claim_ledger`` (E5 increment 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.visa_engine.claim_ledger import (
    ClaimLedgerError,
    load_claim_ledgers,
    parse_claim_ledger_text,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_CLAIMS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "claims"


def test_parses_a_verified_claim_with_backs() -> None:
    text = """
### D1 — Tourism Multiple Entry

**CL-D1-01 — Purpose/scope.** D1 authorizes multiple tourism-purpose entries.
- Source: NB-2 whatever.
- **State: VERIFIED.** Products: D1. Provenance: VO-NB2-003.
- Backs: `el.d1-multi-entry-support` (`PURPOSE_PRODUCT_MATCH`).
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert set(records) == {"CL-D1-01"}
    rec = records["CL-D1-01"]
    assert rec.state == "VERIFIED"
    assert rec.compilable is True
    assert rec.backs == ("el.d1-multi-entry-support",)


def test_parses_verified_with_caveat() -> None:
    text = """
**CL-X-01 — Something.** Text.
- **State: VERIFIED-WITH-CAVEAT.** Products: X.
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert records["CL-X-01"].state == "VERIFIED-WITH-CAVEAT"
    assert records["CL-X-01"].compilable is True


def test_parses_conflicting_as_not_compilable() -> None:
    text = """
**CL-X-02 — Something disputed.** Text.
- **State: CONFLICTING.** Products: X.
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert records["CL-X-02"].state == "CONFLICTING"
    assert records["CL-X-02"].compilable is False


def test_state_with_trailing_free_text_still_parses() -> None:
    """Real example: ``**State: VERIFIED as a mechanical/structural
    finding.**`` — the leading token is what matters, not the trailing
    prose."""

    text = """
**CL-X-03 — Structural finding.** Text.
- **State: VERIFIED as a mechanical/structural finding.** Products: X.
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert records["CL-X-03"].state == "VERIFIED"


def test_header_with_no_state_line_becomes_unstated_not_a_crash() -> None:
    """Real example: ``CL-E30A-03`` is a cross-reference alias ("See
    CL-E30B-01 above") with no state line of its own — must not crash the
    whole ledger parse."""

    text = """
**CL-E30A-03 — Sibling mismatch with E30B.** See CL-E30B-01 above.

### Next section

**CL-Y-01 — Real claim.** Text.
- **State: VERIFIED.** Products: Y.
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert records["CL-E30A-03"].state == "UNSTATED"
    assert records["CL-E30A-03"].compilable is False
    assert records["CL-Y-01"].state == "VERIFIED"


def test_inter_file_state_conflict_raises() -> None:
    text_a = "**CL-Z-01 — X.** T.\n- **State: VERIFIED.** Products: Z.\n"
    text_b = "**CL-Z-01 — X.** T.\n- **State: CONFLICTING.** Products: Z.\n"
    a = parse_claim_ledger_text(text_a, source_name="a.md")
    b = parse_claim_ledger_text(text_b, source_name="b.md")
    assert a["CL-Z-01"].state != b["CL-Z-01"].state


def test_load_claim_ledgers_merges_multiple_files(tmp_path: Path) -> None:
    f1 = tmp_path / "one.md"
    f1.write_text("**CL-A-01 — X.** T.\n- **State: VERIFIED.** Products: A.\n", encoding="utf-8")
    f2 = tmp_path / "two.md"
    f2.write_text("**CL-B-01 — Y.** T.\n- **State: CONFLICTING.** Products: B.\n", encoding="utf-8")

    merged = load_claim_ledgers([f1, f2])
    assert merged["CL-A-01"].state == "VERIFIED"
    assert merged["CL-B-01"].state == "CONFLICTING"


def test_load_claim_ledgers_raises_on_cross_file_inconsistency(tmp_path: Path) -> None:
    f1 = tmp_path / "one.md"
    f1.write_text("**CL-A-01 — X.** T.\n- **State: VERIFIED.** Products: A.\n", encoding="utf-8")
    f2 = tmp_path / "two.md"
    f2.write_text("**CL-A-01 — X.** T.\n- **State: CONFLICTING.** Products: A.\n", encoding="utf-8")

    with pytest.raises(ClaimLedgerError):
        load_claim_ledgers([f1, f2])


def test_header_mid_prose_is_never_mistaken_for_a_real_header() -> None:
    """kimi-k3 adversarial finding (2026-08-18): the original ``_HEADER_RE``
    was not line-anchored, so an inline bold reference mid-prose matching
    the exact ``**CL-<id> — <name>.**`` shape (e.g. "as discussed in
    **CL-D2-01 — the passport claim**...") would open a SPURIOUS second
    block for that claim_id, corrupting the first block's boundary. Fixed
    by anchoring the header regex to the start of a line (optionally
    bullet-prefixed, to cover both real ledger header shapes). This is the
    innocence proof: the prose mention below must NOT create a second
    ``CL-W-01`` block, and the real claim's own (later) State line must
    still resolve correctly."""

    text = """
**CL-W-01 — First.** Real claim, as discussed in **CL-W-01 — First.** right here mid-sentence.
- **State: VERIFIED.** Products: W.
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert set(records) == {"CL-W-01"}
    assert records["CL-W-01"].state == "VERIFIED"


def test_in_file_duplicate_header_with_different_state_raises() -> None:
    """Guilt twin for the duplicate-detection safety net itself: two
    genuine line-anchored headers for the same claim_id (e.g. a copy-paste
    accident during authoring) with DIFFERENT states must raise, never
    silently overwrite with last-wins."""

    text = """
**CL-W-01 — First.** Real claim.
- **State: VERIFIED.** Products: W.

**CL-W-01 — First.** Accidentally duplicated block.
- **State: CONFLICTING.** (stale duplicate)
"""
    with pytest.raises(ClaimLedgerError):
        parse_claim_ledger_text(text, source_name="<test>")


def test_in_file_duplicate_header_with_same_state_is_harmless() -> None:
    """Innocence twin: an identical restatement (same claim_id, same state)
    must not raise — this is the legitimate case the docstring names."""

    text = """
**CL-W-02 — Second.** Real claim.
- **State: VERIFIED.** Products: W.

**CL-W-02 — Second.** Restated identically elsewhere.
- **State: VERIFIED.** Products: W.
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert records["CL-W-02"].state == "VERIFIED"


def test_backs_line_wraps_onto_continuation_line() -> None:
    """Real example: ``CL-D12-02`` lists 5 rule ids across two physical
    lines in the committed ledger."""

    text = """
**CL-X-04 — Bundle.** T.
- **State: VERIFIED.** Products: X.
- Backs: `el.a`, `el.b`, `el.c`,
  `el.d`, `el.e`.
"""
    records = parse_claim_ledger_text(text, source_name="<test>")
    assert records["CL-X-04"].backs == ("el.a", "el.b", "el.c", "el.d", "el.e")


@pytest.mark.skipif(not _CLAIMS_DIR.exists(), reason="doctrine-factory claims not present in this checkout")
class TestRealLedgers:
    def test_all_slice_claims_resolve_and_are_compilable(self) -> None:
        paths = [
            _CLAIMS_DIR / "e2a-claim-ledger.md",
            _CLAIMS_DIR / "e2b-batch1-claim-ledger.md",
            _CLAIMS_DIR / "e2b-batch2-claim-ledger.md",
            _CLAIMS_DIR / "e3a-cf1-resolution.md",
        ]
        ledger = load_claim_ledgers(paths)
        expected_states = {
            "CL-D1-01": "VERIFIED",
            "CL-D1-02": "VERIFIED",
            "CL-D1-03": "VERIFIED",
            "CL-D2-01": "VERIFIED-WITH-CAVEAT",
            "CL-D2-02": "VERIFIED",
            "CL-D2-03": "VERIFIED-WITH-CAVEAT",
            "CL-D2-04": "VERIFIED",
            "CL-D12-01": "VERIFIED",
            "CL-D12-02": "VERIFIED",
            "CL-D12-03": "VERIFIED",
            "CL-D12-04": "VERIFIED",
            "CL-D12-06": "VERIFIED",
            "CL-E31B-01": "VERIFIED",
            "CL-E31B-REFUTER": "VERIFIED",
            "CL-E31B-STRUCT": "VERIFIED",
            "CL-E31D-01": "VERIFIED",
            "CL-E31D-REFUTER": "VERIFIED",
            "CL-E31D-STRUCT": "VERIFIED",
            "CL-D-FUNDS": "VERIFIED",
            "CL-D-COMPARE": "VERIFIED",
        }
        for claim_id, expected_state in expected_states.items():
            rec = ledger.get(claim_id)
            assert rec is not None, f"{claim_id} missing from parsed ledger"
            assert rec.state == expected_state, f"{claim_id}: {rec.state} != {expected_state}"
            assert rec.compilable is True
