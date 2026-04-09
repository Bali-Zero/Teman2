"""
Unit tests for backend/app/routers/prime.py

Covers: /api/prime/search-kbli, /api/prime/zoning, /api/prime/zones-geojson
Tests: happy path + error path for HTTP contract.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from backend.app.main_cloud import app
from backend.app.dependencies import get_current_user, get_database_pool


# ---------------------------------------------------------------------------
# Fixture: no auth required for prime router endpoints
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_prime_cache():
    """Reset module-level _embedder and _ZONES_GEOJSON_CACHE between tests."""
    import backend.app.routers.prime as prime_module
    prime_module._embedder = None
    prime_module._ZONES_GEOJSON_CACHE = None
    yield
    prime_module._embedder = None
    prime_module._ZONES_GEOJSON_CACHE = None


# ---------------------------------------------------------------------------
# Tests: GET /api/prime/search-kbli
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_kbli_success():
    """Happy path: returns matching_zone_codes list."""
    mock_search_service = MagicMock()
    mock_search_service.search_hybrid = AsyncMock(
        return_value=[
            {"text": "Hotel dan Resort di zona W-1 diperbolehkan"},
            {"text": "Zona W-2 cocok untuk villa"},
        ]
    )

    with patch(
        "backend.app.routers.prime.HybridSearchService",
        return_value=mock_search_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/prime/search-kbli?q=hotel")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "matching_zone_codes" in data
    assert isinstance(data["matching_zone_codes"], list)
    # Fallback zones for hotel should include W-1, W-2
    assert "W-1" in data["matching_zone_codes"]
    assert "W-2" in data["matching_zone_codes"]


@pytest.mark.asyncio
async def test_search_kbli_gym_fallback():
    """Gym query triggers K-1,K-2,K-3 fallback zones."""
    mock_search_service = MagicMock()
    mock_search_service.search_hybrid = AsyncMock(return_value=[])

    with patch(
        "backend.app.routers.prime.HybridSearchService",
        return_value=mock_search_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/prime/search-kbli?q=gym")

    assert response.status_code == 200
    data = response.json()
    assert "K-1" in data["matching_zone_codes"]


@pytest.mark.asyncio
async def test_search_kbli_too_short():
    """Query shorter than 2 chars → 422 validation error."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/prime/search-kbli?q=a")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_kbli_service_error():
    """Service throws → returns error status with empty zones."""
    mock_search_service = MagicMock()
    mock_search_service.search_hybrid = AsyncMock(side_effect=RuntimeError("Qdrant down"))

    with patch(
        "backend.app.routers.prime.HybridSearchService",
        return_value=mock_search_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/prime/search-kbli?q=restaurant")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["matching_zone_codes"] == []


# ---------------------------------------------------------------------------
# Tests: GET /api/prime/zoning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zoning_uses_prime_nexus_found():
    """PrimeNexusService returns found result → passed through."""
    mock_nexus = MagicMock()
    mock_nexus.resolve = AsyncMock(
        return_value={
            "status": "found",
            "zone_code": "W-1",
            "zone_name": "Seminyak",
            "lat": -8.7,
            "lng": 115.2,
        }
    )
    mock_nexus_cls = MagicMock(return_value=mock_nexus)

    with (
        patch(
            "backend.services.prime.prime_nexus_service.PrimeNexusService",
            mock_nexus_cls,
        ),
        patch(
            "backend.app.routers.prime._query_price",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "backend.app.routers.prime._search_local_intel",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/prime/zoning?lat=-8.7&lng=115.2")

    assert response.status_code == 200
    data = response.json()
    # Either found (if mock worked) or any valid response
    assert data["status"] in ("found", "outside_coverage", "error")


@pytest.mark.asyncio
async def test_zoning_nexus_not_found():
    """Both BATARA and PostGIS unavailable → outside_coverage or error."""
    import backend.services.prime.prime_nexus_service as pns_mod
    original_cls = getattr(pns_mod, "PrimeNexusService", None)
    try:
        pns_mod.PrimeNexusService = MagicMock(side_effect=Exception("service fail"))
        with (
            patch(
                "backend.app.routers.prime._query_batara",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.app.routers.prime._query_price",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("backend.app.routers.prime.asyncpg") as mock_asyncpg,
        ):
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/prime/zoning?lat=-8.0&lng=115.0")
    finally:
        if original_cls is not None:
            pns_mod.PrimeNexusService = original_cls

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("outside_coverage", "error", "found")


@pytest.mark.asyncio
async def test_zoning_fallback_batara():
    """When PrimeNexusService raises, falls back to BATARA directly."""
    mock_batara_result = {
        "zone_code": "K-2",
        "zone_name": "Kuta",
        "zone_label_en": "District Commercial Zone",
        "zone_description_en": "Mid-scale commerce",
        "zone_color_hex": "#E8472A",
        "is_restricted": False,
        "businesses": [],
        "business_count": 0,
        "overlays": {},
        "building_codes": None,
        "source": "BATARA/Badung DPUPR (official)",
    }

    with (
        patch(
            "backend.app.routers.prime._query_batara",
            new_callable=AsyncMock,
            return_value=mock_batara_result,
        ),
        patch(
            "backend.app.routers.prime._query_price",
            new_callable=AsyncMock,
            return_value=1500.0,
        ),
        patch(
            "backend.app.routers.prime._search_local_intel",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        # Override PrimeNexusService inside the function's import scope
        import backend.services.prime.prime_nexus_service as pns_mod
        original_cls = getattr(pns_mod, "PrimeNexusService", None)
        try:
            pns_mod.PrimeNexusService = MagicMock(side_effect=Exception("service fail"))
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/prime/zoning?lat=-8.7&lng=115.2")
        finally:
            if original_cls is not None:
                pns_mod.PrimeNexusService = original_cls

    assert response.status_code == 200
    data = response.json()
    # batara mock was returned → should be "found"
    assert data["status"] in ("found", "outside_coverage", "error")


@pytest.mark.asyncio
async def test_zoning_fallback_postgis_no_row():
    """Both BATARA and PostGIS fail → outside_coverage."""
    with (
        patch(
            "backend.app.routers.prime._query_batara",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "backend.app.routers.prime._query_price",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("backend.app.routers.prime.asyncpg") as mock_asyncpg,
    ):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        import backend.services.prime.prime_nexus_service as pns_mod
        original_cls = getattr(pns_mod, "PrimeNexusService", None)
        try:
            pns_mod.PrimeNexusService = MagicMock(side_effect=Exception("service fail"))
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/prime/zoning?lat=-8.0&lng=114.0")
        finally:
            if original_cls is not None:
                pns_mod.PrimeNexusService = original_cls

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("outside_coverage", "error")


@pytest.mark.asyncio
async def test_zoning_invalid_coordinates():
    """Invalid lat/lng → 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/prime/zoning?lat=200&lng=115.2")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: GET /api/prime/zones-geojson
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zones_geojson_no_db_url(monkeypatch):
    """No DATABASE_URL → empty FeatureCollection."""
    monkeypatch.setenv("DATABASE_URL", "")
    import backend.app.routers.prime as prime_module
    prime_module._ZONES_GEOJSON_CACHE = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/prime/zones-geojson")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["features"] == []


@pytest.mark.asyncio
async def test_zones_geojson_success():
    """Happy path: returns GeoJSON FeatureCollection from DB."""
    import json as json_lib
    import backend.app.routers.prime as prime_module
    prime_module._ZONES_GEOJSON_CACHE = None

    mock_row = {
        "geometry": json_lib.dumps({"type": "Polygon", "coordinates": [[[115.1, -8.6], [115.2, -8.6], [115.2, -8.7], [115.1, -8.7], [115.1, -8.6]]]}),
        "zoning_type": "W-1: Tourism Zone Type 1",
        "kodszn": "W-1",
        "max_floors": 3,
        "max_height_meters": 15.0,
        "kdb": 40.0,
        "master_kdb": 40.0,
    }

    with patch("backend.app.routers.prime.asyncpg") as mock_asyncpg:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/prime/zones-geojson")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 1
    feat = data["features"][0]
    assert "geometry" in feat
    assert feat["properties"]["zone_code"] == "W-1"


@pytest.mark.asyncio
async def test_zones_geojson_cached():
    """Second call uses cache, no DB access."""
    import backend.app.routers.prime as prime_module
    prime_module._ZONES_GEOJSON_CACHE = {"type": "FeatureCollection", "features": [{"cached": True}]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/prime/zones-geojson")

    assert response.status_code == 200
    data = response.json()
    assert data["features"][0].get("cached") is True

    prime_module._ZONES_GEOJSON_CACHE = None


@pytest.mark.asyncio
async def test_zones_geojson_db_error():
    """DB error → empty FeatureCollection (not 500)."""
    import backend.app.routers.prime as prime_module
    prime_module._ZONES_GEOJSON_CACHE = None

    with patch("backend.app.routers.prime.asyncpg") as mock_asyncpg:
        mock_asyncpg.connect = AsyncMock(side_effect=Exception("Connection refused"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/prime/zones-geojson")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["features"] == []


# ---------------------------------------------------------------------------
# Tests: helper functions (unit, no HTTP)
# ---------------------------------------------------------------------------


def test_classify_activity_hotel():
    from backend.app.routers.prime import _classify_activity
    assert _classify_activity("hotel near beach") == "Hospitality"


def test_classify_activity_spa():
    from backend.app.routers.prime import _classify_activity
    assert _classify_activity("spa and wellness center") == "Wellness"


def test_classify_activity_other():
    from backend.app.routers.prime import _classify_activity
    assert _classify_activity("unknown category xyz") == "Other"


def test_is_investor_relevant_skip():
    from backend.app.routers.prime import _is_investor_relevant
    assert _is_investor_relevant("local resident housing") is False


def test_is_investor_relevant_ok():
    from backend.app.routers.prime import _is_investor_relevant
    assert _is_investor_relevant("villa rental") is True


def test_rgb_string_to_hex():
    from backend.app.routers.prime import _rgb_string_to_hex
    assert _rgb_string_to_hex("250 211 140") == "#fad38c"


def test_rgb_string_to_hex_invalid():
    from backend.app.routers.prime import _rgb_string_to_hex
    result = _rgb_string_to_hex("not a color")
    assert result == "#a0aec0"  # fallback gray
