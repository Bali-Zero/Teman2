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
    pma_status: str = "UNKNOWN"
    risk_category: str = "Unknown"


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


KBLI_COLLECTION = "kbli_2025_final"


async def _get_kbli_payload_from_qdrant(code: str) -> dict | None:
    """Fetch Qdrant payload for a specific KBLI code (by exact match on kode_kbli)."""
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    url = f"{settings.qdrant_url}/collections/{KBLI_COLLECTION}/points/scroll"
    payload = {
        "filter": {"must": [{"key": "kode_kbli", "match": {"value": code}}]},
        "limit": 1,
        "with_payload": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
                    pma_status=p.get("pma_status") or "UNKNOWN",
                    risk_category=p.get("kategori_risiko") or "Unknown",
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

            # 5. Enrich with Qdrant payload (pma_status, risk category)
            qdrant_payload = await _get_kbli_payload_from_qdrant(code)
            qdrant_risk = qdrant_payload.get("kategori_risiko") if qdrant_payload else None

            pma_status = (
                (qdrant_payload.get("pma_status") if qdrant_payload else None)
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
            return KBLIDetail(
                code=code,
                title=node["name"].replace(f"KBLI {code}", "").strip() or node["name"],
                description=props.get("uraian", node["description"]),
                pma_status=pma_status,
                licensing_status=props.get("licensing_status", "REGULATED"),
                sector=sector_id.replace("sektor:", "") if sector_id else "N/A",
                risk_profile=risk_profile,
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
    "You are a KBLI notebook — a grounded data tool, NOT a generic chatbot. "
    "Your ONLY knowledge source is the KBLI data provided in each message context. "
    "STRICT RULES:\n"
    "1. ONLY cite facts from the KBLI data in context. NEVER add information from general knowledge.\n"
    "2. For each KBLI code, state: what it covers, PMA status if present, risk category if present.\n"
    "3. If the user asks whether they need 1 or multiple codes, answer ONLY based on context data.\n"
    "4. NEVER suggest consulting a notary, lawyer, or other professional. You ARE the expert.\n"
    "5. NEVER respond in Indonesian. The KBLI data is in Indonesian but your response language is set per-message.\n"
    "6. Keep it concise: 2-3 sentences per code.\n"
    "7. Translate Indonesian terms inline: TERBUKA=open to foreigners, TERBATAS=restricted, TERTUTUP=closed.\n"
    "8. If context data is insufficient, say 'Based on the available KBLI data, I cannot determine...' — do NOT guess."
)


_TRANSLATE_SYSTEM = (
    "You convert business activity queries into Indonesian KBLI search phrases. "
    "KBLI = Klasifikasi Baku Lapangan Usaha Indonesia. "
    "Output ONLY the Indonesian search phrase. No explanation, no quotes, no punctuation.\n"
    "Use the specific activity descriptions used in KBLI titles, not generic translations.\n\n"
    "ristorante → aktivitas penyediaan makanan restoran\n"
    "restaurant → aktivitas penyediaan makanan restoran\n"
    "hotel → aktivitas hotel bintang\n"
    "bar → aktivitas rumah minum kafe\n"
    "real estate → agen properti real estat\n"
    "construction → konstruksi bangunan gedung\n"
    "beauty salon → salon kecantikan perawatan\n"
    "travel agency → agen perjalanan wisata\n"
    "import export → perdagangan besar impor ekspor\n"
    "villa rental → penyediaan akomodasi villa penginapan\n"
    "consulting → aktivitas konsultasi manajemen\n"
    "spa → aktivitas spa panti pijat"
)


async def _translate_query_for_kbli(query: str) -> str:
    """Translate any-language query to Indonesian KBLI search terms."""
    try:
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        gateway = _get_llm_gateway()
        chat = gateway.create_chat_with_history(
            history_to_use=[],
            model_tier=TIER_FLASH,
            system_instruction=_TRANSLATE_SYSTEM,
        )
        translated, _model, _resp, _usage = await gateway.send_message(
            chat=chat,
            message=query,
            system_prompt=_TRANSLATE_SYSTEM,
            tier=TIER_FLASH,
            enable_function_calling=False,
            conversation_messages=[{"role": "user", "content": query}],
        )
        translated = translated.strip().strip('"').strip("'")
        logger.info(f"🌐 Query translation: '{query}' → '{translated}'")
        return translated
    except Exception as e:
        logger.warning(f"Query translation failed, using original: {e}")
        return query


def _detect_language(query: str) -> str:
    """Detect query language using keyword heuristics."""
    words = set(query.lower().split())
    # Italian markers
    it_words = {
        "voglio",
        "aprire",
        "quale",
        "codice",
        "serve",
        "come",
        "sono",
        "che",
        "per",
        "una",
        "della",
        "questo",
        "quanto",
        "costa",
        "cosa",
        "posso",
        "devo",
        "fare",
        "mio",
        "bisogno",
        "attivita",
        "licenza",
        "negozio",
    }
    if len(words & it_words) >= 2:
        return "Italian"
    # French markers
    fr_words = {
        "je",
        "veux",
        "ouvrir",
        "quel",
        "pour",
        "une",
        "est",
        "les",
        "des",
        "mon",
        "faire",
        "comment",
    }
    if len(words & fr_words) >= 2:
        return "French"
    # Spanish markers
    es_words = {"quiero", "abrir", "cual", "para", "como", "necesito", "puedo", "hacer", "negocio"}
    if len(words & es_words) >= 2:
        return "Spanish"
    return "English"


async def _generate_kbli_explanation(query: str, results: list[KBLISearchResult]) -> str:
    """Generate a grounded explanation of KBLI search results using LLM."""
    if not results:
        return "No matching KBLI codes found for your search. Try different keywords or describe your business activity in more detail."

    lang = _detect_language(query)
    logger.info(f"🌐 Detected language: {lang} for query: '{query[:40]}'")

    context_parts = []
    for r in results:
        context_parts.append(
            f"- KBLI {r.code}: {r.title}\n  Data: {r.description}\n  Score: {r.score:.0%}"
        )
    context = "\n".join(context_parts)

    # Build language-specific system instruction
    if lang.lower() == "italian":
        lang_system = (
            "Sei un notebook KBLI — uno strumento dati, NON un chatbot generico. "
            "Rispondi SOLO in italiano. Ogni frase deve essere in italiano. "
            "Usa SOLO i dati KBLI forniti nel contesto. NON inventare informazioni. "
            "Per ogni codice KBLI spiega: cosa copre, status PMA se presente, categoria rischio. "
            "NON suggerire mai di consultare un notaio o professionista. Tu sei l'esperto. "
            "Traduci i termini indonesiani: TERBUKA=aperto a stranieri, TERBATAS=con restrizioni, TERTUTUP=chiuso. "
            "Sii conciso: 2-3 frasi per codice."
        )
    else:
        lang_system = KBLI_SYSTEM_PROMPT

    message = f"Question: {query}\n\nSource data:\n{context}"

    try:
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        gateway = _get_llm_gateway()
        chat = gateway.create_chat_with_history(
            history_to_use=[],
            model_tier=TIER_FLASH,
            system_instruction=lang_system,
        )
        response_text, _model, _resp, _usage = await gateway.send_message(
            chat=chat,
            message=message,
            system_prompt=lang_system,
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
        # Translate query to Indonesian KBLI terms for better matching
        search_query = await _translate_query_for_kbli(request.query)

        # Search semantic context with translated query
        embedding = await search_service.embedder.generate_query_embedding(search_query)
        raw_results = await _search_kbli_qdrant(embedding, 7)

        # Deduplicate by code (same code can appear multiple times), take top 5
        seen_codes = set()
        results = []
        for r in raw_results:
            p = r.get("payload", {})
            code = p.get("kode_kbli", "N/A")
            if code in seen_codes:
                continue
            seen_codes.add(code)
            results.append(
                KBLISearchResult(
                    code=code,
                    title=p.get("judul", "N/A"),
                    description=(p.get("content", "") or "")[:200] + "...",
                    score=round(r.get("score", 0.0), 4),
                    pma_status=p.get("pma_status") or "UNKNOWN",
                    risk_category=p.get("kategori_risiko") or "Unknown",
                )
            )
            if len(results) >= 5:
                break

        # Detect KBLI codes from results + regex on query
        codes_from_query = re.findall(r"\d{5}", request.query)
        codes_from_results = [r.code for r in results if r.code != "N/A"]
        detected_kbli = list(dict.fromkeys(codes_from_query + codes_from_results))

        # Generate Italian explanation via LLM (with fallback)
        answer = await _generate_kbli_explanation(request.query, results)

        # Generate template-based follow-up suggestions
        suggested_queries = []
        if results:
            top = results[0]
            suggested_queries.append(f"What licenses do I need for KBLI {top.code}?")
            if top.pma_status in ("TERBUKA", "TERBATAS", "TERTUTUP"):
                suggested_queries.append(f"Is {top.title} open to foreign investors?")
            else:
                suggested_queries.append(f"Can a foreigner own a {top.title} business?")
            if len(results) > 1:
                suggested_queries.append(
                    f"What's the difference between KBLI {top.code} and {results[1].code}?"
                )
            else:
                suggested_queries.append(f"What are the risk requirements for KBLI {top.code}?")

        return KBLINotebookChatResponse(
            answer=answer,
            detected_kbli=detected_kbli,
            results=results,
            sources=[{"title": "PP 28/2025", "relevance": "High"}],
            suggested_queries=suggested_queries,
        )
    except Exception as e:
        logger.error(f"❌ KBLI Chat Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI Engine connection failed") from e
