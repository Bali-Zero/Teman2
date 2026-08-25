"""SqliteMemberMemoryStore end-to-end — CRUD across all three layers, and
the forget-completeness proof the team lead's mandate specifically asked
for: "a real deletion with a test that proves the data is gone from every
layer, not just hidden from the card."

Every test uses a fresh in-memory sqlite DB — no shared state between
tests (mirrors `test_confirmation_store.py`).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from team_bot.memory.models import IntentCategory, Locale, ResponseFormat, StaffRole, TargetType
from team_bot.memory.store import ForgetScope, SqliteMemberMemoryStore

_NOW = datetime(2026, 8, 25, 10, 0, 0, tzinfo=UTC)


def _store(*, max_episodic: int = 50) -> SqliteMemberMemoryStore:
    conn = sqlite3.connect(":memory:")
    return SqliteMemberMemoryStore(conn, max_episodic_per_principal=max_episodic)


def _raw_row_counts(store: SqliteMemberMemoryStore, principal_id: str) -> dict[str, int]:
    """Bypasses the store's own API entirely — a raw query against its
    connection, so this does not merely re-trust `count_rows_for_principal`
    (which is itself part of the unit under test)."""
    conn = store._conn  # noqa: SLF001 — deliberate white-box check, test-only
    counts: dict[str, int] = {}
    for table in ("member_profile", "episodic_event", "learned_pattern"):
        (n,) = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE principal_id = ?", (principal_id,)).fetchone()
        counts[table] = n
    return counts


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


def test_upsert_profile_creates_then_updates_in_place() -> None:
    store = _store()
    created = store.upsert_profile(
        principal_id="USR-102", role=StaffRole.AGENT, preferred_language=Locale.EN, now=_NOW
    )
    assert created.role == StaffRole.AGENT
    assert created.preferred_language == Locale.EN

    updated = store.upsert_profile(
        principal_id="USR-102",
        role=StaffRole.MANAGER,
        preferred_language=Locale.ID,
        response_format=ResponseFormat.DETAILED,
        now=_NOW + timedelta(days=1),
    )
    assert updated.role == StaffRole.MANAGER
    assert updated.preferred_language == Locale.ID
    assert updated.response_format == ResponseFormat.DETAILED

    # ON CONFLICT DO UPDATE, not a second row.
    (count,) = store._conn.execute(  # noqa: SLF001
        "SELECT COUNT(*) FROM member_profile WHERE principal_id = ?", ("USR-102",)
    ).fetchone()
    assert count == 1


def test_get_profile_returns_none_when_absent() -> None:
    store = _store()
    assert store.get_profile("USR-999") is None


def test_upsert_profile_rejects_malformed_working_hours() -> None:
    store = _store()
    with pytest.raises(ValueError, match="working_hours_start"):
        store.upsert_profile(
            principal_id="USR-102",
            role=StaffRole.AGENT,
            preferred_language=Locale.EN,
            working_hours_start="not-a-time",
            now=_NOW,
        )


# ---------------------------------------------------------------------------
# episodic
# ---------------------------------------------------------------------------


def test_record_episodic_event_then_lists_most_recent_first() -> None:
    store = _store()
    store.record_episodic_event(
        principal_id="USR-102",
        target_type=TargetType.CLIENT,
        target_id="CL-1042",
        intent_category=IntentCategory.LOOKUP,
        now=_NOW,
    )
    store.record_episodic_event(
        principal_id="USR-102",
        target_type=TargetType.PRACTICE,
        target_id="PR-3090",
        intent_category=IntentCategory.STATUS_CHECK,
        now=_NOW + timedelta(minutes=5),
    )

    recent = store.list_recent_episodic("USR-102", limit=5)
    assert [e.target_id for e in recent] == ["PR-3090", "CL-1042"]


def test_record_episodic_event_rejects_mismatched_target_type() -> None:
    store = _store()
    with pytest.raises(ValueError, match="target_id"):
        store.record_episodic_event(
            principal_id="USR-102",
            target_type=TargetType.CLIENT,
            target_id="PR-3090",
            intent_category=IntentCategory.LOOKUP,
            now=_NOW,
        )


def test_episodic_retention_is_bounded_to_max_per_principal() -> None:
    store = _store(max_episodic=3)
    for i in range(6):
        store.record_episodic_event(
            principal_id="USR-102",
            target_type=TargetType.CLIENT,
            target_id=f"CL-{1000 + i}",
            intent_category=IntentCategory.LOOKUP,
            now=_NOW + timedelta(minutes=i),
        )

    recent = store.list_recent_episodic("USR-102", limit=10)
    assert len(recent) == 3
    # The newest 3 survive — CL-1003, CL-1004, CL-1005 (i=3,4,5).
    assert [e.target_id for e in recent] == ["CL-1005", "CL-1004", "CL-1003"]

    (raw_count,) = store._conn.execute(  # noqa: SLF001
        "SELECT COUNT(*) FROM episodic_event WHERE principal_id = ?", ("USR-102",)
    ).fetchone()
    assert raw_count == 3


def test_episodic_retention_is_per_principal_not_global() -> None:
    store = _store(max_episodic=1)
    store.record_episodic_event(
        principal_id="USR-101",
        target_type=TargetType.CLIENT,
        target_id="CL-1001",
        intent_category=IntentCategory.LOOKUP,
        now=_NOW,
    )
    store.record_episodic_event(
        principal_id="USR-102",
        target_type=TargetType.CLIENT,
        target_id="CL-1002",
        intent_category=IntentCategory.LOOKUP,
        now=_NOW,
    )
    assert len(store.list_recent_episodic("USR-101")) == 1
    assert len(store.list_recent_episodic("USR-102")) == 1


# ---------------------------------------------------------------------------
# learned patterns
# ---------------------------------------------------------------------------


def test_record_pattern_signal_increments_observation_count_on_repeat() -> None:
    store = _store()
    first = store.record_pattern_signal(principal_id="USR-102", pattern_key="monday_digest_request", now=_NOW)
    assert first.observation_count == 1

    second = store.record_pattern_signal(
        principal_id="USR-102", pattern_key="monday_digest_request", now=_NOW + timedelta(days=7)
    )
    assert second.observation_count == 2
    assert second.first_observed_at == _NOW
    assert second.last_observed_at == _NOW + timedelta(days=7)


def test_record_pattern_signal_rejects_a_malformed_key() -> None:
    store = _store()
    with pytest.raises(ValueError, match="pattern_key"):
        store.record_pattern_signal(principal_id="USR-102", pattern_key="Not Snake Case", now=_NOW)


def test_list_patterns_filters_below_min_observations() -> None:
    store = _store()
    store.record_pattern_signal(principal_id="USR-102", pattern_key="seen_once", now=_NOW)
    store.record_pattern_signal(principal_id="USR-102", pattern_key="seen_twice", now=_NOW)
    store.record_pattern_signal(principal_id="USR-102", pattern_key="seen_twice", now=_NOW + timedelta(days=1))

    patterns = store.list_patterns("USR-102", min_observations=2)
    assert [p.pattern_key for p in patterns] == ["seen_twice"]


# ---------------------------------------------------------------------------
# forget — the completeness proof
# ---------------------------------------------------------------------------


def _seed_full_member(store: SqliteMemberMemoryStore, principal_id: str) -> None:
    store.upsert_profile(
        principal_id=principal_id, role=StaffRole.AGENT, preferred_language=Locale.EN, now=_NOW
    )
    store.record_episodic_event(
        principal_id=principal_id,
        target_type=TargetType.CLIENT,
        target_id="CL-1042",
        intent_category=IntentCategory.LOOKUP,
        now=_NOW,
    )
    store.record_episodic_event(
        principal_id=principal_id,
        target_type=TargetType.PRACTICE,
        target_id="PR-3090",
        intent_category=IntentCategory.STATUS_CHECK,
        now=_NOW,
    )
    store.record_pattern_signal(principal_id=principal_id, pattern_key="monday_digest_request", now=_NOW)


def test_forget_member_deletes_every_row_in_every_table() -> None:
    store = _store()
    _seed_full_member(store, "USR-102")

    # Pre-condition: the seed actually landed, verified two ways —
    # through the store's own get/list surface AND a raw query — so the
    # post-forget assertion below is meaningful (there was something to
    # delete, not an already-empty no-op).
    assert store.get_profile("USR-102") is not None
    assert len(store.list_recent_episodic("USR-102")) == 2
    assert len(store.list_patterns("USR-102", min_observations=1)) == 1
    pre = _raw_row_counts(store, "USR-102")
    assert pre == {"member_profile": 1, "episodic_event": 2, "learned_pattern": 1}

    result = store.forget_member(principal_id="USR-102", now=_NOW)

    assert result.scope == ForgetScope.MEMBER
    assert result.profile_rows_deleted == 1
    assert result.episodic_rows_deleted == 2
    assert result.pattern_rows_deleted == 1
    assert result.total_rows_deleted == 4

    # Gone from the store's own read surface...
    assert store.get_profile("USR-102") is None
    assert store.list_recent_episodic("USR-102") == ()
    assert store.list_patterns("USR-102", min_observations=1) == ()

    # ...AND gone from the raw tables themselves — the bar the team lead
    # set explicitly: not merely hidden from a render, actually absent.
    post = _raw_row_counts(store, "USR-102")
    assert post == {"member_profile": 0, "episodic_event": 0, "learned_pattern": 0}


def test_forget_member_never_touches_another_principal() -> None:
    store = _store()
    _seed_full_member(store, "USR-102")
    _seed_full_member(store, "USR-103")

    store.forget_member(principal_id="USR-102", now=_NOW)

    assert _raw_row_counts(store, "USR-102") == {"member_profile": 0, "episodic_event": 0, "learned_pattern": 0}
    assert _raw_row_counts(store, "USR-103") == {"member_profile": 1, "episodic_event": 2, "learned_pattern": 1}


def test_forget_member_on_an_unknown_principal_is_a_safe_no_op() -> None:
    store = _store()
    result = store.forget_member(principal_id="USR-404", now=_NOW)
    assert result.total_rows_deleted == 0


def test_forget_target_removes_only_the_matching_episodic_rows() -> None:
    store = _store()
    _seed_full_member(store, "USR-102")

    result = store.forget_target(principal_id="USR-102", target_id="CL-1042", now=_NOW)

    assert result.scope == ForgetScope.TARGET
    assert result.target_id == "CL-1042"
    assert result.episodic_rows_deleted == 1
    assert result.profile_rows_deleted == 0
    assert result.pattern_rows_deleted == 0

    remaining = store.list_recent_episodic("USR-102", limit=10)
    assert [e.target_id for e in remaining] == ["PR-3090"]

    # Profile and pattern layers are untouched by a target-scoped forget.
    assert store.get_profile("USR-102") is not None
    assert len(store.list_patterns("USR-102", min_observations=1)) == 1

    raw = _raw_row_counts(store, "USR-102")
    assert raw == {"member_profile": 1, "episodic_event": 1, "learned_pattern": 1}


def test_forget_target_on_an_untouched_target_is_a_safe_no_op() -> None:
    store = _store()
    _seed_full_member(store, "USR-102")
    result = store.forget_target(principal_id="USR-102", target_id="CL-9999", now=_NOW)
    assert result.episodic_rows_deleted == 0
    assert len(store.list_recent_episodic("USR-102", limit=10)) == 2


def test_forget_result_rejects_target_id_present_with_member_scope() -> None:
    from team_bot.memory.store import ForgetResult

    with pytest.raises(ValidationError):
        ForgetResult(
            scope=ForgetScope.MEMBER,
            principal_id="USR-102",
            target_id="CL-1042",
            profile_rows_deleted=1,
            episodic_rows_deleted=0,
            pattern_rows_deleted=0,
        )
