"""Tests for the F11/B7 tripwire registry (`services/client_bot/tripwires.py`).

Guards the specific claim the team lead's mandate asked this lane to make
checkable: tripwires are tagged `business` vs `technical`, and at least
one business-invariant tripwire exists per bot. Also binds every `wired`
tripwire to a real collector in `observability.py` so a metric rename
there cannot silently orphan a tripwire that still claims to read it —
and binds every non-`None` `plane` to a kill switch that actually exists
for that plane (a tripwire naming a switch that isn't registered would be
exactly the "esiste != armato" failure this control tower exists to
prevent, applied one level up from the switches themselves).
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.services import client_bot
from backend.services.client_bot import observability as obs
from backend.services.client_bot.kill_switches import KILL_SWITCHES, TripwirePlane
from backend.services.client_bot.tripwires import (
    TRIPWIRES,
    MetricStatus,
    TripwireKind,
    business_invariants,
    by_plane,
)

_METRIC_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _referenced_metric_names(metric_expr: str) -> list[str]:
    """A `.metric` value is either a bare name or a `a / b` ratio expression
    (and one row carries a `{label=value}` suffix) — pull out every plain
    identifier token so a ratio's numerator AND denominator are both
    checked against observability.py.
    """
    # Strip a trailing `{...}` label-filter suffix before tokenizing.
    metric_expr = re.sub(r"\{.*\}$", "", metric_expr)
    return _METRIC_TOKEN_RE.findall(metric_expr)


def test_registry_is_non_empty() -> None:
    assert len(TRIPWIRES) >= 15


def test_no_duplicate_ids() -> None:
    ids = [t.id for t in TRIPWIRES]
    assert len(ids) == len(set(ids)), "duplicate tripwire id"


def test_wired_tripwires_reference_real_metrics() -> None:
    for t in TRIPWIRES:
        if t.metric_status != MetricStatus.WIRED:
            continue
        for name in _referenced_metric_names(t.metric):
            assert hasattr(obs, name), (
                f"tripwire {t.id!r} claims metric_status=WIRED but "
                f"{name!r} is not exported from observability.py"
            )


def test_planned_tripwires_are_all_team_bot_naming_contracts() -> None:
    # Every PLANNED row today is a team-bot metric (apps/team-bot/ does not
    # exist yet). If a client-bot/codex metric is ever added as PLANNED,
    # that is a real gap, not a naming contract — this test forces a
    # conscious choice rather than a silent default.
    for t in TRIPWIRES:
        if t.metric_status == MetricStatus.PLANNED:
            assert t.id.startswith("team."), (
                f"{t.id!r} is PLANNED but is not a team.* row — either wire "
                "it in observability.py or explain why it stays planned"
            )


def test_every_plane_referenced_has_a_registered_kill_switch() -> None:
    registered_planes = {k.plane for k in KILL_SWITCHES}
    for t in TRIPWIRES:
        if t.plane is None:
            continue
        assert t.plane in registered_planes, (
            f"tripwire {t.id!r} names plane {t.plane!r}, which has no "
            "registered KillSwitch"
        )


def test_page_only_tripwires_do_not_claim_a_flip() -> None:
    # plane=None is legitimate for a packet-producing or pure-page action
    # (no registered switch to name). Its prose must not then turn around
    # and claim to flip one anyway — that would be a real plane hiding
    # behind an unset field.
    for t in TRIPWIRES:
        if t.plane is None:
            assert "flip" not in t.automatic_action.lower(), (
                f"tripwire {t.id!r} has plane=None but its automatic_action "
                "claims to flip a switch"
            )


def test_at_least_one_business_invariant_per_bot() -> None:
    business = business_invariants()
    assert any(t.id.startswith("client.") or t.id.startswith("codex.") for t in business)
    assert any(t.id.startswith("team.") for t in business)


def test_kind_is_a_closed_vocabulary() -> None:
    for t in TRIPWIRES:
        assert t.kind in (TripwireKind.BUSINESS, TripwireKind.TECHNICAL)


def test_packet_producing_tripwires_point_at_an_existing_template() -> None:
    repo_root = Path(client_bot.__file__).resolve().parents[5]
    for t in TRIPWIRES:
        if t.packet_template is None:
            continue
        template_path = repo_root / t.packet_template
        assert template_path.exists(), (
            f"tripwire {t.id!r} points at packet_template "
            f"{t.packet_template!r} which does not exist on disk"
        )


def test_by_plane_matches_linear_scan() -> None:
    for plane in (*TripwirePlane, None):
        expected = tuple(t for t in TRIPWIRES if t.plane == plane)
        assert by_plane(plane) == expected
