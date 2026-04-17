"""
Unit tests for backend/services/prime/prime_nexus_service.py

Covers:
- encode_geohash()
- parse_tb_to_meters()
- calculate_building_yield()
- classify_activity()
- is_investor_relevant()
- rgb_string_to_hex()
- calculate_zone_kbli_fit()
- calculate_investment_score()
- PrimeNexusService (circuit breaker, resolve pipeline, analyze, etc.)
"""

import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.prime.prime_nexus_service import (
    RESTRICTED_ZONES,
    ZONE_COLORS_MAP,
    ZONE_LABELS,
    PrimeNexusService,
    calculate_building_yield,
    calculate_investment_score,
    calculate_zone_kbli_fit,
    classify_activity,
    encode_geohash,
    is_investor_relevant,
    parse_tb_to_meters,
    rgb_string_to_hex,
)

logger = logging.getLogger(__name__)


# ============================================================================
# encode_geohash
# ============================================================================
class TestEncodeGeohash:
    """Tests for the geohash encoding function."""

    def test_known_location_bali(self) -> None:
        """Encode a known Bali coordinate and verify length."""
        gh = encode_geohash(-8.65, 115.22, precision=8)
        assert isinstance(gh, str)
        assert len(gh) == 8

    def test_precision_controls_length(self) -> None:
        """Precision parameter must control output length."""
        for prec in (4, 6, 8, 12):
            gh = encode_geohash(0.0, 0.0, precision=prec)
            assert len(gh) == prec

    def test_deterministic(self) -> None:
        """Same input must produce same hash."""
        a = encode_geohash(-8.65, 115.22, precision=8)
        b = encode_geohash(-8.65, 115.22, precision=8)
        assert a == b

    def test_different_coords_different_hash(self) -> None:
        """Different coordinates must produce different hashes."""
        a = encode_geohash(-8.65, 115.22, precision=8)
        b = encode_geohash(40.71, -74.00, precision=8)
        assert a != b

    def test_zero_coords(self) -> None:
        """Equator-meridian crossing must produce valid hash."""
        gh = encode_geohash(0.0, 0.0, precision=6)
        assert len(gh) == 6
        assert all(c in "0123456789bcdefghjkmnpqrstuvwxyz" for c in gh)


# ============================================================================
# parse_tb_to_meters
# ============================================================================
class TestParseTbToMeters:
    """Tests for TB height string parsing."""

    def test_standard_format(self) -> None:
        assert parse_tb_to_meters("15 Meter") == 15.0

    def test_short_format(self) -> None:
        assert parse_tb_to_meters("8m") == 8.0

    def test_decimal_comma(self) -> None:
        assert parse_tb_to_meters("4,5 Meter") == 4.5

    def test_na_returns_none(self) -> None:
        assert parse_tb_to_meters("N/A") is None

    def test_none_returns_none(self) -> None:
        assert parse_tb_to_meters(None) is None

    def test_empty_returns_none(self) -> None:
        assert parse_tb_to_meters("") is None

    def test_no_digits_returns_none(self) -> None:
        assert parse_tb_to_meters("abc") is None


# ============================================================================
# calculate_building_yield
# ============================================================================
class TestCalculateBuildingYield:
    """Tests for building yield calculation."""

    def test_unknown_zone_returns_none(self) -> None:
        assert calculate_building_yield("ZZZZZZ") is None

    @patch("backend.services.prime.geo_service._BUILDING_CODES", {
        "K-1": {
            "name": "Kawasan Komersial 1",
            "KDB": "70",
            "KLB": "3.0",
            "KDH": "20",
            "KTB": "50",
            "TB": "15 Meter",
            "GSB": "5 Meter",
            "note": "test note",
        },
    })
    def test_valid_zone_returns_dict(self) -> None:
        result = calculate_building_yield("K-1")
        assert result is not None
        assert result["zone_name_id"] == "Kawasan Komersial 1"
        assert result["kdb_pct"] == 70.0
        assert result["klb_ratio"] == 3.0
        assert result["max_height_meters"] == 15.0
        assert result["notes"] == "test note"

    @patch("backend.services.prime.geo_service._BUILDING_CODES", {
        "BAD": {"name": "Bad", "KDB": "not_a_number"},
    })
    def test_parse_error_returns_none(self) -> None:
        result = calculate_building_yield("BAD")
        assert result is None


