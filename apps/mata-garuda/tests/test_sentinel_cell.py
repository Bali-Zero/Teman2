"""Tests for SentinelCell — the living organ."""
import pytest
from pathlib import Path


class TestSensors:
    def test_arxiv_sensor_has_name(self):
        from mata_garuda.cells.sensors.arxiv_sensor import ArXivSensor
        s = ArXivSensor()
        assert s.name == "arxiv"

    def test_rss_sensor_has_name(self):
        from mata_garuda.cells.sensors.rss_sensor import RSSSensor
        s = RSSSensor()
        assert s.name == "rss"

    def test_github_sensor_has_name(self):
        from mata_garuda.cells.sensors.github_sensor import GitHubSensor
        s = GitHubSensor()
        assert s.name == "github"

    def test_youtube_sensor_has_name(self):
        from mata_garuda.cells.sensors.youtube_sensor import YouTubeSensor
        s = YouTubeSensor()
        assert s.name == "youtube"


class TestThinker:
    @pytest.mark.asyncio
    async def test_think_with_empty_readings(self):
        from mata_garuda.cells.thinker import SentinelThinker
        from cell_core.types import HomeostaticState

        t = SentinelThinker()
        proposal = await t.think([], HomeostaticState(), {})
        assert proposal.action == "none"

    @pytest.mark.asyncio
    async def test_think_with_data(self):
        from mata_garuda.cells.thinker import SentinelThinker
        from cell_core.types import HomeostaticState, SensorReading

        t = SentinelThinker()
        readings = [
            SensorReading(
                sensor_name="arxiv",
                status="green",
                value=[
                    {"title": "Test Paper", "url": "http://arxiv.org/abs/1234", "abstract": "Test abstract", "source": "arxiv"},
                    {"title": "Paper 2", "url": "http://arxiv.org/abs/5678", "abstract": "Another paper", "source": "arxiv"},
                ],
                metadata={"count": 2},
            )
        ]
        proposal = await t.think(readings, HomeostaticState(), {})
        assert proposal.action == "publish_all"
        assert proposal.confidence > 0.5

    def test_get_deduped_items(self):
        from mata_garuda.cells.thinker import SentinelThinker
        from cell_core.types import SensorReading

        t = SentinelThinker()
        readings = [
            SensorReading(
                sensor_name="arxiv", status="green",
                value=[
                    {"title": "Paper A", "url": "http://a.com", "abstract": "x"},
                    {"title": "Paper A", "url": "http://a.com", "abstract": "x"},  # dupe
                    {"title": "Paper B", "url": "http://b.com", "abstract": "y"},
                ],
                metadata={"count": 3},
            )
        ]
        items = t.get_deduped_items(readings)
        assert len(items) == 2  # deduped


class TestActor:
    def test_actor_can_execute(self, tmp_path):
        from mata_garuda.cells.actors.sentinel_actor import SentinelActor
        from mata_garuda.runtime.knowledge import KnowledgeBase

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        actor = SentinelActor(kb=kb)
        assert actor.can_execute("publish_all")
        assert actor.can_execute("none")
        assert not actor.can_execute("random_action")
        kb.close()


class TestCellFactory:
    def test_create_sentinel_cell(self):
        from mata_garuda.cells.sentinel_cell import create_sentinel_cell
        cell = create_sentinel_cell()
        assert cell is not None
        assert len(cell.sensors) == 4
        assert cell.lifecycle.phase is not None

    def test_dna_exists(self):
        dna_path = Path(__file__).parent.parent / "sentinel_dna.json"
        assert dna_path.exists()
        import json
        dna = json.loads(dna_path.read_text())
        assert len(dna["rules"]) >= 5
        assert "constraints" in dna
