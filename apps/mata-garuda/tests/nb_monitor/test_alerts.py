"""Tests for nb_monitor.alerts (pure logic, no I/O)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from mata_garuda.scripts.nb_monitor.alerts import (
    AlertCondition,
    AlertContext,
    AlertDecision,
    evaluate_alerts,
    can_send,
    COOLDOWNS,
)
from mata_garuda.scripts.nb_monitor.tier import Tier


def _ctx(**over) -> AlertContext:
    base = dict(
        uuid="u1",
        name="NB-X",
        tier_now=Tier.ALIVE,
        tier_lastweek=Tier.ALIVE,
        read_freq_7d_now=20,
        read_freq_7d_lastweek=50,
        age_days=30,
        skill_derivation_count=None,
        in_top5_alive_lastweek=True,
        consecutive_dying_days=0,
        rf7_30d_window_max=15,
    )
    base.update(over)
    return AlertContext(**base)


def test_top5_drop_alert_fires_when_drop_meets_pct_and_floor():
    decisions = evaluate_alerts(_ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT in conds


def test_top5_drop_alert_blocked_by_floor():
    """5→2 is 60% drop but absolute drop is 3 < floor 10 → no alert."""
    decisions = evaluate_alerts(_ctx(read_freq_7d_now=2, read_freq_7d_lastweek=5))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT not in conds


def test_top5_drop_alert_requires_top5_membership():
    decisions = evaluate_alerts(
        _ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50, in_top5_alive_lastweek=False)
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT not in conds


def test_top5_drop_alert_requires_alive_lastweek():
    decisions = evaluate_alerts(
        _ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50, tier_lastweek=Tier.IDLE)
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT not in conds


def test_lifecycle_drop_alert_fires_on_alive_to_idle():
    decisions = evaluate_alerts(_ctx(tier_now=Tier.IDLE, tier_lastweek=Tier.ALIVE))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TIER_TRANSITION in conds


def test_lifecycle_drop_alert_skipped_in_bootstrap_window():
    decisions = evaluate_alerts(
        _ctx(tier_now=Tier.IDLE, tier_lastweek=Tier.ALIVE, age_days=10)
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.TIER_TRANSITION not in conds


def test_lifecycle_drop_alert_skipped_for_promotion():
    """IDLE→ALIVE is good news, not an alert."""
    decisions = evaluate_alerts(_ctx(tier_now=Tier.ALIVE, tier_lastweek=Tier.IDLE))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TIER_TRANSITION not in conds


def test_dying_no_action_alert_requires_skill_derivation_zero():
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=14,
            skill_derivation_count=0,
            rf7_30d_window_max=0,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION in conds


def test_dying_no_action_alert_self_suppresses_when_skill_count_is_none():
    """Pre-FASE-1 default: skill_derivation_count is None → alert MUST NOT fire."""
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=14,
            skill_derivation_count=None,
            rf7_30d_window_max=0,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION not in conds


def test_dying_no_action_requires_consecutive_streak():
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=5,
            skill_derivation_count=0,
            rf7_30d_window_max=0,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION not in conds


def test_dying_no_action_blocked_when_recent_traffic():
    """If rf7 was non-zero anywhere in the 30d window, no alert."""
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=14,
            skill_derivation_count=0,
            rf7_30d_window_max=3,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION not in conds


def test_can_send_returns_true_when_no_prior_send():
    assert (
        can_send(uuid="u1", condition=AlertCondition.TOP5_DROP_50PCT, last_sent=None, now=10**9)
        is True
    )


def test_can_send_returns_false_within_cooldown():
    last = 10**9
    now = last + 100
    assert (
        can_send(uuid="u1", condition=AlertCondition.TOP5_DROP_50PCT, last_sent=last, now=now)
        is False
    )


def test_can_send_returns_true_after_cooldown():
    last = 10**9
    now = last + COOLDOWNS[AlertCondition.TOP5_DROP_50PCT] + 1
    assert (
        can_send(uuid="u1", condition=AlertCondition.TOP5_DROP_50PCT, last_sent=last, now=now)
        is True
    )


def test_dying_cooldown_is_seven_days():
    assert COOLDOWNS[AlertCondition.DYING_NO_ACTION] == 7 * 86400


def test_alert_decision_includes_payload_with_facts():
    decisions = evaluate_alerts(_ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50))
    top5 = next(d for d in decisions if d.condition == AlertCondition.TOP5_DROP_50PCT)
    assert "u1" in top5.payload
    assert "50" in top5.payload
    assert "10" in top5.payload
