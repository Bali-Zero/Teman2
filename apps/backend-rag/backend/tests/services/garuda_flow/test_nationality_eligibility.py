"""Tests for the GARUDA VOA nationality-eligibility dataset (pure, no I/O).

Closes spec §1's "no nationality-eligibility dataset yet" gap: before this
module existed, `intake._build_eligibility_input` hardcoded
``nationality_entry_eligible=True`` for every request, so a case with
nationality ``AFG`` (not VOA-eligible) silently ACCEPTed. See
`test_intake.py::TestNationalityEligibility` for the end-to-end
`build_verdict` wiring; this file pins the dataset and the pure lookup
function in isolation.
"""

from __future__ import annotations

from backend.services.garuda_flow.nationality_eligibility import (
    COUNT,
    VOA_ELIGIBLE_NATIONALITIES,
    is_voa_eligible_nationality,
)


class TestGuilt:
    """A nationality absent from the verified list must NOT be eligible."""

    def test_afg_is_not_voa_eligible(self) -> None:
        # Afghanistan — not on the M.HH-02.GR.01.06/2024 list.
        assert is_voa_eligible_nationality("AFG") is False

    def test_prk_is_not_voa_eligible(self) -> None:
        # North Korea — a second, independent non-listed real country, so
        # this isn't a single-fixture coincidence.
        assert is_voa_eligible_nationality("PRK") is False

    def test_unassigned_code_is_not_voa_eligible(self) -> None:
        # ZZZ is not an assigned ISO 3166-1 country code at all. Per the
        # module's documented "unknown-code decision", this still resolves
        # to False (fail-closed), never a guess or a crash.
        assert is_voa_eligible_nationality("ZZZ") is False


class TestInnocence:
    """A representative sample of genuinely listed nationalities must still
    be eligible — including the two special entities (Hong Kong, Taiwan)
    the mandate specifically calls out."""

    def test_usa_is_voa_eligible(self) -> None:
        assert is_voa_eligible_nationality("USA") is True

    def test_ita_is_voa_eligible(self) -> None:
        assert is_voa_eligible_nationality("ITA") is True

    def test_rus_is_voa_eligible(self) -> None:
        assert is_voa_eligible_nationality("RUS") is True

    def test_aus_is_voa_eligible(self) -> None:
        assert is_voa_eligible_nationality("AUS") is True

    def test_hkg_hong_kong_is_voa_eligible(self) -> None:
        assert is_voa_eligible_nationality("HKG") is True

    def test_twn_taiwan_is_voa_eligible(self) -> None:
        assert is_voa_eligible_nationality("TWN") is True

    def test_gbr_united_kingdom_inggris_is_voa_eligible(self) -> None:
        # "Inggris" on the source page maps to GBR, not a constituent
        # country of the UK — see the module docstring's provenance note.
        assert is_voa_eligible_nationality("GBR") is True


class TestCaseInsensitivity:
    """`internal_preview_cli.InternalPreviewRequest` normalises to upper
    case before this module ever sees the value, but the lookup itself must
    not depend on that — belt and braces for any other future caller."""

    def test_lowercase_matches_uppercase(self) -> None:
        assert is_voa_eligible_nationality("usa") is True

    def test_mixed_case_matches(self) -> None:
        assert is_voa_eligible_nationality("UsA") is True

    def test_lowercase_non_eligible_still_declines(self) -> None:
        assert is_voa_eligible_nationality("afg") is False

    def test_surrounding_whitespace_is_tolerated(self) -> None:
        assert is_voa_eligible_nationality(" USA ") is True


class TestNonVacuity:
    """A future edit that silently empties or truncates the dataset must
    fail loudly, not quietly start declining (or accepting) everyone."""

    def test_count_matches_verified_count(self) -> None:
        assert len(VOA_ELIGIBLE_NATIONALITIES) == COUNT == 97

    def test_every_code_is_a_three_letter_uppercase_string(self) -> None:
        for code in VOA_ELIGIBLE_NATIONALITIES:
            assert isinstance(code, str)
            assert len(code) == 3
            assert code == code.upper()
            assert code.isalpha()

    def test_no_duplicate_entries(self) -> None:
        # frozenset already guarantees this structurally, but pin the
        # cardinality explicitly so a future refactor to a list/tuple can't
        # silently introduce duplicates without a test noticing.
        assert len(set(VOA_ELIGIBLE_NATIONALITIES)) == len(VOA_ELIGIBLE_NATIONALITIES)
