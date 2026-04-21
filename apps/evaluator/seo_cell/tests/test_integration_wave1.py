"""SEO Cell — Wave 1 integration tests.

Scope (per session brief 2026-04-22):
    1. Sensor schema compat — every sensor returns a SensorReading with
       the uniform envelope (sensor_name, status, value, timestamp,
       metadata) regardless of whether its backing service is up.
    2. Tier gating sanity — each tier routes to the expected target in
       a live phase, and pre_natal refuses everything.
    3. Cross-sensor graceful — a single sensor failure does not crash
       the pulse loop; the thinker still sees a valid list.

Not in scope for Wave 1: Bayesian sensitivity analysis, actor execution
beyond refusal, PulseLoop end-to-end (see NOTES.md §Wave 2).

All external I/O is mocked (GSC, GA4, Postgres, SERP cache). No network.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from cell_core.types import (
    HomeostaticState,
    Phase,
    Proposal,
    SensorReading,
)

from apps.evaluator.seo_cell.phase import SEOPhase
from apps.evaluator.seo_cell.sensors import (
    CannibalizationSensor,
    CompetitorSERPSensor,
    GA4Sensor,
    GSCSensor,
    KGSensor,
    WarRoomEventSensor,
)
from apps.evaluator.seo_cell.thinker import SEOThinker
from apps.evaluator.seo_cell.tier_gating_policy import (
    RoutingTarget,
    TierGatingPolicy,
)


# ── helpers ────────────────────────────────────────────────────────────

EXPECTED_SENSOR_NAMES: frozenset[str] = frozenset({
    "gsc",
    "ga4",
    "competitor_serp",
    "kg",
    "war_room_event",
    "cannibalization",
})


def _prop(action: str, tier_used: int = 1) -> Proposal:
    return Proposal(
        action=action,
        reason="integration-wave1",
        confidence=0.8,
        tier_used=tier_used,
    )


def _all_sensors_no_backing_infra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list:
    """Build all 6 sensors pointed at *absent* backing infra.

    This is the real-world Sprint 1 / fresh-clone configuration: the
    cell is supposed to come up clean and return yellow readings rather
    than crash. Used by schema and cross-sensor tests.
    """
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        missing,
    )
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        missing,
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    return [
        GSCSensor(),
        GA4Sensor(),
        CompetitorSERPSensor(cache_db=tmp_path / "absent.db"),
        KGSensor(),
        WarRoomEventSensor(),
        CannibalizationSensor(),
    ]


# ── 1. Sensor schema compat (7 tests) ──────────────────────────────────

@pytest.mark.asyncio
async def test_every_sensor_returns_sensor_reading(tmp_path, monkeypatch):
    """Envelope contract: all 6 sensors return a SensorReading instance."""
    sensors = _all_sensors_no_backing_infra(tmp_path, monkeypatch)
    readings = await asyncio.gather(*[s.read() for s in sensors])
    assert len(readings) == 6
    for r in readings:
        assert isinstance(r, SensorReading), (
            f"sensor produced {type(r).__name__}, expected SensorReading"
        )


@pytest.mark.asyncio
async def test_every_reading_has_required_fields(tmp_path, monkeypatch):
    """Every reading carries sensor_name, status, value, timestamp, metadata."""
    sensors = _all_sensors_no_backing_infra(tmp_path, monkeypatch)
    readings = await asyncio.gather(*[s.read() for s in sensors])
    for r in readings:
        # Hard fields — dataclass guarantees presence, but we pin types
        assert isinstance(r.sensor_name, str) and r.sensor_name
        assert r.status in ("green", "yellow", "red"), r.status
        assert r.value is not None, f"{r.sensor_name} has null value"
        assert isinstance(r.metadata, dict), r.sensor_name


@pytest.mark.asyncio
async def test_sensor_names_match_expected_set(tmp_path, monkeypatch):
    """6 sensors → 6 distinct names, matching EXPECTED_SENSOR_NAMES."""
    sensors = _all_sensors_no_backing_infra(tmp_path, monkeypatch)
    readings = await asyncio.gather(*[s.read() for s in sensors])
    got = {r.sensor_name for r in readings}
    assert got == EXPECTED_SENSOR_NAMES, f"drift: {got ^ EXPECTED_SENSOR_NAMES}"


@pytest.mark.asyncio
async def test_every_reading_timestamp_is_utc_aware(tmp_path, monkeypatch):
    """Timestamps must be tz-aware UTC — otherwise cross-sensor time
    arithmetic in the thinker silently yields naive/aware mixing
    errors on downstream aggregation."""
    sensors = _all_sensors_no_backing_infra(tmp_path, monkeypatch)
    readings = await asyncio.gather(*[s.read() for s in sensors])
    now = datetime.now(timezone.utc)
    for r in readings:
        assert isinstance(r.timestamp, datetime), r.sensor_name
        assert r.timestamp.tzinfo is not None, (
            f"{r.sensor_name} produced naive timestamp"
        )
        # Reading should be dated "now" within a generous fudge window
        assert abs((now - r.timestamp).total_seconds()) < 60


@pytest.mark.asyncio
async def test_yellow_readings_carry_error_code_when_infra_absent(
    tmp_path, monkeypatch
):
    """When backing infra is missing, sensors degrade to yellow *with*
    an error_code — never silent green. The thinker reads error_code to
    decide "signal missing vs real null"."""
    # gsc/ga4 depend on creds file, competitor on cache db, kg + war_room
    # on DATABASE_URL. Cannibalization is a stub (no infra) and is
    # excluded from this contract.
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        missing,
    )
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        missing,
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    infra_sensors = [
        GSCSensor(),
        GA4Sensor(),
        CompetitorSERPSensor(cache_db=tmp_path / "absent.db"),
        KGSensor(),
        WarRoomEventSensor(),
    ]
    readings = await asyncio.gather(*[s.read() for s in infra_sensors])
    for r in readings:
        assert r.status == "yellow", (
            f"{r.sensor_name} returned {r.status} — expected yellow on missing infra"
        )
        assert "error_code" in r.metadata, (
            f"{r.sensor_name} yellow reading has no error_code"
        )
        assert r.metadata["error_code"], f"{r.sensor_name} empty error_code"


@pytest.mark.asyncio
async def test_value_dict_shape_is_stable_on_yellow(tmp_path, monkeypatch):
    """Downstream (thinker, tests) destructures value.* on every path.
    A yellow reading must keep the same top-level dict keys as a green
    one so `.get("query_count", 0)` style code works without
    branch-on-status gymnastics."""
    sensors = _all_sensors_no_backing_infra(tmp_path, monkeypatch)
    readings = await asyncio.gather(*[s.read() for s in sensors])
    # Known keys per sensor (the public schema each one exposes).
    expected_keys = {
        "gsc": {"query_count", "clicks_total", "impressions_total", "top_queries"},
        "ga4": {
            "page_count",
            "sessions_total",
            "conversions_total",
            "sessions_by_page",
            "conversions_by_page",
        },
        "competitor_serp": {"ranks", "vendors", "query_count", "fresh_rows"},
        "kg": {
            "node_count",
            "edge_count",
            "nodes_by_type",
            "edges_by_type",
            "last_updated_at",
        },
        "war_room_event": {"event_count", "by_platform", "recent_posts"},
        "cannibalization": {"clusters"},
    }
    for r in readings:
        assert isinstance(r.value, dict), r.sensor_name
        assert set(r.value.keys()) >= expected_keys[r.sensor_name], (
            f"{r.sensor_name}: expected at least {expected_keys[r.sensor_name]}, "
            f"got {set(r.value.keys())}"
        )


@pytest.mark.asyncio
async def test_cannibalization_stub_flagged_in_metadata():
    """The last stub sensor declares itself as such so the thinker /
    operators can tell "no signal because sprint phase" apart from "no
    signal because infra down"."""
    r = await CannibalizationSensor().read()
    assert r.metadata.get("stub") is True
    assert r.status in ("yellow", "green", "red")
    # stubs must still speak the full schema so aggregation does not
    # special-case them
    assert isinstance(r.value, dict)


