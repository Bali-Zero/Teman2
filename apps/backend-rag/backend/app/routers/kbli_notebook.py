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
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import (
    get_optional_database_pool,
    get_search_service,
)
from backend.core.cache import cached

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


KBLI_COLLECTION = "kbli_2025_final"


@router.get("/llm-health")
async def kbli_llm_health():
    """Check LLM health for KBLI Notebook chat functionality."""
    gateway = _get_llm_gateway()
    
    health_status = {
        "llm_available": False,
        "models": {},
        "error": None
    }
    
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
                    }
                }
            except Exception as test_err:
                health_status["test_generation"] = {
                    "success": False,
                    "error": str(test_err)
                }
        else:
            health_status["error"] = "LLM Gateway not available. Check GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS."
            
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
    """Retrieve deep KG metadata with dynamic TTL based on sector volatility."""
    from backend.core.cache import cache_manager # Assume we have access to the manager
    
    cache_key = f"kbli_inspect_v2_{code}"
    ttl = get_kbli_ttl(code)
    
    # Try manual cache check
    if cache_manager:
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            return KBLIDetail(**cached_data)

    logger.info(f"🧐 KBLI Inspection (Dynamic TTL {ttl}s): {code}")
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
            
            result = KBLIDetail(
                code=code,
                title=node["name"].replace(f"KBLI {code}", "").strip() or node["name"],
                description=props.get("uraian", node["description"]),
                pma_status=pma_status,
                licensing_status=props.get("licensing_status", "REGULATED"),
                sector=sector_id.replace("sektor:", "") if sector_id else "N/A",
                risk_profile=risk_profile,
                licenses=licenses,
                related_codes=related_codes,
                expert_legal=props.get("expert_legal")
            )
            
            # Save to cache with dynamic TTL
            if cache_manager:
                await cache_manager.set(cache_key, result.model_dump(), ttl=ttl)
                
            return result
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


KBLI_MASTER_PROMPT = (
    "You are the Senior Legal Compliance Officer (Zantara AI). Your expertise is the Indonesian Business Classification System (KBLI 2025).\n\n"
    "LANGUAGE RULES (ABSOLUTE PRIORITY):\n"
    "- You MUST respond in the user's language: {lang}.\n"
    "- Default language is English. Indonesian is your second language for technical data.\n"
    "- NEVER respond in Italian, French, Spanish, or any other language unless the user explicitly wrote in that language.\n"
    "- If you cannot detect the user's language, respond in English.\n\n"
    "CORE CAPABILITIES:\n"
    "- Primary Knowledge: You are an absolute expert in Indonesian regulations (PP 28/2025, BPS 7/2025, INGUB 6/2025).\n"
    "- Multilingual Mastery: You speak Indonesian and English natively for technical data.\n\n"
    "PMA STATUS GLOSSARY (answer these directly without needing source data):\n"
    "- TERBUKA = Open to 100% foreign ownership (PMA diperbolehkan penuh)\n"
    "- TERBATAS = Open with restrictions — max foreign ownership percentage applies (PMA dengan batasan kepemilikan)\n"
    "- TERTUTUP = Closed to foreign investment — Indonesian nationals only (PMA tidak diperbolehkan)\n"
    "- PMA = Penanaman Modal Asing = Foreign Direct Investment\n"
    "- Modal Disetor Minimum for PMA = Rp 10 Billion (Ten Billion IDR) paid-up capital\n"
    "- OSS = Online Single Submission system at oss.go.id — official licensing portal\n"
    "- NIB = Nomor Induk Berusaha = Business Identification Number (first step in OSS)\n"
    "If a user asks what these terms mean, explain them directly using this glossary.\n\n"
    "KNOWN KBLI CODES (use these exact definitions when asked):\n"
    "- 47911 = PERDAGANGAN ECERAN MELALUI MEDIA UNTUK BERBAGAI MACAM BARANG — Retail trade of various consumer goods via internet/digital media platforms. PMA: TERBATAS (restricted).\n"
    "- 56101 = AKTIVITAS PENYEDIAAN MAKANAN DI BANGUNAN TETAP (RESTORAN) — Restaurant services with permanent building. PMA: TERBUKA (open to foreigners), Risiko: Menengah Rendah.\n"
    "- 56210 = AKTIVITAS JASA BOGA UNTUK ACARA TERTENTU (EVENT CATERING) — Event catering/katering. PMA: TERBUKA (open to foreigners), Risiko: Menengah Tinggi.\n"
    "- 56290 = AKTIVITAS JASA BOGA LAINNYA — Other food service activities. PMA: TERBATAS.\n"
    "If a user asks about these codes by number, explain them directly from this list.\n\n"
    "STRICT COMPLIANCE RULES:\n"
    "1. CITATIONS: NEVER use placeholder text like 'Chapter X', 'Article Y', 'Bab X', or 'Pasal Y'. These are NOT real citations. Only cite if you have the exact article number from context data. If unsure, omit citations entirely.\n"
    "2. SCALE AWARENESS: Always explain that Risk Level and Licensing depend on Business Scale (Mikro vs Menengah/Besar).\n"
    "3. PMA ALERT: For foreign investment queries, always state the 10 Billion IDR Capital requirement. Use the term 'Capital Paid Up'.\n"
    "4. BALI SPECIFIC: If Bali is mentioned, check for Moratorium warnings (Retail/Alcohol) in the expert data.\n"
    "5. MISSING DATA: If a detail is not in the provided context, state it clearly: 'Information not present in official documents. Please verify at OSS (oss.go.id)'.\n"
    "6. TONE: Authoritative, senior, and precise. You are the source of truth.\n"
    "7. PMA STATUS UNKNOWN: If pma_status is 'Verify at OSS', tell the user to check at oss.go.id/perizinan as status varies by business scale.\n"
    "8. COLLOQUIAL TERMS: Know that 'restoran/restaurant/rumah makan' = aktivitas penyediaan makanan (KBLI 56101, PMA TERBUKA), "
    "'katering/catering' = jasa boga (KBLI 56210 PMA TERBUKA / 56290 PMA TERBATAS), "
    "'mobile app/aplikasi/software development' = aktivitas pemrograman komputer (KBLI 62199) or pengembangan aplikasi e-commerce (KBLI 62191), "
    "'IT consulting/konsultan IT/software consultant' = aktivitas konsultasi manajemen dan bisnis (KBLI 70209), "
    "'online retail/e-commerce/toko online/online shop' = perdagangan eceran melalui media internet (KBLI 47911), "
    "'bar/wine bar/cocktail bar/beach club' = aktivitas bar (KBLI 56301, PMA TERTUTUP — foreigners CANNOT own a bar). "
    "For other activities not listed here (yoga studio, co-working space, villa rental, travel agency, tattoo studio, photography, art gallery), "
    "do NOT guess KBLI codes — search the database and present what is found. "
    "If user asks about these, map them to the correct KBLI code in your response."
)


