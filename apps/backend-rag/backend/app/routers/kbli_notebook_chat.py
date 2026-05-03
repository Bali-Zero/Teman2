"""
KBLI Notebook Chat API - LLM-powered chat, translation, explanation

Split from kbli_notebook.py for maintainability.
Provides: LLM gateway singleton, query translation, language detection,
KBLI explanation generation, multi-domain routing, chat endpoint.
"""

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.dependencies import (
    get_optional_database_pool,
    get_search_service,
)
from backend.app.routers.kbli_notebook import (
    KBLINotebookChatRequest,
    KBLINotebookChatResponse,
    KBLISearchResult,
    _get_kbli_payload_from_qdrant,
    _payload_value,
    _resolve_embedding,
    _search_kbli_qdrant,
)
from backend.core.cache import cached
from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kbli-notebook", tags=["KBLI Notebook Chat"])

_llm_gateway_instance = None


def _get_llm_gateway() -> Any:
    global _llm_gateway_instance
    if _llm_gateway_instance is None:
        from backend.services.rag.agentic.llm_gateway import LLMGateway

        _llm_gateway_instance = LLMGateway()
    return _llm_gateway_instance


KBLI_MASTER_PROMPT = (
    "You are Zantara AI, helping people navigate Indonesian business regulations. Your expertise is KBLI 2025 (Indonesian Business Classification), and you can also answer questions about visa, legal, and tax matters when relevant.\n\n"
    "LANGUAGE RULES:\n"
    "- Respond in the user's language: {lang}\n"
    "- If Indonesian query → answer in Indonesian. If English → answer in English.\n"
    "- Never respond in Italian, French, or Spanish unless explicitly asked.\n\n"
    "YOUR APPROACH:\n"
    "- Be conversational, clear, and helpful — like talking to a knowledgeable friend, not reading a legal document.\n"
    "- Start with a direct answer to the user's question, then provide supporting details.\n"
    "- Use the full context data provided — don't leave out important licensing, PMA status, or requirements information.\n"
    "- Explain trade-offs, options, and practical next steps when relevant.\n\n"
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
    "ACCURACY GUIDELINES:\n"
    "1. Use only real citations from the context data. Don't make up placeholder references like 'Chapter X' or 'Bab Y'.\n"
    "2. Always explain how licensing and risk levels vary by business scale (Mikro/Kecil/Menengah/Besar) — this is critical.\n"
    "3. For foreign investment (PMA) questions, mention the Rp 10 Billion minimum Capital Paid Up requirement when relevant.\n"
    "4. If data is missing from context, say so clearly: 'This detail isn't in the official documents — please verify at oss.go.id'.\n"
    "5. When PMA status shows 'Verify at OSS', explain that it varies by business scale and they should check oss.go.id/perizinan.\n"
    "8. COLLOQUIAL TERMS: Know that 'restoran/restaurant/rumah makan' = aktivitas penyediaan makanan (KBLI 56101, PMA TERBUKA), "
    "'katering/catering' = jasa boga (KBLI 56210 PMA TERBUKA / 56290 PMA TERBATAS), "
    "'mobile app/aplikasi/software development' = aktivitas pemrograman komputer (KBLI 62199) or pengembangan aplikasi e-commerce (KBLI 62191), "
    "'IT consulting/konsultan IT/software consultant' = aktivitas konsultasi manajemen dan bisnis (KBLI 70209), "
    "'online retail/e-commerce/toko online/online shop' = perdagangan eceran melalui media internet (KBLI 47911), "
    "'co-working space/ruang kerja bersama/shared office' = pengelolaan gedung perkantoran (KBLI 68127), "
    "'villa/sewa villa/villa rental' = aktivitas vila (KBLI 55203 — rumah pribadi disewakan kepada wisatawan), "
    "'homestay/rumah sewa harian' = aktivitas rumah tinggal sewa (KBLI 55201), "
    "'hostel/youth hostel' = aktivitas hostel remaja (KBLI 55202) or akomodasi jangka pendek lainnya (KBLI 55209), "
    "'glamping/bungalow/cottage/glamping/treehouse/cabin' = aktivitas penyediaan akomodasi jangka pendek lainnya (KBLI 55209), "
    "'hotel bintang 5/five star hotel' = KBLI 55101, 'hotel bintang 4' = KBLI 55102, 'hotel bintang 3' = KBLI 55103, "
    "'platform booking akomodasi/intermediasi akomodasi' = aktivitas jasa intermediasi akomodasi (KBLI 55400), "
    "'yoga studio/pilates/studio kebugaran/fitness studio' = fasilitas pusat kebugaran (KBLI 93116), "
    "'gym/fitness center/pusat kebugaran' = fasilitas pusat kebugaran (KBLI 93116), "
    "'surf school/sekolah surfing/olahraga air' = pengelolaan fasilitas olahraga lainnya (KBLI 93119), "
    "'gambling/casino/perjudian' = aktivitas perjudian dan pertaruhan (KBLI 92000 — NOTE: heavily restricted in Indonesia), "
    "'travel agency/agen perjalanan' = aktivitas agen perjalanan (KBLI 79110 — intermediary selling packages), "
    "'tour operator/biro perjalanan/tour organizer' = aktivitas biro perjalanan wisata (KBLI 79121 — organizes and sells tours directly), "
    "'tour guide/pemandu wisata/pramuwisata' = jasa pramuwisata (KBLI 79903), "
    "'photography/foto studio/fotografer/wedding photographer/commercial photo' = aktivitas fotografi lainnya (KBLI 74209), "
    "'drone photography/aerial photo/foto udara' = aktivitas fotografi udara (KBLI 74201), "
    "'graphic design/desain grafis/logo design/branding' = aktivitas desain grafis/komunikasi visual (KBLI 74192), "
    "'interior design/desain interior' = aktivitas desain interior (KBLI 74191), "
    "'fashion design/desain mode/desain tekstil' = aktivitas desain tekstil mode dan garmen (KBLI 74113), "
    "'bar/wine bar/cocktail bar/beach club' = aktivitas bar (KBLI 56301, PMA TERTUTUP — foreigners CANNOT own a bar), "
    "'salon/hair salon/barbershop/pangkas rambut/hair studio' = aktivitas penataan dan pangkas rambut (KBLI 96210), "
    "'beauty salon/nail studio/nail art/eyelash extension/brow studio/wax studio/make-up artist/MUA/perawatan kecantikan' = aktivitas perawatan kecantikan (KBLI 96220), "
    "'spa/day spa/wellness/spa harian/sauna/steam bath/pemandian uap/solarium' = aktivitas SPA harian sauna dan pemandian uap (KBLI 96230), "
    "'laundry/dry cleaning/cuci pakaian/laundromat' = aktivitas pencucian dan pembersihan produk tekstil (KBLI 96100), "
    "'art gallery/galeri seni komersial/commercial art gallery/art shop' = perdagangan eceran khusus barang kesenian dan rekreasi (KBLI 47690 — includes commercial art gallery selling paintings/sculptures/art), "
    "'art venue/art center/performance space/venue kesenian/pusat kebudayaan' = aktivitas operasional tempat dan fasilitas kesenian (KBLI 90310 — NOTE: 90310 exists in BPS 2025 but verify in OSS as it may not have PMA data). "
    "'tattoo studio permanente/permanent tattoo/tattoo artist' = IMPORTANT: BPS 2025 does NOT have a dedicated KBLI code for permanent tattoo. "
    "KBLI 96900 (AKTIVITAS JASA PERORANGAN LAINNYA YTDL) covers only temporary henna/biological ink decoration — NOT permanent tattoo. "
    "Tell the user: permanent tattoo studios in Indonesia operate under KBLI 96900 by convention, but must verify with OSS as there is no dedicated code. "
    "If user asks about these, map them to the correct KBLI code in your response.\n\n"
    "\n"
    "RESPONSE STRUCTURE:\n"
    "Write a complete, helpful answer that covers:\n"
    "- The main KBLI code(s) that answer the user's question\n"
    "- PMA status (TERBUKA/TERBATAS/TERTUTUP) and what it means for foreign investors\n"
    "- Key requirements, licensing steps, or business scale considerations\n"
    "- Practical guidance or next steps when relevant\n"
    "\n"
    "DO NOT append lists of related KBLI codes at the end (like 'Verify at OSS KBLI 56101...') — the UI shows those separately.\n"
    "Only mention additional codes if they directly clarify the answer (e.g., comparing restaurant vs catering).\n"
    "Be thorough but conversational — explain everything they need to know without being robotic."
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
    "   tattoo permanente/permanent tattoo/tattoo studio → jasa perorangan lainnya (NOTE: no dedicated BPS code)\n"
    "   henna/tato henna/temporary tattoo → jasa perorangan lainnya\n"
    "   salon/hair salon/barbershop/pangkas rambut → aktivitas penataan dan pangkas rambut\n"
    "   beauty salon/nail studio/nail art/eyelash extension/brow studio/MUA → aktivitas perawatan kecantikan\n"
    "   spa/day spa/wellness spa/spa harian/sauna/steam bath → aktivitas SPA harian sauna pemandian uap\n"
    "   laundry/dry cleaning/cuci pakaian → aktivitas pencucian pembersihan tekstil\n"
    "   art gallery/galeri seni komersial/commercial art gallery → perdagangan eceran barang kesenian\n"
    "   art venue/art center/venue pertunjukan/pusat kebudayaan → aktivitas operasional tempat fasilitas kesenian\n"
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


@cached(
    ttl=604800, prefix="kbli_translate_v14",
)  # Cache translations for 7 days (v13: recommendation redirect fix)
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
        "apa",
        "bagaimana",
        "syarat",
        "usaha",
        "bisa",
        "saya",
        "mau",
        "buka",
        "perizinan",
        "risiko",
        "modal",
        "asing",
        "pma",
        "lokal",
        "investasi",
    }
    if len(words & id_words) >= 2:
        return "Indonesian"
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


