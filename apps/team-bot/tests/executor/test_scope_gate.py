"""Guilt+innocence pairs for scope_gate.py (cicatrix-superscar family #3:
a guard shipped with only its guilty case tested is the anti-pattern).
"""

from __future__ import annotations

from team_bot.executor.scope_gate import (
    ScopeGateDenyReason,
    crm_record_ids_in,
    evaluate_early_deny,
    is_valid_principal_id,
)

# ---------------------------------------------------------------------------
# is_valid_principal_id
# ---------------------------------------------------------------------------


def test_innocence_well_formed_principal_id_is_valid() -> None:
    assert is_valid_principal_id("USR-001") is True
    assert is_valid_principal_id("wa-hmac-abc123_XYZ") is True


def test_guilt_empty_principal_id_is_invalid() -> None:
    assert is_valid_principal_id("") is False


def test_guilt_principal_id_with_illegal_characters_is_invalid() -> None:
    # PRINCIPAL_ID_PATTERN is [A-Za-z0-9_-] only — a space or slash must fail.
    assert is_valid_principal_id("USR 001") is False
    assert is_valid_principal_id("USR/001") is False


def test_guilt_principal_id_partial_match_is_rejected() -> None:
    # A regex without fullmatch would let "USR-001<script>" slide if the
    # pattern were anchored with a bare `match`; this proves fullmatch is
    # actually in effect (a leading/trailing illegal char must fail whole).
    assert is_valid_principal_id("USR-001 ") is False
    assert is_valid_principal_id(" USR-001") is False


# ---------------------------------------------------------------------------
# evaluate_early_deny
# ---------------------------------------------------------------------------


def test_innocence_valid_principal_is_allowed() -> None:
    verdict = evaluate_early_deny(principal_id="USR-001")
    assert verdict.allow is True
    assert verdict.deny_reason is None


def test_guilt_missing_principal_is_denied() -> None:
    verdict = evaluate_early_deny(principal_id="")
    assert verdict.allow is False
    assert verdict.deny_reason is ScopeGateDenyReason.MISSING_OR_MALFORMED_PRINCIPAL


def test_guilt_malformed_principal_is_denied() -> None:
    verdict = evaluate_early_deny(principal_id="not a principal!")
    assert verdict.allow is False
    assert verdict.deny_reason is ScopeGateDenyReason.MISSING_OR_MALFORMED_PRINCIPAL


# ---------------------------------------------------------------------------
# crm_record_ids_in — the record-reference scan get_required_documents
# itself never triggers (no CL-/PR- shaped argument exists in its schema),
# proven here against a SYNTHETIC args shape standing in for a future tool
# that does carry one (e.g. get_practice(practice_id=...)).
# ---------------------------------------------------------------------------


def test_innocence_get_required_documents_shaped_args_reference_no_record() -> None:
    # practice_type is an enum member, never a CL-/PR- shaped string.
    assert crm_record_ids_in({"practice_type": "limited_stay_kitas"}) == ()


def test_guilt_practice_id_shaped_arg_is_detected() -> None:
    assert crm_record_ids_in({"practice_id": "PR-1234"}) == ("PR-1234",)


def test_guilt_client_id_shaped_arg_is_detected() -> None:
    assert crm_record_ids_in({"client_id": "CL-9999"}) == ("CL-9999",)


def test_innocence_a_string_that_merely_contains_the_prefix_is_not_matched() -> None:
    # Substring-trap check (cicatrix family #3): "PR-12" embedded inside a
    # longer, unrelated string must NOT be treated as a record reference —
    # crm_record_ids_in uses fullmatch, not a bare "in"/search.
    assert crm_record_ids_in({"note": "see PR-1234 for details"}) == ()


def test_innocence_non_string_values_are_ignored() -> None:
    assert crm_record_ids_in({"limit": 5, "flag": True}) == ()


def test_duplicate_record_ids_are_deduplicated_in_order() -> None:
    assert crm_record_ids_in({"a": "PR-1000", "b": "PR-1000", "c": "PR-2000"}) == ("PR-1000", "PR-2000")
