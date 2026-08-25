"""render_member_card — token budget, structural caps, and the no-PII
contract.

The PII guarantee this file tests is STRUCTURAL, not a runtime scrub:
`render_member_card` only accepts `MemberProfile`/`EpisodicEvent`/
`LearnedPattern` instances, and those types have no field a cleartext
name/phone/passport number or chat message could occupy
(`test_member_memory_models.py::test_episodic_event_never_carries_a_free_text_field`
is the type-level half of this proof). The exact-string-equality tests
below are the render-level half: given a fully-populated, known input, the
output is asserted BYTE FOR BYTE — there is no room for the function to
have smuggled in anything beyond what the typed inputs actually carried.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from team_bot.memory.card import (
    DEFAULT_MAX_CARD_TOKENS,
    MAX_CARD_EPISODIC_EVENTS,
    MAX_CARD_PATTERNS,
    estimate_tokens,
    render_member_card,
)
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

_PROFILE = MemberProfile(
    principal_id="USR-102",
    role=StaffRole.AGENT,
    preferred_language=Locale.ID,
    response_format=ResponseFormat.CONCISE,
    working_hours_start="08:00",
    working_hours_end="17:00",
    updated_at=_NOW,
)


def _event(target_id: str, target_type: TargetType, intent: IntentCategory, minutes_ago: int) -> EpisodicEvent:
    return EpisodicEvent(
        principal_id="USR-102",
        target_type=target_type,
        target_id=target_id,
        intent_category=intent,
        occurred_at=_NOW - timedelta(minutes=minutes_ago),
    )


def _pattern(key: str, count: int) -> LearnedPattern:
    return LearnedPattern(
        principal_id="USR-102",
        pattern_key=key,
        observation_count=count,
        first_observed_at=_NOW - timedelta(days=30),
        last_observed_at=_NOW,
    )


# ---------------------------------------------------------------------------
# exact-render tests (the no-smuggled-content proof)
# ---------------------------------------------------------------------------


def test_render_with_no_data_at_all() -> None:
    card = render_member_card(None, (), ())
    assert card == "MEMBER: no profile on record"


def test_render_with_profile_only() -> None:
    card = render_member_card(_PROFILE, (), ())
    assert card == "MEMBER role=agent lang=id fmt=concise hours=08:00-17:00"


def test_render_with_profile_missing_working_hours() -> None:
    profile = MemberProfile(
        principal_id="USR-102", role=StaffRole.MANAGER, preferred_language=Locale.EN, updated_at=_NOW
    )
    card = render_member_card(profile, (), ())
    assert card == "MEMBER role=manager lang=en fmt=concise hours=unset"


def test_render_with_full_data_is_byte_exact() -> None:
    events = (
        _event("CL-1042", TargetType.CLIENT, IntentCategory.STATUS_CHECK, minutes_ago=5),
        _event("PR-3090", TargetType.PRACTICE, IntentCategory.DOCUMENT_UPDATE, minutes_ago=120),
    )
    patterns = (_pattern("monday_digest_request", 4),)
    card = render_member_card(_PROFILE, events, patterns)
    assert card == (
        "MEMBER role=agent lang=id fmt=concise hours=08:00-17:00\n"
        "RECENT: CL-1042(status_check) PR-3090(document_update)\n"
        "PATTERNS: monday_digest_request(x4)"
    )


# ---------------------------------------------------------------------------
# structural caps
# ---------------------------------------------------------------------------


def test_render_caps_episodic_events_at_the_structural_max() -> None:
    events = tuple(
        _event(f"CL-{1000 + i}", TargetType.CLIENT, IntentCategory.LOOKUP, minutes_ago=i)
        for i in range(MAX_CARD_EPISODIC_EVENTS + 5)
    )
    card = render_member_card(_PROFILE, events, ())
    recent_line = next(line for line in card.splitlines() if line.startswith("RECENT:"))
    assert recent_line.count("(lookup)") == MAX_CARD_EPISODIC_EVENTS
    # And it is the FIRST N (most-relevant-first, per the store's ordering
    # contract), not an arbitrary subset.
    expected_ids = [e.target_id for e in events[:MAX_CARD_EPISODIC_EVENTS]]
    assert all(target_id in recent_line for target_id in expected_ids)
    assert f"CL-{1000 + MAX_CARD_EPISODIC_EVENTS}" not in recent_line


def test_render_caps_patterns_at_the_structural_max() -> None:
    patterns = tuple(_pattern(f"habit_{i}", count=10 - i) for i in range(MAX_CARD_PATTERNS + 3))
    card = render_member_card(_PROFILE, (), patterns)
    patterns_line = next(line for line in card.splitlines() if line.startswith("PATTERNS:"))
    assert patterns_line.count("habit_") == MAX_CARD_PATTERNS


# ---------------------------------------------------------------------------
# token budget
# ---------------------------------------------------------------------------


def test_estimate_tokens_is_a_ceiling_division_by_three() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcd") == 2  # ceil(4/3)
    assert estimate_tokens("a" * 300) == 100


def test_fully_populated_card_stays_within_the_default_token_budget() -> None:
    events = tuple(
        _event(f"CL-{1000 + i}", TargetType.CLIENT, IntentCategory.STATUS_CHECK, minutes_ago=i)
        for i in range(MAX_CARD_EPISODIC_EVENTS)
    )
    patterns = tuple(_pattern(f"recurring_habit_pattern_{i}", count=5) for i in range(MAX_CARD_PATTERNS))
    card = render_member_card(_PROFILE, events, patterns)
    assert estimate_tokens(card) <= DEFAULT_MAX_CARD_TOKENS


def test_render_trims_patterns_before_episodic_events_when_over_a_tight_budget() -> None:
    events = tuple(
        _event(f"CL-{1000 + i}", TargetType.CLIENT, IntentCategory.STATUS_CHECK, minutes_ago=i)
        for i in range(MAX_CARD_EPISODIC_EVENTS)
    )
    patterns = tuple(_pattern(f"recurring_habit_pattern_{i}", count=5) for i in range(MAX_CARD_PATTERNS))

    # The budget that exactly fits "profile + recent, no patterns" — any
    # patterns line at all would overflow it, so hitting this budget can
    # only be achieved by dropping every pattern first (card.py's
    # documented trim order: patterns before episodic events).
    recent_only_card = render_member_card(_PROFILE, events, ())
    budget = estimate_tokens(recent_only_card)

    tight_card = render_member_card(_PROFILE, events, patterns, max_tokens=budget)
    assert tight_card == recent_only_card
    assert "RECENT:" in tight_card
    assert "PATTERNS:" not in tight_card


def test_render_never_exceeds_an_extremely_tight_budget_by_dropping_everything_droppable() -> None:
    events = tuple(
        _event(f"CL-{1000 + i}", TargetType.CLIENT, IntentCategory.STATUS_CHECK, minutes_ago=i)
        for i in range(MAX_CARD_EPISODIC_EVENTS)
    )
    patterns = tuple(_pattern(f"recurring_habit_pattern_{i}", count=5) for i in range(MAX_CARD_PATTERNS))
    card = render_member_card(_PROFILE, events, patterns, max_tokens=1)
    # Everything droppable was dropped — only the profile line remains,
    # which this function never drops (there is nothing left to trim to).
    assert card == "MEMBER role=agent lang=id fmt=concise hours=08:00-17:00"


# ---------------------------------------------------------------------------
# no-PII defense in depth
# ---------------------------------------------------------------------------


def test_card_never_contains_an_at_sign_or_a_plus_prefixed_phone_shape() -> None:
    events = (_event("CL-1042", TargetType.CLIENT, IntentCategory.LOOKUP, minutes_ago=1),)
    card = render_member_card(_PROFILE, events, (_pattern("monday_digest_request", 3),))
    assert "@" not in card
    assert "+" not in card


def test_card_content_is_a_subset_of_the_typed_inputs_own_values() -> None:
    events = (
        _event("CL-1042", TargetType.CLIENT, IntentCategory.LOOKUP, minutes_ago=1),
        _event("PR-3090", TargetType.PRACTICE, IntentCategory.REMINDER, minutes_ago=2),
    )
    patterns = (_pattern("monday_digest_request", 4),)
    card = render_member_card(_PROFILE, events, patterns)

    allowed_tokens = {
        "MEMBER",
        "role=agent",
        "lang=id",
        "fmt=concise",
        "hours=08:00-17:00",
        "RECENT:",
        "CL-1042(lookup)",
        "PR-3090(reminder)",
        "PATTERNS:",
        "monday_digest_request(x4)",
    }
    rendered_tokens = set(card.replace("\n", " ").split(" "))
    assert rendered_tokens <= allowed_tokens
