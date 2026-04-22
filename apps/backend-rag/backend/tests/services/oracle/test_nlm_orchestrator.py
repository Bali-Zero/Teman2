"""Tests for NLM Orchestrator — unified NLM routing.

# Organo: backend-rag/oracle → produce NLMResult → consuma da orchestrator_core
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.oracle.nlm_orchestrator import (
    DOMAIN_NOTEBOOK_MAP_V2,
    NLMOrchestrator,
    NLMResult,
)


class TestNLMOrchestrator:
    """NLM Orchestrator routes to correct notebooks, handles failures."""

    def setup_method(self) -> None:
        self.mock_enrichment = AsyncMock()
        self.mock_cache = AsyncMock()
        self.mock_redis = AsyncMock()
        self.orch = NLMOrchestrator(
            enrichment_service=self.mock_enrichment,
            cache_service=self.mock_cache,
            redis_client=self.mock_redis,
        )

    # ── Single notebook queries ──

    @pytest.mark.asyncio
    async def test_visa_query_routes_to_nb2(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = {
            "answer": "KITAS requires RPTKA",
            "citations": [{"source": "nb-2"}],
        }

        result = await self.orch.query("What is KITAS?", domain="visa")

        assert result is not None
        assert result.answer == "KITAS requires RPTKA"
        assert result.domain == "visa"
        expected_nb = DOMAIN_NOTEBOOK_MAP_V2["visa"][0]
        self.mock_enrichment.query.assert_called_once_with(
            expected_nb, "What is KITAS?", timeout=10.0
        )

    @pytest.mark.asyncio
    async def test_tax_query_routes_to_nb4(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = {
            "answer": "PPh 21 is employee income tax",
            "citations": [],
        }

        result = await self.orch.query("What is PPh 21?", domain="tax")

        assert result is not None
        expected_nb = DOMAIN_NOTEBOOK_MAP_V2["tax"][0]
        self.mock_enrichment.query.assert_called_once_with(
            expected_nb, "What is PPh 21?", timeout=10.0
        )

    # ── Cache behavior ──

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self) -> None:
        self.mock_redis.get.return_value = None
        self.mock_cache.get.return_value = {
            "answer": "Cached KITAS answer",
            "citations": [],
        }

        result = await self.orch.query("KITAS?", domain="visa")

        assert result is not None
        assert result.cached is True
        assert result.answer == "Cached KITAS answer"
        self.mock_enrichment.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_result_cached_after_query(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = {
            "answer": "Fresh answer",
            "citations": [],
        }

        await self.orch.query("test?", domain="visa")

        self.mock_cache.set.assert_called_once()

    # ── Rate limiting ──

    @pytest.mark.asyncio
    async def test_rate_limit_reached_returns_none(self) -> None:
        self.mock_redis.get.return_value = b"10"  # at limit

        result = await self.orch.query("test?", domain="visa")

        assert result is None
        self.mock_enrichment.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_counter_incremented(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = b"5"  # under limit
        self.mock_enrichment.query.return_value = {"answer": "ok", "citations": []}

        await self.orch.query("test?", domain="visa")

        self.mock_redis.incr.assert_called_once()

    # ── Graceful degradation ──

    @pytest.mark.asyncio
    async def test_enrichment_unavailable_returns_none(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = None

        result = await self.orch.query("test?", domain="visa")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_enrichment_service_returns_none(self) -> None:
        orch = NLMOrchestrator()
        result = await orch.query("test?", domain="visa")
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_domain_returns_none(self) -> None:
        self.mock_redis.get.return_value = None
        result = await self.orch.query("test?", domain="unknown_domain")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_failure_still_works(self) -> None:
        """Redis failure → fail-open, proceed with query."""
        self.mock_cache.get.return_value = None
        self.mock_redis.get.side_effect = Exception("Redis down")
        self.mock_enrichment.query.return_value = {"answer": "ok", "citations": []}

        result = await self.orch.query("test?", domain="visa")

        assert result is not None
        assert result.answer == "ok"

    # ── Domain coverage ──

    def test_expanded_domain_coverage(self) -> None:
        """Verify 7+ domains are mapped."""
        assert len(DOMAIN_NOTEBOOK_MAP_V2) >= 7
        for domain in ["visa", "immigration", "tax", "legal", "company", "kbli", "property"]:
            assert domain in DOMAIN_NOTEBOOK_MAP_V2, f"Missing domain: {domain}"

    # ── NLMResult dataclass ──

    def test_nlm_result_defaults(self) -> None:
        result = NLMResult()
        assert result.answer == ""
        assert result.citations == []
        assert result.cached is False
        assert result.synthesis == ""


# ── Sprint 1a golden tests: extended routing via NLM_EXTENDED_ROUTING ────────

# The 5 notebooks that were orphaned on the backend side before Sprint 1a.
NB_5_PROPERTY = "d9438180-5e63-4e2a-a473-6061101f6a8d"
NB_6_OPERATIONS = "85207af3-352f-4554-8d2a-18f42cc541ba"
NB_7_EDITORIAL = "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8"
NB_8_LIFESTYLE = "4fd8cd0f-93f1-4e43-9c9e-86c0d581852c"
NB_10_TEAM = "f0307c2c-9220-4160-93c8-f4a6ef4a3b65"
# And the legacy-fallback used before the fix.
NB_3_COMPANY = "933509f9-1561-403d-bd44-4a7a67a36df2"


class TestExtendedRoutingFlag:
    """Feature flag NLM_EXTENDED_ROUTING drives which map is live.

    Shadow mode (flag off) = base map used for answers, extended map
    only logged. Flag on = extended map used for answers.
    """

    def _make_orch(self) -> NLMOrchestrator:
        return NLMOrchestrator(
            enrichment_service=AsyncMock(),
            cache_service=AsyncMock(),
            redis_client=AsyncMock(),
        )

    # ── Flag OFF: base map is live (backwards-compatible) ──

    def test_flag_off_property_routes_to_nb3_legacy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NLM_EXTENDED_ROUTING", raising=False)
        orch = self._make_orch()
        nbs = orch._resolve_notebooks("property", is_cross_domain=False)
        assert nbs == [NB_3_COMPANY], (
            "Flag off must preserve historical property → NB-3 fallback"
        )

    def test_flag_off_new_domains_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NLM_EXTENDED_ROUTING", raising=False)
        orch = self._make_orch()
        for domain in ("operations", "editorial", "lifestyle", "team"):
            nbs = orch._resolve_notebooks(domain, is_cross_domain=False)
            assert nbs == [], f"Flag off must not expose {domain} yet"

    def test_flag_off_emits_shadow_log_for_property(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.delenv("NLM_EXTENDED_ROUTING", raising=False)
        orch = self._make_orch()
        with caplog.at_level("INFO", logger="backend.services.oracle.nlm_orchestrator"):
            orch._resolve_notebooks("property", is_cross_domain=False)
        assert any(
            "shadow" in rec.message and "property" in rec.message and NB_5_PROPERTY in rec.message
            for rec in caplog.records
        ), "Shadow-mode log must surface the extended choice for property"

    def test_flag_off_existing_domains_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """visa/immigration/tax/company/kbli/legal behavior never regresses."""
        monkeypatch.delenv("NLM_EXTENDED_ROUTING", raising=False)
        orch = self._make_orch()
        assert orch._resolve_notebooks("visa", is_cross_domain=False) == [
            "cff93ab0-813a-42f2-a8de-36987e724271"
        ]
        assert orch._resolve_notebooks("tax", is_cross_domain=False) == [
            "d4b2eedb-9863-4a1a-81ff-a11b0b45d853"
        ]
        assert orch._resolve_notebooks("company", is_cross_domain=False) == [NB_3_COMPANY]

    # ── Flag ON: extended map is live ──

    def test_flag_on_property_routes_to_nb5(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NLM_EXTENDED_ROUTING", "1")
        orch = self._make_orch()
        assert orch._resolve_notebooks("property", is_cross_domain=False) == [NB_5_PROPERTY]

    def test_flag_on_exposes_five_new_domains(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NLM_EXTENDED_ROUTING", "true")
        orch = self._make_orch()
        expected = {
            "operations": NB_6_OPERATIONS,
            "editorial": NB_7_EDITORIAL,
            "lifestyle": NB_8_LIFESTYLE,
            "team": NB_10_TEAM,
            "real_estate": NB_5_PROPERTY,
            "zoning": NB_5_PROPERTY,
            "compliance": NB_6_OPERATIONS,
            "content": NB_7_EDITORIAL,
            "expat": NB_8_LIFESTYLE,
            "healthcare": NB_8_LIFESTYLE,
            "hr": NB_10_TEAM,
            "payroll": NB_10_TEAM,
        }
        for domain, uuid in expected.items():
            nbs = orch._resolve_notebooks(domain, is_cross_domain=False)
            assert nbs == [uuid], f"{domain} should route to {uuid[:8]}…, got {nbs}"

    def test_flag_on_existing_domains_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Flag on must preserve visa/immigration/tax/kbli."""
        monkeypatch.setenv("NLM_EXTENDED_ROUTING", "yes")
        orch = self._make_orch()
        assert orch._resolve_notebooks("visa", is_cross_domain=False) == [
            "cff93ab0-813a-42f2-a8de-36987e724271"
        ]
        assert orch._resolve_notebooks("tax", is_cross_domain=False) == [
            "d4b2eedb-9863-4a1a-81ff-a11b0b45d853"
        ]
        assert orch._resolve_notebooks("company", is_cross_domain=False) == [NB_3_COMPANY]

    def test_flag_on_cross_domain_extended_pair(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """property+tax cross pair is only honoured when flag on."""
        monkeypatch.setenv("NLM_EXTENDED_ROUTING", "1")
        orch = self._make_orch()
        # Need a non-None correlator for the cross branch.
        orch._correlator = AsyncMock()
        nbs = orch._resolve_notebooks("property+tax", is_cross_domain=True)
        assert nbs == [NB_5_PROPERTY, "d4b2eedb-9863-4a1a-81ff-a11b0b45d853"]

    def test_flag_off_cross_domain_extended_pair_skipped(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """property+tax must NOT fan out when flag is off, but must be logged."""
        monkeypatch.delenv("NLM_EXTENDED_ROUTING", raising=False)
        orch = self._make_orch()
        orch._correlator = AsyncMock()
        with caplog.at_level("INFO", logger="backend.services.oracle.nlm_orchestrator"):
            nbs = orch._resolve_notebooks("property+tax", is_cross_domain=True)
        # Flag off -> base map has no "property+tax" key, returns []
        assert nbs == []
        assert any(
            "property+tax" in rec.message and "extended only" in rec.message
            for rec in caplog.records
        )

    # ── Boolean parser robustness ──

    @pytest.mark.parametrize(
        "value,expected_nb",
        [
            ("1", NB_5_PROPERTY),
            ("true", NB_5_PROPERTY),
            ("True", NB_5_PROPERTY),
            ("yes", NB_5_PROPERTY),
            ("ON", NB_5_PROPERTY),
            ("0", NB_3_COMPANY),
            ("false", NB_3_COMPANY),
            ("", NB_3_COMPANY),
            ("garbage", NB_3_COMPANY),
        ],
    )
    def test_flag_parser_tolerates_various_truthy_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
        expected_nb: str,
    ) -> None:
        monkeypatch.setenv("NLM_EXTENDED_ROUTING", value)
        orch = self._make_orch()
        assert orch._resolve_notebooks("property", is_cross_domain=False) == [expected_nb]


class TestSefirotIntegration:
    """Sefirot cascade integration into nlm_orchestrator._resolve_notebooks.

    Flag SEFIROT_ROUTING gates the behaviour:

    - off (default): keyword logic runs as before, sefirot_router emits shadow log
    - on: when a query matches a curated path, cascade wins over keyword logic
    """

    def _make_orch(self) -> NLMOrchestrator:
        return NLMOrchestrator(
            enrichment_service=AsyncMock(),
            cache_service=AsyncMock(),
            redis_client=AsyncMock(),
        )

    def test_sefirot_off_falls_back_to_keyword_logic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With sefirot OFF, even a query that would match keeps keyword routing."""
        monkeypatch.delenv("SEFIROT_ROUTING", raising=False)
        monkeypatch.setenv("NLM_EXTENDED_ROUTING", "1")
        orch = self._make_orch()
        # PT PMA query would match sefirot; but flag off → use keyword on domain=company
        nbs = orch._resolve_notebooks(
            "company",
            is_cross_domain=False,
            question="I want to open a PT PMA",
        )
        assert nbs == [NB_3_COMPANY]

    def test_sefirot_on_pt_pma_query_returns_cascade(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With sefirot ON, PT PMA query returns the 5-NB cascade."""
        monkeypatch.setenv("SEFIROT_ROUTING", "1")
        monkeypatch.setenv("NLM_EXTENDED_ROUTING", "1")
        orch = self._make_orch()
        nbs = orch._resolve_notebooks(
            "company",
            is_cross_domain=False,
            question="Open a PT PMA with team in Bali",
        )
        # pt_pma_complete_flow: nb3, nb2, nb6, nb10, nb4 in weight order
        assert nbs[0] == NB_3_COMPANY  # primary
        assert len(nbs) == 5  # cascade has 5 NBs

    def test_sefirot_on_no_match_falls_back_to_keyword(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With sefirot ON but no path match, keyword logic still runs."""
        monkeypatch.setenv("SEFIROT_ROUTING", "1")
        monkeypatch.delenv("NLM_EXTENDED_ROUTING", raising=False)
        orch = self._make_orch()
        nbs = orch._resolve_notebooks(
            "visa",
            is_cross_domain=False,
            question="nothing special in this query",
        )
        # base keyword routing for visa → NB-2
        assert nbs == ["cff93ab0-813a-42f2-a8de-36987e724271"]

    def test_sefirot_on_empty_question_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With sefirot ON but empty question, skip sefirot layer entirely."""
        monkeypatch.setenv("SEFIROT_ROUTING", "1")
        orch = self._make_orch()
        # question="" → sefirot is skipped; keyword routes normally
        nbs = orch._resolve_notebooks(
            "visa",
            is_cross_domain=False,
            question="",
        )
        assert nbs == ["cff93ab0-813a-42f2-a8de-36987e724271"]

    def test_sefirot_off_emits_shadow_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Shadow mode: flag off + matching query still emits sefirot shadow log line."""
        monkeypatch.delenv("SEFIROT_ROUTING", raising=False)
        orch = self._make_orch()
        with caplog.at_level("INFO", logger="backend.services.oracle.sefirot_router"):
            orch._resolve_notebooks(
                "company",
                is_cross_domain=False,
                question="Open a PT PMA",
            )
        assert any(
            "sefirot shadow" in rec.message for rec in caplog.records
        ), "Expected sefirot shadow log line when flag off but path matches"

    def test_sefirot_on_emits_active_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Active mode: flag on + matching query emits 'sefirot active' INFO line."""
        monkeypatch.setenv("SEFIROT_ROUTING", "1")
        orch = self._make_orch()
        with caplog.at_level("INFO", logger="backend.services.oracle.nlm_orchestrator"):
            orch._resolve_notebooks(
                "company",
                is_cross_domain=False,
                question="Open a PT PMA",
            )
        assert any(
            "sefirot active" in rec.message for rec in caplog.records
        ), "Expected 'sefirot active' log when flag on + path match"

    def test_question_param_backwards_compatible_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pre-existing callers without `question` kwarg still work."""
        monkeypatch.delenv("SEFIROT_ROUTING", raising=False)
        orch = self._make_orch()
        # Legacy call signature (no question kwarg)
        nbs = orch._resolve_notebooks("visa", is_cross_domain=False)
        assert nbs == ["cff93ab0-813a-42f2-a8de-36987e724271"]
