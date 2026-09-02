"""Unit tests for `staff_transitions.validate_transition_body` — no DB needed,
this function is pure. Covers the cross-family refuter's MAJOR finding #1
(Codex): `evidence_id`/`artifact_id`/`resolved_block_id` previously checked
only LENGTH (16-128), matching the database CHECK constraint's length bound
but not its character class (`^[A-Za-z0-9_-]{16,128}$`,
`305_garuda_practices_assignment.sql:148`). A value that passes the
length-only check but fails the DB's character-class CHECK used to reach
`apply_transition`'s INSERT and crash with an unhandled
`asyncpg.CheckViolationError` -> HTTP 500, instead of the contract's 422
INVALID_REQUEST. This file proves the 422 happens at validation time, before
any DB round-trip.

`pytest.raises` is inlined in every test body (not delegated to a shared
helper) so `scripts/lint_test_reward_hacking.py`'s RH005 heuristic -- which
only looks for an assert/raises literal in the test's own body, not inside a
helper it calls -- sees the real assertion, not a false RH005.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.services.garuda_portal.staff_transitions import validate_transition_body

_VALID_REASON = "garuda_voa.practice.missing_document"


class TestEvidenceIdCharacterClass:
    """PR-04 (submit) / PR-06 (approve) / PR-07 (reject) all validate
    `evidence_id` through the same character-class check -- guilt+innocence
    across all three call sites, not just one."""

    @pytest.mark.parametrize("transition_id", ["PR-04", "PR-06"])
    def test_whitespace_in_evidence_id_is_422_not_a_db_crash(self, transition_id: str) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_body(transition_id, {"evidence_id": "has a space" + "x" * 10})
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "INVALID_REQUEST"

    @pytest.mark.parametrize("transition_id", ["PR-04", "PR-06"])
    def test_punctuation_in_evidence_id_is_422(self, transition_id: str) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_body(transition_id, {"evidence_id": "bad!chars!!!" + "x" * 10})
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "INVALID_REQUEST"

    @pytest.mark.parametrize("transition_id", ["PR-04", "PR-06"])
    def test_valid_evidence_id_passes(self, transition_id: str) -> None:
        fields = validate_transition_body(transition_id, {"evidence_id": "valid_evidence-id0001"})
        assert fields["evidence_id"] == "valid_evidence-id0001"

    def test_reject_rejects_malformed_evidence_id(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_body(
                "PR-07",
                {"evidence_id": "bad space" + "x" * 10, "customer_reason_key": _VALID_REASON},
            )
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "INVALID_REQUEST"

    def test_reject_accepts_well_formed_evidence_id(self) -> None:
        fields = validate_transition_body(
            "PR-07",
            {"evidence_id": "valid_evidence-id0001", "customer_reason_key": _VALID_REASON},
        )
        assert fields["evidence_id"] == "valid_evidence-id0001"


class TestArtifactIdCharacterClass:
    def test_whitespace_in_artifact_id_is_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_body(
                "PR-11",
                {"artifact_id": "bad artifact" + "x" * 10, "artifact_digest": "a" * 64},
            )
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "INVALID_REQUEST"

    def test_valid_artifact_id_passes(self) -> None:
        fields = validate_transition_body(
            "PR-11",
            {"artifact_id": "valid_artifact-id00001", "artifact_digest": "a" * 64},
        )
        assert fields["artifact_id"] == "valid_artifact-id00001"


class TestResolvedBlockIdCharacterClass:
    @pytest.mark.parametrize("transition_id", ["PR-09", "PR-10"])
    def test_whitespace_in_resolved_block_id_is_422(self, transition_id: str) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_body(transition_id, {"resolved_block_id": "bad block" + "x" * 10})
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "INVALID_REQUEST"

    @pytest.mark.parametrize("transition_id", ["PR-09", "PR-10"])
    def test_valid_resolved_block_id_passes(self, transition_id: str) -> None:
        fields = validate_transition_body(transition_id, {"resolved_block_id": "valid_block-id0000001"})
        assert fields["resolved_block_id"] == "valid_block-id0000001"
