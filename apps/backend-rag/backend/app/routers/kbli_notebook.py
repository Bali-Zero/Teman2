"""
KBLI Notebook API Router

Specialized router for the KBLI Explorer/Notebook UI.
Provides deep integration between BPS 2025 standards and PP 28/2025 regulations.

Author: Nuzantara Team
Date: 2026-02-05
"""

import json
import logging
import re
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.config import settings
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
    results: list[KBLISearchResult]
    sources: list[dict]


# =============================================================================
# ENDPOINTS
# =============================================================================


KBLI_COLLECTION = "kbli_2025_final"


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


@router.get("/search", response_model=list[KBLISearchResult])
async def search_kbli(query: str, limit: int = 10, search_service=Depends(get_search_service)):
    """Search for KBLI codes using semantic search (Qdrant)."""
    start_time = time.time()
    logger.info(f"🔍 KBLI Search Request: '{query}' (limit: {limit})")

    try:
        embedding = await search_service.embedder.generate_query_embedding(query)
        results = await _search_kbli_qdrant(embedding, limit)

        search_results = []
        for r in results:
            p = r.get("payload", {})
            search_results.append(
                KBLISearchResult(
                    code=p.get("kode_kbli", "N/A"),
                    title=p.get("judul", "N/A"),
                    description=(p.get("content", "") or "")[:200] + "...",
                    score=round(r.get("score", 0.0), 4),
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


_llm_gateway_instance = None


def _get_llm_gateway():
    global _llm_gateway_instance
    if _llm_gateway_instance is None:
        from backend.services.rag.agentic.llm_gateway import LLMGateway

        _llm_gateway_instance = LLMGateway()
    return _llm_gateway_instance


KBLI_SYSTEM_PROMPT = (
    "Sei un consulente aziendale italiano specializzato in investimenti in Indonesia (Bali). "
    "Il tuo interlocutore e' un imprenditore italiano NON esperto di burocrazia indonesiana. "
    "Rispondi SEMPRE in italiano. Sii chiaro, concreto e amichevole. "
    "Non usare gergo tecnico indonesiano senza spiegarlo. "
    "Spiega cosa copre ogni codice KBLI e perche' e' rilevante. "
    "Mantieni la risposta breve (3-5 frasi per risultato). "
    "Se PMA e' rilevante: TERBUKA=aperto stranieri, TERBATAS=con limitazioni, TERTUTUP=chiuso. "
    "NON inventare informazioni. Usa SOLO i dati forniti nel contesto."
)


async def _generate_kbli_explanation(query: str, results: list[KBLISearchResult]) -> str:
    """Generate an Italian explanation of KBLI search results using LLM."""
    if not results:
        return "Non ho trovato codici KBLI corrispondenti alla tua ricerca. Prova con parole diverse o descrivi la tua attivita' in modo piu' dettagliato."

    context_parts = []
    for r in results:
        context_parts.append(f"- KBLI {r.code}: {r.title}\n  Descrizione: {r.description}\n  Rilevanza: {r.score:.0%}")
    context = "\n".join(context_parts)

    message = f"Domanda dell'utente: {query}\n\nRisultati KBLI trovati:\n{context}\n\nSpiega questi codici KBLI in italiano, in modo semplice e utile per un imprenditore."

    try:
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        gateway = _get_llm_gateway()
        chat = gateway.create_chat_with_history(
            history_to_use=[],
            model_tier=TIER_FLASH,
            system_instruction=KBLI_SYSTEM_PROMPT,
        )
        response_text, _model, _resp, _usage = await gateway.send_message(
            chat=chat,
            message=message,
            system_prompt=KBLI_SYSTEM_PROMPT,
            tier=TIER_FLASH,
            enable_function_calling=False,
            conversation_messages=[{"role": "user", "content": message}],
        )
        return response_text
    except Exception as e:
        logger.warning(f"LLM explanation failed, using fallback: {e}")
        # Deterministic fallback: markdown list of results
        lines = [f"Ho trovato {len(results)} codici KBLI rilevanti per la tua ricerca:\n"]
        for r in results:
            lines.append(f"**KBLI {r.code}** - {r.title}\n{r.description}\n")
        return "\n".join(lines)


@router.post("/chat", response_model=KBLINotebookChatResponse)
async def chat_kbli(request: KBLINotebookChatRequest, search_service=Depends(get_search_service)):
    """Specialized chat for KBLI Notebook with BPS 2025 focus."""
    logger.info(f"💬 KBLI Chat Request: '{request.query[:50]}...'")

    try:
        # Search semantic context (5 results for richer answers)
        embedding = await search_service.embedder.generate_query_embedding(request.query)
        raw_results = await _search_kbli_qdrant(embedding, 5)

        # Build structured results (same pattern as /search endpoint)
        results = []
        for r in raw_results:
            p = r.get("payload", {})
            results.append(
                KBLISearchResult(
                    code=p.get("kode_kbli", "N/A"),
                    title=p.get("judul", "N/A"),
                    description=(p.get("content", "") or "")[:200] + "...",
                    score=round(r.get("score", 0.0), 4),
                )
            )

        # Detect KBLI codes from results + regex on query
        codes_from_query = re.findall(r"\d{5}", request.query)
        codes_from_results = [r.code for r in results if r.code != "N/A"]
        detected_kbli = list(dict.fromkeys(codes_from_query + codes_from_results))

        # Generate Italian explanation via LLM (with fallback)
        answer = await _generate_kbli_explanation(request.query, results)

        return KBLINotebookChatResponse(
            answer=answer,
            detected_kbli=detected_kbli,
            results=results,
            sources=[{"title": "PP 28/2025", "relevance": "High"}],
        )
    except Exception as e:
        logger.error(f"❌ KBLI Chat Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI Engine connection failed") from e
