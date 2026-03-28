"""
KBLI Notebook API Router

Specialized router for the KBLI Explorer/Notebook UI.
Provides deep integration between BPS 2025 standards and PP 28/2025 regulations.

Author: Nuzantara Team
Date: 2026-02-05
"""

import json
import logging
import time
from inspect import isawaitable
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import (
    get_optional_database_pool,
    get_search_service,
)
from backend.core.collection_registry import resolve_collection_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kbli-notebook", tags=["KBLI Notebook"])

# =============================================================================
# MODELS
# =============================================================================


class KBLILicense(BaseModel):
    type: str
    scale: list[str]
    risk_level: str
    sla: str
    requirements: list[str]


class KBLIDetail(BaseModel):
    code: str
    title: str
    description: str
    pma_status: str
    licensing_status: str
    sector: str
    risk_profile: str
    licenses: list[KBLILicense]
    related_codes: list[str] = []
    expert_legal: dict | None = None


class KBLISearchResult(BaseModel):
    code: str
    title: str
    description: str
    score: float
    pma_status: str = "UNKNOWN"
    risk_category: str = "Unknown"
    expert_legal: dict | None = None


class KBLINotebookChatRequest(BaseModel):
    query: str
    session_id: str | None = None


class KBLINotebookChatResponse(BaseModel):
    answer: str
    detected_kbli: list[str]
    results: list[KBLISearchResult]
    sources: list[dict]
    suggested_queries: list[str] = []


# =============================================================================
# ENDPOINTS
# =============================================================================


KBLI_COLLECTION = resolve_collection_name("kbli_2025_final")


def _payload_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Read flat or legacy nested KBLI payload values."""
    metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
    for key in keys:
        if payload.get(key) not in (None, ""):
            return payload[key]
        if metadata.get(key) not in (None, ""):
            return metadata[key]
    return default


async def _resolve_embedding(search_service: Any, query: str) -> list[float]:
    """Support both async and sync embedding generators in tests and runtime."""
    embedding_result = search_service.embedder.generate_query_embedding(query)
    if isawaitable(embedding_result):
        return await embedding_result
    return embedding_result


@router.get("/llm-health")
async def kbli_llm_health() -> Any:
    """Check LLM health for KBLI Notebook chat functionality."""
    from backend.app.routers.kbli_notebook_chat import _get_llm_gateway

    gateway = _get_llm_gateway()

    health_status = {"llm_available": False, "models": {}, "error": None}

    try:
        # Check gateway availability
        health_status["llm_available"] = gateway._available

        if gateway._available:
            # Run detailed health check
            models_health = await gateway.health_check()
            health_status["models"] = models_health

            # Quick test generation
            try:
                from backend.services.rag.agentic.llm_gateway import TIER_FLASH

                chat = gateway.create_chat_with_history(
                    history_to_use=[],
                    model_tier=TIER_FLASH,
                    system_instruction="You are a helpful assistant.",
                )
                test_response, model_used, _, usage = await gateway.send_message(
                    chat=chat,
                    message="Say 'OK'",
                    system_prompt="You are a helpful assistant.",
                    tier=TIER_FLASH,
                    enable_function_calling=False,
                    conversation_messages=[{"role": "user", "content": "Say 'OK'"}],
                )
                health_status["test_generation"] = {
                    "success": bool(test_response and test_response.strip()),
                    "model_used": model_used,
                    "response_preview": test_response[:50] if test_response else None,
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens if usage else 0,
                        "completion_tokens": usage.completion_tokens if usage else 0,
                        "cost_usd": usage.cost_usd if usage else 0.0,
                    },
                }
            except Exception as test_err:
                health_status["test_generation"] = {"success": False, "error": str(test_err)}
        else:
            health_status["error"] = (
                "LLM Gateway not available. Check GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS."
            )

    except Exception as e:
        health_status["error"] = f"Health check failed: {str(e)}"
        logger.error(f"❌ LLM health check error: {e}", exc_info=True)

    return health_status


async def _get_kbli_payload_from_qdrant(code: str) -> dict | None:
    """Fetch Qdrant payload for a specific KBLI code (by exact match on kode_kbli)."""
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    url = f"{settings.qdrant_url}/collections/{KBLI_COLLECTION}/points/scroll"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for filter_key in (
                "kode_kbli",
                "kode",
                "metadata.kode",
                "metadata.kode_kbli",
                "metadata.kode_kbli_2025",
            ):
                payload = {
                    "filter": {"must": [{"key": filter_key, "match": {"value": code}}]},
                    "limit": 1,
                    "with_payload": True,
                }
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                points = resp.json().get("result", {}).get("points", [])
                if points:
                    return points[0].get("payload", {})
    except Exception as e:
        logger.warning(f"Qdrant lookup for KBLI {code} failed (non-critical): {e}")
    return None


async def _search_kbli_qdrant(query_embedding: list[float], limit: int) -> list[dict]:
    """Direct Qdrant search for KBLI collection (flat payload structure)."""
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    url = f"{settings.qdrant_url}/collections/{KBLI_COLLECTION}/points/search"
    payload = {"vector": query_embedding, "limit": limit, "with_payload": True}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json().get("result", [])


def get_kbli_ttl(code: str) -> int:
    """Determine dynamic TTL based on NotebookLM's sector volatility analysis."""
    # Red Zone: Retail, Alcohol, Clubs, Crypto (High Volatility)
    if code.startswith(("471", "472", "563", "661", "62")):
        return 43200  # 12 Hours
    # Yellow Zone: Hospitality, Construction, Health
    if code.startswith(("55", "41", "86", "05", "06", "07", "08", "09")):
        return 604800  # 7 Days
    # Green Zone: Manufacturing, Services, Agriculture
    return 2592000  # 30 Days


