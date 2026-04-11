"""Test fixtures for anomaly detectors.

Provides a mock Neo4j AsyncSession that executes against an in-memory
graph representation. This avoids requiring a live Neo4j instance for
unit tests while allowing integration tests to use a real server.

For live Neo4j tests, set NEO4J_TEST_URI env var and use @pytest.mark.neo4j.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest


# ── In-memory graph store for unit tests ──


@dataclass
class MockNode:
    """A node in the mock graph."""

    element_id: str
    labels: list[str]
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockRelationship:
    """A relationship in the mock graph."""

    element_id: str
    start_id: str
    end_id: str
    rel_type: str
    properties: dict[str, Any] = field(default_factory=dict)


class MockResult:
    """Simulates a Neo4j Result with async iteration."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records
        self._index = 0

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._index >= len(self._records):
            raise StopAsyncIteration
        record = self._records[self._index]
        self._index += 1
        return record

    async def single(self) -> dict[str, Any] | None:
        return self._records[0] if self._records else None


class MockGraph:
    """In-memory graph for test assertions.

    Provides a fluent API for building synthetic test graphs and a
    mock session that returns pre-configured results.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, MockNode] = {}
        self.relationships: list[MockRelationship] = []
        self._next_node_id = 1
        self._next_rel_id = 1
        self._query_handlers: dict[str, list[dict[str, Any]]] = {}

    def add_node(
        self,
        labels: list[str],
        properties: dict[str, Any] | None = None,
        element_id: str | None = None,
    ) -> str:
        """Add a node and return its element_id."""
        eid = element_id or f"4:{self._next_node_id}"
        self._next_node_id += 1
        self.nodes[eid] = MockNode(
            element_id=eid,
            labels=labels,
            properties=properties or {},
        )
        return eid

    def add_relationship(
        self,
        start_id: str,
        end_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Add a relationship and return its element_id."""
        eid = f"5:{self._next_rel_id}"
        self._next_rel_id += 1
        self.relationships.append(
            MockRelationship(
                element_id=eid,
                start_id=start_id,
                end_id=end_id,
                rel_type=rel_type,
                properties=properties or {},
            )
        )
        return eid

    def set_query_result(
        self, pattern: str, records: list[dict[str, Any]]
    ) -> None:
        """Register a result for queries matching a pattern (substring match)."""
        self._query_handlers[pattern] = records

    def get_session(self) -> AsyncMock:
        """Create a mock AsyncSession wired to this graph's query handlers."""
        session = AsyncMock()

        async def mock_run(query: str, parameters: dict | None = None):
            query_lower = query.lower().strip()

            # Check GDS availability — always return False in unit tests
            if "gds.version()" in query_lower:
                raise Exception("GDS not available")

            # Match against registered patterns
            for pattern, records in self._query_handlers.items():
                if pattern.lower() in query_lower:
                    return MockResult(records)

            # Default: empty result
            return MockResult([])

        session.run = mock_run
        return session


# ── Fixtures ──


@pytest.fixture
def mock_graph() -> MockGraph:
    """Provide a fresh in-memory mock graph."""
    return MockGraph()


@pytest.fixture
def mock_session(mock_graph: MockGraph) -> AsyncMock:
    """Provide a mock Neo4j session from the mock graph."""
    return mock_graph.get_session()


# ── Live Neo4j fixtures (skipped when NEO4J_TEST_URI unset) ──

neo4j_marker = pytest.mark.neo4j


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "neo4j: requires live Neo4j instance")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not os.getenv("NEO4J_TEST_URI"):
        skip = pytest.mark.skip(reason="NEO4J_TEST_URI not set")
        for item in items:
            if "neo4j" in item.keywords:
                item.add_marker(skip)
