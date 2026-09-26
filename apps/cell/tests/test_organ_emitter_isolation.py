import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import cell.utils.organ_emitter as organ_emitter
from cell.sensors.health_sensor import HealthSensor

REAL_DIR = Path("~/.organism/last_seen").expanduser()


def _degraded_reading_sensor():
    response = MagicMock(status_code=503)
    response.elapsed.total_seconds.return_value = 0.5
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    return HealthSensor(client=client, url="http://test/health")


def test_a_mocked_503_lands_in_the_test_dir(_isolated_last_seen_dir):
    asyncio.run(_degraded_reading_sensor().read())
    assert (_isolated_last_seen_dir / "backend.api.json").is_file()


def test_the_live_organism_dir_is_not_the_default_under_test(_isolated_last_seen_dir):
    assert organ_emitter.DEFAULT_LAST_SEEN_DIR == _isolated_last_seen_dir
    assert organ_emitter.DEFAULT_LAST_SEEN_DIR != REAL_DIR