# ============================================================================
# classify_activity / is_investor_relevant
# ============================================================================
class TestClassifyActivity:
    """Tests for activity classification."""

    def test_hotel_is_hospitality(self) -> None:
        assert classify_activity("Small Hotel Near Beach") == "Hospitality"

    def test_restaurant_is_fnb(self) -> None:
        assert classify_activity("Restaurant and Café") == "F&B"

    def test_spa_is_wellness(self) -> None:
        assert classify_activity("Spa Treatment Center") == "Wellness"

    def test_software_is_technology(self) -> None:
        assert classify_activity("Software Development") == "Technology"

    def test_unknown_is_other(self) -> None:
        assert classify_activity("xyzzy nonsense") == "Other"

    def test_boutique_is_retail(self) -> None:
        assert classify_activity("Boutique Fashion Store") == "Retail"

    def test_consulting_is_services(self) -> None:
        assert classify_activity("Consulting Firm") == "Services"


class TestIsInvestorRelevant:
    """Tests for investor relevance filter."""

    def test_hotel_is_relevant(self) -> None:
        assert is_investor_relevant("International Hotel") is True

    def test_local_resident_is_not_relevant(self) -> None:
        assert is_investor_relevant("Local Resident Housing") is False

    def test_septic_tank_is_not_relevant(self) -> None:
        assert is_investor_relevant("Septic Tank Installation") is False

    def test_wholesale_filtered(self) -> None:
        assert is_investor_relevant("Wholesale trade of fishery") is False

    def test_road_network_not_relevant(self) -> None:
        assert is_investor_relevant("Road Network Planning") is False


# ============================================================================
# rgb_string_to_hex
# ============================================================================
class TestRgbStringToHex:
    """Tests for RGB string conversion."""

    def test_standard_rgb(self) -> None:
        assert rgb_string_to_hex("250 211 140") == "#fad38c"

    def test_zeros(self) -> None:
        assert rgb_string_to_hex("0 0 0") == "#000000"

    def test_max(self) -> None:
        assert rgb_string_to_hex("255 255 255") == "#ffffff"

    def test_comma_separated(self) -> None:
        assert rgb_string_to_hex("255,0,0") == "#ff0000"

    def test_invalid_returns_fallback(self) -> None:
        assert rgb_string_to_hex("invalid") == "#6B7280"

    def test_empty_returns_fallback(self) -> None:
        assert rgb_string_to_hex("") == "#6B7280"


# ============================================================================
# calculate_zone_kbli_fit
# ============================================================================
class TestCalculateZoneKbliFit:
    """Tests for zone-KBLI compatibility scoring."""

    def test_none_inputs(self) -> None:
        score, tier = calculate_zone_kbli_fit(None, None)
        assert score == 12
        assert tier == "unknown"

    def test_non_buildable_zone(self) -> None:
        score, tier = calculate_zone_kbli_fit("BA", "56101")
        assert score == 0
        assert tier == "incompatible"

    def test_nightlife_in_ideal_zone(self) -> None:
        score, tier = calculate_zone_kbli_fit("K-1", "56301")
        assert score == 20
        assert tier == "ideal"

    def test_nightlife_in_residential(self) -> None:
        score, tier = calculate_zone_kbli_fit("R-2", "56301")
        assert score == 2
        assert tier == "poor"

    def test_nightlife_in_other_zone(self) -> None:
        score, tier = calculate_zone_kbli_fit("KPI", "56301")
        assert score == 8
        assert tier == "tolerated"

    def test_hotel_in_tourism_zone(self) -> None:
        """KBLI 55 (accommodation) in W- zone should be ideal."""
        score, tier = calculate_zone_kbli_fit("W-1", "55101")
        assert score == 20
        assert tier == "ideal"

    def test_hotel_in_residential(self) -> None:
        """KBLI 55 in R- zone should be tolerated."""
        score, tier = calculate_zone_kbli_fit("R-3", "55101")
        assert score == 8
        assert tier == "tolerated"

    def test_unmatched_prefix_is_poor(self) -> None:
        """Unknown KBLI prefix in an unknown zone should be poor."""
        score, tier = calculate_zone_kbli_fit("KPI", "99999")
        assert score == 4
        assert tier == "poor"


