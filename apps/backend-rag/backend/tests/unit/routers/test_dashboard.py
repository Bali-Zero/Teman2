"""
Unit tests for backend/app/routers/dashboard.py

Tests route handler functions directly (no TestClient) with mocked dependencies.
Covers all endpoints and helper/scoring functions:
- POST /validate-property          -> validate_property
- POST /gistaru-zone               -> gistaru_zone_lookup
- GET  /clients/geo                -> get_clients_geo
- GET  /compliance/risk-zones      -> get_risk_zones
- POST /analytics/log-lookup       -> log_lookup
- GET  /stats                      -> get_stats
- POST /analyze-investment         -> analyze_investment

Plus scoring engine & helper functions:
- _zone_matches_prefix
- _calculate_zone_kbli_fit
- calculate_investment_score
- _gistaru_rdtr_lookup
- _gistaru_rdtr_direct_query
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: _zone_matches_prefix
# ---------------------------------------------------------------------------


class TestZoneMatchesPrefix:
    def test_match(self) -> None:
        from backend.app.routers.dashboard import _zone_matches_prefix

        assert _zone_matches_prefix("K-1", {"K-", "W-"}) is True

    def test_no_match(self) -> None:
        from backend.app.routers.dashboard import _zone_matches_prefix

        assert _zone_matches_prefix("R-3", {"K-", "W-"}) is False

    def test_empty_prefixes(self) -> None:
        from backend.app.routers.dashboard import _zone_matches_prefix

        assert _zone_matches_prefix("K-1", set()) is False


# ---------------------------------------------------------------------------
# Helper: _calculate_zone_kbli_fit
# ---------------------------------------------------------------------------


class TestCalculateZoneKBLIFit:
    def test_no_zone_or_kbli(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit(None, None)
        assert score == 12 and tier == "unknown"

    def test_non_buildable_zone(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("BA", "55111")
        assert score == 0 and tier == "incompatible"

    def test_nightlife_ideal(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("K-1", "56301")
        assert score == 20 and tier == "ideal"

    def test_nightlife_residential(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("R-3", "56302")
        assert score == 2 and tier == "poor"

    def test_nightlife_other(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("SPU", "56301")
        assert score == 8 and tier == "tolerated"

    def test_ideal_match(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("W-2", "55111")
        assert score == 20 and tier == "ideal"

    def test_acceptable_match(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("K-1", "55111")
        assert score == 12 and tier == "acceptable"

    def test_tolerated_match(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("R-3", "55111")
        assert score == 8 and tier == "tolerated"

    def test_poor_unknown_prefix(self) -> None:
        from backend.app.routers.dashboard import _calculate_zone_kbli_fit

        score, tier = _calculate_zone_kbli_fit("R-3", "99999")
        assert score == 4 and tier == "poor"


# ---------------------------------------------------------------------------
# calculate_investment_score
# ---------------------------------------------------------------------------


class TestCalculateInvestmentScore:
    def test_hard_block_kbli_rejected(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        result = calculate_investment_score(None, "REJECTED", None, None, None)
        assert result["verdict"] == "RED"
        assert result["can_invest"] is False
        assert len(result["hard_blocks"]) > 0

    def test_hard_block_non_buildable_zone(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "BA", "overlays": {}, "source": "batara_live"}
        result = calculate_investment_score(zone, "APPROVED", "55111", None, None)
        assert result["verdict"] == "RED"

    def test_hard_block_lp2b(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "R-3", "overlays": {"LP2B_2": True}, "source": "batara_live", "klb": "1.0"}
        result = calculate_investment_score(zone, "APPROVED", "55111", None, None)
        assert result["verdict"] == "RED"

    def test_hard_block_unavailable_zone(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "NO_DATA", "overlays": {}, "source": "unavailable"}
        result = calculate_investment_score(zone, None, None, None, None)
        assert result["verdict"] == "RED"

    def test_hard_block_low_klb(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "R-4", "overlays": {}, "source": "batara_live", "klb": "0.01"}
        result = calculate_investment_score(zone, "APPROVED", "55111", None, None)
        assert result["verdict"] == "RED"

    def test_hard_block_kkop_low_tb(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "R-3", "overlays": {"KKOP_1": True}, "source": "batara_live", "klb": "1.0", "tb": "3.5 m"}
        result = calculate_investment_score(zone, "APPROVED", "55111", None, None)
        assert result["verdict"] == "RED"

    def test_green_verdict(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "W-2", "overlays": {}, "source": "batara_live", "klb": "2.5"}
        roi = {"golden_strategy": {"roi": 15, "bey": 4}}
        geo = {"flood_risk": "safe", "densita_1km": 50, "walk_score": 80}
        result = calculate_investment_score(zone, "APPROVED", "55111", roi, geo)
        assert result["verdict"] == "GREEN"
        assert result["can_invest"] is True
        assert result["score"] >= 65

    def test_yellow_verdict(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "R-3", "overlays": {}, "source": "batara_live", "klb": "0.8"}
        result = calculate_investment_score(zone, "WARNING", "55111", None, None)
        assert result["verdict"] in ("YELLOW", "RED")

    def test_gistaru_cap(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "W-2", "overlays": {}, "source": "gistaru_rdtr", "klb": "N/A"}
        roi = {"golden_strategy": {"roi": 15, "bey": 3}}
        geo = {"flood_risk": "safe", "densita_1km": 50, "walk_score": 80}
        result = calculate_investment_score(zone, "APPROVED", "55111", roi, geo)
        assert result["verdict"] == "YELLOW"

    def test_overlay_penalties(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "W-2", "overlays": {"KKOP_1": True, "KRB_03": True}, "source": "batara_live", "klb": "2.0", "tb": "15 m"}
        roi = {"golden_strategy": {"roi": 15, "bey": 3}}
        geo = {"flood_risk": "safe", "densita_1km": 50, "walk_score": 80}
        result = calculate_investment_score(zone, "APPROVED", "55111", roi, geo)
        assert len(result["modifiers"]) > 0

    def test_sea_view_bonus(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "W-2", "overlays": {}, "source": "batara_live", "klb": "2.5"}
        roi = {"golden_strategy": {"roi": 15, "bey": 3}}
        geo = {"flood_risk": "safe", "densita_1km": 50, "walk_score": 80, "sea_view": True}
        result = calculate_investment_score(zone, "APPROVED", "55111", roi, geo)
        assert any("+5" in m for m in result["modifiers"])

    def test_w2_villa_warning(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "W-2", "overlays": {}, "source": "batara_live", "klb": "2.5", "tb": "8m"}
        result = calculate_investment_score(zone, "APPROVED", "55111", None, None)
        assert any("W-2" in m for m in result["modifiers"])

    def test_oss_risk_tinggi(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}
        result = calculate_investment_score(zone, "APPROVED", "62011", None, None, oss_risk="Tinggi")
        reg = result["breakdown"]["regulatory"]
        assert reg["score"] <= 7

    def test_oss_risk_menengah_tinggi(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}
        result = calculate_investment_score(zone, "APPROVED", "62011", None, None, oss_risk="Menengah Tinggi")
        reg = result["breakdown"]["regulatory"]
        assert reg["score"] <= 8

    def test_flood_risk_high(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}
        geo = {"flood_risk": "high"}
        result = calculate_investment_score(zone, "APPROVED", "62011", None, geo)
        assert result["breakdown"]["flood_risk"]["score"] == 0

    def test_flood_risk_check(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}
        geo = {"flood_risk": "check"}
        result = calculate_investment_score(zone, "APPROVED", "62011", None, geo)
        assert result["breakdown"]["flood_risk"]["score"] == 5

    def test_market_saturated(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}
        geo = {"densita_1km": 100}
        result = calculate_investment_score(zone, "APPROVED", "62011", None, geo)
        assert result["breakdown"]["market"]["score"] == 3

    def test_market_low(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}
        geo = {"densita_1km": 10}
        result = calculate_investment_score(zone, "APPROVED", "62011", None, geo)
        assert result["breakdown"]["market"]["score"] == 6

    def test_roi_tiers(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}

        for roi_val, expected_min in [(15, 30), (10, 22), (6, 12), (2, 0)]:
            roi = {"golden_strategy": {"roi": roi_val}}
            result = calculate_investment_score(zone, "APPROVED", "62011", roi, None)
            assert result["breakdown"]["roi"]["score"] >= expected_min

    def test_bey_tiers(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}

        for bey_val, expected in [(3, 15), (6, 12), (10, 6), (20, 0)]:
            roi = {"golden_strategy": {"bey": bey_val}}
            result = calculate_investment_score(zone, "APPROVED", "62011", roi, None)
            assert result["breakdown"]["break_even"]["score"] == expected

    def test_klb_tiers(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        for klb_val, expected in [("3.0", 10), ("1.5", 8), ("0.8", 5), ("0.3", 2)]:
            zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": klb_val}
            result = calculate_investment_score(zone, "APPROVED", "62011", None, None)
            assert result["breakdown"]["building_capacity"]["score"] == expected

    def test_walk_score_tiers(self) -> None:
        from backend.app.routers.dashboard import calculate_investment_score

        zone = {"code": "K-1", "overlays": {}, "source": "batara_live", "klb": "2.0"}

        for ws, expected in [(80, 5), (50, 3), (10, 1)]:
            geo = {"walk_score": ws}
            result = calculate_investment_score(zone, "APPROVED", "62011", None, geo)
            assert result["breakdown"]["amenity"]["score"] == expected


# ---------------------------------------------------------------------------
# Endpoint: validate_property
# ---------------------------------------------------------------------------


class TestValidateProperty:
    @pytest.mark.asyncio
    async def test_approved(self) -> None:
        from backend.app.routers.dashboard import ValidatePropertyRequest, validate_property

        mock_eye = MagicMock()
        mock_eye.get_decision.return_value = {"audit": {"state": "APPROVED"}, "state": "APPROVED"}

        with patch("backend.app.routers.dashboard._get_kbli_eye", return_value=mock_eye):
            req = ValidatePropertyRequest(kbli_code="55203", is_pma=True, location="Bali")
            result = await validate_property(req)
        assert result["audit"]["state"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_rejected(self) -> None:
        from backend.app.routers.dashboard import ValidatePropertyRequest, validate_property

        mock_eye = MagicMock()
        mock_eye.get_decision.return_value = {"state": "REJECTED"}

        with patch("backend.app.routers.dashboard._get_kbli_eye", return_value=mock_eye):
            req = ValidatePropertyRequest(kbli_code="47111", is_pma=True)
            result = await validate_property(req)
        assert result["state"] == "REJECTED"


# ---------------------------------------------------------------------------
# Endpoint: gistaru_zone_lookup
# ---------------------------------------------------------------------------


class TestGistaruZoneLookup:
    @pytest.mark.asyncio
    async def test_found(self) -> None:
        from backend.app.routers.dashboard import GistaruLookupRequest, gistaru_zone_lookup

        zone_data = {"code": "K-1", "name": "Komersial", "source": "gistaru_rdtr"}

        with patch("backend.app.routers.dashboard._gistaru_rdtr_lookup", new=AsyncMock(return_value=zone_data)):
            req = GistaruLookupRequest(lat=-8.65, lon=115.2)
            result = await gistaru_zone_lookup(req)
        assert result["found"] is True
        assert result["code"] == "K-1"

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        from backend.app.routers.dashboard import GistaruLookupRequest, gistaru_zone_lookup

        with patch("backend.app.routers.dashboard._gistaru_rdtr_lookup", new=AsyncMock(return_value=None)):
            req = GistaruLookupRequest(lat=-8.65, lon=115.2)
            result = await gistaru_zone_lookup(req)
        assert result["found"] is False


# ---------------------------------------------------------------------------
# Endpoint: get_clients_geo
# ---------------------------------------------------------------------------


class TestClientsGeo:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.dashboard import get_clients_geo

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {"id": 1, "full_name": "Client A", "email": "a@b.com", "phone": "123", "status": "active", "address": "Bali"},
        ])
        pool = MagicMock()
        acm = MagicMock()
        acm.__aenter__ = AsyncMock(return_value=conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acm)

        request = MagicMock()
        request.app.state.db_pool = pool

        result = await get_clients_geo(request)
        assert result["total"] == 1
        assert len(result["clients"]) == 1

    @pytest.mark.asyncio
    async def test_no_pool(self) -> None:
        from backend.app.routers.dashboard import get_clients_geo

        request = MagicMock()
        request.app.state.db_pool = None

        result = await get_clients_geo(request)
        assert result["clients"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_db_error(self) -> None:
        from backend.app.routers.dashboard import get_clients_geo

        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=Exception("DB error"))
        pool = MagicMock()
        acm = MagicMock()
        acm.__aenter__ = AsyncMock(return_value=conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acm)

        request = MagicMock()
        request.app.state.db_pool = pool

        result = await get_clients_geo(request)
        assert "error" in result


# ---------------------------------------------------------------------------
# Endpoint: get_risk_zones
# ---------------------------------------------------------------------------


class TestRiskZones:
    @pytest.mark.asyncio
    async def test_structure(self) -> None:
        from backend.app.routers.dashboard import get_risk_zones

        result = await get_risk_zones()
        assert "zones" in result
        assert len(result["zones"]) == 3

    @pytest.mark.asyncio
    async def test_levels(self) -> None:
        from backend.app.routers.dashboard import get_risk_zones

        result = await get_risk_zones()
        levels = {z["level"] for z in result["zones"]}
        assert levels == {"HIGH", "MEDIUM", "LOW"}


# ---------------------------------------------------------------------------
# Endpoint: log_lookup
# ---------------------------------------------------------------------------


class TestLogLookup:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.dashboard import LogLookupRequest, log_lookup

        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=None)
        pool = MagicMock()
        acm = MagicMock()
        acm.__aenter__ = AsyncMock(return_value=conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acm)

        request = MagicMock()
        request.app.state.db_pool = pool

        req = LogLookupRequest(user_email="test@balizero.com", kbli_code="55111")
        result = await log_lookup(req, request)
        assert result["logged"] is True

    @pytest.mark.asyncio
    async def test_no_pool(self) -> None:
        from backend.app.routers.dashboard import LogLookupRequest, log_lookup

        request = MagicMock()
        request.app.state.db_pool = None

        req = LogLookupRequest(user_email="test@balizero.com")
        result = await log_lookup(req, request)
        assert result["logged"] is False

    @pytest.mark.asyncio
    async def test_db_error(self) -> None:
        from backend.app.routers.dashboard import LogLookupRequest, log_lookup

        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("DB fail"))
        pool = MagicMock()
        acm = MagicMock()
        acm.__aenter__ = AsyncMock(return_value=conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acm)

        request = MagicMock()
        request.app.state.db_pool = pool

        result = await log_lookup(LogLookupRequest(user_email="t@b.com"), request)
        assert result["logged"] is False


# ---------------------------------------------------------------------------
# Endpoint: get_stats
# ---------------------------------------------------------------------------


class TestStats:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.dashboard import get_stats

        conn = AsyncMock()
        conn.fetchval = AsyncMock(side_effect=[100, 50, 5])
        pool = MagicMock()
        acm = MagicMock()
        acm.__aenter__ = AsyncMock(return_value=conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acm)

        request = MagicMock()
        request.app.state.db_pool = pool

        result = await get_stats(request)
        assert result["total_clients"] == 100
        assert result["total_practices"] == 50

    @pytest.mark.asyncio
    async def test_no_pool(self) -> None:
        from backend.app.routers.dashboard import get_stats

        request = MagicMock()
        request.app.state.db_pool = None

        result = await get_stats(request)
        assert result["total_clients"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_db_error(self) -> None:
        from backend.app.routers.dashboard import get_stats

        conn = AsyncMock()
        conn.fetchval = AsyncMock(side_effect=Exception("DB fail"))
        pool = MagicMock()
        acm = MagicMock()
        acm.__aenter__ = AsyncMock(return_value=conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acm)

        request = MagicMock()
        request.app.state.db_pool = pool

        result = await get_stats(request)
        assert "error" in result


# ---------------------------------------------------------------------------
# Endpoint: analyze_investment
# ---------------------------------------------------------------------------


class TestAnalyzeInvestment:
    @pytest.mark.asyncio
    async def test_with_batara_success(self) -> None:
        from backend.app.routers.dashboard import AnalyzeInvestmentRequest, analyze_investment

        batara_response = MagicMock()
        batara_response.json.return_value = {
            "data": {
                "territorials": {
                    "geom": [{
                        "zone": {"code": "K-1", "name": "Komersial", "zone_intensity_requirements": [{"maximum_kdb": "60", "maximum_klb": "2.0", "mininum_kdh": "30", "old_building_height": "15m", "old_minimum_gsb": "5m"}]},
                        "location": {"name": "Kuta"},
                    }],
                },
            },
        }
        batara_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=batara_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.app.routers.dashboard.httpx.AsyncClient", return_value=mock_client):
            req = AnalyzeInvestmentRequest(lat=-8.65, lon=115.2)
            result = await analyze_investment(req)

        assert result["zone"] is not None
        assert result["zone"]["code"] == "K-1"

    @pytest.mark.asyncio
    async def test_batara_fails_gistaru_fallback(self) -> None:
        from backend.app.routers.dashboard import AnalyzeInvestmentRequest, analyze_investment

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        gistaru_zone = {"code": "W-2", "name": "Wisata", "source": "gistaru_rdtr", "overlays": {}}

        with (
            patch("backend.app.routers.dashboard.httpx.AsyncClient", return_value=mock_client),
            patch("backend.app.routers.dashboard._gistaru_rdtr_lookup", new=AsyncMock(return_value=gistaru_zone)),
        ):
            req = AnalyzeInvestmentRequest(lat=-8.65, lon=115.2)
            result = await analyze_investment(req)

        assert result["zone"]["source"] == "gistaru_rdtr"

    @pytest.mark.asyncio
    async def test_with_kbli(self) -> None:
        from backend.app.routers.dashboard import AnalyzeInvestmentRequest, analyze_investment

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_eye = MagicMock()
        mock_eye.get_decision.return_value = {"audit": {"state": "APPROVED", "reason_code": "OK", "oss_risk": "Rendah"}, "pma_logic": {"max_foreign_ownership": 100}, "kbli_2025": "55203", "title": "Hotel"}

        with (
            patch("backend.app.routers.dashboard.httpx.AsyncClient", return_value=mock_client),
            patch("backend.app.routers.dashboard._gistaru_rdtr_lookup", new=AsyncMock(return_value=None)),
            patch("backend.app.routers.dashboard._get_kbli_eye", return_value=mock_eye),
        ):
            req = AnalyzeInvestmentRequest(lat=-8.65, lon=115.2, kbli_code="55203")
            result = await analyze_investment(req)

        assert result["kbli"] is not None
        assert result["kbli"]["state"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_with_geo_data(self) -> None:
        from backend.app.routers.dashboard import AnalyzeInvestmentRequest, analyze_investment

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("backend.app.routers.dashboard.httpx.AsyncClient", return_value=mock_client),
            patch("backend.app.routers.dashboard._gistaru_rdtr_lookup", new=AsyncMock(return_value=None)),
        ):
            req = AnalyzeInvestmentRequest(
                lat=-8.65, lon=115.2,
                geo_data={"flood_risk": "safe", "densita_1km": 50, "walk_score": 70},
            )
            result = await analyze_investment(req)

        assert result["verdict"] is not None

    @pytest.mark.asyncio
    async def test_no_data_anywhere(self) -> None:
        from backend.app.routers.dashboard import AnalyzeInvestmentRequest, analyze_investment

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("backend.app.routers.dashboard.httpx.AsyncClient", return_value=mock_client),
            patch("backend.app.routers.dashboard._gistaru_rdtr_lookup", new=AsyncMock(return_value=None)),
        ):
            req = AnalyzeInvestmentRequest(lat=-8.65, lon=115.2)
            result = await analyze_investment(req)

        assert result["zone"]["source"] == "unavailable"


# ---------------------------------------------------------------------------
# Constants / module-level
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_non_buildable_zones(self) -> None:
        from backend.app.routers.dashboard import NON_BUILDABLE_ZONES

        assert "BA" in NON_BUILDABLE_ZONES
        assert "RTH-1" in NON_BUILDABLE_ZONES

    def test_pydantic_models(self) -> None:
        from backend.app.routers.dashboard import AnalyzeInvestmentRequest, LogLookupRequest, ValidatePropertyRequest

        vp = ValidatePropertyRequest(kbli_code="55111")
        assert vp.is_pma is True

        ll = LogLookupRequest(user_email="x@y.com")
        assert ll.user_email == "x@y.com"

        ai = AnalyzeInvestmentRequest(lat=-8.0, lon=115.0)
        assert ai.lat == -8.0
