"""Tests for claims extraction pure functions (no I/O, no API calls)."""
from __future__ import annotations

from scripts.claims_extractor import (
    generate_claim_id,
    parse_claims_response,
    stamp_claims,
    validate_claim,
)


def test_generate_claim_id_sequential() -> None:
    assert generate_claim_id("immigration", 1) == "IMM-001"
    assert generate_claim_id("immigration", 42) == "IMM-042"
    assert generate_claim_id("company", 7) == "COM-007"
    assert generate_claim_id("tax", 100) == "TAX-100"
    assert generate_claim_id("property", 5) == "PRO-005"


def test_parse_claims_response_valid() -> None:
    llm_output = '''
[
  {
    "claim": "Il KITAS dura massimo 2 anni.",
    "verbatim": "Pasal 52: Izin Tinggal Terbatas diberikan untuk paling lama 2 tahun.",
    "pasal_ref": "UU 6/2011 Pasal 52",
    "instrument_id": "UU-6-2011",
    "category": "duration"
  }
]
'''
    claims = parse_claims_response(llm_output)
    assert len(claims) == 1
    assert "2 anni" in claims[0]["claim"]
    assert claims[0]["instrument_id"] == "UU-6-2011"


def test_parse_claims_response_strips_markdown() -> None:
    llm_output = '```json\n[{"claim":"T","verbatim":"V","pasal_ref":"P","instrument_id":"I","category":"rule"}]\n```'
    claims = parse_claims_response(llm_output)
    assert len(claims) == 1
    assert claims[0]["claim"] == "T"


def test_parse_claims_response_invalid_json() -> None:
    claims = parse_claims_response("not json at all")
    assert claims == []


def test_validate_claim_complete() -> None:
    claim = {
        "claim": "KITAS E28 berlaku 2 tahun.",
        "verbatim": "Pasal 52: Izin Tinggal Terbatas...",
        "pasal_ref": "Permenkumham 22/2023 Pasal 52",
        "instrument_id": "Permenkumham-22-2023",
        "category": "duration",
    }
    assert validate_claim(claim) is True


def test_validate_claim_missing_verbatim() -> None:
    claim = {
        "claim": "Test claim",
        "pasal_ref": "UU 6/2011 Pasal 1",
        "instrument_id": "UU-6-2011",
        "category": "rule",
        # missing "verbatim"
    }
    assert validate_claim(claim) is False


def test_stamp_claims_adds_ids_and_filters_invalid() -> None:
    claims = [
        {"claim": "C1", "verbatim": "V1", "pasal_ref": "P1", "instrument_id": "I1", "category": "rule"},
        {"claim": "C2", "verbatim": "V2", "pasal_ref": "P2", "instrument_id": "I2"},  # missing category
        {"claim": "C3", "verbatim": "V3", "pasal_ref": "P3", "instrument_id": "I3", "category": "procedure"},
    ]
    stamped = stamp_claims(claims, "immigration", start_index=5)
    assert len(stamped) == 2  # one invalid filtered
    assert stamped[0]["claim_id"] == "IMM-005"
    assert stamped[1]["claim_id"] == "IMM-006"
