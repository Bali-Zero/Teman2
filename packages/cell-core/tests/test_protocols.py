"""Tests for cell_core.protocols — runtime_checkable Protocol compliance."""
import pytest


class TestSensorProtocol:
    def test_valid_sensor_is_instance(self):
        from cell_core.protocols import Sensor
        from cell_core.types import SensorReading

        class MySensor:
            name = "test"
            async def read(self, **context):
                return SensorReading(sensor_name="test", status="green")

        assert isinstance(MySensor(), Sensor)

    def test_missing_name_is_not_sensor(self):
        from cell_core.protocols import Sensor

        class BadSensor:
            async def read(self, **context):
                return None

        assert not isinstance(BadSensor(), Sensor)


class TestThinkerProtocol:
    def test_valid_thinker(self):
        from cell_core.protocols import Thinker
        from cell_core.types import Proposal

        class MyThinker:
            async def think(self, readings, state, memory_context):
                return Proposal(action="none", reason="ok", confidence=1.0, tier_used=-1)

        assert isinstance(MyThinker(), Thinker)


class TestActorProtocol:
    def test_valid_actor(self):
        from cell_core.protocols import Actor

        class MyActor:
            async def act(self, proposal):
                return "done"
            def can_execute(self, action_name):
                return True

        assert isinstance(MyActor(), Actor)

    def test_missing_can_execute_is_not_actor(self):
        from cell_core.protocols import Actor

        class BadActor:
            async def act(self, proposal):
                return "done"

        assert not isinstance(BadActor(), Actor)


class TestSTMStoreProtocol:
    def test_valid_stm(self):
        from cell_core.protocols import STMStore

        class MySTM:
            async def store(self, event_type, data):
                pass
            async def recent(self, event_type, limit):
                return []

        assert isinstance(MySTM(), STMStore)


class TestLTMStoreProtocol:
    def test_valid_ltm(self):
        from cell_core.protocols import LTMStore

        class MyLTM:
            async def store_rule(self, rule):
                pass
            async def load_rules(self, limit):
                return []
            async def condense(self, episodes):
                return []

        assert isinstance(MyLTM(), LTMStore)


class TestEpisodicStoreProtocol:
    def test_valid_episodic(self):
        from cell_core.protocols import EpisodicStore

        class MyEpisodic:
            async def store(self, episode):
                return 1
            async def recall(self, situation, limit):
                return []
            async def recall_recent(self, hours, limit):
                return []
            async def forget_weak(self, keep):
                return 0

        assert isinstance(MyEpisodic(), EpisodicStore)
