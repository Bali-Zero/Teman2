# tests/test_self_model.py
"""Tests for CELL's self-model — persistent identity across restarts."""
import json
import os
import tempfile
import pytest
from cell.identity.self_model import SelfModel, SelfModelManager


class TestSelfModel:
    def test_default_model(self) -> None:
        model = SelfModel()
        assert model.age_days == 0
        assert model.total_pulses == 0
        assert model.total_actions == 0
        assert model.capabilities == {}
        assert model.preferences == []
        assert model.weaknesses == []

    def test_record_pulse_increments_counter(self) -> None:
        model = SelfModel()
        model.total_pulses += 1
        assert model.total_pulses == 1

    def test_serialization_roundtrip(self) -> None:
        model = SelfModel(
            capabilities={"health_sensor": 0.95, "ollama_sensor": 0.7},
            preferences=["restart before scale_up"],
            weaknesses=["slow to detect flapping"],
            total_pulses=1000,
            total_actions=42,
            age_days=7,
        )
        data = model.to_dict()
        restored = SelfModel.from_dict(data)
        assert restored.capabilities == model.capabilities
        assert restored.preferences == model.preferences
        assert restored.weaknesses == model.weaknesses
        assert restored.total_pulses == 1000
        assert restored.age_days == 7


class TestSelfModelManager:
    def test_save_and_load(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            mgr = SelfModelManager(path=path)
            mgr.model.total_pulses = 500
            mgr.model.capabilities["health_sensor"] = 0.99
            mgr.save()

            mgr2 = SelfModelManager(path=path)
            mgr2.load()
            assert mgr2.model.total_pulses == 500
            assert mgr2.model.capabilities["health_sensor"] == 0.99
        finally:
            os.unlink(path)

    def test_load_missing_file_creates_default(self) -> None:
        mgr = SelfModelManager(path="/tmp/cell_self_model_nonexistent_test.json")
        mgr.load()
        assert mgr.model.total_pulses == 0

    def test_update_sensor_reliability(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.update_sensor_reliability("health_sensor", success=True)
        mgr.update_sensor_reliability("health_sensor", success=True)
        mgr.update_sensor_reliability("health_sensor", success=False)
        # 2 success / 3 total ≈ 0.667
        assert 0.5 < mgr.model.capabilities["health_sensor"] < 0.8

    def test_add_preference_no_duplicates(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.add_preference("restart before scale_up")
        mgr.add_preference("restart before scale_up")
        assert mgr.model.preferences.count("restart before scale_up") == 1

    def test_record_pulse_updates_age(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.record_pulse()
        assert mgr.model.total_pulses == 1

    def test_to_prompt_context(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.model.total_pulses = 100
        mgr.model.age_days = 3
        mgr.model.capabilities = {"health_sensor": 0.95}
        ctx = mgr.to_prompt_context()
        assert "age_days: 3" in ctx
        assert "health_sensor" in ctx

    def test_sensor_reliability_persists_across_restart(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            mgr = SelfModelManager(path=path)
            for _ in range(10):
                mgr.update_sensor_reliability("health_sensor", success=True)
            mgr.save()

            # Simulate restart
            mgr2 = SelfModelManager(path=path)
            mgr2.load()
            # Should continue with 10 True readings already in history
            mgr2.update_sensor_reliability("health_sensor", success=False)
            # 10 True + 1 False = 10/11 ≈ 0.909
            assert mgr2.model.capabilities["health_sensor"] > 0.8
        finally:
            os.unlink(path)