# ── 2. Tier gating sanity (6 tests) ────────────────────────────────────

_LIVE_PHASE = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
_PRE_NATAL = SEOPhase(native=Phase.EMBRIONE, pre_natal=True)


def test_gating_low_tier_action_routes_to_direct_apply_in_live():
    """Happy path: LOW → DIRECT_APPLY, no human approval."""
    decision = TierGatingPolicy().decide(
        _prop("publish_schema"), phase=_LIVE_PHASE
    )
    assert decision.tier == "LOW"
    assert decision.target == RoutingTarget.DIRECT_APPLY
    assert decision.requires_human_approval is False
    assert decision.requires_zero_approval is False


def test_gating_med_tier_action_routes_to_newsroom_queue_in_live():
    """Happy path: MED → NEWSROOM_QUEUE, no human approval."""
    decision = TierGatingPolicy().decide(
        _prop("queue_article_draft"), phase=_LIVE_PHASE
    )
    assert decision.tier == "MED"
    assert decision.target == RoutingTarget.NEWSROOM_QUEUE
    assert decision.requires_human_approval is False


def test_gating_high_tier_action_requires_human_approval_in_live():
    """Happy path: HIGH → REVIEW_HANDLER + human approval required."""
    decision = TierGatingPolicy().decide(
        _prop("publish_article"), phase=_LIVE_PHASE
    )
    assert decision.tier == "HIGH"
    assert decision.target == RoutingTarget.REVIEW_HANDLER
    assert decision.requires_human_approval is True
    assert decision.requires_zero_approval is False


