"""Tests for cell_core.types — shared vocabulary."""
import time
from datetime import datetime, timezone

import pytest


def test_phase_enum_values():
    from cell_core.types import Phase
    assert Phase.EMBRIONE.value == "embrione"
    assert Phase.NEONATO.value == "neonato"
    assert Phase.GIOVANE.value == "giovane"
    assert Phase.ADULTO.value == "adulto"
    assert Phase.ANZIANO.value == "anziano"


def test_phase_is_str_enum():
    from cell_core.types import Phase
    assert isinstance(Phase.EMBRIONE, str)
    assert f"phase={Phase.ADULTO}" == "phase=adulto"


def test_cell_config_defaults():
    from cell_core.types import CellConfig
    cfg = CellConfig(name="test", dna_path="dna.json")
    assert cfg.pulse_interval_seconds == 60
    assert cfg.memory_backend == "sqlite"
    assert cfg.db_path == "cell.db"
    assert cfg.sleep_hours == (2, 6)
    assert cfg.birth_date is None


def test_cell_config_custom():
    from cell_core.types import CellConfig
    bd = datetime(2026, 3, 26, tzinfo=timezone.utc)
    cfg = CellConfig(
        name="mata-garuda", dna_path="mg.json",
        pulse_interval_seconds=3600, birth_date=bd,
        memory_backend="postgres", db_path="mg.db",
        sleep_hours=(1, 5),
    )
    assert cfg.name == "mata-garuda"
    assert cfg.birth_date == bd
    assert cfg.pulse_interval_seconds == 3600


def test_sensor_reading_defaults():
    from cell_core.types import SensorReading
    r = SensorReading(sensor_name="health", status="green")
    assert r.sensor_name == "health"
    assert r.status == "green"
    assert r.value is None
    assert isinstance(r.timestamp, datetime)
    assert r.metadata == {}


def test_sensor_reading_with_value():
    from cell_core.types import SensorReading
    r = SensorReading(sensor_name="db", status="yellow", value={"latency_ms": 150})
    assert r.value == {"latency_ms": 150}


def test_proposal_defaults():
    from cell_core.types import Proposal
    p = Proposal(action="restart_service", reason="high latency", confidence=0.9, tier_used=0)
    assert p.cost_usd == 0.0


def test_episode_defaults():
    from cell_core.types import Episode
    e = Episode(
        situation={"status": "red"}, emotion="stressed",
        action_taken="restart", outcome="success", lesson="restart helps",
    )
    assert e.id == 0
    assert e.recall_count == 0
    assert e.activation == 0.0
    assert e.timestamp == 0.0


def test_episode_compute_activation():
    from cell_core.types import Episode
    now = time.time()
    e = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok", timestamp=now, recall_count=5,
    )
    act = e.compute_activation()
    assert act > 0.5
    e2 = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok", timestamp=now, recall_count=0,
    )
    assert e.compute_activation() > e2.compute_activation()


def test_episode_old_has_lower_activation():
    from cell_core.types import Episode
    old = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok",
        timestamp=time.time() - 86400 * 7,
    )
    recent = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok",
        timestamp=time.time(),
    )
    assert recent.compute_activation() > old.compute_activation()


def test_learned_rule():
    from cell_core.types import LearnedRule
    r = LearnedRule(rule_text="When latency > 500ms, restart", support_count=3)
    assert r.created_at == ""


def test_homeostatic_state_defaults():
    from cell_core.types import HomeostaticState
    s = HomeostaticState()
    assert s.stress_level == 0.0
    assert s.energy_level == 1.0
    assert s.arousal == 0.5
    assert s.circadian_phase == "awake"


def test_homeostatic_state_clamp():
    from cell_core.types import HomeostaticState
    s = HomeostaticState(stress_level=1.5, energy_level=-0.5, arousal=2.0)
    assert 0.0 <= s.stress_level <= 1.0
    assert 0.0 <= s.energy_level <= 1.0
    assert 0.0 <= s.arousal <= 1.0


def test_pulse_result_defaults():
    from cell_core.types import PulseResult
    now = datetime.now(timezone.utc)
    r = PulseResult(timestamp=now, pulse_number=1)
    assert r.halted is False
    assert r.action_taken is None


def test_safety_check_result():
    from cell_core.types import SafetyCheckResult
    ok = SafetyCheckResult(can_proceed=True)
    assert ok.reason == ""
    blocked = SafetyCheckResult(can_proceed=False, reason="disabled", detail="file exists")
    assert not blocked.can_proceed


def test_dna_rule():
    from cell_core.types import DNARule
    r = DNARule(text="Never modify DNA", priority=1)
    assert r.text == "Never modify DNA"


def test_dna_config():
    from cell_core.types import DNAConfig, DNARule
    cfg = DNAConfig(
        rules=[DNARule(text="Rule 1", priority=1)],
        constraints={"max_daily_budget_usd": 10.0},
    )
    assert len(cfg.rules) == 1
    assert cfg.constraints["max_daily_budget_usd"] == 10.0


def test_pulse_result_has_pulse_id_default():
    """PulseResult must have a pulse_id field auto-populated with a ULID-like string."""
    from cell_core.types import PulseResult
    result = PulseResult(
        timestamp=datetime.now(timezone.utc),
        pulse_number=1,
    )
    assert hasattr(result, "pulse_id")
    assert isinstance(result.pulse_id, str)
    assert len(result.pulse_id) >= 16


def test_pulse_result_pulse_id_unique_per_instance():
    """Two PulseResult created back-to-back must have different pulse_ids."""
    from cell_core.types import PulseResult
    a = PulseResult(timestamp=datetime.now(timezone.utc), pulse_number=1)
    b = PulseResult(timestamp=datetime.now(timezone.utc), pulse_number=2)
    assert a.pulse_id != b.pulse_id
