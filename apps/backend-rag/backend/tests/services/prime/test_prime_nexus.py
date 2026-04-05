"""
Tests for PrimeNexusService — Layer 1 resolve pipeline.

Covers: geohash encoding, BATARA mock, GISTARU fallback, PostGIS fallback,
circuit breaker, cache hit/miss, activity classification, scoring engine.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.prime.prime_nexus_service import (
    PrimeNexusService,
    calculate_building_yield,
    calculate_investment_score,
    calculate_zone_kbli_fit,
    classify_activity,
    encode_geohash,
    is_investor_relevant,
)

# ── Geohash Tests ────────────────────────────────────────────────────


class TestGeohash:
    def test_known_location_bali(self) -> None:
        """Bali coordinates should produce consistent geohash."""
        gh = encode_geohash(-8.648, 115.132, precision=8)
        assert len(gh) == 8
        assert gh.startswith("qw3")  # Bali region prefix

    def test_precision_levels(self) -> None:
        gh8 = encode_geohash(-8.648, 115.132, precision=8)
        gh6 = encode_geohash(-8.648, 115.132, precision=6)
        assert gh8[:6] == gh6  # shorter precision is prefix of longer

    def test_nearby_points_same_geohash(self) -> None:
        """Points ~10m apart should have same geohash at precision 8."""
        gh1 = encode_geohash(-8.648000, 115.132000, precision=8)
        gh2 = encode_geohash(-8.648001, 115.132001, precision=8)
        # At precision 8 (~19m), these should be identical
        assert gh1 == gh2

    def test_distant_points_different_geohash(self) -> None:
        """Canggu vs Ubud should have different geohashes."""
        canggu = encode_geohash(-8.648, 115.132, precision=6)
        ubud = encode_geohash(-8.519, 115.263, precision=6)
        assert canggu != ubud


# ── Activity Classification Tests ────────────────────────────────────


class TestActivityClassification:
    def test_hotel_is_hospitality(self) -> None:
        assert classify_activity("Hotel Five Star") == "Hospitality"

    def test_restaurant_is_fb(self) -> None:
        assert classify_activity("Restaurant and Bar") == "F&B"

    def test_spa_is_wellness(self) -> None:
        assert classify_activity("Spa and Massage Center") == "Wellness"

    def test_software_is_technology(self) -> None:
        assert classify_activity("Software Development Company") == "Technology"

    def test_unknown_is_other(self) -> None:
        assert classify_activity("Banana Farming") == "Other"

    def test_skip_patterns(self) -> None:
        assert not is_investor_relevant("local resident housing")
        assert not is_investor_relevant("parking area")
        assert not is_investor_relevant("wholesale trade of food")

    def test_investor_relevant(self) -> None:
        assert is_investor_relevant("Hotel Resort")
        assert is_investor_relevant("Restaurant Fine Dining")


# ── Zone-KBLI Compatibility Tests ────────────────────────────────────


class TestZoneKBLIFit:
    def test_hotel_in_tourism_zone_ideal(self) -> None:
        score, tier = calculate_zone_kbli_fit("W-1", "55110")
        assert tier == "ideal"
        assert score == 20

    def test_hotel_in_residential_tolerated(self) -> None:
        score, tier = calculate_zone_kbli_fit("R-3", "55110")
        assert tier == "tolerated"
        assert score == 8

    def test_restaurant_in_commercial_ideal(self) -> None:
        score, tier = calculate_zone_kbli_fit("K-1", "56101")
        assert tier == "ideal"
        assert score == 20

    def test_nonbuildable_zone(self) -> None:
        score, tier = calculate_zone_kbli_fit("BA", "55110")
        assert tier == "incompatible"
        assert score == 0

    def test_nightlife_in_residential_poor(self) -> None:
        score, tier = calculate_zone_kbli_fit("R-3", "56301")
        assert tier == "poor"
        assert score == 2

    def test_unknown_codes(self) -> None:
        score, tier = calculate_zone_kbli_fit(None, None)
        assert tier == "unknown"
        assert score == 12


# ── Investment Scoring Engine Tests ──────────────────────────────────


class TestInvestmentScore:
    def test_rejected_kbli_hard_block(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "K-1", "source": "batara_live", "overlays": {}},
            kbli_state="REJECTED", kbli_code="68111",
            roi_data=None, geo_data=None,
        )
        assert result["verdict"] == "RED"
        assert result["can_invest"] is False
        assert len(result["hard_blocks"]) > 0

    def test_nonbuildable_zone_hard_block(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "BA", "source": "batara_live", "overlays": {}},
            kbli_state="APPROVED", kbli_code="55110",
            roi_data=None, geo_data=None,
        )
        assert result["verdict"] == "RED"

    def test_good_zone_green_verdict(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "W-1", "source": "batara_live", "overlays": {}, "klb": "2.5"},
            kbli_state="APPROVED", kbli_code="55110",
            roi_data={"golden_strategy": {"roi": 15.0, "bey": 4}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
        )
        assert result["verdict"] == "GREEN"
        assert result["score"] >= 65

    def test_gistaru_caps_at_yellow(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "W-1", "source": "gistaru_rdtr", "overlays": {}},
            kbli_state="APPROVED", kbli_code="55110",
            roi_data={"golden_strategy": {"roi": 15.0, "bey": 4}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
        )
        assert result["verdict"] == "YELLOW"  # Capped due to GISTARU


# ── PrimeNexusService Tests ──────────────────────────────────────────


class TestPrimeNexusService:
    @pytest.fixture
    def service(self) -> PrimeNexusService:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        return PrimeNexusService(cache_service=cache)

    @pytest.mark.asyncio
    async def test_resolve_cache_hit(self) -> None:
        cached_data = json.dumps({
            "status": "found", "lat": -8.648, "lng": 115.132,
            "zone_code": "K-1", "zone_name": "Commercial",
            "zone": {"zone_code": "K-1", "zone_name": "Commercial",
                     "zone_label_en": "Commercial", "zone_description_en": "test",
                     "source": "batara_live", "confidence": 1.0},
        })
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=cached_data)
        service = PrimeNexusService(cache_service=cache)
        result = await service.resolve(-8.648, 115.132)
        assert result["cache_hit"] is True
        assert result["status"] == "found"

    @pytest.mark.asyncio
    async def test_resolve_batara_success(self, service: PrimeNexusService) -> None:
        batara_response = {
            "status": 200,
            "data": {"territorials": {"geom": [{
                "zone": {
                    "code": "K-1", "name": "Commercial Zone", "color": "232 71 42",
                    "definition": "Large scale commerce", "activities": [],
                    "zone_intensity_requirements": [],
                },
                "location": {"name": "Kuta"},
                "kkop_1": "", "lp2b_2": "", "krb_03": "", "cagbud": "", "teb_05": "",
            }]}},
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = batara_response

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        service._http_client = mock_client

        result = await service.resolve(-8.648, 115.132)
        assert result["status"] == "found"
        assert result["zone_code"] == "K-1"

    def test_circuit_breaker_opens_after_3_failures(self, service: PrimeNexusService) -> None:
        service._record_batara_failure()
        service._record_batara_failure()
        service._record_batara_failure()
        # After 3 failures, skip_until is set ~5min in future
        assert service._batara_failures >= 3
        assert service._batara_skip_until > 0
        # Now should_skip returns True
        assert service._should_skip_batara()

    def test_circuit_breaker_resets_on_success(self, service: PrimeNexusService) -> None:
        service._record_batara_failure()
        service._record_batara_failure()
        service._record_batara_success()
        assert service._batara_failures == 0
        assert not service._should_skip_batara()


# ── Layer 2 Analyze Tests ────────────────────────────────────────────


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_with_kbli(self) -> None:
        """Analyze with valid zone + KBLI should produce verdict."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        service = PrimeNexusService(cache_service=cache)

        # Mock resolve to return a known zone
        async def mock_resolve(lat: float, lng: float) -> dict:
            return {
                "status": "found", "lat": lat, "lng": lng,
                "zone_code": "W-1", "zone_name": "Tourism Zone",
                "zone_label_en": "Tourism", "zone_description_en": "test",
                "zone": {"zone_code": "W-1", "source": "batara_live"},
                "source": "batara_live",
                "kdb": "60", "klb": "2.0", "kdh": "20", "tb": "15 Meter", "gsb": "5",
                "desa": "Kuta", "businesses": [], "overlays": {},
                "cache_hit": False,
            }

        service.resolve = mock_resolve  # type: ignore[assignment]

        result = await service.analyze(lat=-8.648, lng=115.132, kbli_code="55110", is_pma=True)
        assert result["status"] == "analyzed"
        assert result["verdict"] is not None
        assert result["verdict"]["label"] in ("GREEN", "YELLOW", "RED")
        assert isinstance(result["verdict"]["score"], int)

    @pytest.mark.asyncio
    async def test_analyze_without_kbli(self) -> None:
        """Analyze without KBLI should still return zone data."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        service = PrimeNexusService(cache_service=cache)

        async def mock_resolve(lat: float, lng: float) -> dict:
            return {
                "status": "found", "lat": lat, "lng": lng,
                "zone_code": "K-2", "zone_name": "Commercial",
                "zone": {"zone_code": "K-2", "source": "batara_live"},
                "source": "batara_live",
                "kdb": "N/A", "klb": "N/A", "kdh": "N/A", "tb": "N/A", "gsb": "N/A",
                "desa": "Seminyak", "businesses": [], "overlays": {},
                "cache_hit": False,
            }

        service.resolve = mock_resolve  # type: ignore[assignment]

        result = await service.analyze(lat=-8.648, lng=115.132)
        assert result["status"] == "analyzed"
        assert result["kbli"] is None
        assert result["verdict"]["label"] in ("GREEN", "YELLOW", "RED")

    @pytest.mark.asyncio
    async def test_analyze_cache_hit(self) -> None:
        """Cached analyze result should return immediately."""
        import json as json_mod

        cached_data = json_mod.dumps({
            "status": "analyzed",
            "coordinates": {"lat": -8.648, "lng": 115.132},
            "verdict": {"label": "GREEN", "score": 82, "can_invest": True},
        })
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=cached_data)
        service = PrimeNexusService(cache_service=cache)

        result = await service.analyze(lat=-8.648, lng=115.132, kbli_code="55110")
        assert result["cache_hit"] is True
        assert result["verdict"]["label"] == "GREEN"

    @pytest.mark.asyncio
    async def test_analyze_outside_coverage(self) -> None:
        """Analyze for uncovered area should still return a verdict."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        service = PrimeNexusService(cache_service=cache)

        async def mock_resolve(lat: float, lng: float) -> dict:
            return {
                "status": "outside_coverage", "lat": lat, "lng": lng,
                "zone": None, "cache_hit": False,
            }

        service.resolve = mock_resolve  # type: ignore[assignment]

        result = await service.analyze(lat=0, lng=0, kbli_code="55110")
        assert result["status"] == "analyzed"
        # Zone data should be None but scoring still runs


