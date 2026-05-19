"""Unit tests for IntelLakeRouter (Tier 1 rules engine)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from backend.services.intel.intel_lake_router import (
    NB_INTEL_AI_RESEARCH,
    NB_INTEL_IMMIGRATION,
    NB_INTEL_PRESS,
    NB_INTEL_REGULATION,
    NB_INTEL_TAX,
    IntelLakeRouter,
    _press_content_gate,
    backfill_needs_review,
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


class _PaginatedBackfillConn:
    """Fake connection that fails if dry-run pagination re-reads a full batch."""

    def __init__(self) -> None:
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[Any, ...]] = []
        self._row_1 = {
            "id": "11111111-1111-1111-1111-111111111111",
            "source_domain": "money.kompas.com",
            "title": "New visa rules for investors",
            "canonical_url": "https://money.kompas.com/visa",
        }
        self._row_2 = {
            "id": "22222222-2222-2222-2222-222222222222",
            "source_domain": "unknown.example",
            "title": "Unknown source",
            "canonical_url": "https://unknown.example/story",
        }

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((query, args))
        if len(args) < 2:
            if len(self.fetch_calls) > 1:
                raise AssertionError("backfill_needs_review re-read the first dry-run batch")
            return [self._row_1]
        last_id = args[1]
        if last_id is None:
            return [self._row_1]
        if str(last_id) == self._row_1["id"]:
            return [self._row_2]
        return []

    async def execute(self, query: str, *args: Any) -> None:
        self.execute_calls.append((query, *args))


class _PaginatedBackfillPool:
    """Fake asyncpg pool for backfill pagination tests."""

    def __init__(self) -> None:
        self.conn = _PaginatedBackfillConn()

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
        # Press subdomain prefixes are tolerated only for exact approved roots
        # such as ``money.kompas.com``. A lookalike hostname must not match
        # merely because it contains ``kompas`` in the middle.
        d = _make_router()._classify("fake.kompas.somewhere")
        assert d["status"] == "needs_review"

    def test_imigrasi_in_middle_rejected(self) -> None:
        # Government domains remain strict; generic subdomain tolerance is only
        # for vetted press roots.
        d = _make_router()._classify("malicious.imigrasi.go.id")
        assert d["status"] == "needs_review"


# ─── PR-B1a: subdomain prefix tolerance ─────────────────────────────────────


class TestSubdomainPrefixTolerance:
    """PR-B1a 2026-05-20 — root cause of 79/88 items in needs_review.

    The old regex ``^kompas`` did not match real-world subdomains like
    ``money.kompas.com`` or ``en.tempo.co``. Verified empirically Phase A.6.
    """

    def test_www_prefix(self) -> None:
        d = _make_router()._classify("www.antaranews.com")
        # Generic news → press_general → blog (no regulatory keyword)
        assert d["status"] == "blog"

    def test_en_subdomain_tempo(self) -> None:
        d = _make_router()._classify("en.tempo.co")
        assert d["status"] == "blog"

    def test_money_subdomain_kompas(self) -> None:
        d = _make_router()._classify("money.kompas.com")
        assert d["status"] == "blog"

    def test_sumsel_subdomain_antaranews(self) -> None:
        d = _make_router()._classify("sumsel.antaranews.com")
        assert d["status"] == "blog"


class TestNewPressDomains:
    """PR-B1a 2026-05-20 — expanded news domain set."""

    def test_indonesiaexpat(self) -> None:
        d = _make_router()._classify("indonesiaexpat.id")
        assert d["status"] == "blog"

    def test_letsmoveindonesia(self) -> None:
        d = _make_router()._classify("www.letsmoveindonesia.com")
        assert d["status"] == "blog"

    def test_expat_com(self) -> None:
        d = _make_router()._classify("www.expat.com")
        assert d["status"] == "blog"

    def test_livenworkindonesia(self) -> None:
        d = _make_router()._classify("livenworkindonesia.com")
        assert d["status"] == "blog"


class TestPressContentGate:
    """PR-B1a 2026-05-20 — 2-stage routing for press_general rule.

    Stage 1: domain eligibility (matches press_general regex).
    Stage 2: title/url contains regulatory keyword → upgrade to nb-intel/press.
    Empty stage-2 input → fallback to blog (legacy behavior).
    """

    def test_gate_blocks_when_no_content(self) -> None:
        assert _press_content_gate(None, None) is False
        assert _press_content_gate("", "") is False

    def test_gate_matches_visa_keyword(self) -> None:
        assert _press_content_gate("New visa rules for foreigners", None) is True

    def test_gate_matches_kitas_keyword(self) -> None:
        assert _press_content_gate(None, "https://x.com/kitas-news") is True

    def test_gate_matches_pajak_keyword(self) -> None:
        assert _press_content_gate("Aturan pajak baru 2026", None) is True

    def test_gate_matches_oss_keyword(self) -> None:
        assert _press_content_gate("OSS BKPM streamlines KBLI", None) is True

    def test_gate_blocks_sports_content(self) -> None:
        assert _press_content_gate("Liga 1 hasil pertandingan", None) is False

    def test_gate_blocks_entertainment(self) -> None:
        assert _press_content_gate("Selebriti memilih liburan ke Bali", None) is False

    def test_gate_blocks_tax_substring_false_positive(self) -> None:
        assert _press_content_gate("Best taxi apps for Bali airport", None) is False

    def test_classify_with_regulatory_keyword_upgrades_to_nbintel(self) -> None:
        d = _make_router()._classify(
            "money.kompas.com",
            title="New PMK rules on PPh imported services",
            canonical_url="https://money.kompas.com/2026/pajak",
        )
        assert d["status"] == "nb-intel"
        assert NB_INTEL_PRESS in d["targets"]["nb_uuids"]
        assert "regulatory" in d["rule"]

    def test_classify_without_keyword_stays_blog(self) -> None:
        d = _make_router()._classify(
            "en.tempo.co",
            title="Indonesian musician wins international award",
            canonical_url="https://en.tempo.co/entertainment",
        )
        assert d["status"] == "blog"
        assert d["targets"] == {}

    def test_classify_without_content_defaults_to_blog(self) -> None:
        """Legacy compat: no title/url means content gate returns False,
        which means press_general → blog (existing behavior preserved)."""
        d = _make_router()._classify("kompas.com")
        assert d["status"] == "blog"


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
            {"item_id": "11111111-1111-1111-1111-111111111111", "source_domain": "imigrasi.go.id"}
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
            {
                "item_id": "22222222-2222-2222-2222-222222222222",
                "source_domain": "regulatory-watcher",
            }
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
            {"item_id": "33333333-3333-3333-3333-333333333333", "source_domain": "detik.com"}
        )
        bound_status = self._update_call(pool)[2]
        assert bound_status == "blog"
        assert isinstance(bound_status, str)


class TestBackfillNeedsReview:
    @pytest.mark.asyncio
    async def test_dry_run_paginates_full_batches_without_repeating_rows(self) -> None:
        pool = _PaginatedBackfillPool()

        counts = await backfill_needs_review(pool, batch_size=1, dry_run=True)  # type: ignore[arg-type]

        assert counts["selected"] == 2
        assert counts["reclassified"] == 1
        assert counts["nb-intel"] == 1
        assert counts["needs_review"] == 1
        assert counts["skipped"] == 1
        assert pool.conn.execute_calls == []
        assert len(pool.conn.fetch_calls) == 3