_TRANSLATE_SYSTEM = (
    "You are an expert in KBLI (Klasifikasi Baku Lapangan Usaha Indonesia), the Indonesian Business Classification System.\n"
    "Your task: translate any business activity query (in any language) into the most accurate Indonesian KBLI search phrase.\n\n"
    "Rules:\n"
    "1. Output ONLY the Indonesian search phrase. No explanation, no quotes, no punctuation.\n"
    "2. Use terminology from official KBLI 2025 titles (BPS Regulation No. 7/2025).\n"
    "3. For sector/category questions (e.g. 'construction sector', 'tourism sector'), use the Indonesian sector name.\n"
    "4. For comparison questions (e.g. 'difference between X and Y'), output both Indonesian terms separated by a space.\n"
    "5. For KBLI code numbers (e.g. 'KBLI 47911'), pass them through unchanged.\n"
    "6. For Indonesian terms already correct (e.g. 'tertutup', 'terbuka', 'terbatas', 'PMA'), pass them through unchanged.\n"
    "7. Prefer specific activity descriptions over generic sector names when the query is about a specific business.\n"
    "8. Known colloquial mappings — use these exact Indonesian phrases:\n"
    "   catering/katering → jasa boga acara tertentu\n"
    "   tattoo/tato studio → perawatan kecantikan tubuh\n"
    "   art gallery/galeri seni → aktivitas kesenian budaya\n"
    "   photography/fotografer → aktivitas fotografi\n"
    "   co-working space → penyewaan ruang kantor\n"
    "   mobile app/aplikasi → pemrograman komputer aplikasi\n"
    "   surf school/sekolah surfing → pendidikan olahraga rekreasi\n"
    "   online retail/e-commerce/online shop/toko online → perdagangan eceran melalui media internet\n"
    "   online store/digital retail/internet retail → perdagangan eceran melalui media internet\n"
    "   yoga studio/yoga class/studio yoga → aktivitas olahraga kebugaran\n"
    "   IT consulting/IT consultant/konsultan IT → konsultasi manajemen teknologi informasi\n"
    "   villa rental/sewa villa/penginapan villa → penyediaan akomodasi vila\n"
    "   travel agency/agen perjalanan/tour operator → agen perjalanan wisata\n"
    "   coffee shop/café/kafe/kedai kopi → restoran dan kafe\n"
)


