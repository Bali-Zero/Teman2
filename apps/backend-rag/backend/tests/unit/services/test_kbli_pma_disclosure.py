"""Atomic disclosure contract for KBLI PMA claims."""

from __future__ import annotations

import pytest

from backend.services.kbli_pma_disclosure import disclose_bali, disclose_pma, pma_claims_verified


@pytest.mark.parametrize(
    "missing",
    ["pma_verification_status", "pma_status", "pma_official_basis", "pma_source_vintage"],
)
def test_partial_evidence_tuple_fails_closed_atomically(missing: str) -> None:
    raw = {
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "located",
        "pma_official_basis": "official locator",
        "pma_source_vintage": "2021-05-25",
        "pma_kondisi": "UNSAFE_CONDITION",
        "pma_prioritas": "UNSAFE_PRIORITY",
        "pma_nota": "UNSAFE_NOTE",
        "pma_cap_verified": True,
    }
    raw[missing] = None

    disclosed = disclose_pma(raw)

    assert pma_claims_verified(raw) is False
    assert disclosed == {
        "pma_status": "NOT_VERIFIED",
        "pma_max_asing": None,
        "pma_verification_status": "declared_gap",
        "pma_official_basis": None,
        "pma_source_vintage": None,
        "pma_kondisi": None,
        "pma_prioritas": None,
        "pma_nota": None,
        "pma_cap_special": False,
        "pma_cap_verified": False,
    }


def test_complete_located_tuple_preserves_zero_cap_and_provenance() -> None:
    raw = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_verification_status": "located",
        "pma_official_basis": "official locator",
        "pma_source_vintage": "2021-05-25",
        "pma_cap_verified": True,
    }

    disclosed = disclose_pma(raw)

    assert pma_claims_verified(raw) is True
    assert disclosed["pma_status"] == "TERBATAS"
    assert disclosed["pma_max_asing"] == 0
    assert disclosed["pma_official_basis"] == "official locator"
    assert disclosed["pma_cap_verified"] is True


@pytest.mark.parametrize("status", ["OPEN", "terbuka", "FUTURE_STATUS", " TERBUKA "])
def test_unknown_or_noncanonical_status_fails_closed(status: str) -> None:
    raw = {
        "pma_status": status,
        "pma_max_asing": 100,
        "pma_verification_status": "located",
        "pma_official_basis": "official locator",
        "pma_source_vintage": "2021-05-25",
    }

    disclosed = disclose_pma(raw)

    assert pma_claims_verified(raw) is False
    assert disclosed["pma_status"] == "NOT_VERIFIED"
    assert disclosed["pma_max_asing"] is None
    assert disclosed["pma_verification_status"] == "declared_gap"


def _located_record() -> dict:
    return {
        "pma_status": "TERBUKA",
        "pma_verification_status": "located",
        "pma_official_basis": "official locator",
        "pma_source_vintage": "2021-05-25",
    }


def test_bali_disclosure_requires_the_complete_pma_tuple() -> None:
    raw = {
        **_located_record(),
        "pma_verification_status": "declared_gap",
        "l4_bali": {
            "status": "OK_or_HIGHER_RISK",
            "blocked": False,
            "needs_review": False,
            "reason": "UNSAFE_REASON",
        },
    }

    assert disclose_bali(raw) == {
        "bali_status": None,
        "bali_blocked": None,
        "bali_needs_review": None,
        "bali_reason": "",
        "has_bali_l4": False,
    }


@pytest.mark.parametrize("blocked", ["false", "true", 0, 1, None])
def test_bali_disclosure_never_coerces_a_non_boolean_blocked_value(blocked: object) -> None:
    raw = {
        **_located_record(),
        "l4_bali": {
            "status": "CHIUSO_MORATORIA_BALI",
            "blocked": blocked,
            "needs_review": False,
            "reason": "UNSAFE_REASON",
        },
    }

    assert disclose_bali(raw)["has_bali_l4"] is False
    assert disclose_bali(raw)["bali_blocked"] is None


@pytest.mark.parametrize("status", [None, "", " ", 7, " OPEN ", "OK", "FUTURE_STATUS"])
def test_bali_disclosure_rejects_unknown_or_malformed_status(status: object) -> None:
    raw = {
        **_located_record(),
        "l4_bali": {"status": status, "blocked": False, "needs_review": False},
    }

    assert disclose_bali(raw)["has_bali_l4"] is False