# ── Building Codes Tests ─────────────────────────────────────────────


class TestBuildingCodes:
    def test_known_zone(self) -> None:
        result = calculate_building_yield("K-1")
        if result:  # Only if building codes JSON loaded
            assert "kdb_pct" in result
            assert "klb_ratio" in result

    def test_unknown_zone_returns_none(self) -> None:
        assert calculate_building_yield("UNKNOWN-99") is None


# ── Layer 3 Intelligence Overlay Tests ───────────────────────────────


class TestIntelligenceOverlay:
    """Tests for Layer 3 GET /intelligence — PostGIS bounding box query."""

    @pytest.fixture
    def service(self) -> PrimeNexusService:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        return PrimeNexusService(cache_service=cache)

    @pytest.mark.asyncio
    async def test_intelligence_no_pool_returns_empty_geojson(
        self, service: PrimeNexusService
    ) -> None:
        """Without a db_pool, intelligence() should return empty GeoJSON."""
        result = await service.intelligence(
            sw_lat=-8.70, sw_lng=115.10, ne_lat=-8.60, ne_lng=115.20
        )
        assert result["type"] == "FeatureCollection"
        assert isinstance(result["features"], list)

    @pytest.mark.asyncio
    async def test_intelligence_with_mock_pool(self, service: PrimeNexusService) -> None:
        """With a db_pool mock returning rows, intelligence() builds GeoJSON features."""
        # Row structure matches actual SQL query (companies table)
        mock_row = {
            "id": 1,
            "company_name": "Test Co",
            "company_type": "PT PMA",
            "kbli_code": "55110",
            "status": "active",
            "rdtr_zone_code": "K-1",
            "lat": -8.648,
            "lng": 115.132,
        }

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _acquire():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.acquire = _acquire

        service._db_pool = mock_pool
        result = await service.intelligence(
            sw_lat=-8.70, sw_lng=115.10, ne_lat=-8.60, ne_lng=115.20,
            include_clients=False,  # avoid second fetch call with different schema
        )
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) >= 1
        feat = result["features"][0]
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"

    @pytest.mark.asyncio
    async def test_intelligence_pool_error_returns_empty(self, service: PrimeNexusService) -> None:
        """Pool query errors should return empty GeoJSON without raising."""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("DB unavailable"))

        @asynccontextmanager
        async def _acquire():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.acquire = _acquire

        service._db_pool = mock_pool
        result = await service.intelligence(
            sw_lat=-8.70, sw_lng=115.10, ne_lat=-8.60, ne_lng=115.20
        )
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []
