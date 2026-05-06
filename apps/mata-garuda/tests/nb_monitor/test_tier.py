"""Tests for nb_monitor.tier."""
from __future__ import annotations

import pytest

from mata_garuda.scripts.nb_monitor.tier import (
    Tier,
    TierInputs,
    classify,
)


def _inputs(**overrides) -> TierInputs:
    base = dict(read_freq_7d=20, push_success_rate=0.99, age_days=30)
    base.update(overrides)
    return TierInputs(**base)


def test_alive_when_engaged_and_matured():
    assert classify(_inputs(read_freq_7d=10)) == Tier.ALIVE


def test_alive_when_psr_is_none():
    """psr=None must not downgrade — neutral default."""
    assert classify(_inputs(push_success_rate=None)) == Tier.ALIVE


def test_idle_when_age_is_below_bootstrap_window():
    assert classify(_inputs(age_days=3, read_freq_7d=100)) == Tier.IDLE


def test_idle_when_freq_below_alive_threshold():
    assert classify(_inputs(read_freq_7d=4)) == Tier.IDLE


def test_idle_when_push_success_below_alive_threshold():
    assert classify(_inputs(push_success_rate=0.85)) == Tier.IDLE


def test_dying_when_idle_long_and_psr_low():
    assert (
        classify(_inputs(read_freq_7d=0, age_days=30, push_success_rate=0.5))
        == Tier.DYING
    )


def test_dying_when_idle_long_and_psr_none():
    """psr=None should still be eligible for DYING (Round 2 decision)."""
    assert (
        classify(_inputs(read_freq_7d=0, age_days=30, push_success_rate=None))
        == Tier.DYING
    )


def test_idle_takes_precedence_over_dying_for_young_nb():
    assert (
        classify(_inputs(read_freq_7d=0, age_days=10, push_success_rate=0.5))
        == Tier.IDLE
    )


def test_read_freq_zero_when_none_treated_as_zero_for_classification():
    assert (
        classify(_inputs(read_freq_7d=None, age_days=20, push_success_rate=None))
        == Tier.IDLE
    )