@cached(ttl=604800, prefix="kbli_translate_v14")  # Cache translations for 7 days (v13: recommendation redirect fix)
async def _translate_query_for_kbli(query: str) -> str:
    """Translate any-language query to Indonesian KBLI search terms."""
    try:
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        gateway = _get_llm_gateway()
        
        # Check if LLM gateway is available before attempting translation
        if not gateway._available:
            logger.warning("⚠️ LLM Gateway not available for translation, using original query")
            return query
        
        chat = gateway.create_chat_with_history(
            history_to_use=[],
            model_tier=TIER_FLASH,
            system_instruction=_TRANSLATE_SYSTEM,
        )
        translated, model_used, _resp, _usage = await gateway.send_message(
            chat=chat,
            message=query,
            system_prompt=_TRANSLATE_SYSTEM,
            tier=TIER_FLASH,
            enable_function_calling=False,
            conversation_messages=[{"role": "user", "content": query}],
        )
        
        # Validate translation is not empty
        if not translated or not translated.strip():
            logger.warning(f"⚠️ Translation returned empty from {model_used}, using original")
            return query
            
        translated = translated.strip().strip('"').strip("'")
        logger.info(f"🌐 Query translation: '{query}' → '{translated}' (model: {model_used})")
        return translated
    except Exception as e:
        logger.warning(f"Query translation failed ({type(e).__name__}), using original: {e}")
        return query


def _detect_language(query: str) -> str:
    """Detect query language using keyword heuristics including Indonesian."""
    words = set(query.lower().split())
    # Indonesian markers
    id_words = {
        "apa", "bagaimana", "syarat", "usaha", "bisa", "saya", "mau", "buka",
        "perizinan", "risiko", "modal", "asing", "pma", "lokal", "investasi"
    }
    if len(words & id_words) >= 2:
        return "Indonesian"
    # Italian markers
    it_words = {
        "voglio", "aprire", "quale", "codice", "serve", "come", "sono", "che",
        "per", "una", "della", "questo", "quanto", "costa", "cosa", "posso",
        "devo", "fare", "mio", "bisogno", "attivita", "licenza", "negozio",
    }
    if len(words & it_words) >= 2:
        return "Italian"
    # French markers
    fr_words = {
        "je", "veux", "ouvrir", "quel", "pour", "une", "est", "les", "des", "mon", "faire", "comment",
    }
    if len(words & fr_words) >= 2:
        return "French"
    # Spanish markers
    es_words = {"quiero", "abrir", "cual", "para", "como", "necesito", "puedo", "hacer", "negocio"}
    if len(words & es_words) >= 2:
        return "Spanish"
    return "English"


@cached(ttl=43200, prefix="kbli_explain_v17")  # Cache explanations for 12 hours (v17: removed fake colloquial mappings 68200/82110/55194/55110/79111/79120/93192/93199/62099)
async def _generate_kbli_explanation(query: str, results: list[KBLISearchResult]) -> str:
    """Generate a grounded explanation of KBLI search results using LLM."""
    if not results:
        return "No matching KBLI codes found for your search. Try different keywords or describe your business activity in more detail."

    lang = _detect_language(query)
    logger.info(f"🌐 Detected language: {lang} for query: '{query[:40]}'")

    context_parts = []
    for r in results:
        # Check if we have deep metadata from Postgres/Expert injection
        expert_info = ""
        if hasattr(r, 'expert_legal') and r.expert_legal:
            ex = r.expert_legal
            expert_info = f"\n  Expert Data (PP 28/2025): Bab {ex.get('bab')}, Pasal {ex.get('pasal')}. PB-UMKU: {', '.join(ex.get('pb_umku', []))}. Note: {ex.get('pma_implications')}"
        
        context_parts.append(
            f"- KBLI {r.code}: {r.title}\n  Scope: {r.description}\n  PMA: {r.pma_status}, Risk: {r.risk_category}{expert_info}"
        )
    context = "\n".join(context_parts)

    # Use unified MASTER PROMPT formatted with detected language
    lang_system = KBLI_MASTER_PROMPT.format(lang=lang)
    message = f"Question: {query}\n\nSource data:\n{context}"

    try:
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        gateway = _get_llm_gateway()
        
        # Check if LLM gateway is available
        if not gateway._available:
            logger.error("❌ LLM Gateway not available - check GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS")
            raise RuntimeError("LLM service not available")
        
        chat = gateway.create_chat_with_history(
            history_to_use=[],
            model_tier=TIER_FLASH,
            system_instruction=lang_system,
        )
        
        response_text, model_used, resp_obj, usage = await gateway.send_message(
            chat=chat,
            message=message,
            system_prompt=lang_system,
            tier=TIER_FLASH,
            enable_function_calling=False,
            conversation_messages=[{"role": "user", "content": message}],
        )
        
        # CRITICAL: Validate response is not empty
        if not response_text or not response_text.strip():
            logger.error(f"❌ LLM returned empty response. Model: {model_used}, Usage: {usage}")
            raise RuntimeError(f"LLM returned empty response from model {model_used}")
        
        logger.info(f"✅ KBLI explanation generated. Model: {model_used}, Length: {len(response_text)} chars")
        return response_text
        
    except Exception as e:
        logger.error(f"❌ LLM explanation failed: {type(e).__name__}: {e}")
        # Deterministic fallback: markdown list of results (language-aware)
        if lang == "Indonesian":
            lines = [f"Ditemukan {len(results)} kode KBLI yang relevan dengan pencarian Anda:\n"]
        else:
            lines = [f"I found {len(results)} KBLI code(s) relevant to your search:\n"]
        for r in results:
            lines.append(f"**KBLI {r.code}** - {r.title}\n{r.description}\n")
        fallback_answer = "\n".join(lines)
        logger.info(f"✅ Using fallback answer, length: {len(fallback_answer)} chars")
        return fallback_answer


