"""
Unit tests for backend/app/routers/prime.py
Covers: helper functions, _query_batara, _query_price, _search_local_intel,
_calculate_building_yield, _get_embedder, zone labels, restricted zones.
Direct function calls (no TestClient/AsyncClient) for maximum coverage.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================
# _classify_activity — full category coverage
# ============================================================


def test_classify_activity_hospitality():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("hotel near beach") == "Hospitality"
    assert _classify_activity("resort and villa") == "Hospitality"
    assert _classify_activity("guesthouse rental") == "Hospitality"


def test_classify_activity_fnb():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("restaurant and café") == "F&B"
    assert _classify_activity("bakery shop") == "F&B"
    assert _classify_activity("catering service") == "F&B"
    assert _classify_activity("food court") == "F&B"
    assert _classify_activity("coffee shop and bistro") == "F&B"


def test_classify_activity_wellness():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("spa and wellness") == "Wellness"
    assert _classify_activity("beauty salon") == "Wellness"
    assert _classify_activity("yoga studio") == "Wellness"
    assert _classify_activity("fitness center gym") == "Wellness"


def test_classify_activity_retail():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("boutique clothing") == "Retail"
    assert _classify_activity("retail of textiles") == "Retail"
    assert _classify_activity("art gallery space") == "Retail"
    assert _classify_activity("jewelry shop") == "Retail"
    assert _classify_activity("souvenir store") == "Retail"


def test_classify_activity_services():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("consulting firm") == "Services"
    assert _classify_activity("law firm office") == "Services"
    assert _classify_activity("accounting firm") == "Services"


def test_classify_activity_property():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("real estate agency") == "Property"
    assert _classify_activity("co-working space") == "Property"
    assert _classify_activity("property development") == "Property"


def test_classify_activity_technology():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("software development") == "Technology"
    assert _classify_activity("it service company") == "Technology"
    assert _classify_activity("digital marketing") == "Technology"
    assert _classify_activity("data center hosting") == "Technology"


def test_classify_activity_education():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("international school") == "Education"
    assert _classify_activity("language course center") == "Education"


def test_classify_activity_healthcare():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("hospital facility") == "Healthcare"
    assert _classify_activity("dental clinic") == "Healthcare"


def test_classify_activity_industry():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("food processing plant") == "Industry"
    assert _classify_activity("handicraft workshop") == "Industry"


def test_classify_activity_creative():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("design studio") == "Creative"
    assert _classify_activity("photography studio") == "Creative"
    assert _classify_activity("film production") == "Creative"


def test_classify_activity_other():
    from backend.app.routers.prime import _classify_activity

    assert _classify_activity("unknown xyz activity") == "Other"


# ============================================================
# _is_investor_relevant
# ============================================================


def test_is_investor_relevant_true():
    from backend.app.routers.prime import _is_investor_relevant

    assert _is_investor_relevant("villa rental") is True
    assert _is_investor_relevant("restaurant") is True
    assert _is_investor_relevant("spa wellness") is True


def test_is_investor_relevant_false_skip():
    from backend.app.routers.prime import _is_investor_relevant

    assert _is_investor_relevant("local resident housing") is False
    assert _is_investor_relevant("septic tank facility") is False
    assert _is_investor_relevant("parking area lot") is False
    assert _is_investor_relevant("single house unit") is False
    assert _is_investor_relevant("police station") is False


def test_is_investor_relevant_false_wholesale():
    from backend.app.routers.prime import _is_investor_relevant

    assert _is_investor_relevant("wholesale trade of food") is False


def test_is_investor_relevant_false_infra():
    from backend.app.routers.prime import _is_investor_relevant

    assert _is_investor_relevant("road network planning") is False
    assert _is_investor_relevant("minimum gsb requirements") is False


# ============================================================
# _rgb_string_to_hex
# ============================================================


def test_rgb_string_to_hex_valid():
    from backend.app.routers.prime import _rgb_string_to_hex

    assert _rgb_string_to_hex("250 211 140") == "#fad38c"
    assert _rgb_string_to_hex("0 0 0") == "#000000"
    assert _rgb_string_to_hex("255 255 255") == "#ffffff"


def test_rgb_string_to_hex_comma_separated():
    from backend.app.routers.prime import _rgb_string_to_hex

    assert _rgb_string_to_hex("250,211,140") == "#fad38c"


def test_rgb_string_to_hex_invalid():
    from backend.app.routers.prime import _rgb_string_to_hex

    assert _rgb_string_to_hex("not a color") == "#a0aec0"
    assert _rgb_string_to_hex("") == "#a0aec0"
    assert _rgb_string_to_hex("250 211") == "#a0aec0"  # only 2 parts


# ============================================================
# _calculate_building_yield
# ============================================================


def test_calculate_building_yield_found():
    from backend.app.routers.prime import _calculate_building_yield

    with patch.dict(
        "backend.app.routers.prime._BUILDING_CODES",
        {
            "W-1": {
                "name": "Tourism Zone Type 1",
                "KDB": "60",
                "KLB": "1,8",
                "KDH": "30",
                "KTB": "40",
                "TB": "15 Meter",
                "GSB": "6 Meter",
                "note": "Tourism zone",
            }
        },
    ):
        result = _calculate_building_yield("W-1")
    assert result is not None
    assert result["kdb_pct"] == 60.0
    assert result["klb_ratio"] == 1.8
    assert result["kdh_pct"] == 30.0
    assert result["zone_name_id"] == "Tourism Zone Type 1"


def test_calculate_building_yield_not_found():
    from backend.app.routers.prime import _calculate_building_yield

    result = _calculate_building_yield("NONEXISTENT-99")
    assert result is None


def test_calculate_building_yield_parse_error():
    from backend.app.routers.prime import _calculate_building_yield

    with patch.dict(
        "backend.app.routers.prime._BUILDING_CODES",
        {"BAD-1": {"name": "Bad", "KDB": "not_a_number", "KLB": "0", "KDH": "0", "KTB": "0"}},
    ):
        result = _calculate_building_yield("BAD-1")
    assert result is None


# ============================================================
# _ZONE_LABELS and _RESTRICTED_ZONES constants
# ============================================================


def test_zone_labels_structure():
    from backend.app.routers.prime import _ZONE_LABELS

    assert isinstance(_ZONE_LABELS, dict)
    assert "K-1" in _ZONE_LABELS
    assert "W-1" in _ZONE_LABELS
    for _, info in _ZONE_LABELS.items():
        assert "label_en" in info
        assert "desc_en" in info


def test_restricted_zones_structure():
    from backend.app.routers.prime import _RESTRICTED_ZONES

    assert isinstance(_RESTRICTED_ZONES, set)
    assert "HL" in _RESTRICTED_ZONES
    assert "EM" in _RESTRICTED_ZONES
    assert "BA" in _RESTRICTED_ZONES
    # Non-restricted zones should NOT be in this set
    assert "K-1" not in _RESTRICTED_ZONES
    assert "W-1" not in _RESTRICTED_ZONES


# ============================================================
# _query_batara — happy path + failures
# ============================================================


@pytest.mark.asyncio
async def test_query_batara_success():
    from backend.app.routers.prime import _query_batara

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": 200,
        "data": {
            "territorials": {
                "geom": [
                    {
                        "zone": {
                            "code": "K-2",
                            "name": "Perdagangan dan Jasa",
                            "color": "200 100 50",
                            "definition": "Commercial zone for trade",
                            "activities": [
                                {
                                    "name": "restaurant",
                                    "pivot": {"i": True},
                                },
                                {
                                    "name": "local resident housing",
                                    "pivot": {"i": True},
                                },
                            ],
                        },
                        "kkop_1": "",
                        "lp2b_2": "Tidak",
                        "krb_03": "Tidak Ada",
                        "cagbud": "Tidak Ada",
                        "teb_05": "",
                    }
                ]
            }
        },
    }

    with patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _query_batara(-8.7, 115.2)

    assert result is not None
    assert result["zone_code"] == "K-2"
    assert result["source"] == "BATARA/Badung DPUPR (official)"


@pytest.mark.asyncio
async def test_query_batara_http_error():
    from backend.app.routers.prime import _query_batara

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _query_batara(-8.7, 115.2)

    assert result is None


@pytest.mark.asyncio
async def test_query_batara_no_geom():
    from backend.app.routers.prime import _query_batara

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": 200,
        "data": {"territorials": {"geom": []}},
    }

    with patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _query_batara(-8.7, 115.2)

    assert result is None


@pytest.mark.asyncio
async def test_query_batara_bad_status():
    from backend.app.routers.prime import _query_batara

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 404, "data": {}}

    with patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _query_batara(-8.7, 115.2)

    assert result is None


@pytest.mark.asyncio
async def test_query_batara_exception():
    from backend.app.routers.prime import _query_batara

    with patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _query_batara(-8.7, 115.2)

    assert result is None


@pytest.mark.asyncio
async def test_query_batara_with_overlays():
    from backend.app.routers.prime import _query_batara

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": 200,
        "data": {
            "territorials": {
                "geom": [
                    {
                        "zone": {
                            "code": "HL",
                            "name": "Protected Forest",
                            "color": "0 128 0",
                            "definition": "Protected forest area",
                            "activities": [],
                        },
                        "kkop_1": "KKOP Zone A",
                        "lp2b_2": "Ya",
                        "krb_03": "Zone 1 Tsunami",
                        "cagbud": "Heritage Site",
                        "teb_05": "Evacuation Center A",
                    }
                ]
            }
        },
    }

    with patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _query_batara(-8.7, 115.2)

    assert result is not None
    assert result["is_restricted"] is True
    assert "kkop" in result["overlays"]
    assert "lp2b" in result["overlays"]
    assert "tsunami" in result["overlays"]
    assert "heritage" in result["overlays"]
    assert "evac_center" in result["overlays"]


# ============================================================
# _query_price
# ============================================================


@pytest.mark.asyncio
async def test_query_price_success():
    from backend.app.routers.prime import _query_price

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"avg_price_per_are": 1500.0})
    mock_conn.close = AsyncMock()

    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}),
        patch("backend.app.routers.prime.asyncpg.connect", new=AsyncMock(return_value=mock_conn)),
    ):
        result = await _query_price(-8.7, 115.2)

    assert result == 1500.0


@pytest.mark.asyncio
async def test_query_price_no_result():
    from backend.app.routers.prime import _query_price

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.close = AsyncMock()

    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}),
        patch("backend.app.routers.prime.asyncpg.connect", new=AsyncMock(return_value=mock_conn)),
    ):
        result = await _query_price(-8.7, 115.2)

    assert result is None


@pytest.mark.asyncio
async def test_query_price_postgres_url_fix():
    from backend.app.routers.prime import _query_price

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.close = AsyncMock()

    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgres://test:test@localhost/test"}),
        patch("backend.app.routers.prime.asyncpg.connect", new=AsyncMock(return_value=mock_conn)),
    ):
        result = await _query_price(-8.7, 115.2)

    assert result is None


@pytest.mark.asyncio
async def test_query_price_exception():
    from backend.app.routers.prime import _query_price

    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}),
        patch("backend.app.routers.prime.asyncpg.connect", new=AsyncMock(side_effect=Exception("conn fail"))),
    ):
        result = await _query_price(-8.7, 115.2)

    assert result is None


# ============================================================
# _get_embedder singleton
# ============================================================


def test_get_embedder_creates_once():
    import backend.app.routers.prime as prime_mod

    prime_mod._embedder = None

    with patch(
        "backend.app.routers.prime.create_embeddings_generator",
        return_value=MagicMock(),
    ) as mock_create:
        embedder1 = prime_mod._get_embedder()
        embedder2 = prime_mod._get_embedder()

    assert embedder1 is embedder2
    mock_create.assert_called_once()

    prime_mod._embedder = None  # cleanup


# ============================================================
# _search_local_intel
# ============================================================


@pytest.mark.asyncio
async def test_search_local_intel_success():
    from backend.app.routers.prime import _search_local_intel

    mock_embed = MagicMock()
    mock_embed.generate_single_embedding = AsyncMock(return_value=[0.1] * 1536)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": [
            {
                "score": 0.85,
                "payload": {
                    "title": "Bali Investment News",
                    "source_url": "https://example.com",
                    "category": "property",
                    "published_at": "2026-01-01",
                    "text": "Some news text here",
                },
            }
        ]
    }

    with (
        patch.dict(os.environ, {"QDRANT_URL": "http://localhost:6333", "QDRANT_API_KEY": "test-key"}),
        patch("backend.app.routers.prime._get_embedder", return_value=mock_embed),
        patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _search_local_intel("W-1", "Seminyak", category="Hospitality")

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_search_local_intel_no_qdrant_url():
    from backend.app.routers.prime import _search_local_intel

    with patch.dict(os.environ, {"QDRANT_URL": ""}):
        result = await _search_local_intel("W-1", "Seminyak")

    assert result == []


@pytest.mark.asyncio
async def test_search_local_intel_http_error():
    from backend.app.routers.prime import _search_local_intel

    mock_embed = MagicMock()
    mock_embed.generate_single_embedding = AsyncMock(return_value=[0.1] * 1536)

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with (
        patch.dict(os.environ, {"QDRANT_URL": "http://localhost:6333", "QDRANT_API_KEY": ""}),
        patch("backend.app.routers.prime._get_embedder", return_value=mock_embed),
        patch("backend.app.routers.prime.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await _search_local_intel("W-1", "Seminyak")

    assert result == []


# ============================================================
# _ZONE_CODE_PATTERN
# ============================================================


def test_zone_code_pattern():
    from backend.app.routers.prime import _ZONE_CODE_PATTERN

    matches = _ZONE_CODE_PATTERN.findall("Zone W-1 and K-2 are allowed")
    assert "W-1" in [m.upper() for m in matches]
    assert "K-2" in [m.upper() for m in matches]


def test_zone_code_pattern_no_match():
    from backend.app.routers.prime import _ZONE_CODE_PATTERN

    matches = _ZONE_CODE_PATTERN.findall("no zone codes here")
    assert matches == []