async def _generate_kbli_explanation_gemini(
    query: str, results: list[KBLISearchResult], parent_docs: dict[str, str] = None,
) -> str:
    """Generate KBLI explanation using Gemini Flash - Fast, Cost-Effective.

    Uses Google Gemini 2.0 Flash with a simplified prompt focused on
    clarity and accuracy.
    """
    logger.info("🤖 Using Gemini Flash for KBLI explanation")
    return await _generate_kbli_explanation(query, results, parent_docs)


@cached(
    ttl=43200, prefix="kbli_explain_v25",
)  # Cache explanations for 12 hours (v25: 96100 risk scale-dependent: Rendah Mikro-Menengah / Tinggi Besar; all sector 96 PMA=TERBUKA)
async def _generate_kbli_explanation(
    query: str, results: list[KBLISearchResult], parent_docs: dict[str, str] = None,
) -> str:
    """Generate a grounded explanation of KBLI search results using LLM.

    Args:
        query: User query
        results: Search results with codes and metadata
        parent_docs: Dict mapping KBLI code -> full parent document content from kbli_documents table
    """
    if not results:
        return "No matching KBLI codes found for your search. Try different keywords or describe your business activity in more detail."

    lang = _detect_language(query)
    logger.info(f"🌐 Detected language: {lang} for query: '{query[:40]}'")

    context_parts = []
    for r in results:
        # Check if we have deep metadata from Postgres/Expert injection
        expert_info = ""
        if hasattr(r, "expert_legal") and r.expert_legal:
            ex = r.expert_legal
            expert_info = f"\n  Expert Data (PP 28/2025): Bab {ex.get('bab')}, Pasal {ex.get('pasal')}. PB-UMKU: {', '.join(ex.get('pb_umku', []))}. Note: {ex.get('pma_implications')}"

        # Use full parent document content if available, otherwise fall back to truncated description
        if parent_docs and r.code in parent_docs:
            full_content = parent_docs[r.code]
            logger.debug(f"  Using full parent doc for {r.code}: {len(full_content)} chars")
            context_parts.append(
                f"- KBLI {r.code}: {r.title}\n  Full details:\n{full_content}{expert_info}",
            )
        else:
            logger.debug(f"  Using truncated description for {r.code}")
            context_parts.append(
                f"- KBLI {r.code}: {r.title}\n  Scope: {r.description}\n  PMA: {r.pma_status}, Risk: {r.risk_category}{expert_info}",
            )
    context = "\n".join(context_parts)

    # Use unified MASTER PROMPT formatted with detected language
    lang_system = KBLI_MASTER_PROMPT.format(lang=lang)

    # Build a structured, detailed message that guides comprehensive responses
    message = (
        f"User question: {query}\n\n"
        f"Relevant KBLI data from official sources (BPS 2025, PP 28/2025):\n{context}\n\n"
        f"Task: Write a comprehensive, conversational answer covering:\n\n"
        f"1. PRIMARY KBLI CODE(S): State the main code(s), full Indonesian name, and English translation\n"
        f"2. PMA STATUS: Explain TERBUKA/TERBATAS/TERTUTUP clearly and what it means for foreign investors\n"
        f"3. CAPITAL REQUIREMENTS: If PMA relevant, mention the Rp 10 Billion minimum paid-up capital\n"
        f"4. LICENSING & RISK: Explain how requirements vary by business scale (Mikro/Kecil/Menengah/Besar)\n"
        f"5. PRACTICAL GUIDANCE: Include next steps, where to register (OSS), or any Bali-specific considerations\n\n"
        f"Be thorough and use all the detailed information provided in the context data above. "
        f"Don't just summarize — explain what each requirement means and how it applies to their situation."
    )

    try:
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        gateway = _get_llm_gateway()

        # Check if LLM gateway is available
        if not gateway._available:
            logger.error(
                "❌ LLM Gateway not available - check GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS",
            )
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

        logger.info(
            f"✅ KBLI explanation generated. Model: {model_used}, Length: {len(response_text)} chars",
        )
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
MIN_RELEVANCE_SCORE = (
    0.40  # Results below this score trigger ABSTAIN (lowered from 0.60 to reduce false negatives)
)

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
    "47690": {
        "title": "PERDAGANGAN ECERAN KHUSUS BARANG KESENIAN DAN REKREASI YTDL",
        "description": "Retail trade of art, recreation and collectibles, including: recorded media, musical instruments and accessories, philately/numismatics/collectibles, commercial art gallery activities (selling paintings/sculptures). Also includes art supplies (beads, clay, canvas, oils, watercolors).",
        "pma_status": "TERBUKA",
        "risk_category": "Rendah",
    },
    "96210": {
        "title": "AKTIVITAS PENATAAN DAN PANGKAS RAMBUT",
        "description": "Hair salon and barbershop activities: hair washing, cutting, styling, coloring, perming, straightening; shaving and grooming beards/mustaches.",
        "pma_status": "TERBUKA",
        "risk_category": "Rendah",
    },
    "96220": {
        "title": "AKTIVITAS PERAWATAN KECANTIKAN DAN PERAWATAN KECANTIKAN LAINNYA",
        "description": "Beauty care activities not performed by doctors: nail studio (nail art, manicure/pedicure), eyelash studio (eyelash extension, lash lift), brow studio (sulam alis, brow lamination), wax studio, make-up artist (MUA), facial massage, skin tanning.",
        "pma_status": "TERBUKA",
        "risk_category": "Verify at OSS",
    },
    "96230": {
        "title": "AKTIVITAS SANTE PAR AQUA (SPA) HARIAN, SAUNA, DAN PEMANDIAN UAP",
        "description": "Day spa, sauna, steam bath activities providing wellness and beauty treatments combining traditional and modern holistic methods using water, massage with herbal preparations, aromatherapy, physical therapy. Turkish bath, solarium, slimming salon.",
        "pma_status": "TERBUKA",
        "risk_category": "Verify at OSS",
    },
    "96100": {
        "title": "AKTIVITAS PENCUCIAN DAN PEMBERSIHAN PRODUK TEKSTIL DAN BULU",
        "description": "Laundry and dry cleaning services: washing, ironing, dry cleaning of clothing and textiles including fur; pick-up and delivery; carpet and curtain cleaning; coin-operated laundromat; reusable diaper service. PMA: TERBUKA (open to foreigners, 100%). Risk level is SCALE-DEPENDENT: Mikro/Kecil/Menengah = Rendah (NIB only); Besar = Tinggi (NIB + Izin required).",
        "pma_status": "TERBUKA",
        "risk_category": "Rendah (Mikro/Kecil/Menengah) — Tinggi (Besar)",
    },
    "96900": {
        "title": "AKTIVITAS JASA PERORANGAN LAINNYA YTDL",
        "description": "Other personal service activities: astrology/spiritualism, social services (dating/matchmaking/escort), genealogy, pet care (boarding/grooming/training), shoe shiners/porters/valet parking, coin-operated personal service machines, photo booth. IMPORTANT: Also includes temporary henna/biological ink body decoration — BPS 2025 does NOT have a dedicated code for PERMANENT tattoo studios.",
        "pma_status": "TERBUKA",
        "risk_category": "Verify at OSS",
    },
}

