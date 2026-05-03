"""
Unit tests for backend/services/rag/kg_subgraph_property.py

Covers: _get_client, close_property_subgraph_client,
        _resolve_desa_code_from_latlng, _fetch_and_ingest_desa,
        _fetch_badung_provider, _fetch_gistaru_provider,
        _execute_batch_insert, _check_existing_zoning,
        get_property_zoning, get_property_requirements,
        synthesize_property_workflow, build_property_subgraph,
        identify_property_type_node, get_property_requirements_node,
        synthesize_property_workflow_node, legacy wrappers.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.kg_subgraph_property import (
    PropertyState,
    _check_existing_zoning,
    _execute_batch_insert,
    _fetch_and_ingest_desa,
    _fetch_badung_provider,
    _fetch_gistaru_provider,
    _resolve_desa_code_from_latlng,
    build_property_subgraph,
    close_property_subgraph_client,
    get_property_requirements,
    get_property_requirements_node,
    get_property_zoning,
    get_property_zoning_node,
    identify_property_type_node,
    synthesize_property_workflow,
    synthesize_property_workflow_node,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def base_state():
    return PropertyState(
        query="buy villa in Bali",
        lat=None, lng=None,
        zoning_info=None,
        workflow_steps=[],
        final_analysis="",
        confidence_score=0.0,
    )


# ============================================================================
# _get_client / close
# ============================================================================


class TestClientManagement:
    @pytest.mark.asyncio
    async def test_close_property_subgraph_client(self):
        # Should not raise even if no clients exist
        with patch("backend.services.rag.kg_subgraph_property._client_verified", None), \
             patch("backend.services.rag.kg_subgraph_property._client_unverified", None):
            await close_property_subgraph_client()


# ============================================================================
# _resolve_desa_code_from_latlng
# ============================================================================


class TestResolvDesaCode:
    @pytest.mark.asyncio
    async def test_returns_code(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [{
                "address_components": [{"short_name": "5103030005"}],
            }],
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _resolve_desa_code_from_latlng(-8.5, 115.2, "fake_key")
        assert result == "5103030005"

    @pytest.mark.asyncio
    async def test_no_match(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _resolve_desa_code_from_latlng(-8.5, 115.2, "fake_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_api_error(self):
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))
        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _resolve_desa_code_from_latlng(-8.5, 115.2, "fake_key")
        assert result is None


# ============================================================================
# _fetch_badung_provider
# ============================================================================


class TestFetchBadung:
    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "features": [{
                "geometry": {"type": "Polygon", "coordinates": [[]]},
                "properties": {
                    "attribute": {"kabupaten": "Badung", "kecamatan": "Kuta"},
                    "zone": {"code": "R-1", "name": "Residensial"},
                },
            }],
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        mock_db_pool._mock_conn.executemany = AsyncMock(return_value="INSERT 0 1")

        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _fetch_badung_provider("5103030005", mock_db_pool)
        assert result >= 0

    @pytest.mark.asyncio
    async def test_api_error(self, mock_db_pool):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _fetch_badung_provider("5103030005", mock_db_pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_exception(self, mock_db_pool):
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _fetch_badung_provider("5103030005", mock_db_pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_skip_non_polygon(self, mock_db_pool):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "features": [{
                "geometry": {"type": "Point", "coordinates": [115.2, -8.5]},
                "properties": {"zone": {"code": "R-1", "name": "Residensial"}},
            }],
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _fetch_badung_provider("5103030005", mock_db_pool)
        assert result == 0


# ============================================================================
# _fetch_gistaru_provider
# ============================================================================


class TestFetchGistaru:
    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "features": [{
                "geometry": {"type": "Polygon", "coordinates": [[]]},
                "properties": {"KODZON": "R-1", "NAMZNP": "Residensial", "WADMKK": "Gianyar", "WADMKC": "Ubud"},
            }],
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_db_pool._mock_conn.executemany = AsyncMock(return_value="INSERT 0 1")

        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _fetch_gistaru_provider("5104010001", mock_db_pool)
        assert result >= 0

    @pytest.mark.asyncio
    async def test_error_status(self, mock_db_pool):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("backend.services.rag.kg_subgraph_property._get_client", return_value=mock_client):
            result = await _fetch_gistaru_provider("5104010001", mock_db_pool)
        assert result == 0


# ============================================================================
# _execute_batch_insert
# ============================================================================


class TestExecuteBatchInsert:
    @pytest.mark.asyncio
    async def test_empty_rows(self, mock_db_pool):
        result = await _execute_batch_insert([], mock_db_pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_with_rows(self, mock_db_pool):
        rows = [("Badung", "Kuta", "R-1: Residensial", '["R-1"]', '{"type":"Polygon"}', 0.0, 0.5)]
        mock_db_pool._mock_conn.executemany = AsyncMock(return_value="INSERT 0 1")
        result = await _execute_batch_insert(rows, mock_db_pool)
        assert result >= 1

    @pytest.mark.asyncio
    async def test_db_error(self, mock_db_pool):
        rows = [("A", "B", "C", "[]", "{}", 0, 0)]
        mock_db_pool._mock_conn.executemany = AsyncMock(side_effect=Exception("DB error"))
        result = await _execute_batch_insert(rows, mock_db_pool)
        assert result == 0


# ============================================================================
# _check_existing_zoning
# ============================================================================


class TestCheckExistingZoning:
    @pytest.mark.asyncio
    async def test_found(self, mock_db_pool):
        row = {"district_name": "Badung", "subdistrict_name": "Kuta", "zoning_type": "R-1"}
        mock_row = MagicMock()
        mock_row.__iter__ = MagicMock(return_value=iter(row.items()))
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=row)
        result = await _check_existing_zoning(-8.5, 115.2, mock_db_pool)
        assert result is not None

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await _check_existing_zoning(-8.5, 115.2, mock_db_pool)
        assert result is None

    @pytest.mark.asyncio
    async def test_db_error(self, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        result = await _check_existing_zoning(-8.5, 115.2, mock_db_pool)
        assert result is None


# ============================================================================
# LangGraph node functions
# ============================================================================


class TestGetPropertyZoning:
    @pytest.mark.asyncio
    async def test_missing_coordinates(self, base_state):
        result = await get_property_zoning(base_state, {})
        assert result["zoning_info"]["error"] == "Missing coordinates"

    @pytest.mark.asyncio
    async def test_no_db_pool(self, base_state):
        base_state["lat"] = -8.5
        base_state["lng"] = 115.2
        result = await get_property_zoning(base_state, {"configurable": {}})
        assert "error" in result["zoning_info"]

    @pytest.mark.asyncio
    async def test_cache_hit(self, base_state, mock_db_pool):
        base_state["lat"] = -8.5
        base_state["lng"] = 115.2
        config = {"configurable": {"db_pool": mock_db_pool, "google_api_key": "key"}}

        with patch("backend.services.rag.kg_subgraph_property._check_existing_zoning",
                    AsyncMock(return_value={"zoning_type": "R-1", "district_name": "Badung"})):
            result = await get_property_zoning(base_state, config)
        assert result["zoning_info"]["zoning_type"] == "R-1"

    @pytest.mark.asyncio
    async def test_no_gmaps_key(self, base_state, mock_db_pool):
        base_state["lat"] = -8.5
        base_state["lng"] = 115.2
        config = {"configurable": {"db_pool": mock_db_pool}}

        with patch("backend.services.rag.kg_subgraph_property._check_existing_zoning",
                    AsyncMock(return_value=None)):
            result = await get_property_zoning(base_state, config)
        assert "error" in result["zoning_info"]


class TestGetPropertyRequirements:
    @pytest.mark.asyncio
    async def test_residential_zone(self, base_state):
        base_state["zoning_info"] = {"zoning_type": "R-1 Residensial"}
        result = await get_property_requirements(base_state, {})
        assert "Hak Pakai" in str(result["workflow_steps"])

    @pytest.mark.asyncio
    async def test_tourism_zone(self, base_state):
        base_state["zoning_info"] = {"zoning_type": "W-1 Pariwisata"}
        result = await get_property_requirements(base_state, {})
        assert "PMA" in str(result["workflow_steps"])

    @pytest.mark.asyncio
    async def test_unknown_zone(self, base_state):
        base_state["zoning_info"] = {"zoning_type": "X-99"}
        result = await get_property_requirements(base_state, {})
        assert len(result["workflow_steps"]) >= 3


class TestSynthesizePropertyWorkflow:
    @pytest.mark.asyncio
    async def test_with_error(self, base_state):
        base_state["zoning_info"] = {"error": "No data"}
        base_state["workflow_steps"] = ["Step 1", "Step 2"]

        with patch("backend.services.rag.confidence.calculate_subgraph_confidence",
                    return_value={"final_score": 0.4}):
            result = await synthesize_property_workflow(base_state, {})
        assert "couldn't retrieve" in result["final_analysis"].lower()

    @pytest.mark.asyncio
    async def test_with_valid_zoning(self, base_state):
        base_state["zoning_info"] = {"zoning_type": "R-1", "district_name": "Badung"}
        base_state["workflow_steps"] = ["Req 1", "Req 2"]

        with patch("backend.services.rag.confidence.calculate_subgraph_confidence",
                    return_value={"final_score": 0.85}):
            result = await synthesize_property_workflow(base_state, {})
        assert "R-1" in result["final_analysis"]
        assert result["confidence_score"] > 0


# ============================================================================
# build_property_subgraph
# ============================================================================


class TestBuildSubgraph:
    def test_build(self):
        sg = build_property_subgraph()
        assert sg is not None


# ============================================================================
# Legacy wrappers
# ============================================================================


class TestLegacyNodes:
    @pytest.mark.asyncio
    async def test_identify_hak_pakai(self):
        state = {"query": "I want hak pakai", "user_context": {"citizenship": "foreign"}}
        result = await identify_property_type_node(state)
        assert result["property_type"] == "hak_pakai"
        assert result["is_foreign_buyer"] is True

    @pytest.mark.asyncio
    async def test_identify_hgb(self):
        state = {"query": "HGB land acquisition", "user_context": {}}
        result = await identify_property_type_node(state)
        assert result["property_type"] == "hgb"

    @pytest.mark.asyncio
    async def test_identify_rental(self):
        state = {"query": "I want to rent a villa", "user_context": {}}
        result = await identify_property_type_node(state)
        assert result["property_type"] == "rental"

    @pytest.mark.asyncio
    async def test_identify_default_foreign(self):
        state = {"query": "buy property", "user_context": {"citizenship": "foreign"}}
        result = await identify_property_type_node(state)
        assert result["property_type"] == "hak_pakai"

    @pytest.mark.asyncio
    async def test_identify_default_local(self):
        state = {"query": "buy property", "user_context": {"citizenship": "indonesian"}}
        result = await identify_property_type_node(state)
        assert result["property_type"] == "hak_milik"

    @pytest.mark.asyncio
    async def test_requirements_node_fallback(self):
        state = {"property_type": "hak_pakai"}
        result = await get_property_requirements_node(state, db_pool=None)
        assert len(result["property_requirements"]) >= 1
        assert result["kg_sources_used"] == 0

    @pytest.mark.asyncio
    async def test_requirements_node_with_db(self, mock_db_pool):
        state = {"property_type": "hak_pakai"}
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await get_property_requirements_node(state, db_pool=mock_db_pool)
        assert len(result["property_requirements"]) >= 1

    @pytest.mark.asyncio
    async def test_synthesize_workflow_node(self):
        from backend.services.rag.confidence import ConfidenceBreakdown
        state = {"property_type": "hak_pakai", "kg_sources_used": 0}
        breakdown = ConfidenceBreakdown(overall=0.75)
        with patch("backend.services.rag.confidence.calculate_subgraph_confidence",
                    return_value=breakdown):
            result = await synthesize_property_workflow_node(state)
        assert "workflow" in result
        assert result["workflow"]["type"] == "property_acquisition"
        assert len(result["workflow"]["steps"]) == 7

    @pytest.mark.asyncio
    async def test_zoning_node_wrapper(self):
        state = {"query": "test", "lat": None, "lng": None}
        result = await get_property_zoning_node(state, {})
        assert "zoning_info" in result


# ============================================================================
# _fetch_and_ingest_desa routing
# ============================================================================


class TestFetchAndIngestDesa:
    @pytest.mark.asyncio
    async def test_routes_to_badung(self, mock_db_pool):
        with patch("backend.services.rag.kg_subgraph_property._fetch_badung_provider",
                    AsyncMock(return_value=5)) as mock_badung:
            result = await _fetch_and_ingest_desa("5103030005", mock_db_pool)
        mock_badung.assert_awaited_once()
        assert result == 5

    @pytest.mark.asyncio
    async def test_routes_to_gistaru(self, mock_db_pool):
        with patch("backend.services.rag.kg_subgraph_property._fetch_gistaru_provider",
                    AsyncMock(return_value=3)) as mock_gistaru:
            result = await _fetch_and_ingest_desa("5171010001", mock_db_pool)
        mock_gistaru.assert_awaited_once()
        assert result == 3
