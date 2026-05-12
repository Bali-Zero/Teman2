"""Unit tests for IntelLakeRouter (Tier 1 rules engine)."""

from __future__ import annotations

from backend.services.intel.intel_lake_router import (
    NB_INTEL_AI_RESEARCH,
    NB_INTEL_IMMIGRATION,
    NB_INTEL_REGULATION,
    NB_INTEL_TAX,
    IntelLakeRouter,
)


def _make_router() -> IntelLakeRouter:
    return IntelLakeRouter(None)  # type: ignore[arg-type]


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
