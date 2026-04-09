"""
Tests for Practice State Machine — validates transition enforcement.

Tests all valid transitions, invalid transitions, admin-only gates,
legacy state normalization, and edge cases.
"""

import pytest

from backend.services.crm.practice_state_machine import (
    ADMIN_ONLY_TRANSITIONS,
    ALL_STATES,
    LEGACY_STATE_MAP,
    VALID_TRANSITIONS,
    InvalidTransitionError,
    normalize_state,
    validate_transition,
)

# ─── Valid Forward Transitions ──────────────────────────────────────────────


class TestValidForwardTransitions:
    """Test all allowed forward transitions in the workflow."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            ("inquiry", "waiting_documents"),
            ("waiting_documents", "sending_invoice"),
            ("sending_invoice", "on_process"),
            ("on_process", "completed"),
        ],
    )
    def test_forward_transition(self, from_state: str, to_state: str) -> None:
        assert validate_transition(from_state, to_state) is True

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            ("waiting_documents", "inquiry"),
            ("sending_invoice", "waiting_documents"),
            ("on_process", "sending_invoice"),
        ],
    )
    def test_backward_one_step(self, from_state: str, to_state: str) -> None:
        assert validate_transition(from_state, to_state) is True


# ─── Cancelled Transitions ──────────────────────────────────────────────────


class TestCancelledTransitions:
    """Any state → cancelled is always allowed. Reopen requires admin."""

    @pytest.mark.parametrize(
        "from_state", ["inquiry", "waiting_documents", "sending_invoice", "on_process"]
    )
    def test_cancel_from_active_state(self, from_state: str) -> None:
        assert validate_transition(from_state, "cancelled") is True

    def test_cancel_completed_requires_admin(self) -> None:
        # completed → cancelled is admin-only
        assert validate_transition("completed", "cancelled", {"role": "admin"}) is True
        with pytest.raises(InvalidTransitionError, match="requires admin role"):
            validate_transition("completed", "cancelled")

    def test_reopen_cancelled_as_admin(self) -> None:
        assert validate_transition("cancelled", "inquiry", {"role": "admin"}) is True

    def test_reopen_cancelled_as_team(self) -> None:
        # cancelled -> inquiry is admin-only; team (non-admin) should be denied
        with pytest.raises(InvalidTransitionError):
            validate_transition("cancelled", "inquiry", {"role": "team"})

    def test_reopen_cancelled_without_user_raises(self) -> None:
        with pytest.raises(InvalidTransitionError, match="requires admin role"):
            validate_transition("cancelled", "inquiry")

    def test_reopen_cancelled_as_client_raises(self) -> None:
        # Error message is "Admin-only transition: ..." for non-admin users
        with pytest.raises(InvalidTransitionError, match="Admin-only transition|requires admin role"):
            validate_transition("cancelled", "inquiry", {"role": "client"})


# ─── Invalid Transitions ────────────────────────────────────────────────────


class TestInvalidTransitions:
    """Test that invalid transitions are rejected."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            ("inquiry", "on_process"),  # Skip 2 steps
            ("inquiry", "completed"),  # Skip 3 steps
            ("inquiry", "sending_invoice"),  # Skip 1 step
            ("waiting_documents", "on_process"),  # Skip 1 step
            ("waiting_documents", "completed"),  # Skip 2 steps
            ("sending_invoice", "completed"),  # Skip 1 step
            ("completed", "inquiry"),  # Can't reopen completed
            ("completed", "on_process"),  # Can't go back from completed
        ],
    )
    def test_invalid_skip_transition(self, from_state: str, to_state: str) -> None:
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_state, to_state)


# ─── Same State (No-op) ────────────────────────────────────────────────────


class TestSameStateNoop:
    """Same state transitions should always pass (no-op)."""

    @pytest.mark.parametrize("state", list(ALL_STATES))
    def test_same_state_is_noop(self, state: str) -> None:
        assert validate_transition(state, state) is True


# ─── Unknown States ─────────────────────────────────────────────────────────


class TestUnknownStates:
    """Unknown states should raise errors."""

    def test_unknown_from_state(self) -> None:
        with pytest.raises(InvalidTransitionError, match="unknown current state"):
            validate_transition("nonexistent", "inquiry")

    def test_unknown_to_state(self) -> None:
        with pytest.raises(InvalidTransitionError, match="unknown target state"):
            validate_transition("inquiry", "nonexistent")


# ─── Legacy State Normalization ─────────────────────────────────────────────


class TestLegacyNormalization:
    """Legacy states should map to their canonical equivalents."""

    @pytest.mark.parametrize(
        "legacy,canonical",
        [
            ("quotation_sent", "sending_invoice"),
            ("payment_pending", "sending_invoice"),
            ("waiting_payment", "sending_invoice"),
            ("in_progress", "on_process"),
            ("submitted_to_gov", "on_process"),
            ("approved", "on_process"),
        ],
    )
    def test_legacy_mapping(self, legacy: str, canonical: str) -> None:
        assert normalize_state(legacy) == canonical

    def test_canonical_state_unchanged(self) -> None:
        for state in ALL_STATES:
            assert normalize_state(state) == state


# ─── Structural Integrity ───────────────────────────────────────────────────


class TestStructuralIntegrity:
    """Verify state machine data structures are consistent."""

    def test_all_states_have_transitions(self) -> None:
        for state in ALL_STATES:
            assert state in VALID_TRANSITIONS, f"Missing transitions for {state}"

    def test_transition_targets_are_valid_states(self) -> None:
        for from_state, to_states in VALID_TRANSITIONS.items():
            for to_state in to_states:
                assert to_state in ALL_STATES, f"Invalid target {to_state} from {from_state}"

    def test_admin_transitions_are_valid(self) -> None:
        for from_state, to_state in ADMIN_ONLY_TRANSITIONS:
            assert from_state in ALL_STATES
            assert to_state in VALID_TRANSITIONS.get(from_state, set())

    def test_legacy_targets_are_valid(self) -> None:
        for target in LEGACY_STATE_MAP.values():
            assert target in ALL_STATES, f"Legacy target {target} not in ALL_STATES"

    def test_exactly_six_states(self) -> None:
        assert len(ALL_STATES) == 6  # 5 workflow + cancelled
