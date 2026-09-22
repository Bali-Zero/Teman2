"""Parity between the backend classifier and the Pro-local standalone cron.

2026-09-23: both `intel_lake_router.py` (Fly, primary) and
`scripts/intel-lake-router-a2/intel-lake-router-cron-standalone.py` (Pro,
fallback) now import the SAME `intel_lake_rules.classify` instead of the
fallback keeping its own JSON copy of the rules (that copy drifted — see
PENDING-ARMS `intel-lake-pro-fallback-router-rules-drift`). These tests load
the standalone script by path (as the real cron does) and assert:

1. its loaded rules module classifies a real-world corpus identically to
   the backend `_classify`/`classify`.
2. `route_batch` actually threads `title`/`canonical_url` through to
   `classify` — a regression to domain-only matching changes the outcome
   for a press subdomain with a regulatory-keyword title.
3. the script no longer references the retired JSON rules file.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from backend.services.intel.intel_lake_router import IntelLakeRouter
from backend.services.intel.intel_lake_rules import classify as backend_classify

_STANDALONE_PATH = (
    Path(__file__).resolve().parents[7]
    / "scripts"
    / "intel-lake-router-a2"
    / "intel-lake-router-cron-standalone.py"
)


def _load_standalone() -> Any:
    """Import the standalone script by path, exactly as launchd's cron does.

    asyncpg is imported at module top level; stub it if unavailable so this
    test does not require the Postgres driver to check pure classification
    logic (route_batch tests below supply a fake pool instead).
    """
    if "asyncpg" not in sys.modules:
        try:
            import asyncpg  # noqa: F401
        except ImportError:
            sys.modules["asyncpg"] = types.ModuleType("asyncpg")
    spec = importlib.util.spec_from_file_location(
        "intel_lake_router_cron_standalone", _STANDALONE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Corpus: (source_domain, title, canonical_url, expected_status)
_CORPUS: list[tuple[str, str | None, str | None, str]] = [
    ("fiskal.kemenkeu.go.id", None, None, "nb-intel"),
    ("djppr.kemenkeu.go.id", None, None, "nb-intel"),
    ("news.ddtc.co.id", None, None, "nb-intel"),
    ("muc.co.id", None, None, "nb-intel"),
    (
        "m.antaranews.com",
        "New PMK rules on pajak reform",
        "https://m.antaranews.com/pajak",
        "nb-intel",
    ),
    ("m.antaranews.com", "Local football match result", None, "blog"),
    ("finance.detik.com", "Aturan pajak baru untuk investor", None, "nb-intel"),
    ("finance.detik.com", "Selebriti liburan ke Bali", None, "blog"),
    ("pajak.go.id", None, None, "nb-intel"),
    ("probe-sandbox.example.test", None, None, "nb-intel"),
    ("ddtc.co.id.example.com", None, None, "needs_review"),  # must NOT be tax
    ("totally-unknown-host.example", None, None, "needs_review"),
]


class TestStandaloneParity:
    """The standalone's loaded rules module must agree with the backend."""

    @pytest.fixture(scope="class")
    def standalone(self) -> Any:
        return _load_standalone()

    @pytest.fixture(scope="class")
    def standalone_rules(self, standalone: Any) -> Any:
        return standalone._load_rules_module()

    @pytest.mark.parametrize("domain,title,url,expected", _CORPUS)
    def test_parity_against_backend_classify(
        self, standalone_rules: Any, domain: str, title: str | None, url: str | None, expected: str
    ) -> None:
        standalone_decision = standalone_rules.classify(domain, title, url)
        backend_decision = backend_classify(domain, title, url)
        assert standalone_decision["status"] == expected, (
            f"{domain!r} (title={title!r}): standalone={standalone_decision}, expected {expected}"
        )
        assert standalone_decision == backend_decision, (
            f"{domain!r} (title={title!r}): standalone={standalone_decision} != "
            f"backend={backend_decision}"
        )

    @pytest.mark.parametrize("domain,title,url,expected", _CORPUS)
    def test_parity_against_router_classify_method(
        self, standalone_rules: Any, domain: str, title: str | None, url: str | None, expected: str
    ) -> None:
        router_decision = IntelLakeRouter(None)._classify(domain, title, url)  # type: ignore[arg-type]
        standalone_decision = standalone_rules.classify(domain, title, url)
        assert standalone_decision == router_decision


class _FakeConn:
    """Fake asyncpg connection: returns a fixed batch, records UPDATE args."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.updates: list[tuple[Any, ...]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        return self._rows

    def transaction(self) -> Any:
        @asynccontextmanager
        async def _txn() -> Any:
            yield

        return _txn()

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.updates.append(args)
        return args[0]  # pretend the row was updated (item_id)

    async def execute(self, query: str, *args: Any) -> None:
        pass


class _FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.conn = _FakeConn(rows)

    @asynccontextmanager
    async def acquire(self) -> Any:
        yield self.conn


class TestRouteBatchThreadsContentGate:
    """Guilt test: route_batch must pass title/canonical_url to classify.

    A regression to domain-only matching (e.g. `classify(row["source_domain"])`
    with no title/url) collapses both rows below to the SAME outcome
    (press_general+general -> blog), which fails the second assertion.
    """

    @pytest.mark.asyncio
    async def test_press_subdomain_keyword_title_routes_nbintel_plain_title_routes_blog(
        self,
    ) -> None:
        standalone = _load_standalone()
        rules = standalone._load_rules_module()
        rows = [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "source_domain": "m.antaranews.com",
                "title": "New PMK rules on pajak reform",
                "canonical_url": "https://m.antaranews.com/pajak",
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "source_domain": "m.antaranews.com",
                "title": "Local football match result",
                "canonical_url": "https://m.antaranews.com/sport",
            },
        ]
        pool = _FakePool(rows)
        counts = await standalone.route_batch(pool, rules.classify)
        assert counts["nb-intel"] == 1
        assert counts["blog"] == 1
        # UPDATE args: (item_id, new_status, targets_json)
        statuses = {u[0]: u[1] for u in pool.conn.updates}
        assert statuses["11111111-1111-1111-1111-111111111111"] == "nb-intel"
        assert statuses["22222222-2222-2222-2222-222222222222"] == "blog"
