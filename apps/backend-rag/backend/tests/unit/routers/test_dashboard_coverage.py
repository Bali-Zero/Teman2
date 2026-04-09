"""
Coverage tests for backend/app/routers/dashboard.py

Endpoints covered:
- POST /api/dashboard/map/validate-property
- POST /api/dashboard/map/gistaru-zone
- GET  /api/dashboard/map/clients/geo
- GET  /api/dashboard/map/compliance/risk-zones
- POST /api/dashboard/map/analytics/log-lookup
- GET  /api/dashboard/map/stats
- POST /api/dashboard/map/analyze-investment
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_overrides():
    """Return FastAPI app with minimal dependency overrides (no auth/db needed for dashboard)."""
    from backend.app.main_cloud import app

    yield app
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. POST /validate-property
# ---------------------------------------------------------------------------


class TestValidateProperty:
    @pytest.mark.asyncio
    async def test_validate_property_approved(self, app_with_overrides):
        """KBLIEye returns APPROVED for an open PMA code."""
        mock_eye = MagicMock()
        mock_eye.get_decision.return_value = {
            "state": "APPROVED",
            "audit": {"state": "APPROVED", "reason_code": "OPEN_PMA"},
        }

        with patch("backend.app.routers.dashboard._get_kbli_eye", return_value=mock_eye):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/validate-property",
                    json={"kbli_code": "55203", "is_pma": True, "location": "Bali"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "state" in data or "audit" in data

    @pytest.mark.asyncio
    async def test_validate_property_rejected(self, app_with_overrides):
        """KBLIEye returns REJECTED for a closed PMA code."""
        mock_eye = MagicMock()
        mock_eye.get_decision.return_value = {
            "state": "REJECTED",
            "audit": {"state": "REJECTED", "reason_code": "DNI"},
        }

        with patch("backend.app.routers.dashboard._get_kbli_eye", return_value=mock_eye):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/validate-property",
                    json={"kbli_code": "47111", "is_pma": True, "location": "Bali"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data is not None

    @pytest.mark.asyncio
    async def test_validate_property_missing_kbli(self, app_with_overrides):
        """Missing required field kbli_code → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/dashboard/map/validate-property",
                json={"is_pma": True},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_validate_property_with_skala(self, app_with_overrides):
        """Optional skala field is accepted."""
        mock_eye = MagicMock()
        mock_eye.get_decision.return_value = {
            "state": "WARNING",
            "audit": {"state": "WARNING"},
        }

        with patch("backend.app.routers.dashboard._get_kbli_eye", return_value=mock_eye):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/validate-property",
                    json={
                        "kbli_code": "56101",
                        "is_pma": False,
                        "location": "Bali",
                        "skala": "MENENGAH",
                    },
                )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 2. POST /gistaru-zone
# ---------------------------------------------------------------------------


