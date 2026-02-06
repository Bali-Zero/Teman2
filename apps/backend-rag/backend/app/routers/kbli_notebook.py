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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.dependencies import (
    get_optional_database_pool,
    get_search_service,
)

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


class KBLISearchResult(BaseModel):
    code: str
    title: str
    description: str
    score: float


class KBLINotebookChatRequest(BaseModel):
    query: str
    session_id: str | None = None


class KBLINotebookChatResponse(BaseModel):
    answer: str
    detected_kbli: list[str]
    sources: list[dict]


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/search", response_model=list[KBLISearchResult])
async def search_kbli(query: str, limit: int = 10, search_service=Depends(get_search_service)):
    """Search for KBLI codes using semantic search (Qdrant)."""
    start_time = time.time()
    logger.info(f"🔍 KBLI Search Request: '{query}' (limit: {limit})")

    try:
        raw = await search_service.search_collection(
            query=query, collection_name="kbli_2025_final", limit=limit
        )

        search_results = []
        for doc in raw.get("results", []):
            metadata = doc.get("metadata", {})
            search_results.append(
                KBLISearchResult(
                    code=metadata.get("kode", "N/A"),
                    title=metadata.get("judul", "N/A"),
                    description=doc.get("text", "")[:200] + "...",
                    score=doc.get("score", 0.0),
                )
            )

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"✅ KBLI Search Completed: found {len(search_results)} results in {duration:.2f}ms"
        )
        return search_results
    except Exception as e:
        logger.error(f"❌ KBLI Search Failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search engine unavailable") from e


@router.get("/inspect/{code}", response_model=KBLIDetail)
async def inspect_kbli(code: str, pool=Depends(get_optional_database_pool)):
    """Retrieve deep KG metadata for a specific KBLI code from PostgreSQL."""
    logger.info(f"🧐 KBLI Inspection: {code}")
    if not pool:
        logger.error("❌ Database pool not available for KBLI inspection")
        raise HTTPException(status_code=500, detail="Database connection error")

    try:
        async with pool.acquire() as conn:
            # 1. Fetch Main Node
            node = await conn.fetchrow(
                "SELECT * FROM kg_nodes WHERE entity_id = $1", f"kbli:{code}"
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
                    )
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
                others = await conn.fetch(
                    "SELECT source_entity_id FROM kg_edges WHERE target_entity_id = $1 AND relationship_type = 'BELONGS_TO' LIMIT 6",
                    sector_id,
                )
                related_codes = [
                    r["source_entity_id"].replace("kbli:", "")
                    for r in others
                    if r["source_entity_id"] != f"kbli:{code}"
                ]

            logger.info(f"✅ KBLI {code} details retrieved successfully")
            return KBLIDetail(
                code=code,
                title=node["name"].replace(f"KBLI {code}", "").strip() or node["name"],
                description=props.get("uraian", node["description"]),
                pma_status=props.get("pma_status", "UNKNOWN"),
                licensing_status=props.get("licensing_status", "REGULATED"),
                sector=sector_id.replace("sektor:", "") if sector_id else "N/A",
                risk_profile=licenses[0].risk_level if licenses else "Low",
                licenses=licenses,
                related_codes=related_codes,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ KBLI Inspection Error for {code}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal processing error: {str(e)}") from e


@router.post("/chat", response_model=KBLINotebookChatResponse)
async def chat_kbli(request: KBLINotebookChatRequest, search_service=Depends(get_search_service)):
    """Specialized chat for KBLI Notebook with BPS 2025 focus."""
    logger.info(f"💬 KBLI Chat Request: '{request.query[:50]}...'")

    try:
        # Search semantic context
        raw = await search_service.search_collection(
            query=request.query, collection_name="kbli_2025_final", limit=3
        )
        search_results = raw.get("results", [])

        # Detect KBLI codes mentioned in query
        import re

        codes_found = re.findall(r"\d{5}", request.query)

        return KBLINotebookChatResponse(
            answer=f"Analisi della richiesta completata. Ho trovato {len(search_results)} contesti normativi rilevanti basati su BPS 2025 e PP 28/2025.",
            detected_kbli=list(set(codes_found)),
            sources=[{"title": "PP 28/2025", "relevance": "High"}],
        )
    except Exception as e:
        logger.error(f"❌ KBLI Chat Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI Engine connection failed") from e
