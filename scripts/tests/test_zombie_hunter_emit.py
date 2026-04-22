import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parents[2] / "apps" / "organism"))
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))


@pytest.mark.asyncio
async def test_zombie_detected_after_3_consecutive_exit1():
    """Relaxed criterion: last_exit=1 × 3 cycles → zombie."""
    from sentinel_lib import zombie_hunter as zh
    agent_state = {
        "test_agent": {"consecutive_exit1": 3, "last_pid": None, "label": "com.balizero.test"},
    }
    mock_emit = AsyncMock()
    with patch("organism.emit.emit_event", mock_emit):
        zombies = zh.identify_zombies(agent_state)
    assert "test_agent" in zombies


@pytest.mark.asyncio
async def test_healthy_agent_not_zombie():
    from sentinel_lib import zombie_hunter as zh
    agent_state = {"healthy_agent": {"consecutive_exit1": 0, "last_pid": 1234, "label": "com.balizero.h"}}
    zombies = zh.identify_zombies(agent_state)
    assert "healthy_agent" not in zombies