class TestGistaruZone:
    @pytest.mark.asyncio
    async def test_gistaru_zone_found(self, app_with_overrides):
        """Returns zone data when GISTARU finds a result."""
        mock_zone = {
            "source": "gistaru_rdtr",
            "code": "W-2",
            "name": "Zona Pariwisata",
            "desa": "Canggu",
            "kecamatan": "Kuta Utara",
            "kabupaten": "Badung",
            "kdb": "N/A",
            "klb": "N/A",
            "kdh": "N/A",
            "tb": "N/A",
            "gsb": "N/A",
            "overlays": {},
        }

        with patch(
            "backend.app.routers.dashboard._gistaru_rdtr_lookup",
            new=AsyncMock(return_value=mock_zone),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/gistaru-zone",
                    json={"lat": -8.65, "lon": 115.13},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["code"] == "W-2"

    @pytest.mark.asyncio
    async def test_gistaru_zone_not_found(self, app_with_overrides):
        """Returns found=False when no zone data available."""
        with patch(
            "backend.app.routers.dashboard._gistaru_rdtr_lookup",
            new=AsyncMock(return_value=None),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/gistaru-zone",
                    json={"lat": 0.0, "lon": 0.0},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["source"] == "gistaru_rdtr"

    @pytest.mark.asyncio
    async def test_gistaru_zone_missing_coordinates(self, app_with_overrides):
        """Missing lat/lon → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/dashboard/map/gistaru-zone",
                json={"lat": -8.65},
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 3. GET /clients/geo
# ---------------------------------------------------------------------------


class TestClientsGeo:
    @pytest.mark.asyncio
    async def test_clients_geo_success(self, app_with_overrides):
        """Returns clients list when DB pool is available."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "full_name": "John Doe",
                    "email": "john@test.com",
                    "phone": "+62812",
                    "status": "active",
                    "address": "Bali",
                }
            ]
        )
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=acquire_cm)

        # Inject pool into app state
        app_with_overrides.state.db_pool = mock_pool

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/clients/geo")

        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_clients_geo_no_pool(self, app_with_overrides):
        """Returns empty clients list with error when DB pool is unavailable."""
        app_with_overrides.state.db_pool = None

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/clients/geo")

        assert response.status_code == 200
        data = response.json()
        assert data["clients"] == []
        assert "error" in data

    @pytest.mark.asyncio
    async def test_clients_geo_db_error(self, app_with_overrides):
        """Returns empty clients with error string when DB raises exception."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("DB connection refused"))
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=acquire_cm)
        app_with_overrides.state.db_pool = mock_pool

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/clients/geo")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data


# ---------------------------------------------------------------------------
# 4. GET /compliance/risk-zones
# ---------------------------------------------------------------------------


class TestRiskZones:
    @pytest.mark.asyncio
    async def test_risk_zones_structure(self, app_with_overrides):
        """Returns static risk zones with correct structure."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/compliance/risk-zones")

        assert response.status_code == 200
        data = response.json()
        assert "zones" in data
        assert isinstance(data["zones"], list)
        assert len(data["zones"]) == 3

    @pytest.mark.asyncio
    async def test_risk_zones_levels(self, app_with_overrides):
        """Risk zones contain HIGH, MEDIUM, LOW levels."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/compliance/risk-zones")

        data = response.json()
        levels = {z["level"] for z in data["zones"]}
        assert levels == {"HIGH", "MEDIUM", "LOW"}


# ---------------------------------------------------------------------------
# 5. POST /analytics/log-lookup
# ---------------------------------------------------------------------------


class TestAnalyticsLogLookup:
    @pytest.mark.asyncio
    async def test_log_lookup_success(self, app_with_overrides):
        """Logs a lookup event and returns logged=True."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=acquire_cm)
        app_with_overrides.state.db_pool = mock_pool

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/dashboard/map/analytics/log-lookup",
                json={
                    "user_email": "user@test.com",
                    "kbli_code": "55203",
                    "location": "Bali",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] is True

    @pytest.mark.asyncio
    async def test_log_lookup_no_pool(self, app_with_overrides):
        """Returns logged=False when DB pool unavailable."""
        app_with_overrides.state.db_pool = None

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/dashboard/map/analytics/log-lookup",
                json={"user_email": "user@test.com"},
            )

        assert response.status_code == 200
        assert response.json()["logged"] is False

    @pytest.mark.asyncio
    async def test_log_lookup_missing_email(self, app_with_overrides):
        """Missing required user_email → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/dashboard/map/analytics/log-lookup",
                json={"kbli_code": "55203"},
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 6. GET /stats
# ---------------------------------------------------------------------------


class TestDashboardStats:
    @pytest.mark.asyncio
    async def test_stats_success(self, app_with_overrides):
        """Returns aggregate stats with correct keys."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[42, 17, 5])  # clients, practices, lookups
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=acquire_cm)
        app_with_overrides.state.db_pool = mock_pool

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_clients" in data
        assert "total_practices" in data
        assert "map_lookups_24h" in data

    @pytest.mark.asyncio
    async def test_stats_no_pool(self, app_with_overrides):
        """Returns zeros with error when pool unavailable."""
        app_with_overrides.state.db_pool = None

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_clients"] == 0
        assert "error" in data

    @pytest.mark.asyncio
    async def test_stats_db_error(self, app_with_overrides):
        """Returns zeros with error string when DB raises exception."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("timeout"))
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=acquire_cm)
        app_with_overrides.state.db_pool = mock_pool

        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/dashboard/map/stats")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data


# ---------------------------------------------------------------------------
# 7. POST /analyze-investment
# ---------------------------------------------------------------------------


class TestAnalyzeInvestment:
    def _make_batara_mock(self, zone_code="W-2"):
        """Return a mock asyncpg-style httpx async client that simulates BATARA."""
        mock_batara_resp = MagicMock()
        mock_batara_resp.raise_for_status = MagicMock(return_value=None)
        mock_batara_resp.json.return_value = {
            "data": {
                "territorials": {
                    "geom": [
                        {
                            "zone": {
                                "code": zone_code,
                                "name": "Zona Pariwisata",
                                "zone_intensity_requirements": [
                                    {
                                        "maximum_kdb": "40",
                                        "maximum_klb": "1.6",
                                        "mininum_kdh": "30",
                                        "old_building_height": "15",
                                        "old_minimum_gsb": "5",
                                    }
                                ],
                            },
                            "location": {"name": "Canggu"},
                        }
                    ]
                }
            }
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_batara_resp)
        # ROI calculator: also fails gracefully
        mock_roi_resp = MagicMock()
        mock_roi_resp.raise_for_status = MagicMock(return_value=None)
        mock_roi_resp.json.return_value = {
            "golden_strategy": {"roi": 10.5, "bey": 6},
            "urbanistica": {},
            "total_investment_idr": 5_000_000_000,
        }
        mock_client_instance.get = AsyncMock(return_value=mock_roi_resp)

        return mock_client_instance

    @pytest.mark.asyncio
    async def test_analyze_investment_with_batara(self, app_with_overrides):
        """BATARA returns zone data, scoring engine returns verdict."""
        mock_client_instance = self._make_batara_mock("W-2")
        # ROI call also succeeds
        mock_roi_resp = MagicMock()
        mock_roi_resp.raise_for_status = MagicMock(return_value=None)
        mock_roi_resp.json.return_value = {
            "golden_strategy": {"roi": 10.5, "bey": 6},
            "urbanistica": {},
            "total_investment_idr": 5_000_000_000,
        }
        mock_client_instance.post.side_effect = [
            mock_client_instance.post.return_value,  # BATARA
            mock_roi_resp,  # ROI (not called since no land_size_m2)
        ]

        with patch("backend.app.routers.dashboard.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/analyze-investment",
                    json={"lat": -8.65, "lon": 115.13},
                )

        assert response.status_code == 200
        data = response.json()
        assert "coordinates" in data
        assert "verdict" in data
        assert data["coordinates"]["lat"] == -8.65

    @pytest.mark.asyncio
    async def test_analyze_investment_with_kbli(self, app_with_overrides):
        """With kbli_code, KBLIEye is called and kbli data returned."""
        mock_eye = MagicMock()
        mock_eye.get_decision.return_value = {
            "kbli_2025": "55203",
            "title": "Villa",
            "state": "APPROVED",
            "audit": {"state": "APPROVED", "reason_code": "OPEN_PMA", "oss_risk": "Rendah"},
            "pma_logic": {"max_foreign_ownership": 100},
        }

        mock_client_instance = self._make_batara_mock("W-2")

        with (
            patch("backend.app.routers.dashboard._get_kbli_eye", return_value=mock_eye),
            patch("backend.app.routers.dashboard.httpx.AsyncClient") as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/analyze-investment",
                    json={"lat": -8.65, "lon": 115.13, "kbli_code": "55203", "is_pma": True},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["kbli"] is not None
        assert data["kbli"]["state"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_analyze_investment_with_geo_data(self, app_with_overrides):
        """geo_data pre-computed by frontend is accepted and used for scoring."""
        mock_client_instance = self._make_batara_mock("K-3")

        with patch("backend.app.routers.dashboard.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            async with AsyncClient(
                transport=ASGITransport(app=app_with_overrides), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/dashboard/map/analyze-investment",
                    json={
                        "lat": -8.65,
                        "lon": 115.13,
                        "geo_data": {
                            "flood_risk": "safe",
                            "densita_1km": 45,
                            "walk_score": 70,
                            "sea_view": True,
                        },
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert "verdict" in data

    @pytest.mark.asyncio
    async def test_analyze_investment_missing_coords(self, app_with_overrides):
        """Missing lat/lon → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_overrides), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/dashboard/map/analyze-investment",
                json={"kbli_code": "55203"},
            )
        assert response.status_code == 422
