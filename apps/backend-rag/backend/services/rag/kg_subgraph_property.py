"""
Property Subgraph for LangGraph KG

Handles property acquisition workflows (Hak Pakai, HGB, villa rental).
Specialized subgraph for real estate queries with domain-specific logic.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md (Phase 3)
"""

import json
import logging
from typing import Any, TypedDict

import asyncpg
import httpx
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

# Module-level persistent HTTP clients — separated by SSL verification mode
# to avoid the singleton bug where verify=False and verify=True would share state.
_client_verified: httpx.AsyncClient | None = None
_client_unverified: httpx.AsyncClient | None = None


def _get_client(timeout: float = 10.0, verify: bool = True) -> httpx.AsyncClient:
    """Get or create the shared async client for this module.

    Two separate singletons are maintained: one with SSL verification enabled
    (default) and one with it disabled (used for Badung DPUPR API which has a
    self-signed certificate).  Timeout is applied at request level via the
    ``timeout`` parameter on each ``get``/``post`` call when finer control is
    needed; the client-level timeout here acts as a safety ceiling.
    """
    global _client_verified, _client_unverified
    if verify:
        if _client_verified is None or _client_verified.is_closed:
            _client_verified = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return _client_verified
    if _client_unverified is None or _client_unverified.is_closed:
        _client_unverified = httpx.AsyncClient(
            timeout=timeout,
            verify=False,  # noqa: S501 — Badung DPUPR uses self-signed cert
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )
    return _client_unverified


async def close_property_subgraph_client() -> None:
    """Close all module-level async clients."""
    global _client_verified, _client_unverified
    for client, _name in [(_client_verified, "verified"), (_client_unverified, "unverified")]:
        if client and not client.is_closed:
            await client.aclose()
    logger.info("Property subgraph module HTTP clients closed.")


# Providers Configuration
_BADUNG_TERRITORIAL_URL = (
    "https://secure.pelayanan-dpupr.badungkab.go.id/storage/id/geojson/territorials/{code}.json"
)
_GISTARU_REST_URL = "https://gistaru.atrbpn.go.id/arcgis/rest/services/RTRW/Bali_RTRWP_5100_2023_2043/MapServer/0/query"

