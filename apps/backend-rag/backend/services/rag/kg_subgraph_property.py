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

# Badung DPUPR GeoJSON API — only kabupaten with public GISTARU endpoint
_BADUNG_TERRITORIAL_URL = (
    "https://secure.pelayanan-dpupr.badungkab.go.id/storage/id/geojson/territorials/{code}.json"
)
# Google Maps Geocoding — used to resolve lat/lng → desa BPS code
_GMAPS_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def _resolve_desa_code_from_latlng(
    lat: float, lng: float, gmaps_api_key: str
) -> str | None:
    """
    Deterministic step 1: call Google Maps Geocoding to get the BPS desa code
    from coordinates.  Returns a 10-digit BPS code like '5103030005' or None.
    Gemini is NOT involved here — this is a pure API call.
    """
    params = {
        "latlng": f"{lat},{lng}",
        "result_type": "administrative_area_level_4",  # desa/kelurahan level
        "language": "id",
        "key": gmaps_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_GMAPS_GEOCODE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        for result in data.get("results", []):
            for comp in result.get("address_components", []):
                # BPS codes are sometimes stored in place_id or short_name
                # We look for the 10-digit numeric code pattern
                val = comp.get("short_name", "")
                if len(val) == 10 and val.isdigit() and val.startswith("51"):
                    return val
        return None
    except Exception as e:
        logger.warning(f"⚠️ [Zoning] Google Maps geocoding failed: {e}")
        return None


async def _fetch_and_ingest_desa(
    desa_code: str, db_pool: asyncpg.Pool
) -> int:
    """
    Deterministic step 2: download GeoJSON for desa_code from Badung API
    and insert all valid GISTARU polygons into bali_zoning_layers.
    Returns count of rows inserted.
    """
    url = _BADUNG_TERRITORIAL_URL.format(code=desa_code)
    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:  # noqa: S501
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                logger.warning(f"⚠️ [Zoning] No data for desa {desa_code} (HTTP {resp.status_code})")
                return 0
            data = resp.json()
    except Exception as e:
        logger.warning(f"⚠️ [Zoning] Failed to fetch desa {desa_code}: {e}")
        return 0

    features = data.get("features", []) if isinstance(data, dict) else []
    rows = []
    subdistrict_name = desa_code  # fallback

    for feat in features:
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry")
        if not geom or geom.get("type") not in ["Polygon", "MultiPolygon"]:
            continue

        props = feat.get("properties", {})
        attr = props.get("attribute", {})
        zone_obj = props.get("zone") or attr.get("zone") or {}
        zoning_code = zone_obj.get("code", "")
        zoning_name = zone_obj.get("name", "")
        if not zoning_code:
            continue  # skip features without official zone code

        district = attr.get("kabupaten") or "Badung"
        subdistrict = attr.get("kecamatan") or subdistrict_name

        rows.append((
            district,
            subdistrict,
            f"{zoning_code}: {zoning_name}",
            json.dumps([zoning_code]),
            json.dumps(geom),
            0.0,
            0.5,
        ))

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
    inserted = 0
    async with db_pool.acquire() as conn:
        try:
            await conn.executemany(query, rows)
            inserted = len(rows)
        except Exception as e:
            logger.warning(f"⚠️ [Zoning] Batch insert failed for {desa_code}: {e}")
    logger.info(f"✅ [Zoning] On-demand ingested {inserted} polygons for desa {desa_code}")
    return inserted


class PropertyState(TypedDict, total=False):
    """State for Property Subgraph."""

    query: str
    user_context: dict
    current_entities: list[str]
    workflow: dict | None

    # Property-specific
    property_type: str | None  # "hak_pakai", "hgb", "hak_milik", "rental"
    is_foreign_buyer: bool
    property_value: int | None
    location: str | None
    lat: float | None
    lng: float | None
    property_requirements: list[dict]
    zoning_info: dict | None


async def identify_property_type_node(state: PropertyState, llm=None) -> PropertyState:  # noqa: ARG001
    """Identify property ownership type."""
    logger.info("🏠 [Property Subgraph] Identifying property type...")

    query_lower = state["query"].lower()
    is_foreign = state.get("user_context", {}).get("citizenship") == "foreign"

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

    state["property_type"] = prop_type
    state["is_foreign_buyer"] = is_foreign

    # Extract coordinates if present in context
    context = state.get("user_context", {})
    if "lat" in context and "lng" in context:
        state["lat"] = float(context["lat"])
        state["lng"] = float(context["lng"])

    logger.info(f"✅ [Property Subgraph] Type: {prop_type}, foreign: {is_foreign}")
    return state


async def check_zoning_requirements_node(
    state: PropertyState, db_pool: asyncpg.Pool, gmaps_api_key: str = ""
) -> PropertyState:
    """
    Check zoning restrictions based on geospatial coordinates using PostGIS.

    Flow:
      1. Query bali_zoning_layers with ST_Contains (fast, deterministic).
      2. If miss → call Google Maps Geocoding to get BPS desa code (deterministic).
      3. Fetch GISTARU GeoJSON for that desa from Badung DPUPR API (deterministic).
      4. Ingest polygons on-demand → re-query PostGIS.
    Gemini / LLM is NOT involved in this node — every step is a direct API call.
    """
    lat = state.get("lat")
    lng = state.get("lng")

    if not lat or not lng:
        logger.info("📍 [Property Subgraph] No coordinates provided, skipping zoning check.")
        return state

    logger.info(f"🗺️ [Property Subgraph] Checking zoning for coordinates: {lat}, {lng}")

    spatial_query = """
        SELECT district_name, subdistrict_name, zoning_type, allowed_kbli,
               avg_price_per_are, risk_score
        FROM bali_zoning_layers
        WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326))
        LIMIT 1
    """

    async def _query_db() -> dict | None:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(spatial_query, lng, lat)
            return dict(row) if row else None

    try:
        zoning_data = await _query_db()

        # --- Fallback: on-demand ingestion for unmapped desa ---
        if not zoning_data and gmaps_api_key:
            logger.info("🔍 [Property Subgraph] Cache miss — resolving desa via Google Maps...")
            desa_code = await _resolve_desa_code_from_latlng(lat, lng, gmaps_api_key)
            if desa_code:
                ingested = await _fetch_and_ingest_desa(desa_code, db_pool)
                if ingested > 0:
                    zoning_data = await _query_db()  # re-query after ingestion

        if zoning_data:
            state["zoning_info"] = zoning_data
            zone = zoning_data["zoning_type"]
            district = zoning_data["district_name"]
            logger.info(f"✅ [Property Subgraph] Found zoning: {zone} in {district}")

            state.setdefault("property_requirements", []).append(
                {
                    "requirement_type": "zoning",
                    "details": {
                        "district": district,
                        "subdistrict": zoning_data.get("subdistrict_name", ""),
                        "zone": zone,
                        "zone_code": zone.split(":")[0].strip(),
                        "allowed_activities": (
                            "Restricted by KBLI" if zoning_data.get("allowed_kbli") else "Unrestricted"
                        ),
                        "risk_level": (
                            "High" if zoning_data.get("risk_score", 0) > 0.7 else "Normal"
                        ),
                        "source": "GISTARU/Badung DPUPR",
                    },
                }
            )
        else:
            logger.info(
                "⚠️ [Property Subgraph] Coordinates outside mapped GISTARU coverage (non-Badung area)."
            )
            state["zoning_info"] = {
                "status": "outside_coverage",
                "message": "Zoning data available only for Kabupaten Badung. Manual GISTARU lookup required for other areas.",
            }
    except Exception as e:
        logger.error(f"❌ [Property Subgraph] Zoning check failed: {e}")

    return state


async def get_property_requirements_node(
    state: PropertyState,
    db_pool: asyncpg.Pool = None,  # noqa: ARG001
) -> PropertyState:
    """Get ownership requirements."""
    logger.info("📋 [Property Subgraph] Getting property requirements...")

    prop_type = state.get("property_type", "unknown")

    requirements_db = {
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
            "requirements": [
                "Indonesian citizen or Indonesian legal entity only",
            ],
            "notes": "Foreigners can acquire via PT PMA",
        },
        "hak_milik": {
            "allowed_for_foreigners": False,
            "max_duration": "Permanent",
            "requirements": [
                "Indonesian citizen only",
            ],
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

    reqs = requirements_db.get(prop_type, {})
    state.setdefault("property_requirements", []).append(
        {
            "requirement_type": "ownership",
            "details": reqs,
        }
    )

    logger.info(f"✅ [Property Subgraph] Requirements added for {prop_type}")
    return state


async def synthesize_property_workflow_node(state: PropertyState) -> PropertyState:
    """Synthesize property acquisition workflow."""
    logger.info("📋 [Property Subgraph] Synthesizing property workflow...")

    prop_type = state.get("property_type", "unknown")

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

    from dataclasses import asdict

    from backend.services.rag.confidence import calculate_subgraph_confidence

    breakdown = calculate_subgraph_confidence(
        workflow_source="property_subgraph",
        steps_count=len(steps),
        has_db_validation=False,
        unique_sources=1,
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

    state["workflow"] = workflow
    logger.info(f"✅ [Property Subgraph] Workflow with {len(steps)} steps")
    return state


def build_property_subgraph(
    db_pool: asyncpg.Pool, llm: Any, gmaps_api_key: str = ""
) -> StateGraph:
    """Build Property Subgraph."""
    import os

    _gmaps_key = gmaps_api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
    logger.info("🏗️ [Property Subgraph] Building property subgraph...")

    subgraph = StateGraph(PropertyState)

    # Async closures (lambdas can't be async, causing coroutine-instead-of-dict errors)
    async def _identify(s) -> Any:
        return await identify_property_type_node(s, llm)

    async def _check_zoning(s) -> Any:
        return await check_zoning_requirements_node(s, db_pool, _gmaps_key)

    async def _get_reqs(s) -> Any:
        return await get_property_requirements_node(s, db_pool)

    async def _synthesize(s) -> Any:
        return await synthesize_property_workflow_node(s)

    subgraph.add_node("identify_property_type", _identify)
    subgraph.add_node("check_zoning_requirements", _check_zoning)
    subgraph.add_node("get_property_requirements", _get_reqs)
    subgraph.add_node("synthesize_property_workflow", _synthesize)

    subgraph.set_entry_point("identify_property_type")
    subgraph.add_edge("identify_property_type", "check_zoning_requirements")
    subgraph.add_edge("check_zoning_requirements", "get_property_requirements")
    subgraph.add_edge("get_property_requirements", "synthesize_property_workflow")
    subgraph.add_edge("synthesize_property_workflow", END)

    logger.info("✅ [Property Subgraph] Built with 4 nodes")
    return subgraph
