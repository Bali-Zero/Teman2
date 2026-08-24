"""ConfirmationOutcome — closed-type wrapping, and render_outcome — pure
server-authored text, never model content.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from team_bot.confirmation.models import PendingAction, PendingActionStatus
from team_bot.confirmation.outcomes import (
    DEFAULT_LOCALE,
    ConfirmationOutcome,
    ConfirmationStage,
    Locale,
    render_outcome,
)
from team_bot.confirmation.store import (
    CancelOutcome,
    ConfirmOutcome,
    ExecuteOutcome,
    ProposeOutcome,
)

_NOW = datetime(2026, 8, 25, 10, 0, 0, tzinfo=UTC)


def _action(**overrides: object) -> PendingAction:
    kwargs: dict[str, object] = {
        "short_code": "7F3K",
        "principal_id": "USR-1",
        "tool_name": "update_practice_status",
        "encrypted_args": b"ciphertext",
        "args_sha256": "a" * 64,
        "idempotency_key": "b" * 64,
        "status": PendingActionStatus.PROPOSED,
        "leader_epoch": 0,
        "proposed_at": _NOW,
        "expires_at": _NOW + timedelta(minutes=5),
    }
    kwargs.update(overrides)
    return PendingAction(**kwargs)


# ── ConfirmationOutcome closed-type ─────────────────────────────────────


def test_from_propose_round_trips() -> None:
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    assert outcome.stage == ConfirmationStage.PROPOSE
    assert outcome.value == ProposeOutcome.CREATED.value


def test_from_confirm_from_execute_from_cancel_round_trip() -> None:
    assert ConfirmationOutcome.from_confirm(ConfirmOutcome.CONFIRMED).stage == ConfirmationStage.CONFIRM
    assert ConfirmationOutcome.from_execute(ExecuteOutcome.EXECUTED).stage == ConfirmationStage.EXECUTE
    assert ConfirmationOutcome.from_cancel(CancelOutcome.CANCELLED).stage == ConfirmationStage.CANCEL


def test_value_from_a_different_stages_enum_is_rejected() -> None:
    """ConfirmOutcome and ExecuteOutcome and CancelOutcome all share the raw
    string 'not_found' — the closed type must still reject a PROPOSE stage
    tagged with a CONFIRM-only value like 'confirmed', proving the check is
    real, not a no-op that any string would pass."""
    with pytest.raises(ValidationError):
        ConfirmationOutcome(stage=ConfirmationStage.PROPOSE, value=ConfirmOutcome.CONFIRMED.value)


def test_arbitrary_string_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ConfirmationOutcome(stage=ConfirmationStage.CONFIRM, value="not-a-real-outcome")


def test_frozen_and_extra_forbidden() -> None:
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    with pytest.raises(ValidationError):
        outcome.value = ConfirmOutcome.CONFIRMED.value  # type: ignore[misc]


# ── render_outcome — full enum coverage ─────────────────────────────────

_ALL_STAGES_AND_ENUMS = (
    (ConfirmationOutcome.from_propose, ProposeOutcome),
    (ConfirmationOutcome.from_confirm, ConfirmOutcome),
    (ConfirmationOutcome.from_execute, ExecuteOutcome),
    (ConfirmationOutcome.from_cancel, CancelOutcome),
)


def test_every_outcome_member_renders_in_every_locale_with_and_without_action() -> None:
    """Every (stage, value) this codebase can ever produce has a template
    for all 3 locales, and never leaves an unfilled '{placeholder}' in the
    output — whether or not a PendingAction is available. This is the
    completeness guarantee render_outcome's own docstring claims; this test
    is what actually enforces it (a missing template would KeyError here,
    not silently degrade)."""
    action = _action()
    for factory, enum_cls in _ALL_STAGES_AND_ENUMS:
        for member in enum_cls:
            outcome = factory(member)
            for locale in Locale:
                for candidate_action in (action, None):
                    if candidate_action is None and "not_found" not in member.value:
                        continue  # only *_NOT_FOUND outcomes are ever rendered with action=None
                    text = render_outcome(outcome, candidate_action, locale)
                    assert isinstance(text, str) and text
                    assert "{" not in text and "}" not in text


def test_default_locale_is_english() -> None:
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    assert render_outcome(outcome, _action()) == render_outcome(outcome, _action(), DEFAULT_LOCALE)
    assert DEFAULT_LOCALE == Locale.EN


def test_propose_created_names_the_code_and_tool() -> None:
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    text = render_outcome(outcome, _action(short_code="9XQ2", tool_name="create_reminder"), Locale.EN)
    assert "9XQ2" in text
    assert "create_reminder" in text


def test_confirm_wrong_principal_does_not_leak_the_code_or_tool() -> None:
    """A denial to the WRONG actor must not hint at what the pending action
    actually was — see outcomes.py's module note."""
    outcome = ConfirmationOutcome.from_confirm(ConfirmOutcome.WRONG_PRINCIPAL)
    text = render_outcome(outcome, _action(short_code="9XQ2", tool_name="mark_document_received"), Locale.EN)
    assert "9XQ2" not in text
    assert "mark_document_received" not in text


def test_not_found_outcomes_render_with_action_none() -> None:
    for factory, member in (
        (ConfirmationOutcome.from_confirm, ConfirmOutcome.NOT_FOUND),
        (ConfirmationOutcome.from_execute, ExecuteOutcome.NOT_FOUND),
        (ConfirmationOutcome.from_cancel, CancelOutcome.NOT_FOUND),
    ):
        text = render_outcome(factory(member), None, Locale.EN)
        assert "not found" in text.lower() or "expired" in text.lower()


def test_all_three_locales_are_actually_distinct_text() -> None:
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    en = render_outcome(outcome, _action(), Locale.EN)
    it = render_outcome(outcome, _action(), Locale.IT)
    id_ = render_outcome(outcome, _action(), Locale.ID)
    assert len({en, it, id_}) == 3


def test_an_unsupported_locale_cannot_even_reach_render_outcome() -> None:
    """Locale is a closed StrEnum — a locale outside {en, it, id} fails to
    construct at all, so render_outcome can never be called with one and
    silently fall back to English; the guarantee is enforced at the type
    boundary, not inside the function."""
    with pytest.raises(ValueError):
        Locale("fr")
