"""Unit tests for the E33 runtime claim guard (task 1.3).

Covers ``check_e33_claims`` (per-pattern positives, negation guards, E33
context gating) and ``guard_e33_answer`` (log + fallback note, never raises).
Uses the trimmed registry fixture at ``fixtures/e33_fact_registry.json`` —
tests never touch the sibling worktree path.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from backend.services.visa_check.e33_claim_guard import (
    E33_FORBIDDEN_PATTERNS,
    E33_SAFE_FALLBACK_NOTE,
    LEGACY_ERROR_REF,
    check_e33_claims,
    guard_e33_answer,
)

FIXTURE_REGISTRY = Path(__file__).parent / "fixtures" / "e33_fact_registry.json"

_E33 = "About the E33 Second Home visa: "

# (pattern_id, violating text). Every sample is E33-contextual unless the
# pattern is context-free by design.
POSITIVE_CASES: list[tuple[str, str]] = [
    (
        "e33f_superseded_income_usd1500",
        _E33 + "the E33F retirement route requires USD 1,500/month passive income.",
    ),
    (
        "second_home_any_bank",
        _E33 + "you can place the USD 130,000 deposit at any Indonesian bank.",
    ),
    (
        "second_home_any_bank",
        _E33 + "the deposit may sit at any bank of your choice.",
    ),
    (
        "e33_itap_kitap_automatic_promise",
        _E33 + "after 3 years you are eligible for KITAP conversion.",
    ),
    (
        "e33_itap_kitap_automatic_promise",
        _E33 + "KITAP is automatic after the first grant.",
    ),
    (
        "e33_permits_local_work",
        "The E33 permits you to work for a local employer.",
    ),
    (
        "e33_permits_local_work",
        "You can work legally in Indonesia on an E33 visa.",
    ),
    (
        "bsi_sharia_equivalence",
        _E33 + "a BSI deposit qualifies as the state-owned bank deposit.",
    ),
    (
        "split_deposit_accepted",
        _E33 + "you may split the deposit across two BUMN banks.",
    ),
    (
        "lps_full_coverage",
        _E33 + "the deposit is safe because LPS fully covers it.",
    ),
    (
        "approval_guaranteed",
        _E33 + "with our package, approval is guaranteed.",
    ),
    (
        "idr_2m_fee_error",
        _E33 + "the government fee is IDR 2,000,000.",
    ),
    (
        "second_home_first_grant_5_10_years",
        _E33 + "the first grant is 5-10 years depending on the case.",
    ),
]

# Correct cautionary phrasing must NOT be flagged (negation guards).
NEGATIVE_CASES: list[str] = [
    _E33 + "it is a pure residence permit — it does NOT authorize employment.",
    _E33 + "you cannot work in Indonesia on an E33; paid work needs a separate KITAS.",
    _E33 + "approval is not guaranteed; the decision rests with immigration.",
    _E33 + "LPS does not fully cover the deposit — a cap applies.",
    _E33 + "the deposit cannot be split across banks (unconfirmed).",
    _E33 + "the E33F route requires USD 3,000/month passive income.",
    _E33 + "a USD 130,000 deposit in your own name at a state-owned (BUMN) "
    "Indonesian bank, or USD 1,000,000 qualifying strata-title property.",
    _E33 + "first grant is up to 5 years, renewable per prevailing regulations.",
    # No E33 context at all -> context-gated patterns stay silent.
    "The consulting retainer is USD 1,500/month and approval is guaranteed.",
    "",
]


class TestCheckE33Claims:
    @pytest.mark.parametrize(("pattern_id", "text"), POSITIVE_CASES)
    def test_flags_forbidden_claim(self, pattern_id: str, text: str) -> None:
        violations = check_e33_claims(text)
        flagged = {v.pattern_id for v in violations}
        assert pattern_id in flagged, f"expected '{pattern_id}' in {flagged} for: {text!r}"

    @pytest.mark.parametrize("text", NEGATIVE_CASES)
    def test_clean_text_passes(self, text: str) -> None:
        assert check_e33_claims(text) == [], f"unexpected violations for: {text!r}"

    def test_violation_shape(self) -> None:
        text = _E33 + "deposit at any Indonesian bank is fine."
        (violation,) = check_e33_claims(text)
        assert violation.pattern_id == "second_home_any_bank"
        assert violation.matched_text.lower() == "any indonesian bank"
        assert 0 <= violation.start < violation.end <= len(text)
        assert violation.registry_ref == "e33_base_deposit_amount"

    def test_legacy_error_ref_sentinel(self) -> None:
        (violation,) = check_e33_claims(_E33 + "fee is IDR 2.000.000 flat.")
        assert violation.registry_ref == LEGACY_ERROR_REF


class TestGuardE33Answer:
    def test_clean_answer_returned_unchanged(self) -> None:
        answer = _E33 + "first grant is up to 5 years; it does not authorize employment."
        assert guard_e33_answer(answer) == answer

    def test_violation_appends_fallback_note(self, caplog: pytest.LogCaptureFixture) -> None:
        answer = _E33 + "deposit at any Indonesian bank."
        with caplog.at_level(logging.WARNING):
            guarded = guard_e33_answer(answer)
        assert guarded.startswith(answer)
        assert E33_SAFE_FALLBACK_NOTE in guarded
        assert "[E33Guard]" in caplog.text
        assert "second_home_any_bank" in caplog.text

    def test_empty_answer_passthrough(self) -> None:
        assert guard_e33_answer("") == ""


class TestRegistryFixture:
    def test_fixture_covers_guard_registry_refs(self) -> None:
        fixture = json.loads(FIXTURE_REGISTRY.read_text())
        fact_ids = {f["id"] for f in fixture["facts"]}
        for pattern in E33_FORBIDDEN_PATTERNS:
            if pattern.registry_ref != LEGACY_ERROR_REF:
                assert pattern.registry_ref in fact_ids

    def test_fixture_marks_pending_facts_forbidden(self) -> None:
        fixture = json.loads(FIXTURE_REGISTRY.read_text())
        forbidden_fact_ids = {
            f["id"] for f in fixture["facts"] if "FORBIDDEN" in f.get("notes", "")
        }
        # The three registry facts explicitly marked FORBIDDEN in their notes.
        assert {
            "bsi_sharia_accepted",
            "split_deposit_accepted",
            "itap_after_3y_criteria",
        } <= forbidden_fact_ids

    def test_fixture_documents_legacy_errors(self) -> None:
        fixture = json.loads(FIXTURE_REGISTRY.read_text())
        legacy = " ".join(fixture["forbidden_legacy_errors"]).lower()
        for keyword in ("1,500", "2,000,000", "lps", "guaranteed", "kitap", "work"):
            assert keyword in legacy
