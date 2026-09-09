"""Guilt+innocence corpus for scripts/conductor/army_assignment.py.

One test per reason code (W1 army-assignment validator), plus the positive
controls from the acceptance spec (A01/A03/A04): a valid multi-level plan,
equal-rank dux acceptance, message-traffic exclusion from cycle detection,
and determinism across repeated calls.
"""

from __future__ import annotations

import copy

import pytest

from scripts.conductor.army_assignment import SCHEMA_VERSION, validate_plan
from scripts.conductor.contracts import Decision


def _valid_appointment(dux: str = "opus") -> dict:
    return {
        "dux": dux,
        "approvals": [
            {"imperator": "fable", "packet_hash": "hash-1"},
            {"imperator": "astra", "packet_hash": "hash-1"},
        ],
        "mission_uuid": "mission-uuid-0001",
    }


def _base_plan(mission_id: str = "m1") -> dict:
    """A valid multi-level plan: general -> specialist -> builder -> support."""
    return {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "G1",
                "mission_id": mission_id,
                "role": "general",
                "parent_id": None,
                "generation": 0,
            },
            {
                "assignment_id": "SP1",
                "mission_id": mission_id,
                "role": "specialist",
                "parent_id": "G1",
                "generation": 1,
            },
            {
                "assignment_id": "B1",
                "mission_id": mission_id,
                "role": "builder",
                "parent_id": "SP1",
                "generation": 2,
            },
            {
                "assignment_id": "SU1",
                "mission_id": mission_id,
                "role": "support",
                "parent_id": "B1",
                "generation": 3,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_valid_multi_level_plan_allows_with_no_reasons():
    result = validate_plan(_base_plan())
    assert result.decision is Decision.ALLOW
    assert result.reason_codes == ()


def test_equal_rank_dux_opus_and_sol_both_allow():
    plan_opus = _base_plan()
    plan_opus["appointment"] = _valid_appointment(dux="opus")
    plan_sol = _base_plan()
    plan_sol["appointment"] = _valid_appointment(dux="sol")

    result_opus = validate_plan(plan_opus)
    result_sol = validate_plan(plan_sol)

    assert result_opus.decision is Decision.ALLOW
    assert result_sol.decision is Decision.ALLOW


def test_message_loop_between_two_nodes_does_not_produce_parent_cycle():
    plan = _base_plan()
    plan["messages"] = [
        {"from": "G1", "to": "SP1"},
        {"from": "SP1", "to": "G1"},
    ]
    result = validate_plan(plan)
    assert result.decision is Decision.ALLOW
    assert "parent_cycle" not in result.reason_codes


def test_validate_plan_is_deterministic_across_repeated_calls():
    plan = _base_plan()
    plan["assignments"].append(
        {
            "assignment_id": "SU1",  # duplicate id, differing parent -> multi-code BLOCK
            "mission_id": "m1",
            "role": "support",
            "parent_id": "G1",
            "generation": 3,
        }
    )
    frozen_plan = copy.deepcopy(plan)

    first = validate_plan(plan)
    second = validate_plan(plan)

    assert first == second
    assert plan == frozen_plan  # validator must never mutate its input


# ---------------------------------------------------------------------------
# Rejection rules — one isolated test per reason code
# ---------------------------------------------------------------------------


def test_unknown_schema_version_missing():
    plan = {"assignments": []}
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "unknown_schema_version" in result.reason_codes


def test_unknown_schema_version_wrong_value():
    plan = _base_plan()
    plan["schema_version"] = "army-assignment/0"
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "unknown_schema_version" in result.reason_codes


def test_missing_required_field_when_role_absent():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "G1",
                "mission_id": "m1",
                "parent_id": None,
                "generation": 0,
            }
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes


def test_missing_required_field_when_mission_id_empty_string():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "G1",
                "mission_id": "",
                "role": "general",
                "parent_id": None,
                "generation": 0,
            }
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes


def test_duplicate_assignment_id():
    plan = _base_plan()
    plan["assignments"].append(
        {
            "assignment_id": "G1",  # duplicate, SAME parent -> isolate from two_operational_parents
            "mission_id": "m1",
            "role": "general",
            "parent_id": None,
            "generation": 0,
        }
    )
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "duplicate_assignment_id" in result.reason_codes
    assert "G1" in result.offending_ids


def test_dangling_parent():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "SP1",
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": "GHOST",
                "generation": 0,
            }
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "dangling_parent" in result.reason_codes
    assert "SP1" in result.offending_ids


def test_cross_mission_edge():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "G1",
                "mission_id": "m1",
                "role": "general",
                "parent_id": None,
                "generation": 0,
            },
            {
                "assignment_id": "G2",
                "mission_id": "m2",
                "role": "general",
                "parent_id": None,
                "generation": 0,
            },
            {
                "assignment_id": "SP1",
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": "G2",  # parent lives in mission m2
                "generation": 1,
            },
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "cross_mission_edge" in result.reason_codes
    assert "SP1" in result.offending_ids


