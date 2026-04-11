"""Test infrastructure for anomaly detectors.

We want two tiers:

1. **Offline tier (default)** — a ``FakeSession`` that stores a
   pre-defined list of ``(query_substring, records)`` mappings. We
   don't emulate Cypher. Instead, each detector test *teaches* the
   fake session what to return for the query shape the detector emits.
   This is deliberate: the alternative is a full Cypher interpreter,
   which is out of scope. What we CAN verify offline is:
   - the detector issues queries with expected parameters
   - the detector turns the server's records into alerts correctly
   - thresholds change the output
   - edge cases (empty graph, missing fields) don't crash

2. **Live tier (opt-in)** — provides a neo4j session backed by
   ``testcontainers[neo4j]`` if available OR a local NEO4J_URL. Tests
   that use this fixture are marked ``@pytest.mark.neo4j``. They are
   skipped unless ``NEO4J_URL`` is set in env.

The live fixture is a bonus — unit tests using FakeSession must be
green on every machine, no neo4j required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

# Register the `neo4j` marker so ``pytest -m "not neo4j"`` works even
# when the plugin isn't loaded.
def pytest_configure(config):  # noqa: D401
    config.addinivalue_line(
        "markers", "neo4j: tests that hit a live Neo4j instance (skipped without NEO4J_URL)"
    )


@dataclass
class FakeRecord:
    """Stand-in for neo4j Record. Supports dict-style access only."""

    data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __iter__(self):
        return iter(self.data)

    def keys(self):
        return self.data.keys()


@dataclass
class FakeResult:
    """Iterable cursor over FakeRecords, matching neo4j driver Result."""

    records: list[FakeRecord]

    def __iter__(self):
        return iter(self.records)

    def data(self) -> list[dict[str, Any]]:
        return [r.data for r in self.records]

    def single(self) -> FakeRecord | None:
        return self.records[0] if self.records else None


@dataclass
class FakeSession:
    """A scriptable neo4j session duck.

    Use ``session.teach(predicate, records)`` to say "when a query
    matches this predicate, return these records". The predicate is
    either a substring (case-sensitive) or a callable taking the query
    string.

    Predicates are checked in registration order; first match wins.
    Unknown queries return an empty result — NOT an error — so
    detectors can handle empty-graph paths.
    """

    _rules: list[tuple[Callable[[str], bool], list[dict[str, Any]]]] = field(default_factory=list)
    queries_seen: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    # Compatibility with neo4j driver session signature
    _closed: bool = False

    def teach(
        self,
        predicate: Callable[[str], bool] | str,
        records: list[dict[str, Any]],
    ) -> None:
        if isinstance(predicate, str):
            needle = predicate
            pred_fn: Callable[[str], bool] = lambda q, n=needle: n in q
        else:
            pred_fn = predicate
        self._rules.append((pred_fn, records))

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> FakeResult:
        self.queries_seen.append((query, dict(parameters or {})))
        for pred, records in self._rules:
            if pred(query):
                return FakeResult([FakeRecord(dict(r)) for r in records])
        return FakeResult([])

    def close(self) -> None:
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


@pytest.fixture
def fake_session() -> FakeSession:
    """Blank scriptable session. Each test teaches it what to return."""
    return FakeSession()


# ---------------------------------------------------------------------------
# Live tier (opt-in via @pytest.mark.neo4j + NEO4J_URL env var)
# ---------------------------------------------------------------------------


@pytest.fixture
def neo4j_session():
    """Real neo4j session, skipped unless NEO4J_URL is set.

    Tests that use this fixture MUST be marked @pytest.mark.neo4j and
    must clean up after themselves. We never wipe the live graph — the
    runbook expects the operator to target a throwaway database.
    """
    url = os.getenv("NEO4J_URL")
    if not url:
        pytest.skip("NEO4J_URL not set; skipping live neo4j test")
    try:
        from neo4j import GraphDatabase  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("neo4j driver not installed")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "neo4j")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    driver = GraphDatabase.driver(url, auth=(user, pwd))
    try:
        with driver.session(database=database) as s:
            yield s
    finally:
        driver.close()
