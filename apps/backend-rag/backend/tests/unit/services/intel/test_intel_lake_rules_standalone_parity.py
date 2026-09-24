"""Parity between the backend classifier and the Pro-local standalone cron.

2026-09-23: both `intel_lake_router.py` (Fly, primary) and
`scripts/intel-lake-router-a2/intel-lake-router-cron-standalone.py` (Pro,
fallback) now import the SAME `intel_lake_rules.classify` instead of the
fallback keeping its own JSON copy of the rules (that copy drifted — see
PENDING-ARMS `intel-lake-pro-fallback-router-rules-drift`). These tests load
the standalone script by path (as the real cron does) and assert:

1. its loaded rules module classifies a real-world corpus identically to
   the backend `_classify`/`classify`, including a mixed-case/whitespace
   host and (via `IntelLakeRouter._classify`) the Fly router's own path.
2. `route_batch` actually threads `title`/`canonical_url` through to
   `classify` — a regression to domain-only matching changes the outcome
   for a press subdomain with a regulatory-keyword title — and its SELECT
   literally projects those two columns.
3. the loader picks a sibling `intel_lake_rules.py` over the repo-relative
   fallback when both exist (the Pro-deploy layout).
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


def _load_standalone(
    path: Path = _STANDALONE_PATH,
    module_name: str = "intel_lake_router_cron_standalone",
) -> Any:
    """Import the standalone script by path, exactly as launchd's cron does.

    asyncpg is imported at module top level; stub it if unavailable so this
    test does not require the Postgres driver to check pure classification
    logic (route_batch tests below supply a fake pool instead). `path` and
    `module_name` are overridable so TestSiblingLoaderPrecedence (below) can
    load a COPY of this script from a tmp_path layout without colliding with
    the real one in sys.modules.
    """
    if "asyncpg" not in sys.modules:
        try:
            import asyncpg  # noqa: F401
        except ImportError:
            sys.modules["asyncpg"] = types.ModuleType("asyncpg")
    spec = importlib.util.spec_from_file_location(module_name, path)
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
    # M4: mixed case + surrounding whitespace — classify() must
    # `.strip().lower()` before matching, or this falls through to
    # needs_review (no `_RULES` pattern is anchored on whitespace/uppercase).
    ("  PAJAK.go.ID  ", None, None, "nb-intel"),
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
        # M1 pin: a regression to `SELECT id, source_domain` (dropping the
        # content-gate columns) crashes every real tick with a KeyError on
        # row["title"] — but only once `route_batch` actually reads the row,
        # after this fetch() already returned. Assert on the query text
        # itself so that regression is caught here, at the SQL, not by
        # accident downstream.
        assert "title" in query, "route_batch's SELECT must project title"
        assert "canonical_url" in query, "route_batch's SELECT must project canonical_url"
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


class TestSiblingLoaderPrecedence:
    """M6 pin: the sibling candidate in `_RULES_MODULE_CANDIDATES` must win
    over the repo-relative fallback when BOTH exist.

    In the real repo checkout only the fallback candidate is ever populated
    (no sibling `intel_lake_rules.py` lives next to the script), so no
    existing test distinguishes "loader tries the sibling first" from
    "loader only knows the fallback path" — removing the sibling candidate
    entirely changes nothing THERE. This test builds a standalone
    Pro-deploy-like layout under `tmp_path`: a sibling copy AND a stale
    repo-path copy with different `classify()` stubs, and asserts the
    sibling one is the one actually loaded.
    """

    def test_sibling_wins_over_stale_repo_copy(self, tmp_path: Path) -> None:
        script_dir = tmp_path / "scripts" / "intel-lake-router-a2"
        script_dir.mkdir(parents=True)
        script_copy = script_dir / "intel-lake-router-cron-standalone.py"
        script_copy.write_text(_STANDALONE_PATH.read_text())

        (script_dir / "intel_lake_rules.py").write_text(
            "def classify(source_domain=None, title=None, canonical_url=None):\n"
            "    return {'status': 'SIBLING', 'targets': {}, 'rule': 'sibling_stub'}\n"
        )

        repo_rules_dir = (
            tmp_path / "apps" / "backend-rag" / "backend" / "services" / "intel"
        )
        repo_rules_dir.mkdir(parents=True)
        (repo_rules_dir / "intel_lake_rules.py").write_text(
            "def classify(source_domain=None, title=None, canonical_url=None):\n"
            "    return {'status': 'STALE_REPO', 'targets': {}, 'rule': 'stale_repo_stub'}\n"
        )

        standalone_copy = _load_standalone(
            script_copy, module_name="intel_lake_router_cron_standalone_tmp"
        )
        rules = standalone_copy._load_rules_module()
        assert rules.classify("anything")["status"] == "SIBLING"
