"""Tests for flags.py — the dark-flag helpers, including the multistep-read
budget added for directive #1 §2. The single hard requirement across all
of these: with the dark flag OFF (the default), behavior must be BYTE-
IDENTICAL to a world where the multi-step relaxation never existed —
exactly one read step, regardless of any other env var's value.
"""

from __future__ import annotations

import pytest

from team_bot.flags import (
    ABSOLUTE_MAX_READ_STEPS_ENV_CEILING,
    DEFAULT_MAX_READ_STEPS,
    SINGLE_STEP,
    is_team_bot_enabled,
    is_team_bot_multistep_reads_enabled,
    max_read_steps,
)
from team_bot.loop import ABSOLUTE_MAX_READ_STEPS


def test_ceilings_do_not_drift_apart() -> None:
    """flags.py's operator-facing clamp and turn_plan.py's structural
    Field ceiling are maintained in two different modules for two
    different reasons (see flags.py's docstring) and must never silently
    diverge."""
    assert ABSOLUTE_MAX_READ_STEPS_ENV_CEILING == ABSOLUTE_MAX_READ_STEPS


# ---------------------------------------------------------------------------
# is_team_bot_enabled — pre-existing behavior, now covered by a real test.
# ---------------------------------------------------------------------------


def test_team_bot_enabled_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEAM_BOT_ENABLED", raising=False)
    assert is_team_bot_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on"])
def test_team_bot_enabled_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("TEAM_BOT_ENABLED", value)
    assert is_team_bot_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "garbage"])
def test_team_bot_enabled_falsy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("TEAM_BOT_ENABLED", value)
    assert is_team_bot_enabled() is False


# ---------------------------------------------------------------------------
# is_team_bot_multistep_reads_enabled
# ---------------------------------------------------------------------------


def test_multistep_reads_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEAM_BOT_MULTISTEP_READS_ENABLED", raising=False)
    assert is_team_bot_multistep_reads_enabled() is False


def test_multistep_reads_can_be_flipped_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "true")
    assert is_team_bot_multistep_reads_enabled() is True


# ---------------------------------------------------------------------------
# max_read_steps — the load-bearing "everything born OFF" guarantee.
# ---------------------------------------------------------------------------


def test_max_read_steps_is_single_step_when_flag_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEAM_BOT_MULTISTEP_READS_ENABLED", raising=False)
    monkeypatch.delenv("TEAM_BOT_MAX_READ_STEPS", raising=False)
    assert max_read_steps() == SINGLE_STEP == 1


def test_max_read_steps_ignores_the_numeric_var_while_the_flag_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """The load-bearing guarantee: setting ONLY TEAM_BOT_MAX_READ_STEPS
    (leaving the dark flag unset/false) must NOT widen the chain — a
    stray or leftover config value can never silently reach a live
    effect on its own."""
    monkeypatch.delenv("TEAM_BOT_MULTISTEP_READS_ENABLED", raising=False)
    monkeypatch.setenv("TEAM_BOT_MAX_READ_STEPS", "8")
    assert max_read_steps() == SINGLE_STEP == 1


def test_max_read_steps_explicit_false_also_ignores_numeric_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "false")
    monkeypatch.setenv("TEAM_BOT_MAX_READ_STEPS", "8")
    assert max_read_steps() == SINGLE_STEP == 1


def test_max_read_steps_default_when_flag_on_and_var_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "true")
    monkeypatch.delenv("TEAM_BOT_MAX_READ_STEPS", raising=False)
    assert max_read_steps() == DEFAULT_MAX_READ_STEPS == 8


def test_max_read_steps_honors_configured_value_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "true")
    monkeypatch.setenv("TEAM_BOT_MAX_READ_STEPS", "5")
    assert max_read_steps() == 5


def test_max_read_steps_clamps_above_the_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "true")
    monkeypatch.setenv("TEAM_BOT_MAX_READ_STEPS", "999")
    assert max_read_steps() == ABSOLUTE_MAX_READ_STEPS_ENV_CEILING


def test_max_read_steps_clamps_zero_or_negative_up_to_single_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "true")
    monkeypatch.setenv("TEAM_BOT_MAX_READ_STEPS", "-3")
    assert max_read_steps() == SINGLE_STEP


def test_max_read_steps_falls_back_to_default_on_garbage_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "true")
    monkeypatch.setenv("TEAM_BOT_MAX_READ_STEPS", "not-a-number")
    assert max_read_steps() == DEFAULT_MAX_READ_STEPS