# Non-business keywords that should trigger helpful redirect
NON_BUSINESS_KEYWORDS = [
    "kitas",
    "kitap",
    "visa",
    "immigration",
    "imigrasi",
    "passport",
    "paspor",
    "stay permit",
    "work permit",
    "izin tinggal",
    "izin kerja",
    "renewal",
    "agente immigrazione",
    "visto",
    "permesso di soggiorno",
    "immigrazione",
    # Recommendation/opinion queries (not KBLI classification)
    "best restaurant",
    "best cafe",
    "best coffee shop",
    "recommend restaurant",
    "where to eat",
    "mana makan",
    "restoran terbaik",
    "tempat makan terbaik",
]


def _is_non_business_query(query: str) -> bool:
    """Check if query is about immigration/visa rather than business classification."""
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in NON_BUSINESS_KEYWORDS)


def _is_multi_domain_query(query: str) -> bool:
    """
    Check if query spans multiple knowledge domains (KBLI + visa/immigration/legal/tax).

    Examples:
    - "Can I open a restaurant with retirement KITAS?" → True (KBLI + visa)
    - "What KBLI code for restaurant?" → False (pure KBLI)
    - "KITAS requirements for foreigners" → False (pure visa, will be deflected)

    Returns True only if query mentions BOTH business/KBLI AND visa/legal/tax.
    """
    query_lower = query.lower()

    # Domain 1: Business/KBLI indicators
    business_keywords = [
        "kbli",
        "business",
        "open",
        "start",
        "restaurant",
        "cafe",
        "villa",
        "hotel",
        "company",
        "pt",
        "pma",
        "usaha",
        "bisnis",
        "buka",
        "restoran",
        "kafe",
        "perusahaan",
        "investor",
        "investment",
    ]
    has_business = any(kw in query_lower for kw in business_keywords)

    # Domain 2: Visa/immigration indicators
    visa_keywords = [
        "kitas",
        "kitap",
        "visa",
        "retirement",
        "work permit",
        "imta",
        "rptka",
        "tka",
        "izin kerja",
        "izin tinggal",
        "pensiunan",
    ]
    has_visa = any(kw in query_lower for kw in visa_keywords)

    # Domain 3: Legal/tax indicators
    legal_keywords = [
        "law",
        "regulation",
        "tax",
        "uu ",
        "pp ",
        "permen",
        "pajak",
        "hukum",
        "peraturan",
        "ppn",
        "pph",
    ]
    has_legal = any(kw in query_lower for kw in legal_keywords)

    # Multi-domain = business + (visa OR legal)
    is_multi_domain = has_business and (has_visa or has_legal)

    if is_multi_domain:
        logger.info(
            f"🌐 Multi-domain query detected: business={has_business}, visa={has_visa}, legal={has_legal}",
        )

    return is_multi_domain