def test_gating_critical_tier_action_requires_zero_approval_in_live():
    """Happy path: CRITICAL → REVIEW_HANDLER + Zero approval required.

    This is the apex policy — no autonomous execution of sitewide
    changes, and escalation must *always* reach Zero, not just a
    generic human reviewer."""
    decision = TierGatingPolicy().decide(
        _prop("remove_page"), phase=_LIVE_PHASE
    )
    assert decision.tier == "CRITICAL"
    assert decision.target == RoutingTarget.REVIEW_HANDLER
    assert decision.requires_human_approval is True
    assert decision.requires_zero_approval is True


@pytest.mark.parametrize(
    "action,inferred_tier",
    [
        ("publish_schema", "LOW"),
        ("queue_article_draft", "MED"),
        ("publish_article", "HIGH"),
        ("remove_page", "CRITICAL"),
    ],
)
def test_gating_pre_natal_refuses_every_tier(action, inferred_tier):
    """Edge case for every tier: pre_natal phase refuses routing
    regardless of inferred tier, while still reporting the would-be
    tier so the operator sees what *would* have fired."""
    decision = TierGatingPolicy().decide(
        _prop(action), phase=_PRE_NATAL
    )
    assert decision.target == RoutingTarget.REFUSED_PRE_NATAL
    assert decision.tier == inferred_tier
    assert decision.requires_human_approval is False
    assert decision.requires_zero_approval is False
    assert decision.handler_module == ""


def test_gating_none_action_is_noop_even_in_pre_natal():
    """`action='none'` must short-circuit *before* the pre_natal check
    — otherwise the thinker's default no-op in pre_natal would be
    reported as REFUSED_PRE_NATAL and clog metrics."""
    decision = TierGatingPolicy().decide(_prop("none"), phase=_PRE_NATAL)
    assert decision.target == RoutingTarget.NO_OP
    assert decision.tier == "LOW"


# ── 3. Cross-sensor graceful degradation (5 tests) ─────────────────────

@pytest.mark.asyncio
async def test_one_sensor_raising_does_not_break_gather(tmp_path, monkeypatch):
    """Even if a sensor's `.read()` itself raises (bug, not the handled
    _Error path), `asyncio.gather` with return_exceptions=True keeps the
    rest alive. This matches PulseLoop's behavior — sensors are
    independent and a cell must keep sensing on partial failure."""
    sensors = _all_sensors_no_backing_infra(tmp_path, monkeypatch)

    class ExplodingSensor:
        name = "exploder"

        async def read(self, **context):
            raise RuntimeError("boom")

    sensors.append(ExplodingSensor())
    results = await asyncio.gather(
        *[s.read() for s in sensors], return_exceptions=True
    )
    assert len(results) == 7
    # The 6 real sensors return SensorReading; the exploder returns its
    # exception (caller's responsibility to filter). None of them
    # propagated to the top-level gather.
    good = [r for r in results if isinstance(r, SensorReading)]
    bad = [r for r in results if isinstance(r, BaseException)]
    assert len(good) == 6
    assert len(bad) == 1 and isinstance(bad[0], RuntimeError)