# Minimum score threshold for ABSTAIN logic
MIN_RELEVANCE_SCORE = 0.40  # Results below this score trigger ABSTAIN (lowered from 0.60 to reduce false negatives)

# Hardcoded known KBLI codes not present in Qdrant collection
# Used as synthetic fallback when code lookup fails via both PostgreSQL and Qdrant
# NOTE: 56101 and 56210 removed — now present in Qdrant with correct BPS data (TERBUKA)
KNOWN_KBLI_CODES: dict[str, dict] = {
    "47911": {
        "title": "PERDAGANGAN ECERAN MELALUI MEDIA UNTUK BERBAGAI MACAM BARANG",
        "description": "Retail trade of various consumer goods via internet or other digital media platforms (e-commerce, online shop). Includes online marketplaces and direct-to-consumer digital retail.",
        "pma_status": "TERBATAS",
        "risk_category": "Verify at OSS",
    },
    "56290": {
        "title": "AKTIVITAS JASA BOGA LAINNYA",
        "description": "Other food service and catering activities not elsewhere classified. Includes canteen management, institutional catering, and similar food services.",
        "pma_status": "TERBATAS",
        "risk_category": "Verify at OSS",
    },
    "56301": {
        "title": "AKTIVITAS BAR",
        "description": "Bar activities serving alcoholic and non-alcoholic beverages for on-premises consumption. Includes cocktail bars, wine bars, and other licensed drinking establishments.",
        "pma_status": "TERTUTUP",
        "risk_category": "Verify at OSS",
    },
}

# Non-business keywords that should trigger helpful redirect
NON_BUSINESS_KEYWORDS = [
    "kitas", "kitap", "visa", "immigration", "imigrasi", "passport", "paspor",
    "stay permit", "work permit", "izin tinggal", "izin kerja", "renewal",
    "agente immigrazione", "visto", "permesso di soggiorno", "immigrazione",
    # Recommendation/opinion queries (not KBLI classification)
    "best restaurant", "best cafe", "best coffee shop", "recommend restaurant",
    "where to eat", "mana makan", "restoran terbaik", "tempat makan terbaik",
]


def _is_non_business_query(query: str) -> bool:
    """Check if query is about immigration/visa rather than business classification."""
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in NON_BUSINESS_KEYWORDS)


