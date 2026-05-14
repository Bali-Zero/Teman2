"""Unit tests for IntelLakeRouter (Tier 1 rules engine)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from backend.services.intel.intel_lake_router import (
    NB_INTEL_AI_RESEARCH,
    NB_INTEL_IMMIGRATION,
    NB_INTEL_REGULATION,
    NB_INTEL_TAX,
    IntelLakeRouter,
)


def _make_router() -> IntelLakeRouter:
    return IntelLakeRouter(None)  # type: ignore[arg-type]


class _CapturingConn:
    """Fake asyncpg connection that records fetchval/execute call args."""

    def __init__(self) -> None:
        self.fetchval_calls: list[tuple[Any, ...]] = []
        self.execute_calls: list[tuple[Any, ...]] = []

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.fetchval_calls.append((query, *args))
        return "00000000-0000-0000-0000-000000000001"  # pretend a row was updated

    async def execute(self, query: str, *args: Any) -> None:
        self.execute_calls.append((query, *args))


class _CapturingPool:
    """Fake asyncpg pool yielding a single shared _CapturingConn."""

    def __init__(self) -> None:
        self.conn = _CapturingConn()

    @asynccontextmanager
    async def acquire(self) -> Any:
        yield self.conn


class TestClassifyImmigration:
    def test_imigrasi_govid(self) -> None:
        d = _make_router()._classify("imigrasi.go.id")
        assert d["status"] == "nb-intel"
        assert NB_INTEL_IMMIGRATION in d["targets"]["nb_uuids"]
        assert d["rule"] == "immigration_govid"

    def test_kanim_subdomain(self) -> None:
        d = _make_router()._classify("kanim.bali")
        assert d["status"] == "nb-intel"

    def test_kemenkumham(self) -> None:
        d = _make_router()._classify("kemenkumham.go.id")
        assert NB_INTEL_IMMIGRATION in d["targets"]["nb_uuids"]


class TestClassifyTax:
    def test_pajak_govid(self) -> None:
        d = _make_router()._classify("pajak.go.id")
        assert d["status"] == "nb-intel"
        assert NB_INTEL_TAX in d["targets"]["nb_uuids"]
        assert d["rule"] == "tax_govid"

    def test_ortax(self) -> None:
        d = _make_router()._classify("ortax.org")
        assert NB_INTEL_TAX in d["targets"]["nb_uuids"]

    def test_ddtcnews(self) -> None:
        d = _make_router()._classify("ddtcnews.co.id")
        assert NB_INTEL_TAX in d["targets"]["nb_uuids"]


class TestClassifyRegulation:
    def test_bkpm(self) -> None:
        d = _make_router()._classify("bkpm.go.id")
        assert NB_INTEL_REGULATION in d["targets"]["nb_uuids"]

    def test_oss(self) -> None:
        d = _make_router()._classify("oss.go.id")
        assert NB_INTEL_REGULATION in d["targets"]["nb_uuids"]

    def test_peraturan(self) -> None:
        d = _make_router()._classify("peraturan.go.id")
        assert NB_INTEL_REGULATION in d["targets"]["nb_uuids"]


class TestClassifyAIResearch:
    def test_arxiv(self) -> None:
        d = _make_router()._classify("arxiv.org")
        assert NB_INTEL_AI_RESEARCH in d["targets"]["nb_uuids"]

    def test_github(self) -> None:
        d = _make_router()._classify("github.com")
        assert NB_INTEL_AI_RESEARCH in d["targets"]["nb_uuids"]


class TestClassifyBlog:
    def test_detik(self) -> None:
        d = _make_router()._classify("detik.com")
        assert d["status"] == "blog"
        assert d["targets"] == {}

    def test_kompas(self) -> None:
        d = _make_router()._classify("kompas.com")
        assert d["status"] == "blog"


class TestClassifyArchive:
    def test_reddit(self) -> None:
        d = _make_router()._classify("reddit.com")
        assert d["status"] == "archive"

    def test_twitter(self) -> None:
        d = _make_router()._classify("twitter.com")
        assert d["status"] == "archive"

    def test_x_com(self) -> None:
        d = _make_router()._classify("x.com")
        assert d["status"] == "archive"

    def test_youtube(self) -> None:
        d = _make_router()._classify("youtube.com")
        assert d["status"] == "archive"


class TestClassifyFallback:
    def test_unknown_domain_goes_to_needs_review(self) -> None:
        d = _make_router()._classify("random.example.com")
        assert d["status"] == "needs_review"
        assert d["rule"] == "no_match"

    def test_empty_domain(self) -> None:
        d = _make_router()._classify("")
        assert d["status"] == "needs_review"

    def test_unknown_fallback_intel_radar(self) -> None:
        """intel_radar emits source_domain='unknown' when urlparse fails."""
        d = _make_router()._classify("unknown")
        assert d["status"] == "needs_review"


class TestRoutingTargetsShape:
    def test_nbintel_targets_has_nb_uuids_list(self) -> None:
        d = _make_router()._classify("pajak.go.id")
        assert "nb_uuids" in d["targets"]
        assert isinstance(d["targets"]["nb_uuids"], list)
        assert len(d["targets"]["nb_uuids"]) == 1

    def test_blog_targets_empty_dict(self) -> None:
        assert _make_router()._classify("detik.com")["targets"] == {}


class TestRulesOrdering:
    def test_jdih_kemenkumham_takes_immigration(self) -> None:
        d = _make_router()._classify("jdih.kemenkumham.go.id")
        assert d["rule"] == "immigration_govid"


class TestRegexAnchoring:
    def test_partial_match_in_middle_rejected(self) -> None:
        d = _make_router()._classify("fake.kompas.somewhere")
        assert d["status"] == "needs_review"

    def test_imigrasi_in_middle_rejected(self) -> None:
        d = _make_router()._classify("malicious.imigrasi.go.id")
        assert d["status"] == "needs_review"


class TestRulesNoOverlap:
    def test_pajak_does_not_match_immigration(self) -> None:
        d = _make_router()._classify("pajak.go.id")
        assert NB_INTEL_IMMIGRATION not in d["targets"]["nb_uuids"]

    def test_reddit_does_not_match_blog(self) -> None:
        d = _make_router()._classify("reddit.com")
        assert d["status"] != "blog"


class TestRoutingTargetsBindType:
    """Regression for 2026-05-14 — jsonb double-encoding.

    The asyncpg pool registers a jsonb codec with ``encoder=json.dumps``
    (see ``backend/app/core/database.py``). If ``route_event`` ALSO calls
    ``json.dumps`` on ``routing_targets`` before binding, the value is
    serialized twice and lands in PG as a jsonb *string* scalar (``"{}"``)
    instead of a jsonb *object* (``{}``). The Pro-local router + nb-pusher
    then see ``jsonb_typeof = 'string'`` and cannot read ``nb_uuids``.

    The fix: bind the raw dict and let the pool codec serialize it once.
    These tests assert the value reaching ``conn.fetchval`` is a ``dict``.
    """

    @staticmethod
    def _update_call(pool: _CapturingPool) -> tuple[Any, ...]:
        """Locate the captured UPDATE intel_items fetchval call.

        Anchors assertions to the routing UPDATE by SQL content rather than
        a fragile positional index.
        """
        for call in pool.conn.fetchval_calls:
            if "UPDATE intel_items" in call[0]:
                return call
        raise AssertionError("route_event did not issue an UPDATE intel_items")

    @pytest.mark.asyncio
    async def test_routing_targets_bound_as_dict_not_str_for_nbintel(self) -> None:
        pool = _CapturingPool()
        router = IntelLakeRouter(pool)  # type: ignore[arg-type]
        await router.route_event(
            {"item_id": "11111111-1111-1111-1111-111111111111",
             "source_domain": "imigrasi.go.id"}
        )
        # UPDATE args after query: item_id, new_status, routing_targets
        bound_targets = self._update_call(pool)[3]
        assert isinstance(bound_targets, dict), (
            f"routing_targets bound as {type(bound_targets).__name__}, "
            f"expected dict — json.dumps + pool codec = double-encoding"
        )
        assert bound_targets == {"nb_uuids": [NB_INTEL_IMMIGRATION]}

    @pytest.mark.asyncio
    async def test_routing_targets_bound_as_dict_not_str_for_fallback(self) -> None:
        pool = _CapturingPool()
        router = IntelLakeRouter(pool)  # type: ignore[arg-type]
        await router.route_event(
            {"item_id": "22222222-2222-2222-2222-222222222222",
             "source_domain": "regulatory-watcher"}
        )
        bound_targets = self._update_call(pool)[3]
        assert isinstance(bound_targets, dict), (
            f"empty routing_targets bound as {type(bound_targets).__name__}, "
            f"expected dict {{}} — would land in PG as jsonb string '\"{{}}\"'"
        )
        assert bound_targets == {}

    @pytest.mark.asyncio
    async def test_routing_status_still_bound_as_str(self) -> None:
        # Guard against over-correction: status IS a plain text column.
        pool = _CapturingPool()
        router = IntelLakeRouter(pool)  # type: ignore[arg-type]
        await router.route_event(
            {"item_id": "33333333-3333-3333-3333-333333333333",
             "source_domain": "detik.com"}
        )
        bound_status = self._update_call(pool)[2]
        assert bound_status == "blog"
        assert isinstance(bound_status, str)
