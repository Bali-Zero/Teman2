"""PendingAction — status/timestamp coupling, tool_name<->registry cross-check."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from team_bot.confirmation.models import PendingAction, PendingActionStatus

_NOW = datetime(2026, 8, 25, 10, 0, 0, tzinfo=UTC)
_LATER = _NOW + timedelta(minutes=5)


def _base_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "short_code": "7F3K",
        "principal_id": "USR-102",
        "tool_name": "update_practice_status",
        "encrypted_args": b"ciphertext",
        "args_sha256": "a" * 64,
        "idempotency_key": "b" * 64,
        "status": PendingActionStatus.PROPOSED,
        "leader_epoch": 0,
        "proposed_at": _NOW,
        "expires_at": _LATER,
    }
    kwargs.update(overrides)
    return kwargs


def test_proposed_row_is_valid() -> None:
    action = PendingAction(**_base_kwargs())
    assert action.status == PendingActionStatus.PROPOSED
    assert action.is_terminal is False


def test_confirmed_requires_confirmed_at() -> None:
    with pytest.raises(ValidationError):
        PendingAction(**_base_kwargs(status=PendingActionStatus.CONFIRMED))


def test_confirmed_with_confirmed_at_is_valid() -> None:
    action = PendingAction(**_base_kwargs(status=PendingActionStatus.CONFIRMED, confirmed_at=_NOW))
    assert action.confirmed_at == _NOW


def test_proposed_row_with_confirmed_at_set_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PendingAction(**_base_kwargs(confirmed_at=_NOW))


def test_executed_requires_executed_at_and_result_ref() -> None:
    with pytest.raises(ValidationError):
        PendingAction(
            **_base_kwargs(status=PendingActionStatus.EXECUTED, confirmed_at=_NOW, executed_at=_NOW)
        )  # missing execution_result_ref


def test_executed_with_all_fields_is_valid() -> None:
    action = PendingAction(
        **_base_kwargs(
            status=PendingActionStatus.EXECUTED,
            confirmed_at=_NOW,
            executed_at=_NOW,
            execution_result_ref="AUD-1",
        )
    )
    assert action.is_terminal is True


def test_cancelled_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        PendingAction(**_base_kwargs(status=PendingActionStatus.CANCELLED))


def test_cancelled_with_reason_is_valid_and_terminal() -> None:
    action = PendingAction(
        **_base_kwargs(status=PendingActionStatus.CANCELLED, cancelled_reason="user cancelled")
    )
    assert action.is_terminal is True


def test_expires_at_must_be_after_proposed_at() -> None:
    with pytest.raises(ValidationError):
        PendingAction(**_base_kwargs(expires_at=_NOW))


def test_unregistered_tool_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PendingAction(**_base_kwargs(tool_name="not_a_real_tool"))


def test_short_code_without_a_letter_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PendingAction(**_base_kwargs(short_code="1234"))


def test_short_code_with_a_letter_is_accepted() -> None:
    action = PendingAction(**_base_kwargs(short_code="7F3K"))
    assert action.short_code == "7F3K"