# ============================================================================
# calculate_investment_score
# ============================================================================
class TestCalculateInvestmentScore:
    """Tests for the 3-layer investment scoring engine."""

    def test_kbli_rejected_hard_block(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}},
            kbli_state="REJECTED",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        assert result["verdict"] == "RED"
        assert result["can_invest"] is False
        assert result["score"] == 0
        assert len(result["hard_blocks"]) > 0

    def test_non_buildable_zone_hard_block(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "BA", "overlays": {}},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        assert result["verdict"] == "RED"
        assert result["can_invest"] is False

    def test_lp2b_hard_block(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {"LP2B_2": True}},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        assert result["verdict"] == "RED"
        assert any("LP2B" in b for b in result["hard_blocks"])

    def test_approved_kbli_with_good_data_green(self) -> None:
        """With high ROI, good zone fit, approved KBLI → GREEN."""
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "klb": "2.5", "source": "batara_live"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data={"golden_strategy": {"roi": 15.0, "bey": 4.0}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
        )
        assert result["verdict"] == "GREEN"
        assert result["can_invest"] is True
        assert result["score"] >= 65

    def test_missing_data_excludes_from_calc(self) -> None:
        """When ROI/KLB data missing, modifiers should note exclusion."""
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "source": "batara_live"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        assert any("Esclusi" in m for m in result["modifiers"])

    def test_overlay_penalty_reduces_score(self) -> None:
        result = calculate_investment_score(
            zone_data={
                "code": "K-1",
                "overlays": {"KKOP_1": True, "SEMPDN": True},
                "klb": "2.0",
                "source": "batara_live",
            },
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data={"golden_strategy": {"roi": 12.0, "bey": 5.0}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
        )
        assert any("KKOP" in m or "Sempadan" in m for m in result["modifiers"])

    def test_unavailable_source_hard_block(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "source": "unavailable"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        assert result["verdict"] == "RED"

    def test_very_low_klb_hard_block(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "klb": "0.02"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        assert result["verdict"] == "RED"
        assert any("KLB" in b for b in result["hard_blocks"])

    def test_gistaru_cap_limits_to_yellow(self) -> None:
        """GISTARU-sourced data should cap verdict to YELLOW even if score >= 65."""
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "klb": "2.5", "source": "gistaru_rdtr"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data={"golden_strategy": {"roi": 15.0, "bey": 4.0}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
        )
        assert result["verdict"] == "YELLOW"

    def test_sea_view_bonus(self) -> None:
        result_no_sea = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "klb": "2.5", "source": "batara_live"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data={"golden_strategy": {"roi": 15.0, "bey": 4.0}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70, "sea_view": False},
        )
        result_sea = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "klb": "2.5", "source": "batara_live"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data={"golden_strategy": {"roi": 15.0, "bey": 4.0}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70, "sea_view": True},
        )
        assert result_sea["score"] >= result_no_sea["score"]


# ============================================================================
# PrimeNexusService
# ============================================================================
class TestPrimeNexusService:
    """Tests for the PrimeNexusService class."""

    def test_init_defaults(self) -> None:
        svc = PrimeNexusService()
        assert svc._cache is None
        assert svc._db_pool is None
        assert svc._batara_failures == 0
        assert svc._gistaru_failures == 0

    # ── Circuit Breaker ─────────────────────────────────────────────
    def test_batara_circuit_breaker_closed_initially(self) -> None:
        svc = PrimeNexusService()
        assert svc._should_skip_batara() is False

    def test_batara_circuit_breaker_opens_after_3_failures(self) -> None:
        svc = PrimeNexusService()
        svc._record_batara_failure()
        svc._record_batara_failure()
        svc._record_batara_failure()
        assert svc._should_skip_batara() is True

    def test_batara_circuit_breaker_resets_on_success(self) -> None:
        svc = PrimeNexusService()
        svc._record_batara_failure()
        svc._record_batara_failure()
        svc._record_batara_success()
        assert svc._batara_failures == 0

    def test_batara_circuit_breaker_resets_after_timeout(self) -> None:
        svc = PrimeNexusService()
        svc._batara_failures = 3
        svc._batara_skip_until = time.time() - 1  # expired
        assert svc._should_skip_batara() is False
        assert svc._batara_failures == 0

    def test_gistaru_circuit_breaker_opens_after_3_failures(self) -> None:
        svc = PrimeNexusService()
        svc._record_gistaru_failure()
        svc._record_gistaru_failure()
        svc._record_gistaru_failure()
        assert svc._should_skip_gistaru() is True

    def test_gistaru_circuit_breaker_resets_on_success(self) -> None:
        svc = PrimeNexusService()
        svc._record_gistaru_failure()
        svc._record_gistaru_success()
        assert svc._gistaru_failures == 0

    # ── HTTP client ─────────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_get_client_creates_client(self) -> None:
        svc = PrimeNexusService()
        client = await svc._get_client()
        assert client is not None
        assert not client.is_closed
        await client.aclose()  # cleanup properly
        svc._http_client = None

    @pytest.mark.asyncio
    async def test_close_closes_client(self) -> None:
        svc = PrimeNexusService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.close = AsyncMock()
        svc._http_client = mock_client
        await svc.close()
        assert svc._http_client is None
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_noop_if_no_client(self) -> None:
        svc = PrimeNexusService()
        await svc.close()  # should not raise

    # ── Business extraction ─────────────────────────────────────────
    def test_extract_businesses_filters_non_relevant(self) -> None:
        svc = PrimeNexusService()
        activities = [
            {"name": "Hotel Boutique", "pivot": {"i": True}},
            {"name": "Septic Tank Facility", "pivot": {"i": True}},
            {"name": "Restaurant Beachside", "pivot": {"i": True}},
            {"name": "Local Resident Housing", "pivot": {"i": True}},
            {"name": "Spa and Wellness", "pivot": {"i": True}},
        ]
        result = svc._extract_businesses(activities)
        names = [b["title_en"] for b in result]
        assert "Hotel Boutique" in names
        assert "Septic Tank Facility" not in names
        assert "Local Resident Housing" not in names

    def test_extract_businesses_max_2_per_category(self) -> None:
        svc = PrimeNexusService()
        activities = [
            {"name": "Hotel A", "pivot": {"i": True}},
            {"name": "Hotel B", "pivot": {"i": True}},
            {"name": "Resort C", "pivot": {"i": True}},
        ]
        result = svc._extract_businesses(activities)
        hospitality_count = sum(1 for b in result if b["category_en"] == "Hospitality")
        assert hospitality_count <= 2

    def test_extract_businesses_skips_non_pivot(self) -> None:
        svc = PrimeNexusService()
        activities = [
            {"name": "Hotel A", "pivot": {"i": False}},
            {"name": "Restaurant B", "pivot": {}},
        ]
        result = svc._extract_businesses(activities)
        assert len(result) == 0

    # ── Response builders ───────────────────────────────────────────
    def test_build_resolve_response(self) -> None:
        svc = PrimeNexusService()
        batara_data = {
            "zone_code": "K-1",
            "zone_name": "Kawasan Komersial",
            "zone_label_en": "City Commercial Zone",
            "zone_description_en": "Large-scale commerce",
            "zone_color_hex": "#E8472A",
            "is_restricted": False,
            "businesses": [{"title_en": "Hotel A", "category_en": "Hospitality"}],
            "business_count": 1,
            "overlays": {},
            "building_codes": None,
            "kdb": "70", "klb": "3.0", "kdh": "20", "tb": "15", "gsb": "5", "desa": "Kuta",
        }
        result = svc._build_resolve_response(-8.65, 115.22, batara_data, "batara_live", 1.0)
        assert result["status"] == "found"
        assert result["zone"]["zone_code"] == "K-1"
        assert result["cache_hit"] is False

    def test_build_resolve_response_from_gistaru(self) -> None:
        svc = PrimeNexusService()
        gistaru_data = {
            "code": "W-1",
            "name": "Zona Wisata",
            "overlays": {},
            "kabupaten": "Badung",
            "desa": "Seminyak",
        }
        result = svc._build_resolve_response_from_gistaru(-8.65, 115.22, gistaru_data)
        assert result["status"] == "found"
        assert result["zone"]["zone_code"] == "W-1"
        assert result["zone"]["source"] == "gistaru_rdtr"

    # ── Resolve pipeline ────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_resolve_returns_cache_hit(self) -> None:
        cache = AsyncMock()
        cached_data = {
            "status": "found",
            "zone": {"zone_code": "K-1"},
        }
        cache.get = AsyncMock(return_value=cached_data)
        svc = PrimeNexusService(cache_service=cache)
        result = await svc.resolve(-8.65, 115.22)
        assert result["cache_hit"] is True
        assert result["zone"]["zone_code"] == "K-1"

    @pytest.mark.asyncio
    async def test_resolve_outside_coverage(self) -> None:
        """When all sources fail, return outside_coverage."""
        svc = PrimeNexusService()
        svc._query_batara = AsyncMock(return_value=None)
        svc._query_gistaru = AsyncMock(return_value=None)
        svc._query_postgis = AsyncMock(return_value=None)
        result = await svc.resolve(-8.65, 115.22)
        assert result["status"] == "outside_coverage"

    @pytest.mark.asyncio
    async def test_resolve_batara_success(self) -> None:
        """When BATARA returns data, use it."""
        svc = PrimeNexusService()
        batara_data = {
            "zone_code": "K-2",
            "zone_name": "Commercial",
            "zone_label_en": "District Commercial Zone",
            "zone_description_en": "Mid-scale",
            "zone_color_hex": "#E8472A",
            "is_restricted": False,
            "businesses": [],
            "business_count": 0,
            "overlays": {},
            "building_codes": None,
            "kdb": "70", "klb": "3.0", "kdh": "20", "tb": "15", "gsb": "5", "desa": "Kuta",
        }
        svc._query_batara = AsyncMock(return_value=batara_data)
        svc._cache_zone = AsyncMock()
        result = await svc.resolve(-8.65, 115.22)
        assert result["status"] == "found"
        assert result["zone"]["zone_code"] == "K-2"

    # ── KBLIEye lazy init ──────────────────────────────────────────
    @patch("backend.services.prime.prime_nexus_service.KBLIEye")
    def test_get_kbli_eye_lazy(self, mock_kbli_eye_cls: MagicMock) -> None:
        svc = PrimeNexusService()
        assert svc._kbli_eye is None
        eye = svc._get_kbli_eye()
        assert eye is not None
        mock_kbli_eye_cls.assert_called_once()

    # ── Zone data dictionaries ──────────────────────────────────────
    def test_zone_labels_not_empty(self) -> None:
        assert len(ZONE_LABELS) > 30

    def test_restricted_zones_not_empty(self) -> None:
        assert len(RESTRICTED_ZONES) > 10

    def test_zone_colors_map_not_empty(self) -> None:
        assert len(ZONE_COLORS_MAP) > 20

    def test_oss_risk_penalty(self) -> None:
        """OSS risk Tinggi should penalize regulatory score."""
        result_high = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "klb": "2.0", "source": "batara_live"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data={"golden_strategy": {"roi": 12.0, "bey": 5.0}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
            oss_risk="Tinggi",
        )
        result_low = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "klb": "2.0", "source": "batara_live"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data={"golden_strategy": {"roi": 12.0, "bey": 5.0}},
            geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
            oss_risk=None,
        )
        assert result_high["score"] <= result_low["score"]

    def test_warning_kbli_state_score(self) -> None:
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {}, "source": "batara_live"},
            kbli_state="WARNING",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        reg = result["breakdown"]["regulatory"]
        assert reg["score"] <= 5

    def test_kkop_plus_low_tb_hard_block(self) -> None:
        """KKOP overlay + TB <= 4m should trigger hard block."""
        result = calculate_investment_score(
            zone_data={"code": "K-1", "overlays": {"KKOP_1": True}, "tb": "4 Meter"},
            kbli_state="APPROVED",
            kbli_code="56101",
            roi_data=None,
            geo_data=None,
        )
        assert result["verdict"] == "RED"
        assert any("KKOP" in b for b in result["hard_blocks"])