@pytest.mark.parametrize(
    "status",
    [
        "APERTO_BALI_RISCHIO_ALTO",
        "BLOCCATO_CLASSE_RISCHIO",
        "BLOCCATO_DIPENDE_SCOPE",
        "CHIUSO_BALI",
        "CHIUSO_BALI_PROPOSTO",
        "CHIUSO_MORATORIA_BALI",
        "CHIUSO_PMA_NO_BESAR",
        "CHIUSO_REGOLATORE_SETTORIALE",
        "NON_CLASSIFICABILE",
        "OK_or_HIGHER_RISK",
        "TERBATAS",
        "TERTUTUP",
    ],
)
def test_bali_disclosure_accepts_only_canonical_status_vocabulary(status: str) -> None:
    raw = {
        **_located_record(),
        "l4_bali": {"status": status, "blocked": False, "needs_review": False},
    }

    assert disclose_bali(raw)["bali_status"] == status
    assert disclose_bali(raw)["has_bali_l4"] is True


def test_bali_disclosure_supports_nested_and_flat_verified_shapes() -> None:
    expected = {
        "bali_status": "CHIUSO_MORATORIA_BALI",
        "bali_blocked": True,
        "bali_needs_review": False,
        "bali_reason": "moratorium",
        "has_bali_l4": True,
    }
    nested = {
        **_located_record(),
        "l4_bali": {
            "status": "CHIUSO_MORATORIA_BALI",
            "blocked": True,
            "needs_review": False,
            "reason": "moratorium",
        },
    }
    flat = {**_located_record(), **expected}

    assert disclose_bali(nested) == expected
    assert disclose_bali(flat) == expected


@pytest.mark.parametrize("needs_review", ["false", "true", 0, 1, None])
def test_bali_disclosure_never_coerces_a_non_boolean_review_flag(
    needs_review: object,
) -> None:
    raw = {
        **_located_record(),
        "l4_bali": {
            "status": "CHIUSO_MORATORIA_BALI",
            "blocked": True,
            "needs_review": needs_review,
        },
    }

    disclosed = disclose_bali(raw)
    assert disclosed["has_bali_l4"] is False
    assert disclosed["bali_needs_review"] is None


def test_pma_cap_verified_is_not_truthiness_coerced() -> None:
    raw = {**_located_record(), "pma_cap_verified": "false"}

    assert disclose_pma(raw)["pma_cap_verified"] is False


@pytest.mark.parametrize("cap", [True, False, "49", " 49 ", float("inf"), object()])
def test_pma_cap_is_not_coerced_or_allowed_to_escape_malformed(cap: object) -> None:
    raw = {
        **_located_record(),
        "pma_max_asing": cap,
        "pma_cap_verified": True,
    }

    assert disclose_pma(raw)["pma_max_asing"] is None
    assert disclose_pma(raw)["pma_cap_verified"] is False


def test_only_marked_special_and_finite_numeric_caps_are_preserved() -> None:
    marked = disclose_pma(
        {
            **_located_record(),
            "pma_max_asing": "special",
            "pma_cap_special": True,
            "pma_cap_verified": True,
        }
    )
    unmarked = disclose_pma(
        {
            **_located_record(),
            "pma_max_asing": "special",
            "pma_cap_special": False,
            "pma_cap_verified": True,
        }
    )
    assert marked["pma_max_asing"] == "special"
    assert marked["pma_cap_special"] is True
    assert marked["pma_cap_verified"] is True
    assert unmarked["pma_max_asing"] is None
    assert unmarked["pma_cap_special"] is False
    assert unmarked["pma_cap_verified"] is False
    assert (
        disclose_pma({**_located_record(), "pma_max_asing": 49, "pma_cap_verified": True})[
            "pma_max_asing"
        ]
        == 49
    )


@pytest.mark.parametrize(
    "cap",
    [0, 49, "special"],
)
def test_located_cap_is_withheld_without_the_exact_verified_marker(cap: object) -> None:
    raw = {
        **_located_record(),
        "pma_max_asing": cap,
        "pma_cap_special": cap == "special",
        "pma_cap_verified": False,
    }

    disclosed = disclose_pma(raw)
    assert disclosed["pma_status"] == "TERBUKA"
    assert disclosed["pma_verification_status"] == "located"
    assert disclosed["pma_max_asing"] is None
    assert disclosed["pma_cap_special"] is False
    assert disclosed["pma_cap_verified"] is False


def test_located_auxiliary_fields_use_exact_public_types() -> None:
    raw = {
        **_located_record(),
        "pma_kondisi": 7,
        "pma_prioritas": "false",
        "pma_nota": ["unsafe"],
    }

    disclosed = disclose_pma(raw)
    assert disclosed["pma_kondisi"] is None
    assert disclosed["pma_prioritas"] is False
    assert disclosed["pma_nota"] is None
