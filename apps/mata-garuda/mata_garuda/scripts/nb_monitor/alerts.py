"""Alert evaluator for nb_monitor (pure logic, no I/O).

Three independent alerts per spec §6:

    1. TOP5_DROP_50PCT  — top-5 ALIVE NB drop >=50% AND >=10 absolute
    2. TIER_TRANSITION  — tier degraded vs last week, age > 14d
    3. DYING_NO_ACTION  — DYING for >=14d, skill_derivation_count==0, no traffic

Cooldowns:
    TOP5_DROP_50PCT, TIER_TRANSITION -> 24h
    DYING_NO_ACTION                  -> 7d
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from mata_garuda.scripts.nb_monitor.tier import Tier


class AlertCondition(str, Enum):
    TOP5_DROP_50PCT = "top5_drop_50pct"
    TIER_TRANSITION = "tier_transition"
    DYING_NO_ACTION = "dying_no_action"


COOLDOWNS: dict[AlertCondition, int] = {
    AlertCondition.TOP5_DROP_50PCT: 86400,
    AlertCondition.TIER_TRANSITION: 86400,
    AlertCondition.DYING_NO_ACTION: 7 * 86400,
}

TIER_RANK = {Tier.ALIVE: 2, Tier.IDLE: 1, Tier.DYING: 0}

DROP_PCT_THRESHOLD = 0.5
DROP_ABSOLUTE_FLOOR = 10
TIER_BOOTSTRAP_GUARD_DAYS = 14
DYING_STREAK_DAYS = 14


@dataclass(frozen=True)
class AlertContext:
    uuid: str
    name: str
    tier_now: Tier
    tier_lastweek: Tier | None
    read_freq_7d_now: int | None
    read_freq_7d_lastweek: int | None
    age_days: int
    skill_derivation_count: int | None
    in_top5_alive_lastweek: bool
    consecutive_dying_days: int
    rf7_30d_window_max: int


@dataclass(frozen=True)
class AlertDecision:
    condition: AlertCondition
    message: str
    payload: str  # JSON


def evaluate_alerts(ctx: AlertContext) -> list[AlertDecision]:
    out: list[AlertDecision] = []
    if _should_top5_drop(ctx):
        out.append(_top5_drop_decision(ctx))
    if _should_tier_transition(ctx):
        out.append(_tier_transition_decision(ctx))
    if _should_dying_no_action(ctx):
        out.append(_dying_no_action_decision(ctx))
    return out


def _should_top5_drop(ctx: AlertContext) -> bool:
    if ctx.tier_lastweek != Tier.ALIVE:
        return False
    if not ctx.in_top5_alive_lastweek:
        return False
    prev = ctx.read_freq_7d_lastweek or 0
    now = ctx.read_freq_7d_now or 0
    if prev <= 0:
        return False
    drop = prev - now
    if drop < DROP_ABSOLUTE_FLOOR:
        return False
    return now < (prev * DROP_PCT_THRESHOLD)


def _top5_drop_decision(ctx: AlertContext) -> AlertDecision:
    prev = ctx.read_freq_7d_lastweek or 0
    now = ctx.read_freq_7d_now or 0
    drop = prev - now
    pct = (drop / prev * 100) if prev else 0.0
    payload = json.dumps(
        {
            "uuid": ctx.uuid,
            "name": ctx.name,
            "prev": prev,
            "now": now,
            "drop": drop,
            "pct": round(pct, 1),
            "tier_lastweek": ctx.tier_lastweek.value if ctx.tier_lastweek else None,
            "tier_now": ctx.tier_now.value,
        }
    )
    msg = (
        f"NB drop alert: {ctx.name} read_freq_7d {prev} -> {now} "
        f"(-{drop} / -{round(pct, 1)}%); "
        f"tier_lastweek={ctx.tier_lastweek.value if ctx.tier_lastweek else 'NA'} "
        f"tier_now={ctx.tier_now.value}"
    )
    return AlertDecision(condition=AlertCondition.TOP5_DROP_50PCT, message=msg, payload=payload)


def _should_tier_transition(ctx: AlertContext) -> bool:
    if ctx.age_days <= TIER_BOOTSTRAP_GUARD_DAYS:
        return False
    if ctx.tier_lastweek is None:
        return False
    return TIER_RANK[ctx.tier_now] < TIER_RANK[ctx.tier_lastweek]


def _tier_transition_decision(ctx: AlertContext) -> AlertDecision:
    payload = json.dumps(
        {
            "uuid": ctx.uuid,
            "name": ctx.name,
            "tier_lastweek": ctx.tier_lastweek.value if ctx.tier_lastweek else None,
            "tier_now": ctx.tier_now.value,
            "read_freq_7d_now": ctx.read_freq_7d_now,
            "read_freq_7d_lastweek": ctx.read_freq_7d_lastweek,
        }
    )
    msg = (
        f"NB tier transition: {ctx.name} "
        f"{ctx.tier_lastweek.value if ctx.tier_lastweek else 'NA'} -> "
        f"{ctx.tier_now.value}; "
        f"read_freq_7d {ctx.read_freq_7d_lastweek} -> {ctx.read_freq_7d_now}"
    )
    return AlertDecision(condition=AlertCondition.TIER_TRANSITION, message=msg, payload=payload)


def _should_dying_no_action(ctx: AlertContext) -> bool:
    if ctx.tier_now != Tier.DYING:
        return False
    if ctx.consecutive_dying_days < DYING_STREAK_DAYS:
        return False
    if ctx.skill_derivation_count is None or ctx.skill_derivation_count != 0:
        return False
    if ctx.rf7_30d_window_max > 0:
        return False
    return True


def _dying_no_action_decision(ctx: AlertContext) -> AlertDecision:
    payload = json.dumps(
        {
            "uuid": ctx.uuid,
            "name": ctx.name,
            "consecutive_dying_days": ctx.consecutive_dying_days,
            "skill_derivation_count": ctx.skill_derivation_count,
        }
    )
    msg = (
        f"NB dying-no-action: {ctx.name} DYING for {ctx.consecutive_dying_days}d, "
        f"skill_derivation_count=0, no recent traffic. Propose APOPTOSIS (Zero approval)."
    )
    return AlertDecision(condition=AlertCondition.DYING_NO_ACTION, message=msg, payload=payload)


def can_send(uuid: str, condition: AlertCondition, last_sent: int | None, now: int) -> bool:
    if last_sent is None:
        return True
    return (now - last_sent) >= COOLDOWNS[condition]