@router.get("/search", response_model=list[KBLISearchResult])
async def search_kbli(
    query: str, limit: int = 10, search_service=Depends(get_search_service),
) -> Any:
    """Search for KBLI codes using semantic search (Qdrant)."""
    start_time = time.time()
    logger.info(f"🔍 KBLI Search Request: '{query}' (limit: {limit})")

    try:
        embedding = await _resolve_embedding(search_service, query)
        results = await _search_kbli_qdrant(embedding, limit)

        search_results = []
        for r in results:
            p = r.get("payload", {})
            search_results.append(
                KBLISearchResult(
                    code=_payload_value(p, "kode_kbli", "kode", "kode_kbli_2025", default="N/A"),
                    title=_payload_value(p, "judul", "title_id", default="N/A"),
                    description=(
                        _payload_value(p, "content", "text", "description", default="") or ""
                    )[:200]
                    + "...",
                    score=round(r.get("score", 0.0), 4),
                    pma_status=_payload_value(p, "pma_status", default="UNKNOWN"),
                    risk_category=_payload_value(p, "kategori_risiko", default="Unknown"),
                ),
            )

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"✅ KBLI Search Completed: found {len(search_results)} results in {duration:.2f}ms",
        )
        return search_results
    except httpx.HTTPStatusError as e:
        logger.warning(f"⚠️ KBLI Search Qdrant error: {e}")
        raise HTTPException(status_code=503, detail="Search engine temporarily unavailable") from e
    except httpx.TimeoutException as e:
        logger.warning(f"⚠️ KBLI Search timeout: {e}")
        raise HTTPException(status_code=503, detail="Search engine temporarily unavailable") from e
    except Exception as e:
        logger.error(f"❌ KBLI Search Failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search engine unavailable") from e


