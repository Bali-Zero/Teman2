"""Shared fixtures for HGT tests.

Uses a fake async Redis client that implements xadd/xreadgroup/xack/xgroup_create
in-memory. This tests the logic without requiring a real Redis connection.
For integration tests with real Redis, see test_integration.py.
"""
import asyncio
import pytest
from collections import defaultdict
from typing import Any

from cell_core.genome import Genome


class FakeRedis:
    """In-memory async Redis mock supporting Streams operations.

    Implements just enough of redis.asyncio.Redis for HGT testing:
    - xadd / xreadgroup / xack / xgroup_create
    - maxlen trimming
    - Consumer group tracking
    """

    def __init__(self) -> None:
        # stream_name -> list of (msg_id, data_dict)
        self._streams: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        # stream_name -> {group_name: {consumer_name: set of pending msg_ids}}
        self._groups: dict[str, dict[str, dict[str, set]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(set))
        )
        # stream_name -> {group_name: last_delivered_index}
        self._group_cursor: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._counter = 0

    async def xadd(self, stream: str, data: dict, maxlen: int | None = None, **kwargs) -> str:
        self._counter += 1
        msg_id = f"{self._counter}-0"
        self._streams[stream].append((msg_id, data))
        # Trim to maxlen
        if maxlen and len(self._streams[stream]) > maxlen:
            self._streams[stream] = self._streams[stream][-maxlen:]
        return msg_id

    async def xgroup_create(self, stream: str, group: str, id: str = "0", mkstream: bool = False) -> None:
        if group in self._groups[stream]:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self._groups[stream][group] = defaultdict(set)
        self._group_cursor[stream][group] = 0

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int = 10,
        block: int | None = None,
    ) -> list[tuple[str, list[tuple[str, dict]]]]:
        result = []
        for stream_name, _offset in streams.items():
            cursor = self._group_cursor[stream_name][groupname]
            all_msgs = self._streams.get(stream_name, [])
            new_msgs = all_msgs[cursor:cursor + count]
            if new_msgs:
                self._group_cursor[stream_name][groupname] = cursor + len(new_msgs)
                # Track as pending
                for msg_id, _data in new_msgs:
                    self._groups[stream_name][groupname][consumername].add(msg_id)
                result.append((stream_name, new_msgs))
        return result

    async def xack(self, stream: str, group: str, *msg_ids: str) -> int:
        acked = 0
        for msg_id in msg_ids:
            for consumer_pending in self._groups[stream][group].values():
                if msg_id in consumer_pending:
                    consumer_pending.discard(msg_id)
                    acked += 1
        return acked

    def get_stream(self, name: str) -> list[tuple[str, dict]]:
        """Test helper: inspect stream contents."""
        return list(self._streams.get(name, []))


class BrokenRedis:
    """Redis mock that raises ConnectionError on every operation."""

    async def xadd(self, *args, **kwargs):
        raise ConnectionError("Redis is down")

    async def xgroup_create(self, *args, **kwargs):
        raise ConnectionError("Redis is down")

    async def xreadgroup(self, *args, **kwargs):
        raise ConnectionError("Redis is down")

    async def xack(self, *args, **kwargs):
        raise ConnectionError("Redis is down")


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def broken_redis():
    return BrokenRedis()


@pytest.fixture
def genome(tmp_path):
    return Genome(db_path=str(tmp_path / "hgt_test.db"))


@pytest.fixture
def genome_b(tmp_path):
    """Second genome instance for multi-cell tests (same DB)."""
    return Genome(db_path=str(tmp_path / "hgt_test.db"))
