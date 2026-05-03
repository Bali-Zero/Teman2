# tests/test_homeostasis.py
"""Tests for the homeostatic controller — CELL's body regulation."""
import math
import pytest
from cell.fast.homeostatic_controller import HomeostaticState, HomeostaticController


class TestHomeostaticState:
    def test_initial_state_is_calm(self) -> None:
        state = HomeostaticState()
        assert state.stress_level == 0.0
        assert state.energy_level == 1.0
        assert state.arousal == 0.5
        assert state.circadian_phase == "awake"

    def test_stress_clamped_0_1(self) -> None:
        state = HomeostaticState(stress_level=1.5)
        assert state.stress_level == 1.0
        state2 = HomeostaticState(stress_level=-0.3)
        assert state2.stress_level == 0.0


class TestHomeostaticController:
    def test_setpoint_adapts_to_readings(self) -> None:
        ctrl = HomeostaticController()
        # Feed 10 pulses at 200ms — setpoint should move toward 200
        for _ in range(10):
            ctrl.update(response_time_ms=200, health_status="green")
        assert 180 < ctrl.state.setpoint_rt_ms < 220

    def test_stress_rises_outside_comfort_zone(self) -> None:
        ctrl = HomeostaticController()
        # Establish baseline at 100ms
        for _ in range(20):
            ctrl.update(response_time_ms=100, health_status="green")
        baseline_stress = ctrl.state.stress_level
        # Spike to 5000ms — stress should rise
        ctrl.update(response_time_ms=5000, health_status="red")
        assert ctrl.state.stress_level > baseline_stress

    def test_stress_decays_when_stable(self) -> None:
        ctrl = HomeostaticController()
        # Create stress
        for _ in range(5):
            ctrl.update(response_time_ms=5000, health_status="red")
        high_stress = ctrl.state.stress_level
        # Return to normal — stress should decay
        for _ in range(20):
            ctrl.update(response_time_ms=100, health_status="green")
        assert ctrl.state.stress_level < high_stress

    def test_energy_drains_with_actions(self) -> None:
        ctrl = HomeostaticController()
        initial_energy = ctrl.state.energy_level
        ctrl.record_action_cost(0.1)
        assert ctrl.state.energy_level < initial_energy

    def test_energy_recovers_during_green(self) -> None:
        ctrl = HomeostaticController()
        ctrl.record_action_cost(0.5)  # drain energy
        low_energy = ctrl.state.energy_level
        for _ in range(10):
            ctrl.update(response_time_ms=100, health_status="green")
        assert ctrl.state.energy_level > low_energy

    def test_circadian_phase_asleep(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))  # UTC
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert ctrl.state.circadian_phase == "asleep"

    def test_circadian_phase_awake(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=10)
        assert ctrl.state.circadian_phase == "awake"

    def test_circadian_phase_drowsy(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))
        # Hour 1 = 1 hour before sleep start → drowsy
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=1)
        assert ctrl.state.circadian_phase == "drowsy"

    def test_recommended_interval_increases_when_asleep(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=3)
        interval = ctrl.recommended_pulse_interval()
        assert interval >= 120  # at least 2 minutes when asleep

    def test_recommended_interval_decreases_under_stress(self) -> None:
        ctrl = HomeostaticController()
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=10)
        calm_interval = ctrl.recommended_pulse_interval()
        for _ in range(5):
            ctrl.update(response_time_ms=5000, health_status="red", hour_utc=10)
        stressed_interval = ctrl.recommended_pulse_interval()
        assert stressed_interval < calm_interval

    def test_comfort_zone_widens_with_variance(self) -> None:
        ctrl = HomeostaticController()
        # Low variance readings
        for _ in range(20):
            ctrl.update(response_time_ms=100, health_status="green")
        narrow_zone = ctrl.state.comfort_zone
        # High variance readings
        ctrl2 = HomeostaticController()
        readings = [50, 200, 80, 300, 100, 400, 150, 500]
        for rt in readings * 3:
            ctrl2.update(response_time_ms=rt, health_status="green")
        wide_zone = ctrl2.state.comfort_zone
        assert (wide_zone[1] - wide_zone[0]) > (narrow_zone[1] - narrow_zone[0])

    def test_to_dict_has_correct_keys(self) -> None:
        ctrl = HomeostaticController()
        d = ctrl.to_dict()
        expected_keys = {"stress_level", "energy_level", "arousal",
                         "comfort_zone_low", "comfort_zone_high",
                         "setpoint_rt_ms", "circadian_phase"}
        assert set(d.keys()) == expected_keys

    def test_record_action_cost_clamps_to_zero(self) -> None:
        ctrl = HomeostaticController()
        ctrl.record_action_cost(5.0)  # way more than energy level of 1.0
        assert ctrl.state.energy_level == 0.0
