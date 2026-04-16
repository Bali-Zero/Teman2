"""Tests for CardinalityGuard — label explosion protection."""
from __future__ import annotations

import pytest

from cell_core.observability._prom_compat import HAS_PROM
from cell_core.observability.cardinality import CardinalityGuard, MAX_SERIES

pytestmark = pytest.mark.skipif(not HAS_PROM, reason="prometheus_client not installed")


@pytest.fixture
def registry():
    from prometheus_client import CollectorRegistry
    return CollectorRegistry()


class TestCardinalityGuard:
    def test_passes_normal_usage(self, registry):
        from prometheus_client import Counter
        c = Counter("test_normal_counter", "test", ["cell"], registry=registry)
        for i in range(10):
            c.labels(cell=f"cell_{i}").inc()

        guard = CardinalityGuard(registry=registry, max_series=500)
        assert guard.is_healthy()
        assert guard.total_series() > 0

    def test_warns_on_explosion(self, registry, caplog):
        from prometheus_client import Counter
        c = Counter("test_explode_counter", "test", ["cell", "phase", "domain"], registry=registry)
        # Create 600 unique label combos
        for i in range(600):
            c.labels(cell=f"c{i // 100}", phase=f"p{i // 10 % 10}", domain=f"d{i % 10}").inc()

        guard = CardinalityGuard(registry=registry, max_series=50)
        import logging
        with caplog.at_level(logging.WARNING):
            counts = guard.check()

        assert not guard.is_healthy()
        assert any("CARDINALITY VIOLATION" in r.message for r in caplog.records)

    def test_empty_registry(self, registry):
        guard = CardinalityGuard(registry=registry)
        assert guard.is_healthy()
        assert guard.total_series() == 0

    def test_no_registry_returns_empty(self):
        guard = CardinalityGuard(registry=None)
        assert guard.check() == {}
        assert guard.total_series() == 0

    def test_default_max_series(self):
        assert MAX_SERIES == 500