async def _fetch_parent_documents_from_kbli_table(codes: list[str], pool) -> dict[str, str]:
    """Fetch full parent documents from kbli_documents table for given KBLI codes.

    Returns dict mapping code -> full content from kbli_documents.
    This replaces truncated descriptions with complete parent document content.
    """
    if not codes or not pool:
        return {}

    parent_docs = {}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT kode_kbli, content FROM kbli_documents WHERE kode_kbli = ANY($1)", codes,
            )
            for row in rows:
                parent_docs[row["kode_kbli"]] = row["content"]

            if rows:
                logger.info(
                    f"✅ Fetched {len(rows)} parent documents from kbli_documents (avg {sum(len(d) for d in parent_docs.values()) // len(parent_docs)} chars)",
                )
            else:
                logger.warning(f"⚠️ No parent documents found in kbli_documents for codes: {codes}")
    except Exception as e:
        logger.error(f"❌ Failed to fetch parent documents: {e}")

    return parent_docs


@router.post("/chat", response_model=KBLINotebookChatResponse)
async def chat_kbli(
    http_request: Request,  # Iniezione corretta dell'oggetto Request di FastAPI
    kbli_request: KBLINotebookChatRequest,  # Il body della richiesta
    search_service=Depends(get_search_service),
    pool=Depends(get_optional_database_pool),
) -> KBLINotebookChatResponse:
    """Specialized chat for KBLI Notebook with BPS 2025 focus."""
    logger.info(f"💬 KBLI Chat Request: '{kbli_request.query[:50]}...'")

    # Check LLM availability early
    gateway = _get_llm_gateway()
    if not gateway._available:
        logger.error(
            "❌ LLM Gateway not available - GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS may be missing",
        )
    else:
        logger.debug("✅ LLM Gateway is available")

    try:
        # Translate query to Indonesian KBLI terms for better matching
        search_query = await _translate_query_for_kbli(kbli_request.query)

        # Extract KBLI codes from query for direct lookup
        codes_from_query = re.findall(r"\b\d{5}\b", kbli_request.query)
        direct_kbli_match = None

        # Try direct KBLI lookup from kbli_documents table (NEW: uses parent docs)
        if codes_from_query and pool:
            for code in codes_from_query:
                try:
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow(
                            "SELECT kode_kbli, judul, content, metadata FROM kbli_documents WHERE kode_kbli = $1",
                            code,
                        )

                        if row:
                            metadata = (
                                row["metadata"]
                                if isinstance(row["metadata"], dict)
                                else json.loads(row["metadata"])
                            )
                            # Extract first ~200 chars from content for preview
                            content_preview = (
                                row["content"][:200] + "..."
                                if len(row["content"]) > 200
                                else row["content"]
                            )
                            direct_kbli_match = KBLISearchResult(
                                code=code,
                                title=row["judul"],
                                description=content_preview,
                                score=1.0,
                                pma_status=metadata.get("pma_status", "Verify at OSS"),
                                risk_category="Verify at OSS",  # Will be enriched from full content
                            )
                            logger.info(
                                f"✅ Direct lookup from kbli_documents: {code} ({len(row['content'])} chars)",
                            )
                            break
                        # Fallback to kg_nodes for backward compatibility
                        entity_id = f"kbli:{code}"
                        kg_row = await conn.fetchrow(
                            "SELECT entity_id, name, description, properties FROM kg_nodes WHERE entity_id = $1",
                            entity_id,
                        )
                        if kg_row:
                            props = (
                                json.loads(kg_row["properties"])
                                if isinstance(kg_row["properties"], str)
                                else kg_row["properties"]
                            )
                            direct_kbli_match = KBLISearchResult(
                                code=code,
                                title=kg_row["name"],
                                description=kg_row["description"][:200] + "...",
                                score=1.0,
                                pma_status=props.get("pma_status", "Verify at OSS"),
                                risk_category=props.get("kategori_risiko", "Verify at OSS"),
                            )
                            logger.info(f"⚠️ Direct lookup fallback to kg_nodes: {code}")
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
                    title=_payload_value(
                        qdrant_payload, "judul", "title_id", default=f"KBLI {code}",
                    ),
                    description=(
                        _payload_value(qdrant_payload, "content", "text", "description", default="")
                        or ""
                    )[:200]
                    + "...",
                    score=1.0,
                    pma_status=_payload_value(
                        qdrant_payload, "pma_status", default="Verify at OSS",
                    ),
                    risk_category=_payload_value(
                        qdrant_payload, "kategori_risiko", default="Verify at OSS",
                    ),
                )
                logger.info(
                    f"✅ Found KBLI {code} via Qdrant payload filter: {direct_kbli_match.title}",
                )

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
                logger.info(
                    f"📖 Found KBLI {code} via hardcoded KNOWN_KBLI_CODES: {known['title']}",
                )

        # P2 FIX: Keyword-to-code injection for activities not in Qdrant
        # Detects activity keywords in query and injects a direct match BEFORE semantic search
        # This prevents wrong codes (e.g. 47901 for online retail instead of 47911)
        _activity_keyword_map: list[tuple[list[str], str]] = [
            # Online retail / e-commerce (handle spaced variants like "e comerce", "e commerce")
            (
                [
                    "online retail",
                    "e-commerce",
                    "ecommerce",
                    "e commerce",
                    "e comerce",
                    "toko online",
                    "online shop",
                    "internet retail",
                    "digital retail",
                    "online store",
                    "jual online",
                    "perdagangan online",
                ],
                "47911",
            ),
            # Event catering / catering
            (
                [
                    "event catering",
                    "katering",
                    "catering service",
                    "wedding catering",
                    "jasa boga",
                    "food catering",
                    "corporate catering",
                ],
                "56210",
            ),
            # Restaurant / coffee shop / cafe
            (
                [
                    "restaurant",
                    "restoran",
                    "coffee shop",
                    "café",
                    "cafe ",
                    "kafe ",
                    "kedai kopi",
                    "warung kopi",
                    "tempat makan",
                    "rumah makan",
                ],
                "56101",
            ),
            # Bar / nightclub
            (
                ["bar bali", "open a bar", "nightclub", "klub malam", "diskotek", "buka bar"],
                "56301",
            ),
            # Art gallery (commercial — selling art)
            (
                [
                    "art gallery",
                    "galeri seni",
                    "galeri lukisan",
                    "commercial art gallery",
                    "sell paintings",
                    "art shop",
                    "toko seni",
                    "jual lukisan",
                ],
                "47690",
            ),
            # Hair salon / barbershop
            (
                [
                    "hair salon",
                    "hair studio",
                    "barbershop",
                    "pangkas rambut",
                    "potong rambut",
                    "salon rambut",
                    "barber shop",
                ],
                "96210",
            ),
            # Beauty salon / nail / lash / brow
            (
                [
                    "nail studio",
                    "nail art",
                    "manicure",
                    "pedicure",
                    "eyelash extension",
                    "lash lift",
                    "brow studio",
                    "sulam alis",
                    "wax studio",
                    "make-up artist",
                    "mua ",
                    "beauty salon",
                    "salon kecantikan",
                    "perawatan kecantikan",
                ],
                "96220",
            ),
            # Day spa / sauna
            (
                [
                    "day spa",
                    "spa harian",
                    "sauna",
                    "steam bath",
                    "pemandian uap",
                    "solarium",
                    "wellness center",
                    "spa bali",
                    "open a spa",
                ],
                "96230",
            ),
            # Laundry
            (
                [
                    "laundry",
                    "dry cleaning",
                    "cuci baju",
                    "cuci pakaian",
                    "laundromat",
                    "jasa cuci",
                    "dobi",
                ],
                "96100",
            ),
            # Tattoo studio (permanent — no dedicated BPS code)
            (
                [
                    "tattoo studio",
                    "tattoo artist",
                    "tato studio",
                    "tattoo shop",
                    "buka tattoo",
                    "open tattoo",
                ],
                "96900",
            ),
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
                    logger.info(
                        f"🎯 Keyword injection: '{query_lower_kw[:40]}' → KBLI {target_code}",
                    )
                    break

        # Search semantic context with translated query
        results = []
        try:
            embedding = await _resolve_embedding(search_service, search_query)
            raw_results = await _search_kbli_qdrant(embedding, 7)

            # Deduplicate by code
            seen_codes = set()
            for r in raw_results:
                p = r.get("payload", {})
                code = _payload_value(p, "kode_kbli", "kode", "kode_kbli_2025", default="N/A")
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                results.append(
                    KBLISearchResult(
                        code=code,
                        title=_payload_value(p, "judul", "title_id", default="N/A"),
                        description=(
                            _payload_value(p, "content", "text", "description", default="") or ""
                        )[:200]
                        + "...",
                        score=round(r.get("score", 0.0), 4),
                        pma_status=_payload_value(p, "pma_status", default="Verify at OSS"),
                        risk_category=_payload_value(p, "kategori_risiko", default="Verify at OSS"),
                    ),
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
                                f"kbli:{r.code}",
                            )
                            if row:
                                props = (
                                    json.loads(row["properties"])
                                    if isinstance(row["properties"], str)
                                    else row["properties"]
                                )
                                if "expert_legal" in props:
                                    results[i].expert_legal = props["expert_legal"]
                                    logger.info(
                                        f"✨ Enriched result {r.code} with Expert Legal data",
                                    )
                        except Exception as enrich_err:
                            logger.warning(f"Failed to enrich {r.code}: {enrich_err}")

            # When a specific code is in the query, filter Qdrant results to same 2-digit sector prefix
            # This prevents cross-sector contamination (e.g. 64954 Syariah pawn in catering results)
            if codes_from_query and direct_kbli_match:
                query_prefix = direct_kbli_match.code[:2]
                before = len(results)
                results = [r for r in results if r.code.startswith(query_prefix)]
                if len(results) < before:
                    logger.info(
                        f"🧹 Filtered Qdrant results by sector prefix '{query_prefix}': {before} → {len(results)}",
                    )

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
                            f"%{search_query}%",
                        )
                        for row in rows:
                            code = row["entity_id"].replace("kbli:", "")
                            props = (
                                json.loads(row["properties"])
                                if isinstance(row["properties"], str)
                                else row["properties"]
                            )
                            results.append(
                                KBLISearchResult(
                                    code=code,
                                    title=row["name"],
                                    description=row["description"][:200] + "...",
                                    score=0.8,  # Static score for fallback
                                    pma_status=props.get("pma_status", "UNKNOWN"),
                                    risk_category=props.get("kategori_risiko", "Unknown"),
                                ),
                            )
                        logger.info(
                            f"✅ Found {len(results)} KBLI results from PostgreSQL fallback",
                        )
            except Exception as db_err:
                logger.error(f"❌ PostgreSQL fallback failed: {db_err}")

        # Detect KBLI codes from results
        codes_from_results = [r.code for r in results if r.code != "N/A"]
        detected_kbli = list(dict.fromkeys(codes_from_query + codes_from_results))

        # MULTI-DOMAIN ROUTING: If query spans KBLI + visa/legal, use KG Orchestrator
        if _is_multi_domain_query(kbli_request.query):
            logger.info("🌐 Multi-domain query detected → routing to KG Orchestrator")
            try:
                # Initialize KG Orchestrator with db_pool and search_service
                if not pool:
                    logger.warning("⚠️ Database pool unavailable, falling back to KBLI-only mode")
                else:
                    orchestrator = KGAgenticOrchestrator(db_pool=pool, retriever=search_service)

                    # Process query with full KG-enhanced reasoning
                    kg_response = await orchestrator.process(
                        query=kbli_request.query,
                        session_id=kbli_request.session_id or "kbli-notebook",
                        user_id=None,
                    )

                    logger.info(
                        f"✅ KG Orchestrator response: {len(kg_response.answer)} chars, {len(kg_response.sources)} sources",
                    )
                    logger.info(f"📊 Reasoning trace: {kg_response.reasoning_trace[:2]}")

                    # Map KG response to KBLI chat response format
                    # Extract KBLI codes from KG entities if available
                    kg_detected_kbli = detected_kbli.copy()
                    if kg_response.golden_route_matched:
                        logger.info(f"🎯 Golden route matched: {kg_response.golden_route_matched}")

                    # Build suggested queries from KG context
                    suggested_kg = []
                    if detected_kbli:
                        suggested_kg.append(f"What licenses do I need for KBLI {detected_kbli[0]}?")
                    if (
                        "visa" in kbli_request.query.lower()
                        or "kitas" in kbli_request.query.lower()
                    ):
                        suggested_kg.append(
                            "What are the legal business structures for foreigners in Indonesia?",
                        )
                        suggested_kg.append("Contact Bali Zero for visa consultation")

                    return KBLINotebookChatResponse(
                        answer=kg_response.answer,
                        detected_kbli=kg_detected_kbli,
                        results=[],  # Don't show KBLI cards (info in answer)
                        sources=kg_response.sources
                        if kg_response.sources
                        else [{"title": "Multi-domain KG reasoning", "relevance": "High"}],
                        suggested_queries=suggested_kg
                        or ["Explore more KBLI codes", "Contact Bali Zero team"],
                    )
            except Exception as kg_err:
                logger.error(f"❌ KG Orchestrator failed, falling back to KBLI-only: {kg_err}")
                # Fall through to standard KBLI processing

        # Check for non-business queries (KITAS/visa/immigration OR recommendations)
        if _is_non_business_query(kbli_request.query):
            logger.info(f"⚠️ Non-business query detected: '{kbli_request.query[:50]}'")
            query_lang = _detect_language(kbli_request.query)
            query_lower_nb = kbli_request.query.lower()
            _recommendation_keywords = [
                "best ",
                "recommend",
                "where to eat",
                "mana makan",
                "terbaik",
            ]
            is_recommendation = any(kw in query_lower_nb for kw in _recommendation_keywords)

            if is_recommendation:
                abstain_answer = (
                    "I can't recommend specific restaurants or businesses — that's not my specialty.\n\n"
                    "I am **Zantara AI**, specialized in **KBLI** (Klasifikasi Baku Lapangan Usaha Indonesia) — "
                    "the Indonesian Business Classification System. I help you find the right KBLI code for your "
                    "business and understand licensing, investment status (PMA), and regulatory requirements.\n\n"
                    "Are you perhaps looking to **open** a restaurant or food business in Bali? I can help with that!"
                )
                suggested = [
                    "I want to open a restaurant in Bali",
                    "KBLI code for a cafe or coffee shop",
                    "What KBLI for catering?",
                ]
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
                suggested = [
                    "Buka restoran di Bali",
                    "Kode KBLI untuk impor ekspor",
                    "Hotel dan hospitality KBLI",
                ]
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
                suggested = [
                    "I want to open a restaurant in Bali",
                    "KBLI code for import export business",
                    "Hotel and hospitality KBLI",
                ]
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
            if (
                term in query_lower
                and any(
                    kw in query_lower
                    for kw in [
                        "mean",
                        "what",
                        "explain",
                        "definition",
                        "define",
                        "arti",
                        "apa itu",
                        "pengertian",
                    ]
                )
            ) or query_lower.strip() == term:
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
        logger.info(
            f"🔍 ABSTAIN check: has_direct_match={has_direct_match}, results={len(results)}, codes={codes_from_query}",
        )
        filtered_results = [r for r in results if r.score >= MIN_RELEVANCE_SCORE]

        if not has_direct_match and not filtered_results and results:
            logger.warning(
                f"⚠️ All results below threshold {MIN_RELEVANCE_SCORE}. Triggering ABSTAIN.",
            )
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
                suggested = [
                    "Restaurant in Bali",
                    "Import export Indonesia",
                    "Hotel and hospitality",
                ]
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
            logger.info(
                f"🎯 Keyword injection: restricting results to direct match only ({direct_kbli_match.code})",
            )
        elif not has_direct_match:
            results = filtered_results if filtered_results else results

        # Fetch full parent documents from kbli_documents table for complete context
        codes_to_fetch = [r.code for r in results if r.code != "N/A"]
        parent_docs = await _fetch_parent_documents_from_kbli_table(codes_to_fetch, pool)

        # Generate explanation via Claude Haiku 4.5 (fast, cost-effective)
        # Falls back to Gemini Flash if Claude unavailable
        answer = await _generate_kbli_explanation_gemini(kbli_request.query, results, parent_docs)

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
                    f"What's the difference between KBLI {top.code} and {results[1].code}?",
                )
            else:
                suggested_queries.append(f"What are the risk requirements for KBLI {top.code}?")

        logger.info(
            f"✅ KBLI Chat Response: answer_length={len(answer)}, results={len(results)}, detected={detected_kbli}",
        )

        return KBLINotebookChatResponse(
            answer=answer,
            detected_kbli=detected_kbli,
            results=[],  # Don't show KBLI cards in UI (info already in answer text)
            sources=[{"title": "PP 28/2025", "relevance": "High"}],
            suggested_queries=suggested_queries,
        )
    except Exception as e:
        logger.error(f"❌ KBLI Chat Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI Engine error: {str(e)}") from e
