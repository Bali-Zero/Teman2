"""Registry-shape tests for MANDATE.md F5's ten-tool risk-tiered registry.

Verifies the registry itself is internally coherent (exact count, unique
names, F5's structural requirements — enums not free text, IDs not names,
additionalProperties:false, one mutation per tool) rather than re-testing
pydantic's own validation machinery.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from team_bot.registry import (
    TOOL_NAMES,
    TOOL_REGISTRY,
    ConfirmPolicy,
    RiskTier,
    ToolKind,
    ToolSpec,
    get_tool,
)


def test_registry_has_exactly_ten_tools() -> None:
    assert len(TOOL_REGISTRY) == 10
    assert len(TOOL_NAMES) == 10


def test_tool_names_are_unique_and_match_qwen_4_verbatim() -> None:
    expected = {
        "search_clients",
        "get_client",
        "list_practices",
        "get_practice",
        "get_required_documents",
        "list_assignable_staff",
        "mark_document_received",
        "create_reminder",
        "update_practice_status",
        "open_practice",
    }
    assert TOOL_NAMES == expected


def test_risk_tier_distribution_matches_qwen_4_table() -> None:
    """R0=6 reads, R1=1 (create_reminder), R2=1 (mark_document_received),
    R3=2 (update_practice_status, open_practice) — Qwen §4's own "Tool
    summary" table, verbatim."""
    counts: dict[RiskTier, int] = {tier: 0 for tier in RiskTier}
    for spec in TOOL_REGISTRY:
        counts[spec.risk_tier] += 1
    assert counts[RiskTier.R0] == 6
    assert counts[RiskTier.R1] == 1
    assert counts[RiskTier.R2] == 1
    assert counts[RiskTier.R3] == 2


@pytest.mark.parametrize(
    ("name", "expected_tier", "expected_policy"),
    [
        ("search_clients", RiskTier.R0, ConfirmPolicy.NEVER),
        ("get_client", RiskTier.R0, ConfirmPolicy.NEVER),
        ("list_practices", RiskTier.R0, ConfirmPolicy.NEVER),
        ("get_practice", RiskTier.R0, ConfirmPolicy.NEVER),
        ("get_required_documents", RiskTier.R0, ConfirmPolicy.NEVER),
        ("list_assignable_staff", RiskTier.R0, ConfirmPolicy.NEVER),
        ("mark_document_received", RiskTier.R2, ConfirmPolicy.CONDITIONAL),
        ("create_reminder", RiskTier.R1, ConfirmPolicy.NO_CONFIRM_UNDO),
        ("update_practice_status", RiskTier.R3, ConfirmPolicy.ALWAYS),
        ("open_practice", RiskTier.R3, ConfirmPolicy.ALWAYS),
    ],
)
def test_each_tool_carries_its_frozen_tier_and_policy(
    name: str, expected_tier: RiskTier, expected_policy: ConfirmPolicy
) -> None:
    spec = get_tool(name)
    assert spec is not None
    assert spec.risk_tier == expected_tier
    assert spec.confirm_policy == expected_policy


def test_r0_tools_are_read_kind_and_r1_r2_r3_are_mutation_kind() -> None:
    for spec in TOOL_REGISTRY:
        if spec.risk_tier == RiskTier.R0:
            assert spec.kind == ToolKind.READ
        else:
            assert spec.kind == ToolKind.MUTATION


def test_conditional_confirm_carries_a_condition_and_others_do_not() -> None:
    for spec in TOOL_REGISTRY:
        if spec.confirm_policy == ConfirmPolicy.CONDITIONAL:
            assert spec.confirm_condition is not None
            assert spec.confirm_condition.strip() != ""
        else:
            assert spec.confirm_condition is None


def test_every_tool_forbids_additional_properties() -> None:
    """F5: 'additionalProperties:false, one mutation per tool'."""
    for spec in TOOL_REGISTRY:
        assert spec.parameters_schema.get("additionalProperties") is False, spec.name


def test_every_tool_id_field_uses_a_pattern_not_free_text() -> None:
    """F5: 'IDs not names (^PR-, ^CL-, ^USR- patterns)'."""
    id_field_names = {"client_id", "practice_id", "assigned_to", "target_id"}
    for spec in TOOL_REGISTRY:
        props = spec.parameters_schema.get("properties", {})
        assert isinstance(props, dict)
        for field_name in id_field_names & props.keys():
            field_schema = props[field_name]
            assert isinstance(field_schema, dict)
            assert "pattern" in field_schema, f"{spec.name}.{field_name} has no ID pattern"
            assert field_schema["pattern"].startswith("^"), f"{spec.name}.{field_name}"


def test_open_practice_requires_all_five_business_fields() -> None:
    """The R3 high-mutation tool must not silently accept a partial call —
    Qwen §4 tool 10's `required` array, verbatim."""
    spec = get_tool("open_practice")
    assert spec is not None
    assert spec.parameters_schema["required"] == [
        "client_id",
        "practice_type",
        "assigned_to",
        "priority",
        "source_channel",
    ]


def test_mark_document_received_source_is_not_open_practice_source_channel() -> None:
    """Regression guard for the deliberate split documented in
    envelope.py's SourceChannel docstring: `courier` only exists on
    mark_document_received, `meeting` only on open_practice."""
    received = get_tool("mark_document_received")
    opened = get_tool("open_practice")
    assert received is not None and opened is not None

    received_sources = set(received.parameters_schema["properties"]["source"]["enum"])
    opened_sources = set(opened.parameters_schema["properties"]["source_channel"]["enum"])

    assert "courier" in received_sources
    assert "courier" not in opened_sources
    assert "meeting" in opened_sources
    assert "meeting" not in received_sources


def test_get_tool_is_exact_match_never_substring() -> None:
    """cicatrix-superscar.md family #3 — guard-over-match by substring."""
    assert get_tool("get_client") is not None
    assert get_tool("get_clie") is None
    assert get_tool("get_client_extra") is None
    assert get_tool("") is None


def test_tier_policy_mismatch_is_rejected_at_construction() -> None:
    """The tier<->policy 1:1 mapping is enforced by the model itself, not
    just by how tools.py happens to construct the frozen ten — a future
    edit that desyncs them fails immediately, not at some downstream
    consumer."""
    with pytest.raises(ValidationError):
        ToolSpec(
            name="bad_tool",
            kind=ToolKind.READ,
            risk_tier=RiskTier.R0,
            confirm_policy=ConfirmPolicy.ALWAYS,  # wrong for R0
            description="x",
            parameters_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        )


def test_conditional_policy_without_condition_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolSpec(
            name="bad_tool",
            kind=ToolKind.MUTATION,
            risk_tier=RiskTier.R2,
            confirm_policy=ConfirmPolicy.CONDITIONAL,
            confirm_condition=None,
            description="x",
            parameters_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        )


def test_missing_additional_properties_false_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolSpec(
            name="bad_tool",
            kind=ToolKind.READ,
            risk_tier=RiskTier.R0,
            confirm_policy=ConfirmPolicy.NEVER,
            description="x",
            parameters_schema={"type": "object", "properties": {}, "required": []},
        )