# Google Maps Geocoding — used to resolve lat/lng → desa BPS code
_GMAPS_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def _resolve_desa_code_from_latlng(lat: float, lng: float, gmaps_api_key: str) -> str | None:
    """
    Deterministic step 1: call Google Maps Geocoding to get the BPS desa code
    from coordinates.  Returns a 10-digit BPS code like '5103030005' or None.
    """
    params = {
        "latlng": f"{lat},{lng}",
        "result_type": "administrative_area_level_4",  # desa/kelurahan level
        "language": "id",
        "key": gmaps_api_key,
    }
    try:
        client = _get_client(verify=True)
        resp = await client.get(_GMAPS_GEOCODE_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        for result in data.get("results", []):
            for comp in result.get("address_components", []):
                val = comp.get("short_name", "")
                # Pattern: 10 digits starting with 51 (Bali)
                if len(val) == 10 and val.isdigit() and val.startswith("51"):
                    return val
        return None
    except Exception as e:
        logger.warning(f"⚠️ [Zoning] Google Maps geocoding failed: {e}")
        return None


async def _fetch_and_ingest_desa(desa_code: str, db_pool: asyncpg.Pool) -> int:
    """
    Deterministic step 2: download GeoJSON for desa_code from appropriate provider
    and insert valid polygons into bali_zoning_layers.
    """
    # Route to provider based on BPS prefix
    if desa_code.startswith("5103"):  # Badung
        return await _fetch_badung_provider(desa_code, db_pool)
    # Denpasar (5171), Gianyar (5104) and others use National GISTARU
    return await _fetch_gistaru_provider(desa_code, db_pool)


async def _fetch_badung_provider(desa_code: str, db_pool: asyncpg.Pool) -> int:
    """Fetch from Badung DPUPR GeoJSON API."""
    url = _BADUNG_TERRITORIAL_URL.format(code=desa_code)
    try:
        client = _get_client(verify=False)
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
        if resp.status_code != 200:
            logger.warning(f"⚠️ [Zoning] Badung API error for {desa_code}: {resp.status_code}")
            return 0
        data = resp.json()
    except Exception as e:
        logger.warning(f"⚠️ [Zoning] Badung fetch failed: {e}")
        return 0

    features = data.get("features", []) if isinstance(data, dict) else []
    rows = []

    for feat in features:
        geom = feat.get("geometry")
        if not geom or geom.get("type") not in ["Polygon", "MultiPolygon"]:
            continue

        props = feat.get("properties", {})
        attr = props.get("attribute", {})
        zone_obj = props.get("zone") or attr.get("zone") or {}
        zoning_code = zone_obj.get("code", "")
        zoning_name = zone_obj.get("name", "")
        if not zoning_code:
            continue

        district = attr.get("kabupaten") or "Badung"
        subdistrict = attr.get("kecamatan") or desa_code

        rows.append(
            (
                district,
                subdistrict,
                f"{zoning_code}: {zoning_name}",
                json.dumps([zoning_code]),
                json.dumps(geom),
                0.0,
                0.5,
            ),
        )

    return await _execute_batch_insert(rows, db_pool)


async def _fetch_gistaru_provider(desa_code: str, db_pool: asyncpg.Pool) -> int:
    """Fetch from National GISTARU ArcGIS REST API."""
    # Query parameters for ArcGIS REST: filter by KDPPUM (BPS code)
    params = {
        "where": f"KDPPUM = '{desa_code}'",
        "outFields": "*",
        "f": "geojson",
        "outSR": "4326",
    }

    try:
        client = _get_client(verify=True)
        resp = await client.get(_GISTARU_REST_URL, params=params, timeout=60.0)
        if resp.status_code != 200:
            logger.warning(f"⚠️ [Zoning] GISTARU API error for {desa_code}: {resp.status_code}")
            return 0
        data = resp.json()
    except Exception as e:
        logger.warning(f"⚠️ [Zoning] GISTARU fetch failed: {e}")
        return 0

    features = data.get("features", []) if isinstance(data, dict) else []
    rows = []

    for feat in features:
        geom = feat.get("geometry")
        if not geom or geom.get("type") not in ["Polygon", "MultiPolygon"]:
            continue

        props = feat.get("properties", {})
        # GISTARU schema varies, but common fields are NAMOBJ (Desa), NAMZNP (Zone Name), KODZON (Code)
        zoning_code = props.get("KODZON") or props.get("NAMZNP", "").split(":")[0]
        zoning_name = props.get("NAMZNP") or props.get("KETERANGAN")

        if not zoning_code:
            continue

        district = props.get("WADMKK") or "Bali"  # Kabupaten
        subdistrict = props.get("WADMKC") or props.get("NAMOBJ") or desa_code  # Kecamatan/Desa

        rows.append(
            (
                district,
                subdistrict,
                f"{zoning_code}: {zoning_name}",
                json.dumps([zoning_code]),
                json.dumps(geom),
                0.0,
                0.5,
            ),
        )

    return await _execute_batch_insert(rows, db_pool)


async def _execute_batch_insert(rows: list[tuple[Any, ...]], db_pool: asyncpg.Pool) -> int:
    """Helper to perform bulk insert of zoning layers."""
    if not rows:
        return 0

    query = """
        INSERT INTO bali_zoning_layers (
            district_name, subdistrict_name, zoning_type,
            allowed_kbli, boundary, avg_price_per_are, risk_score
        ) VALUES (
            $1, $2, $3, $4::jsonb,
            ST_SetSRID(ST_MakeValid(ST_GeomFromGeoJSON($5)), 4326),
            $6, $7
        )
        ON CONFLICT DO NOTHING
    """
    try:
        async with db_pool.acquire() as conn:
            result = await conn.executemany(query, rows)
            # result is typically a string like 'INSERT 0 15'
            count = 0
            if isinstance(result, str) and " " in result:
                try:
                    count = int(result.split(" ")[-1])
                except (ValueError, IndexError):
                    count = len(rows)
            return count or len(rows)
    except Exception as e:
        logger.error(f"❌ [Zoning] Batch insert failed: {e}")
        return 0


async def _check_existing_zoning(
    lat: float, lng: float, db_pool: asyncpg.Pool,
) -> dict[str, Any] | None:
    """
    Step 0: check if we already have zoning polygons for these coordinates
    in our local bali_zoning_layers table (PostGIS).
    """
    query = """
        SELECT district_name, subdistrict_name, zoning_type, allowed_kbli, avg_price_per_are, risk_score
        FROM bali_zoning_layers
        WHERE ST_Contains(boundary, ST_SetSRID(ST_Point($1, $2), 4326))
        LIMIT 1
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, lng, lat)  # PostGIS uses (lng, lat)
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"❌ [Zoning] DB check failed: {e}")
        return None


# ═══════════════════════════════════════════════════════
# LANGGRAPH NODE FUNCTIONS
# ═══════════════════════════════════════════════════════


class PropertyState(TypedDict):
    """LangGraph state for property subgraph."""

    query: str
    lat: float | None
    lng: float | None
    zoning_info: dict[str, Any] | None
    workflow_steps: list[str]
    final_analysis: str
    confidence_score: float


async def get_property_zoning(state: PropertyState, config: dict) -> dict:
    """
    Node: Resolve coordinates to official Indonesian zoning data.
    Uses Google Maps + GISTARU/DPUPR APIs.
    """
    lat, lng = state.get("lat"), state.get("lng")
    if not lat or not lng:
        return {"zoning_info": {"error": "Missing coordinates"}}

    db_pool = config.get("configurable", {}).get("db_pool")
    gmaps_key = config.get("configurable", {}).get("google_api_key")

    if not db_pool:
        return {"zoning_info": {"error": "Database pool not available"}}

    # 1. Check local cache first
    zoning = await _check_existing_zoning(lat, lng, db_pool)
    if zoning:
        logger.info(f"✅ [Zoning] Cache hit for ({lat}, {lng}): {zoning['zoning_type']}")
        return {"zoning_info": zoning}

    # 2. Resolve desa code via GMaps
    if not gmaps_key:
        return {"zoning_info": {"error": "Google Maps key missing for resolution"}}

    desa_code = await _resolve_desa_code_from_latlng(lat, lng, gmaps_key)
    if not desa_code:
        return {"zoning_info": {"error": "Could not resolve village code for location"}}

    # 3. Fetch and ingest from official government API
    logger.info(f"📥 [Zoning] Cache miss. Fetching desa {desa_code} from gov API...")
    inserted = await _fetch_and_ingest_desa(desa_code, db_pool)
    if inserted > 0:
        # Check again after ingestion
        zoning = await _check_existing_zoning(lat, lng, db_pool)
        if zoning:
            return {"zoning_info": zoning}

    return {"zoning_info": {"error": "Zoning data not available for this location"}}


async def get_property_requirements(state: PropertyState, config: dict) -> dict:
    """
    Node: Retrieve legal requirements for specific property types.
    """
    zoning = state.get("zoning_info", {})
    zone_type = zoning.get("zoning_type", "Unknown")

    # Mock requirements logic — in production this queries the KG
    requirements = [
        "Certificate of Ownership (SHM) or Right to Build (HGB)",
        "Building Approval (PBG) matching zoning type",
        "Tax ID (NPWP) for transaction",
    ]

    if "Residensial" in zone_type or "R-" in zone_type:
        requirements.append("Hak Pakai (Right to Use) for foreigners")
    elif "Pariwisata" in zone_type or "W-" in zone_type:
        requirements.append("PMA company required for commercial rental")

    return {"workflow_steps": requirements}


async def synthesize_property_workflow(state: PropertyState, config: dict) -> dict:
    """
    Node: Combine zoning and requirements into a final AI analysis.
    """
    zoning = state.get("zoning_info", {})
    reqs = state.get("workflow_steps", [])

    if "error" in zoning:
        analysis = f"I couldn't retrieve official zoning data for this location. General requirements: {', '.join(reqs)}"
    else:
        analysis = (
            f"Official zoning for this location is '{zoning['zoning_type']}' in {zoning['district_name']}. "
            f"Based on this, the requirements are: {'; '.join(reqs)}."
        )

    # Dynamic confidence based on data quality instead of hardcoded values
    from backend.services.rag.confidence import calculate_subgraph_confidence

    breakdown = calculate_subgraph_confidence(
        chains=state.get("kg_chains", []),
        entities=state.get("resolved_entities", []),
        query=state.get("query", ""),
    )
    confidence = breakdown.get("final_score", 0.85 if "error" not in zoning else 0.4)

    return {"final_analysis": analysis, "confidence_score": confidence}


# ═══════════════════════════════════════════════════════
# SUBGRAPH BUILDER
# ═══════════════════════════════════════════════════════


def build_property_subgraph(db_pool: Any = None, llm: Any = None) -> StateGraph:
    """
    Constructs the property acquisition LangGraph subgraph.

    Args:
        db_pool: Optional database pool (passed via config in nodes)
        llm: Optional LLM instance (passed via config in nodes)
    """
    subgraph = StateGraph(PropertyState)

    # Add nodes
    subgraph.add_node("get_property_zoning", get_property_zoning)
    subgraph.add_node("get_property_requirements", get_property_requirements)
    subgraph.add_node("synthesize_property_workflow", synthesize_property_workflow)

    # Define flow
    subgraph.set_entry_point("get_property_zoning")
    subgraph.add_edge("get_property_zoning", "get_property_requirements")
    subgraph.add_edge("get_property_requirements", "synthesize_property_workflow")
    subgraph.add_edge("synthesize_property_workflow", END)

    logger.info("✅ [Property Subgraph] Built with 3 nodes and multi-provider support")
    return subgraph


# ═══════════════════════════════════════════════════════
# LEGACY COMPATIBILITY WRAPPERS
# These implement the OLD node signatures expected by existing tests.
# They DO NOT delegate to the new LangGraph nodes because the signatures
# and return payloads are incompatible.
# ═══════════════════════════════════════════════════════

_LEGACY_REQUIREMENTS_DB: dict[str, dict[str, Any]] = {
    "hak_pakai": {
        "allowed_for_foreigners": True,
        "max_duration": "30 years (renewable 20+30 years)",
        "requirements": [
            "KITAS/KITAP holder",
            "Notary deed",
            "Land certificate check (BPN)",
            "Pay BPHTB (5% tax)",
        ],
        "notes": "Most common for foreign property ownership",
    },
    "hgb": {
        "allowed_for_foreigners": False,
        "max_duration": "30 years (renewable)",
        "requirements": ["Indonesian citizen or Indonesian legal entity only"],
        "notes": "Foreigners can acquire via PT PMA",
    },
    "hak_milik": {
        "allowed_for_foreigners": False,
        "max_duration": "Permanent",
        "requirements": ["Indonesian citizen only"],
        "notes": "Full ownership, not available to foreigners",
    },
    "rental": {
        "allowed_for_foreigners": True,
        "max_duration": "Varies (typically 1-5 years)",
        "requirements": [
            "Rental agreement",
            "Passport copy",
            "Deposit (usually 2-3 months rent)",
        ],
        "notes": "Simplest option for short-term stay",
    },
}


async def get_property_zoning_node(state: PropertyState, config: dict) -> dict:
    """Wrapper for backward compatibility with tests."""
    return await get_property_zoning(state, config)


async def identify_property_type_node(state: Any, llm: Any = None) -> dict:
    """Legacy node: identify property type from query and user_context.

    Accepts the OLD positional signature ``(state, llm)`` used by the test
    suite.  Returns legacy fields ``property_type`` and ``is_foreign_buyer``
    without touching the database or making HTTP requests.
    """
    query_lower = str(state.get("query", "")).lower()
    is_foreign: bool = state.get("user_context", {}).get("citizenship") == "foreign"

    if "hak pakai" in query_lower:
        prop_type = "hak_pakai"
    elif "hgb" in query_lower or "hak guna bangunan" in query_lower:
        prop_type = "hgb"
    elif "hak milik" in query_lower:
        prop_type = "hak_milik"
    elif "rent" in query_lower or "lease" in query_lower:
        prop_type = "rental"
    else:
        prop_type = "hak_pakai" if is_foreign else "hak_milik"

    logger.info(f"[Property/legacy] Identified type={prop_type}, foreign={is_foreign}")
    return {"property_type": prop_type, "is_foreign_buyer": is_foreign}


async def get_property_requirements_node(state: Any, db_pool: Any = None) -> dict:
    """Legacy node: return ownership requirements for the property type in state.

    Queries KG for requirements via kg_nodes/kg_edges. Falls back to
    hardcoded _LEGACY_REQUIREMENTS_DB when KG returns no results.
    """
    prop_type: str = state.get("property_type", "unknown")
    requirements: list[dict] = []
    kg_sources = 0

    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT n.entity_id, n.name, n.properties, e.relationship_type
                    FROM kg_edges e
                    JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                    WHERE e.source_entity_id = $1
                      AND e.relationship_type IN (
                          'HAS_REQUIREMENT', 'REQUIRES_ENTITY',
                          'ALLOWS_OWNERSHIP', 'HAS_FEE'
                      )
                    """,
                    f"property_type:{prop_type}",
                )

                if rows:
                    for row in rows:
                        requirements.append({
                            "type": row["relationship_type"],
                            "name": row["name"],
                            "details": row["properties"] or {},
                        })
                    kg_sources = len(rows)
                    logger.info(
                        f"[Property/legacy] Got {kg_sources} requirements from KG for {prop_type}",
                    )
        except Exception as e:
            logger.warning(f"[Property/legacy] KG query failed, using fallback: {e}")

    # Fallback to hardcoded if KG empty
    if not requirements:
        reqs = _LEGACY_REQUIREMENTS_DB.get(prop_type, {})
        requirements = [{"requirement_type": "ownership", "details": reqs}]
        logger.info(f"[Property/legacy] Using fallback requirements for {prop_type}")

    return {
        "property_requirements": requirements,
        "kg_sources_used": kg_sources,
    }


