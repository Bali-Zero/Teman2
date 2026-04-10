"""Tests for cell_core.identity — SelfModel persistence."""
import json
import pytest


class TestSelfModel:
    def test_default_birth_date(self):
        from cell_core.identity import SelfModel
        m = SelfModel()
        assert m.birth_date != ""
        assert m.total_pulses == 0

    def test_from_dict_round_trip(self):
        from cell_core.identity import SelfModel
        m = SelfModel(total_pulses=100, total_actions=5)
        m.capabilities = {"health": 0.95}
        d = m.to_dict()
        m2 = SelfModel.from_dict(d)
        assert m2.total_pulses == 100
        assert m2.capabilities["health"] == 0.95


class TestSelfModelManager:
    def test_load_creates_default(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.load()
        assert mgr.model.total_pulses == 0

    def test_save_and_load(self, tmp_path):
        from cell_core.identity import SelfModelManager
        path = tmp_path / "model.json"
        mgr = SelfModelManager(path=path)
        mgr.model.total_pulses = 42
        mgr.save()
        mgr2 = SelfModelManager(path=path)
        mgr2.load()
        assert mgr2.model.total_pulses == 42

    def test_record_pulse(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.record_pulse()
        assert mgr.model.total_pulses == 1
        mgr.record_pulse()
        assert mgr.model.total_pulses == 2

    def test_record_action(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.record_action("restart_service")
        assert mgr.model.total_actions == 1

    def test_sensor_reliability(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        for _ in range(8):
            mgr.update_sensor_reliability("health", True)
        mgr.update_sensor_reliability("health", False)
        mgr.update_sensor_reliability("health", False)
        assert mgr.model.capabilities["health"] == pytest.approx(0.8)

    def test_atomic_write(self, tmp_path):
        from cell_core.identity import SelfModelManager
        path = tmp_path / "model.json"
        mgr = SelfModelManager(path=path)
        mgr.model.total_pulses = 99
        mgr.save()
        assert not (tmp_path / "model.tmp").exists()
        data = json.loads(path.read_text())
        assert data["total_pulses"] == 99

    def test_to_prompt_context(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.model.total_pulses = 100
        mgr.model.capabilities = {"health": 0.95}
        ctx = mgr.to_prompt_context()
        assert "100" in ctx
        assert "health" in ctx
