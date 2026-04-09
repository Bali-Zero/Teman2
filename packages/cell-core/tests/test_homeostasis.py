"""Tests for cell_core.homeostasis."""
import pytest
from cell_core.types import HomeostaticState


class TestHomeostaticController:
    def _make(self, **kwargs):
        from cell_core.homeostasis import HomeostaticController
        return HomeostaticController(**kwargs)

    def test_initial_state(self):
        hc = self._make()
        assert hc.state.stress_level == 0.0
        assert hc.state.energy_level == 1.0
        assert hc.state.arousal == 0.5
        assert hc.state.circadian_phase == "awake"

    def test_green_pulse_reduces_stress(self):
        hc = self._make()
        hc.state.stress_level = 0.5
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.state.stress_level < 0.5

    def test_red_pulse_increases_stress(self):
        hc = self._make()
        hc.update(response_time_ms=100, health_status="red", hour_utc=12)
        assert hc.state.stress_level > 0.0

    def test_high_rt_increases_stress(self):
        hc = self._make()
        for _ in range(10):
            hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        stress_before = hc.state.stress_level
        hc.update(response_time_ms=5000, health_status="green", hour_utc=12)
        assert hc.state.stress_level > stress_before

    def test_green_pulse_recovers_energy(self):
        hc = self._make()
        hc.state.energy_level = 0.5
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.state.energy_level > 0.5

    def test_circadian_asleep(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert hc.state.circadian_phase == "asleep"

    def test_circadian_awake(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.state.circadian_phase == "awake"

    def test_circadian_drowsy(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=1)
        assert hc.state.circadian_phase == "drowsy"

    def test_is_sleeping(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert hc.is_sleeping() is True
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.is_sleeping() is False

    def test_recommended_pulse_interval_asleep(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert hc.recommended_pulse_interval() == 300

    def test_recommended_pulse_interval_stressed(self):
        hc = self._make()
        hc.state.stress_level = 0.9
        hc.state.circadian_phase = "awake"
        interval = hc.recommended_pulse_interval()
        assert interval <= 20

    def test_record_action_cost_drains_energy(self):
        hc = self._make()
        hc.record_action_cost(0.3)
        assert hc.state.energy_level == pytest.approx(0.7, abs=0.01)

    def test_ema_setpoint_adapts(self):
        hc = self._make()
        initial = hc.state.setpoint_rt_ms
        for _ in range(20):
            hc.update(response_time_ms=500, health_status="green", hour_utc=12)
        assert hc.state.setpoint_rt_ms > initial


class TestTrendDetector:
    def _make(self):
        from cell_core.homeostasis import TrendDetector
        return TrendDetector()

    def test_no_trend_on_empty(self):
        td = self._make()
        result = td.detect([])
        assert result.monotonic_drift is False
        assert result.flapping is False
        assert result.sustained_degraded is False

    def test_monotonic_drift(self):
        td = self._make()
        pulses = [{"response_time_ms": 100 + i * 50, "health_status": "green"} for i in range(6)]
        result = td.detect(pulses)
        assert result.monotonic_drift is True

    def test_no_drift_when_stable(self):
        td = self._make()
        pulses = [{"response_time_ms": 100, "health_status": "green"} for _ in range(6)]
        result = td.detect(pulses)
        assert result.monotonic_drift is False

    def test_flapping(self):
        td = self._make()
        pulses = [{"response_time_ms": 100, "health_status": "green" if i % 2 == 0 else "red"} for i in range(8)]
        result = td.detect(pulses)
        assert result.flapping is True

    def test_sustained_degraded(self):
        td = self._make()
        pulses = [{"response_time_ms": 100, "health_status": "red"} for _ in range(5)]
        result = td.detect(pulses)
        assert result.sustained_degraded is True

    def test_no_sustained_when_mixed(self):
        td = self._make()
        pulses = [
            {"response_time_ms": 100, "health_status": "red"},
            {"response_time_ms": 100, "health_status": "green"},
            {"response_time_ms": 100, "health_status": "red"},
            {"response_time_ms": 100, "health_status": "red"},
        ]
        result = td.detect(pulses)
        assert result.sustained_degraded is False
