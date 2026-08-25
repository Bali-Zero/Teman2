"""Data-shape tests for team_bot.memory.models — guilt/innocence pairs for
every invariant, matching the house style (`test_confirmation_models.py`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from team_bot.memory.models import (
    EpisodicEvent,
    IntentCategory,
    LearnedPattern,
    Locale,
    MemberProfile,
    ResponseFormat,
    StaffRole,
    TargetType,
)

_NOW = datetime(2026, 8, 25, 10, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# MemberProfile
# ---------------------------------------------------------------------------


def test_member_profile_accepts_a_well_formed_row() -> None:
    profile = MemberProfile(
        principal_id="USR-102",
        role=StaffRole.AGENT,
        preferred_language=Locale.ID,
        response_format=ResponseFormat.CONCISE,
        working_hours_start="08:00",
        working_hours_end="17:00",
        updated_at=_NOW,
    )
    assert profile.role == StaffRole.AGENT
    assert profile.working_hours_start == "08:00"


def test_member_profile_rejects_a_raw_phone_shaped_principal_id() -> None:
    # F7's own text: "Raw phone never in logs" — principal_id is an opaque
    # token, never something that LOOKS like a phone number is a positive
    # test of the pattern's SHAPE, not a claim this module can detect
    # phone numbers semantically; +62-prefixed strings simply fail the
    # PRINCIPAL_ID_PATTERN character class (no leading '+').
    with pytest.raises(ValidationError):
        MemberProfile(
            principal_id="+6281234567890",
            role=StaffRole.AGENT,
            preferred_language=Locale.EN,
            updated_at=_NOW,
        )


def test_member_profile_rejects_malformed_working_hours() -> None:
    with pytest.raises(ValidationError):
        MemberProfile(
            principal_id="USR-102",
            role=StaffRole.AGENT,
            preferred_language=Locale.EN,
            working_hours_start="8:00",  # missing leading zero
            updated_at=_NOW,
        )


def test_member_profile_rejects_an_out_of_range_hour() -> None:
    with pytest.raises(ValidationError):
        MemberProfile(
            principal_id="USR-102",
            role=StaffRole.AGENT,
            preferred_language=Locale.EN,
            working_hours_start="24:00",
            updated_at=_NOW,
        )


def test_member_profile_defaults_response_format_to_concise() -> None:
    profile = MemberProfile(
        principal_id="USR-102", role=StaffRole.MANAGER, preferred_language=Locale.IT, updated_at=_NOW
    )
    assert profile.response_format == ResponseFormat.CONCISE


def test_member_profile_rejects_an_unknown_field() -> None:
    with pytest.raises(ValidationError):
        MemberProfile(
            principal_id="USR-102",
            role=StaffRole.AGENT,
            preferred_language=Locale.EN,
            updated_at=_NOW,
            full_name="Should Never Exist",  # type: ignore[call-arg]
        )


def test_member_profile_is_frozen() -> None:
    profile = MemberProfile(
        principal_id="USR-102", role=StaffRole.AGENT, preferred_language=Locale.EN, updated_at=_NOW
    )
    with pytest.raises(ValidationError):
        profile.role = StaffRole.ADMIN  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EpisodicEvent
# ---------------------------------------------------------------------------


def test_episodic_event_accepts_a_matching_target_type_and_id() -> None:
    event = EpisodicEvent(
        principal_id="USR-102",
        target_type=TargetType.CLIENT,
        target_id="CL-1042",
        intent_category=IntentCategory.STATUS_CHECK,
        occurred_at=_NOW,
    )
    assert event.target_id == "CL-1042"


def test_episodic_event_rejects_a_client_target_type_with_a_practice_id() -> None:
    with pytest.raises(ValidationError):
        EpisodicEvent(
            principal_id="USR-102",
            target_type=TargetType.CLIENT,
            target_id="PR-3090",
            intent_category=IntentCategory.STATUS_CHECK,
            occurred_at=_NOW,
        )


def test_episodic_event_rejects_a_practice_target_type_with_a_client_id() -> None:
    with pytest.raises(ValidationError):
        EpisodicEvent(
            principal_id="USR-102",
            target_type=TargetType.PRACTICE,
            target_id="CL-1042",
            intent_category=IntentCategory.STATUS_CHECK,
            occurred_at=_NOW,
        )


def test_episodic_event_never_carries_a_free_text_field() -> None:
    # Structural guarantee, not a runtime scrub: there is no field this
    # model would even accept for a raw request/message string.
    assert "request_text" not in EpisodicEvent.model_fields
    assert "message" not in EpisodicEvent.model_fields
    assert set(EpisodicEvent.model_fields) == {
        "principal_id",
        "target_type",
        "target_id",
        "intent_category",
        "tool_name",
        "occurred_at",
    }


# ---------------------------------------------------------------------------
# LearnedPattern
# ---------------------------------------------------------------------------


def test_learned_pattern_accepts_a_well_formed_row() -> None:
    pattern = LearnedPattern(
        principal_id="USR-102",
        pattern_key="monday_digest_request",
        observation_count=4,
        first_observed_at=_NOW,
        last_observed_at=_NOW,
    )
    assert pattern.observation_count == 4


def test_learned_pattern_rejects_a_non_snake_case_key() -> None:
    with pytest.raises(ValidationError):
        LearnedPattern(
            principal_id="USR-102",
            pattern_key="Monday Digest Request",
            observation_count=1,
            first_observed_at=_NOW,
            last_observed_at=_NOW,
        )


def test_learned_pattern_rejects_zero_observations() -> None:
    with pytest.raises(ValidationError):
        LearnedPattern(
            principal_id="USR-102",
            pattern_key="monday_digest_request",
            observation_count=0,
            first_observed_at=_NOW,
            last_observed_at=_NOW,
        )


def test_learned_pattern_rejects_last_observed_before_first_observed() -> None:
    earlier = _NOW
    later = _NOW.replace(hour=11)
    with pytest.raises(ValidationError):
        LearnedPattern(
            principal_id="USR-102",
            pattern_key="monday_digest_request",
            observation_count=2,
            first_observed_at=later,
            last_observed_at=earlier,
        )