@router.get("/inspect/{code}", response_model=KBLIDetail)
async def inspect_kbli(code: str, pool=Depends(get_optional_database_pool)) -> Any:
    """Retrieve deep KG metadata with dynamic TTL based on sector volatility."""
    from backend.core.cache import get_cache_service

    cache_key = f"kbli_inspect_v2_{code}"
    ttl = get_kbli_ttl(code)

    # Try manual cache check
    cache_manager = get_cache_service()
    if cache_manager:
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            return KBLIDetail(**cached_data)

    logger.info(f"🧐 KBLI Inspection (Dynamic TTL {ttl}s): {code}")
    if not pool:
        logger.error("❌ Database pool not available for KBLI inspection")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable — retrying shortly",
            headers={"Retry-After": "15"},
        )

    try:
        async with pool.acquire() as conn:
            # 1. Fetch Main Node
            node = await conn.fetchrow(
                "SELECT * FROM kg_nodes WHERE entity_id = $1", f"kbli:{code}",
            )

            if not node:
                logger.warning(f"⚠️ KBLI {code} not found in Knowledge Graph")
                raise HTTPException(status_code=404, detail=f"KBLI code {code} not found")

            # 2. Extract Properties
            props = (
                json.loads(node["properties"])
                if isinstance(node["properties"], str)
                else node["properties"]
            )

            # 3. Fetch Related Licenses (REQUIRES edges)
            license_query = """
                SELECT n.*, e.properties as edge_props
                FROM kg_nodes n
                JOIN kg_edges e ON n.entity_id = e.target_entity_id
                WHERE e.source_entity_id = $1 AND e.relationship_type = 'REQUIRES'
            """
            licenses_raw = await conn.fetch(license_query, f"kbli:{code}")

            licenses = []
            for lic in licenses_raw:
                lic_props = (
                    json.loads(lic["properties"])
                    if isinstance(lic["properties"], str)
                    else lic["properties"]
                )

                licenses.append(
                    KBLILicense(
                        type=lic["name"],
                        scale=lic_props.get("skala_usaha", ["All"]),
                        risk_level=lic_props.get("kategori_risiko", "Unknown"),
                        sla=lic_props.get("jangka_waktu", "N/A"),
                        requirements=lic_props.get("kewajiban", []),
                    ),
                )

            # 4. Fetch Related KBLI
            sector_query = """
                SELECT target_entity_id
                FROM kg_edges
                WHERE source_entity_id = $1 AND relationship_type = 'BELONGS_TO'
                LIMIT 1
            """
            sector_id = await conn.fetchval(sector_query, f"kbli:{code}")

            related_codes = []
            if sector_id:
                # Filter by same 2-digit sector prefix to prevent cross-sector contamination
                # e.g. 56210 (catering, sector I) should only relate to 56xxx codes
                sector_prefix = code[:2]
                others = await conn.fetch(
                    "SELECT source_entity_id FROM kg_edges "
                    "WHERE target_entity_id = $1 AND relationship_type = 'BELONGS_TO' "
                    "AND source_entity_id LIKE $2 "
                    "ORDER BY source_entity_id LIMIT 6",
                    sector_id,
                    f"kbli:{sector_prefix}%",
                )
                related_codes = [
                    r["source_entity_id"].replace("kbli:", "")
                    for r in others
                    if r["source_entity_id"] != f"kbli:{code}"
                ]

            # 5. Enrich with Qdrant payload (pma_status, risk category)
            qdrant_payload = await _get_kbli_payload_from_qdrant(code)
            qdrant_risk = (
                _payload_value(qdrant_payload, "kategori_risiko") if qdrant_payload else None
            )

            pma_status = (
                (_payload_value(qdrant_payload, "pma_status") if qdrant_payload else None)
                or props.get("pma_status")
                or "UNKNOWN"
            )

            risk_profile = qdrant_risk or (licenses[0].risk_level if licenses else None) or "Low"

            # Patch licenses with "Unknown" risk using Qdrant value
            if qdrant_risk:
                for lic in licenses:
                    if lic.risk_level == "Unknown":
                        lic.risk_level = qdrant_risk

            logger.info(f"✅ KBLI {code} details retrieved (pma={pma_status}, risk={risk_profile})")

            result = KBLIDetail(
                code=code,
                title=node["name"],
                description=props.get("uraian", node["description"]),
                pma_status=pma_status,
                licensing_status=props.get("licensing_status", "REGULATED"),
                sector=sector_id.replace("sektor:", "") if sector_id else "N/A",
                risk_profile=risk_profile,
                licenses=licenses,
                related_codes=related_codes,
                expert_legal=props.get("expert_legal"),
            )

            # Save to cache with dynamic TTL
            if cache_manager:
                await cache_manager.set(cache_key, result.model_dump(), ttl=ttl)

            return result
    except HTTPException:
        raise
    except (ConnectionResetError, OSError) as e:
        # Stale connection from Fly.io cold start — expire and signal retry
        logger.warning(f"⚠️ KBLI Inspection stale connection for {code}: {e}")
        try:
            await pool.expire_connections()
        except Exception as pool_err:
            logger.debug(f"Pool expire skipped: {pool_err}")
        raise HTTPException(
            status_code=503,
            detail="Database connection reset — please retry",
            headers={"Retry-After": "5"},
        ) from e
    except Exception as e:
        err_msg = str(e)
        if "connection was closed" in err_msg or "connection is closed" in err_msg:
            logger.warning(f"⚠️ KBLI Inspection closed connection for {code}: {e}")
            try:
                await pool.expire_connections()
            except Exception as pool_err:
                logger.debug(f"Pool expire skipped: {pool_err}")
            raise HTTPException(
                status_code=503,
                detail="Database connection reset — please retry",
                headers={"Retry-After": "5"},
            ) from e
        logger.error(f"❌ KBLI Inspection Error for {code}: {err_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal processing error: {err_msg}") from e



# CHAT ENDPOINT & LLM HELPERS → kbli_notebook_chat.py
