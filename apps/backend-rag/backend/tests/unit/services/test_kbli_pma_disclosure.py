"""Atomic disclosure contract for KBLI PMA claims."""

from __future__ import annotations

import pytest

from backend.services.kbli_pma_disclosure import disclose_pma, pma_claims_verified


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