def test_parent_cycle_two_node_loop():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "A",
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": "B",
                "generation": 0,
            },
            {
                "assignment_id": "B",
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": "A",
                "generation": 0,
            },
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "parent_cycle" in result.reason_codes
    assert {"A", "B"} <= set(result.offending_ids)


def test_parent_cycle_self_parent():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "X",
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": "X",
                "generation": 0,
            }
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "parent_cycle" in result.reason_codes
    assert "X" in result.offending_ids


def test_unassigned_parent():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "SP1",
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": None,
                "generation": 0,
            }
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "unassigned_parent" in result.reason_codes
    assert "SP1" in result.offending_ids


def test_two_operational_parents():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "G1",
                "mission_id": "m1",
                "role": "general",
                "parent_id": None,
                "generation": 0,
            },
            {
                "assignment_id": "G2",
                "mission_id": "m1",
                "role": "general",
                "parent_id": None,
                "generation": 0,
            },
            {
                "assignment_id": "SP1",
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": "G1",
                "generation": 1,
            },
            {
                "assignment_id": "SP1",  # same id, DIFFERENT parent
                "mission_id": "m1",
                "role": "specialist",
                "parent_id": "G2",
                "generation": 1,
            },
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "two_operational_parents" in result.reason_codes
    assert "SP1" in result.offending_ids


def test_invalid_generation():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "G1",
                "mission_id": "m1",
                "role": "general",
                "parent_id": None,
                "generation": -1,
            }
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "invalid_generation" in result.reason_codes
    assert "G1" in result.offending_ids


def test_invalid_generation_non_int():
    plan = {
        "schema_version": SCHEMA_VERSION,
        "assignments": [
            {
                "assignment_id": "G1",
                "mission_id": "m1",
                "role": "general",
                "parent_id": None,
                "generation": "zero",
            }
        ],
    }
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "invalid_generation" in result.reason_codes


def test_invalid_dux_candidate():
    plan = _base_plan()
    appointment = _valid_appointment()
    appointment["dux"] = "caesar"
    plan["appointment"] = appointment
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "invalid_dux_candidate" in result.reason_codes


def test_missing_imperator_approval():
    plan = _base_plan()
    appointment = _valid_appointment()
    appointment["approvals"] = [{"imperator": "fable", "packet_hash": "hash-1"}]
    plan["appointment"] = appointment
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "missing_imperator_approval" in result.reason_codes


def test_packet_hash_mismatch():
    plan = _base_plan()
    appointment = _valid_appointment()
    appointment["approvals"] = [
        {"imperator": "fable", "packet_hash": "hash-1"},
        {"imperator": "astra", "packet_hash": "hash-2"},
    ]
    plan["appointment"] = appointment
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "packet_hash_mismatch" in result.reason_codes


def test_self_supplied_uuid_when_mission_uuid_absent():
    plan = _base_plan()
    appointment = _valid_appointment()
    del appointment["mission_uuid"]
    plan["appointment"] = appointment
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "self_supplied_uuid" in result.reason_codes


def test_self_supplied_uuid_when_flagged_truthy():
    plan = _base_plan()
    appointment = _valid_appointment()
    appointment["uuid_self_supplied"] = True
    plan["appointment"] = appointment
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "self_supplied_uuid" in result.reason_codes


def test_missing_imperator_approval_on_repeated_imperator_same_hash():
    """Each imperator approves exactly once; a repeat is not a stronger

    approval, it is a missing one — "fable" approving twice, even with
    identical hashes, leaves "fable"'s single required approval absent.
    """
    plan = _base_plan()
    appointment = _valid_appointment(dux="sol")
    appointment["mission_uuid"] = "ext-uuid-1"
    appointment["approvals"] = [
        {"imperator": "fable", "packet_hash": "h1"},
        {"imperator": "fable", "packet_hash": "h1"},
        {"imperator": "astra", "packet_hash": "h1"},
    ]
    plan["appointment"] = appointment
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "missing_imperator_approval" in result.reason_codes
    assert "packet_hash_mismatch" not in result.reason_codes


def test_missing_imperator_approval_on_repeated_imperator_clashing_hash():
    """Pinned behaviour: a repeated imperator is `missing_imperator_approval`

    regardless of whether its duplicate hashes agree or clash — the clashing
    duplicate must not surface as `packet_hash_mismatch` instead, since that
    would make the earlier last-wins overwrite bug's symptom look intentional.
    """
    plan = _base_plan()
    appointment = _valid_appointment(dux="sol")
    appointment["mission_uuid"] = "ext-uuid-1"
    appointment["approvals"] = [
        {"imperator": "fable", "packet_hash": "h1"},
        {"imperator": "fable", "packet_hash": "h2"},
        {"imperator": "astra", "packet_hash": "h1"},
    ]
    plan["appointment"] = appointment
    result = validate_plan(plan)
    assert result.decision is Decision.BLOCK
    assert "missing_imperator_approval" in result.reason_codes
    assert "packet_hash_mismatch" not in result.reason_codes


def test_non_dict_payload_returns_structured_block():
    result = validate_plan(["not", "a", "dict"])
    assert result.decision is Decision.BLOCK
    assert "missing_required_field" in result.reason_codes