@pytest.mark.asyncio
async def test_all_sensors_parallel_stay_under_one_second(
    tmp_path, monkeypatch
):
    """The pulse runs sensors in parallel; with all backing infra
    absent (pure local paths) the total wall time must stay well under
    a second. If this ever drifts upward, something started doing sync
    I/O on the no-infra path."""
    import time

    sensors = _all_sensors_no_backing_infra(tmp_path, monkeypatch)
    start = time.perf_counter()
    readings = await asyncio.gather(*[s.read() for s in sensors])
    elapsed = time.perf_counter() - start
    assert len(readings) == 6
    assert elapsed < 1.0, f"no-infra fan-out took {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_thinker_aggregates_mixed_status_readings_into_noop(
    tmp_path, monkeypatch
):
    """End-to-end-ish: feed the thinker a mix of green/yellow/red
    readings. While pre_natal it must still return action='none' and
    label its reason with the phase + sensor counts — never raise."""
    # Pin birth_date so pre_natal stays locked regardless of when the
    # test runs.
    recent_birth = datetime.now(timezone.utc) - timedelta(days=1)
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.config.cell_birth_date",
        lambda: recent_birth,
    )

    now = datetime.now(timezone.utc)
    readings = [
        SensorReading(
            sensor_name="gsc",
            status="green",
            value={"query_count": 42, "clicks_total": 0, "impressions_total": 0,
                   "top_queries": []},
            timestamp=now,
            metadata={},
        ),
        SensorReading(
            sensor_name="ga4",
            status="yellow",
            value={"page_count": 0, "sessions_total": 0, "conversions_total": 0,
                   "sessions_by_page": {}, "conversions_by_page": {}},
            timestamp=now,
            metadata={"error_code": "credentials_missing"},
        ),
        SensorReading(
            sensor_name="kg",
            status="red",
            value={"node_count": 0, "edge_count": 0, "nodes_by_type": {},
                   "edges_by_type": {}, "last_updated_at": None},
            timestamp=now,
            metadata={"error_code": "db_error"},
        ),
    ]
    thinker = SEOThinker()
    proposal = await thinker.think(
        readings=readings,
        state=HomeostaticState(),
        memory_context={},
    )
    assert isinstance(proposal, Proposal)
    assert proposal.action == "none"
    # Reason must surface the phase so operators can tell pre_natal
    # apart from sprint1_stub_graduated.
    assert "pre_natal" in proposal.reason
    # Sensor counts encoded in reason
    assert "green=1" in proposal.reason
    assert "yellow=1" in proposal.reason
    assert "red=1" in proposal.reason


@pytest.mark.asyncio
async def test_sensor_internal_exception_swallowed_as_red(tmp_path, monkeypatch):
    """Per policy, every sensor catches arbitrary Exception subclasses
    internally and returns red. Regression guard: if a new branch
    inside `_fetch_*` forgets the blanket `except Exception`, this
    fails. (BaseException — KeyboardInterrupt, SystemExit — is
    intentionally NOT swallowed.)"""
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GSCSensor()
    with patch.object(
        sensor, "_fetch_rows_blocking", side_effect=ValueError("weird")
    ):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "unexpected"
    assert (
        "weird" in reading.metadata["error"]
        or "ValueError" in reading.metadata["error"]
    )


@pytest.mark.asyncio
async def test_factory_sensors_are_six_distinct_instances():
    """The cell factory wires exactly 6 sensors, each a distinct class
    instance with its own name. Guards against a copy-paste duplication
    (e.g., two GSCSensor in the list)."""
    # We don't call create_seo_cell() here because it touches the
    # filesystem (DNA_PATH, memory backend) and pulls cell-core
    # lifecycle — overkill for this contract. We re-assemble the
    # sensor list the same way the factory does and check identity.
    sensors = [
        GSCSensor(),
        GA4Sensor(),
        CompetitorSERPSensor(),
        KGSensor(),
        WarRoomEventSensor(),
        CannibalizationSensor(),
    ]
    names = [s.name for s in sensors]
    classes = [type(s).__name__ for s in sensors]
    assert len(set(names)) == 6, f"duplicate sensor name: {names}"
    assert len(set(classes)) == 6, f"duplicate sensor class: {classes}"
    # And the names are the ones the thinker keys on
    assert set(names) == EXPECTED_SENSOR_NAMES