async def synthesize_property_workflow_node(state: Any) -> dict:
    """Legacy node: build the 7-step property acquisition workflow.

    Accepts the OLD positional signature ``(state,)`` (no second arg) used by
    the test suite.  Returns legacy field ``workflow``.
    """
    from dataclasses import asdict

    from backend.services.rag.confidence import calculate_subgraph_confidence

    prop_type: str = state.get("property_type", "unknown")

    steps = [
        {
            "step": 1,
            "action": f"Identify property with {prop_type.upper()} title",
            "entity_id": prop_type,
        },
        {
            "step": 2,
            "action": "Conduct due diligence (BPN certificate check)",
            "entity_id": "bpn_check",
        },
        {"step": 3, "action": "Negotiate price and terms", "entity_id": "negotiation"},
        {"step": 4, "action": "Sign Jual Beli (Sale & Purchase Agreement)", "entity_id": "ppjb"},
        {"step": 5, "action": "Notary deed execution", "entity_id": "notary"},
        {"step": 6, "action": "Pay BPHTB tax (5% of transaction value)", "entity_id": "bphtb"},
        {"step": 7, "action": "Register at Land Office (BPN)", "entity_id": "bpn_registration"},
    ]

    kg_sources = state.get("kg_sources_used", 0)
    breakdown = calculate_subgraph_confidence(
        workflow_source="property_subgraph",
        steps_count=len(steps),
        has_db_validation=kg_sources > 0,
        unique_sources=max(1, kg_sources),
    )

    workflow = {
        "id": f"property:{prop_type}",
        "type": "property_acquisition",
        "name": f"{prop_type.upper()} Property Acquisition",
        "steps": steps,
        "source": "property_subgraph",
        "confidence": breakdown.overall,
        "confidence_breakdown": asdict(breakdown),
    }

    logger.info(f"[Property/legacy] Synthesized workflow with {len(steps)} steps for {prop_type}")
    return {"workflow": workflow}