@router.post("/chat", response_model=KBLINotebookChatResponse)
async def chat_kbli(
    http_request: Request,  # Iniezione corretta dell'oggetto Request di FastAPI
    kbli_request: KBLINotebookChatRequest,  # Il body della richiesta
    search_service=Depends(get_search_service),
    pool=Depends(get_optional_database_pool),
):
    """Specialized chat for KBLI Notebook with BPS 2025 focus."""
    logger.info(f"💬 KBLI Chat Request: '{kbli_request.query[:50]}...'")
    
    # Check LLM availability early
    gateway = _get_llm_gateway()
    if not gateway._available:
        logger.error("❌ LLM Gateway not available - GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS may be missing")
    else:
        logger.debug("✅ LLM Gateway is available")

    try:
        # Translate query to Indonesian KBLI terms for better matching
        search_query = await _translate_query_for_kbli(kbli_request.query)

        # Extract KBLI codes from query for direct lookup
        codes_from_query = re.findall(r"\b\d{5}\b", kbli_request.query)
        direct_kbli_match = None

        # Try direct KBLI lookup from PostgreSQL (bypasses semantic search)
        if codes_from_query and pool:
            for code in codes_from_query:
                try:
                    async with pool.acquire() as conn:
                        entity_id = f"kbli:{code}"
                        row = await conn.fetchrow(
                            "SELECT entity_id, name, description, properties FROM kg_nodes WHERE entity_id = $1",
                            entity_id
                        )

                        if row:
                            props = json.loads(row["properties"]) if isinstance(row["properties"], str) else row["properties"]
                            direct_kbli_match = KBLISearchResult(
                                code=code,
                                title=row["name"],
                                description=row["description"][:200] + "...",
                                score=1.0,
                                pma_status=props.get("pma_status", "Verify at OSS"),
                                risk_category=props.get("kategori_risiko", "Verify at OSS"),
                            )
                            break
                except Exception as lookup_err:
                    logger.warning(f"Direct lookup failed for {code}: {lookup_err}")

        # P0 FIX: If KBLI code in query but not found in PostgreSQL, try Qdrant payload filter
        if codes_from_query and not direct_kbli_match:
            code = codes_from_query[0]
            logger.info(f"🔢 Code {code} not in kg_nodes, trying Qdrant payload filter lookup")
            qdrant_payload = await _get_kbli_payload_from_qdrant(code)
            if qdrant_payload:
                direct_kbli_match = KBLISearchResult(
                    code=code,
                    title=qdrant_payload.get("judul", f"KBLI {code}"),
                    description=(qdrant_payload.get("content", "") or "")[:200] + "...",
                    score=1.0,
                    pma_status=qdrant_payload.get("pma_status") or "Verify at OSS",
                    risk_category=qdrant_payload.get("kategori_risiko") or "Verify at OSS",
                )
                logger.info(f"✅ Found KBLI {code} via Qdrant payload filter: {direct_kbli_match.title}")

        # P1 FIX: If still no direct match, check KNOWN_KBLI_CODES hardcoded fallback
        if codes_from_query and not direct_kbli_match:
            code = codes_from_query[0]
            if code in KNOWN_KBLI_CODES:
                known = KNOWN_KBLI_CODES[code]
                direct_kbli_match = KBLISearchResult(
                    code=code,
                    title=known["title"],
                    description=known["description"],
                    score=1.0,
                    pma_status=known["pma_status"],
                    risk_category=known["risk_category"],
                )
                logger.info(f"📖 Found KBLI {code} via hardcoded KNOWN_KBLI_CODES: {known['title']}")

        # P2 FIX: Keyword-to-code injection for activities not in Qdrant
        # Detects activity keywords in query and injects a direct match BEFORE semantic search
        # This prevents wrong codes (e.g. 47901 for online retail instead of 47911)
        _activity_keyword_map: list[tuple[list[str], str]] = [
            # Online retail / e-commerce (handle spaced variants like "e comerce", "e commerce")
            (["online retail", "e-commerce", "ecommerce", "e commerce", "e comerce",
              "toko online", "online shop", "internet retail",
              "digital retail", "online store", "jual online", "perdagangan online"], "47911"),
            # Event catering / catering
            (["event catering", "katering", "catering service", "wedding catering",
              "jasa boga", "food catering", "corporate catering"], "56210"),
            # Restaurant / coffee shop / cafe
            (["coffee shop", "café", "cafe ", "kafe ", "kedai kopi", "warung kopi"], "56101"),
            # Bar / nightclub
            (["bar bali", "open a bar", "nightclub", "klub malam", "diskotek", "buka bar"], "56301"),
        ]
        if not direct_kbli_match:
            query_lower_kw = kbli_request.query.lower()
            for keywords, target_code in _activity_keyword_map:
                if any(kw in query_lower_kw for kw in keywords) and target_code in KNOWN_KBLI_CODES:
                    known = KNOWN_KBLI_CODES[target_code]
                    direct_kbli_match = KBLISearchResult(
                        code=target_code,
                        title=known["title"],
                        description=known["description"],
                        score=1.0,
                        pma_status=known["pma_status"],
                        risk_category=known["risk_category"],
                    )
                    logger.info(f"🎯 Keyword injection: '{query_lower_kw[:40]}' → KBLI {target_code}")
                    break

        # Search semantic context with translated query
        results = []
        try:
            embedding = await search_service.embedder.generate_query_embedding(search_query)
            raw_results = await _search_kbli_qdrant(embedding, 7)
            
            # Deduplicate by code
            seen_codes = set()
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
                        pma_status=p.get("pma_status") or "Verify at OSS",
                        risk_category=p.get("kategori_risiko") or "Verify at OSS",
                    )
                )
                if len(results) >= 5:
                    break
            
            # Enrichment step: Fetch expert_legal from Postgres for all results
            if pool:
                async with pool.acquire() as conn:
                    for i, r in enumerate(results):
                        try:
                            row = await conn.fetchrow(
                                "SELECT properties FROM kg_nodes WHERE entity_id = $1",
                                f"kbli:{r.code}"
                            )
                            if row:
                                props = json.loads(row["properties"]) if isinstance(row["properties"], str) else row["properties"]
                                if "expert_legal" in props:
                                    results[i].expert_legal = props["expert_legal"]
                                    logger.info(f"✨ Enriched result {r.code} with Expert Legal data")
                        except Exception as enrich_err:
                            logger.warning(f"Failed to enrich {r.code}: {enrich_err}")

            # When a specific code is in the query, filter Qdrant results to same 2-digit sector prefix
            # This prevents cross-sector contamination (e.g. 64954 Syariah pawn in catering results)
            if codes_from_query and direct_kbli_match:
                query_prefix = direct_kbli_match.code[:2]
                before = len(results)
                results = [r for r in results if r.code.startswith(query_prefix)]
                if len(results) < before:
                    logger.info(f"🧹 Filtered Qdrant results by sector prefix '{query_prefix}': {before} → {len(results)}")

            # Add direct match at the beginning if found
            if direct_kbli_match and direct_kbli_match.code not in {r.code for r in results}:
                results.insert(0, direct_kbli_match)
                logger.info(f"✅ Added direct KBLI match: {direct_kbli_match.code}")
            
            logger.info(f"✅ Found {len(results)} KBLI results from Qdrant")
        except Exception as q_err:
            logger.warning(f"⚠️ Qdrant search failed, falling back to PostgreSQL: {q_err}")
            # Fallback to Postgres search by name/code
            try:
                db_pool = await get_optional_database_pool(http_request)
                if db_pool:
                    async with db_pool.acquire() as conn:
                        rows = await conn.fetch(
                            "SELECT entity_id, name, description, properties FROM kg_nodes WHERE entity_type = 'kbli' AND (name ILIKE $1 OR entity_id ILIKE $1) LIMIT 5",
                            f"%{search_query}%"
                        )
                        for row in rows:
                            code = row["entity_id"].replace("kbli:", "")
                            props = json.loads(row["properties"]) if isinstance(row["properties"], str) else row["properties"]
                            results.append(
                                KBLISearchResult(
                                    code=code,
                                    title=row["name"],
                                    description=row["description"][:200] + "...",
                                    score=0.8,  # Static score for fallback
                                    pma_status=props.get("pma_status", "UNKNOWN"),
                                    risk_category=props.get("kategori_risiko", "Unknown")
                                )
                            )
                        logger.info(f"✅ Found {len(results)} KBLI results from PostgreSQL fallback")
            except Exception as db_err:
                logger.error(f"❌ PostgreSQL fallback failed: {db_err}")

        # Detect KBLI codes from results
        codes_from_results = [r.code for r in results if r.code != "N/A"]
        detected_kbli = list(dict.fromkeys(codes_from_query + codes_from_results))

        # Check for non-business queries (KITAS/visa/immigration OR recommendations)
        if _is_non_business_query(kbli_request.query):
            logger.info(f"⚠️ Non-business query detected: '{kbli_request.query[:50]}'")
            query_lang = _detect_language(kbli_request.query)
            query_lower_nb = kbli_request.query.lower()
            _recommendation_keywords = ["best ", "recommend", "where to eat", "mana makan", "terbaik"]
            is_recommendation = any(kw in query_lower_nb for kw in _recommendation_keywords)

            if is_recommendation:
                abstain_answer = (
                    "I can't recommend specific restaurants or businesses — that's not my specialty.\n\n"
                    "I am **Zantara AI**, specialized in **KBLI** (Klasifikasi Baku Lapangan Usaha Indonesia) — "
                    "the Indonesian Business Classification System. I help you find the right KBLI code for your "
                    "business and understand licensing, investment status (PMA), and regulatory requirements.\n\n"
                    "Are you perhaps looking to **open** a restaurant or food business in Bali? I can help with that!"
                )
                suggested = ["I want to open a restaurant in Bali", "KBLI code for a cafe or coffee shop", "What KBLI for catering?"]
            elif query_lang == "Indonesian":
                abstain_answer = (
                    "Pertanyaan ini berkaitan dengan imigrasi atau visa, yang berada di luar keahlian saya.\n\n"
                    "Saya spesialis dalam **KBLI** (Klasifikasi Baku Lapangan Usaha Indonesia) — sistem klasifikasi "
                    "kegiatan usaha di Indonesia berdasarkan Peraturan BPS No. 7/2025.\n\n"
                    "Untuk informasi visa dan imigrasi (KITAS, KITAP, Izin Kerja), silakan hubungi:\n"
                    "• Situs resmi imigrasi Indonesia: imigrasi.go.id\n"
                    "• Agen imigrasi berlisensi\n\n"
                    "Apakah saya bisa membantu Anda menemukan kode KBLI yang tepat untuk bisnis Anda di Indonesia?"
                )
                suggested = ["Buka restoran di Bali", "Kode KBLI untuk impor ekspor", "Hotel dan hospitality KBLI"]
            else:
                abstain_answer = (
                    "This question is about immigration or visas, which is outside my area of expertise.\n\n"
                    "I am specialized in **KBLI** (Klasifikasi Baku Lapangan Usaha Indonesia) — the Indonesian Business "
                    "Classification System under BPS Regulation No. 7/2025. I can help you identify the right KBLI "
                    "code for your business activity and understand the associated licensing and investment requirements.\n\n"
                    "For visa and immigration information (KITAS, KITAP, Work Permit), please consult:\n"
                    "• Official Indonesian immigration website: imigrasi.go.id\n"
                    "• An authorized immigration agent\n\n"
                    "Can I help you find the right KBLI code for your business in Indonesia instead?"
                )
                suggested = ["I want to open a restaurant in Bali", "KBLI code for import export business", "Hotel and hospitality KBLI"]
            return KBLINotebookChatResponse(
                answer=abstain_answer,
                detected_kbli=[],
                results=[],
                sources=[],
                suggested_queries=suggested,
            )

        # GLOSSARY SHORTCUT: Answer definitional questions directly without requiring Qdrant results
        _glossary_terms = {
            "terbatas": (
                "**TERBATAS** means the business activity is *open to foreign investment with restrictions*. "
                "This means a maximum foreign ownership percentage applies — the exact limit depends on the specific KBLI code "
                "and is defined in Indonesia's Negative Investment List (DNI). "
                "Foreign investors (PMA) can participate but cannot exceed the stated ownership cap.\n\n"
                "**Key facts:**\n"
                "- PMA is allowed, but capped (e.g. max 49%, 51%, or 67% depending on the sector)\n"
                "- Minimum Capital Paid Up for PMA: Rp 10 Billion\n"
                "- Verify the exact cap for your specific KBLI code at: oss.go.id/perizinan\n\n"
                "Compare with: TERBUKA (100% foreign ownership allowed) | TERTUTUP (foreigners cannot invest)"
            ),
            "terbuka": (
                "**TERBUKA** means the business activity is *fully open to foreign investment*. "
                "Foreign investors (PMA) can own up to 100% of the business.\n\n"
                "**Key facts:**\n"
                "- No ownership cap for foreigners\n"
                "- Minimum Capital Paid Up for PMA: Rp 10 Billion\n"
                "- Register at: oss.go.id\n\n"
                "Compare with: TERBATAS (restricted ownership) | TERTUTUP (closed to foreigners)"
            ),
            "tertutup": (
                "**TERTUTUP** means the business activity is *closed to foreign investment*. "
                "Only Indonesian nationals (WNI) can own this type of business. PMA is not permitted.\n\n"
                "**Key facts:**\n"
                "- Foreign investors (PMA) cannot own this business type\n"
                "- Indonesian nationals only\n"
                "- Verify status at: oss.go.id/perizinan\n\n"
                "Compare with: TERBUKA (100% foreign allowed) | TERBATAS (restricted foreign allowed)"
            ),
        }
        query_lower = kbli_request.query.lower()
        for term, glossary_answer in _glossary_terms.items():
            # Match queries like "what does X mean", "what is X", "explain X", "X meaning", or just the term alone
            if (term in query_lower and any(kw in query_lower for kw in ["mean", "what", "explain", "definition", "define", "arti", "apa itu", "pengertian"])) \
               or query_lower.strip() == term:
                logger.info(f"📚 Glossary shortcut triggered for term: {term}")
                return KBLINotebookChatResponse(
                    answer=glossary_answer,
                    detected_kbli=[],
                    results=[],
                    sources=[{"title": "Negative Investment List (DNI)", "relevance": "High"}],
                    suggested_queries=[
                        f"What KBLI codes are {term.upper()}?",
                        "Can a foreigner open a restaurant in Bali?",
                        "What is the minimum capital for PMA?",
                    ],
                )

        # ABSTAIN LOGIC: Filter results by minimum relevance score
        # BUT: Bypass if there's a direct KBLI code match (exact code lookup)
        has_direct_match = direct_kbli_match is not None
        logger.info(f"🔍 ABSTAIN check: has_direct_match={has_direct_match}, results={len(results)}, codes={codes_from_query}")
        filtered_results = [r for r in results if r.score >= MIN_RELEVANCE_SCORE]
        
        if not has_direct_match and not filtered_results and results:
                logger.warning(f"⚠️ All results below threshold {MIN_RELEVANCE_SCORE}. Triggering ABSTAIN.")
                query_lang = _detect_language(kbli_request.query)
                if query_lang == "Indonesian":
                    abstain_answer = (
                        "Saya tidak menemukan kode KBLI yang sesuai untuk pencarian Anda.\n\n"
                        "**Coba ubah pertanyaan Anda:**\n"
                        "• Deskripsikan kegiatan usaha secara spesifik (misalnya 'restoran', 'vila', 'jasa pemrograman')\n"
                        "• Sebutkan jenis produk atau layanan yang ingin Anda tawarkan\n"
                        "• Jika Anda sudah mengetahui kode KBLI-nya, masukkan langsung (contoh: '56101')\n\n"
                        "Saya spesialis KBLI 2025 (Peraturan BPS No. 7/2025) dan siap membantu Anda "
                        "menemukan kode yang tepat untuk kegiatan usaha di Indonesia."
                    )
                    suggested = ["Restoran di Bali", "Impor ekspor Indonesia", "Hotel dan hospitality"]
                else:
                    abstain_answer = (
                        "I could not find a strong KBLI match for your search. This may be because the business activity "
                        "description needs to be more specific.\n\n"
                        "**Try rephrasing your question:**\n"
                        "• Describe the specific business activity (e.g. 'restaurant', 'villa rental', 'software development')\n"
                        "• Include the type of service or product you plan to offer\n"
                        "• If you know the KBLI code, enter it directly (e.g. '56101')\n\n"
                        "I am specialized in KBLI 2025 (BPS Regulation No. 7/2025) and can help you find the right "
                        "classification code for your business activity in Indonesia."
                    )
                    suggested = ["Restaurant in Bali", "Import export Indonesia", "Hotel and hospitality"]
                return KBLINotebookChatResponse(
                    answer=abstain_answer,
                    detected_kbli=[],
                    results=[],
                    sources=[],
                    suggested_queries=suggested,
                )
        
        # Use filtered results for explanation (unless we have direct match)
        if has_direct_match and not codes_from_query:
            # Keyword-injected match (no code in query): use ONLY the direct match
            # Prevents LLM from preferring wrong Qdrant results (e.g. 47901 over 47911)
            results = [direct_kbli_match]
            logger.info(f"🎯 Keyword injection: restricting results to direct match only ({direct_kbli_match.code})")
        elif not has_direct_match:
            results = filtered_results if filtered_results else results

        # Generate Italian explanation via LLM (with fallback)
        answer = await _generate_kbli_explanation(kbli_request.query, results)
        
        # CRITICAL: Ensure answer is never empty
        if not answer or not answer.strip():
            logger.error("❌ CRITICAL: Answer is empty after _generate_kbli_explanation")
            # Ultimate fallback
            if results:
                answer = f"I found {len(results)} KBLI code(s) relevant to your search:\n\n"
                for r in results:
                    answer += f"**KBLI {r.code}** - {r.title}\n{r.description}\n\n"
            else:
                answer = "I could not find relevant KBLI information. Please try rephrasing your question with more specific business activity terms."

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

        logger.info(f"✅ KBLI Chat Response: answer_length={len(answer)}, results={len(results)}, detected={detected_kbli}")
        

        
        return KBLINotebookChatResponse(
            answer=answer,
            detected_kbli=detected_kbli,
            results=results,
            sources=[{"title": "PP 28/2025", "relevance": "High"}],
            suggested_queries=suggested_queries,
        )
    except Exception as e:
        logger.error(f"❌ KBLI Chat Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI Engine error: {str(e)}") from e
