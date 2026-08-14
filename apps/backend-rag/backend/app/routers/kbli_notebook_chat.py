"""
KBLI Notebook Chat API - LLM-powered chat, translation, explanation

Split from kbli_notebook.py for maintainability.
Provides: LLM gateway singleton, query translation, language detection,
KBLI explanation generation, multi-domain routing, chat endpoint.
"""

import json
import logging
import re
from dataclasses import dataclass
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
    _official_scope,
    _payload_value,
    _pma_disclosure_fields,
    _resolve_embedding,
    _result_from_payload,
    _search_kbli_qdrant,
)
from backend.core.cache import cached
from backend.services.kbli_pma_disclosure import disclose_pma, pma_claims_verified
from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kbli-notebook", tags=["KBLI Notebook Chat"])

_llm_gateway_instance = None

_PMA_EVIDENCE_FIELDS = (
    "pma_status",
    "pma_max_asing",
    "pma_verification_status",
    "pma_official_basis",
    "pma_source_vintage",
)


@dataclass(frozen=True)
class _VerifiedParentDocument:
    """A parent document whose own PMA evidence matches the search result."""

    content: str
    pma_evidence: tuple[Any, ...]


def _publishable_pma_evidence(payload: dict[str, Any]) -> tuple[Any, ...] | None:
    """Normalize one complete PMA tuple, or fail closed for a partial record."""
    if not pma_claims_verified(payload):
        return None
    disclosed = disclose_pma(payload)
    return tuple(disclosed[field] for field in _PMA_EVIDENCE_FIELDS)


def _parent_document_matches_result(
    document: object,
    result: KBLISearchResult,
) -> bool:
    """Re-check provenance at the final prompt-injection boundary."""
    if not isinstance(document, _VerifiedParentDocument):
        return False
    return document.pma_evidence == _publishable_pma_evidence(result.model_dump())


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
    "- Use the eligible context data provided; never fill a provenance gap from memory or analogy.\n"
    "- Explain trade-offs, options, and practical next steps when relevant.\n\n"
    "PMA STATUS GLOSSARY (answer these directly without needing source data):\n"
    "- TERBUKA = Open to 100% foreign ownership (PMA diperbolehkan penuh)\n"
    "- TERBATAS = Open with restrictions — max foreign ownership percentage applies (PMA dengan batasan kepemilikan)\n"
    "- TERTUTUP = Closed to foreign investment — Indonesian nationals only (PMA tidak diperbolehkan)\n"
    "- PMA = Penanaman Modal Asing = Foreign Direct Investment\n"
    "- NOT_VERIFIED = this code's whole-code foreign-ownership verdict is withheld because the record lacks a located official basis and source vintage. Never infer TERBUKA/TERBATAS/TERTUTUP or a percentage for that code; state the gap and direct the user to OSS/BKPM verification.\n"
    "- CAPITAL FACTS FOR PMA (two DIFFERENT thresholds — never conflate them):\n"
    "  * Modal Disetor Minimum (paid-up capital) = Rp 2.5 Billion, per Permen Investasi/Hilirisasi-BKPM "
    "5/2025 (in force 2025-10-02, abrogates Permen BKPM 4/2021).\n"
    "  * Minimum Investment Value per KBLI code per business location (excluding land and buildings) = "
    "more than Rp 10 Billion. This is a SEPARATE threshold from paid-up capital.\n"
    "  * NEVER present Rp 10 Billion as the modal disetor / paid-up capital minimum — that figure is "
    "obsolete (pre-BKPM 5/2025) and conflates the two thresholds.\n"
    "- OSS = Online Single Submission system at oss.go.id — official licensing portal\n"
    "- NIB = Nomor Induk Berusaha = Business Identification Number (first step in OSS)\n"
    "If a user asks what these terms mean, explain them directly using this glossary.\n\n"
    "KNOWN KBLI CODES (use these exact definitions when asked):\n"
    "- 47901 = PLATFORM DIGITAL INTERMEDIASI PERDAGANGAN ECERAN — Operating a digital marketplace that intermediates retail sales. NOTE: this is the MARKETPLACE OPERATOR. A business selling its OWN goods online takes the code of the PRODUCT CATEGORY it sells. KBLI 47911 was a 2020 code and does NOT exist in KBLI 2025 — never cite it.\n"
    "- 56101 = AKTIVITAS PENYEDIAAN MAKANAN DI BANGUNAN TETAP (RESTORAN) — Restaurant services with a permanent building. Risk is scale-dependent.\n"
    "- 56210 = AKTIVITAS JASA BOGA UNTUK ACARA TERTENTU (EVENT CATERING) — Event catering/katering.\n"
    "- 56290 = AKTIVITAS JASA BOGA LAINNYA — Other food service activities.\n"
    "If a user asks about these codes by number, explain them directly from this list.\n\n"
    "ACCURACY GUIDELINES:\n"
    "1. Use only real citations from the context data. Don't make up placeholder references like 'Chapter X' or 'Bab Y'.\n"
    "2. Always explain how licensing and risk levels vary by business scale (Mikro/Kecil/Menengah/Besar) — this is critical.\n"
    "3. For foreign investment (PMA) questions, mention BOTH capital thresholds accurately: modal disetor "
    "(paid-up capital) minimum Rp 2.5 Billion (Permen BKPM 5/2025, effective 2025-10-02) AND minimum "
    "investment value per KBLI per location of more than Rp 10 Billion (excluding land/buildings). "
    "Never state Rp 10 Billion as the paid-up capital figure.\n"
    "4. If data is missing from context, say so clearly: 'This detail isn't in the official documents — please verify at oss.go.id'.\n"
    "5. When PMA status is NOT_VERIFIED or 'Verify at OSS', do not infer a verdict or cap; explain that the whole-code ownership claim lacks a located official basis/source vintage and should be checked with OSS/BKPM.\n"
    "6. NEVER estimate a licensing risk tier (Rendah/Menengah Rendah/Menengah Tinggi/Tinggi) for a KBLI code "
    "by analogy with other codes' risk levels. If risk_category for the code in context is 'Verify at OSS' "
    "or otherwise unverified/absent, say so honestly and point the user to oss.go.id or the Bali Zero team "
    "— do not guess a plausible tier.\n"
    "8. COLLOQUIAL TERMS: Know that 'restoran/restaurant/rumah makan' = aktivitas penyediaan makanan (KBLI 56101), "
    "'katering/catering' = jasa boga (KBLI 56210 / 56290), "
    "'mobile app/aplikasi/software development' = aktivitas pemrograman komputer (KBLI 62199) or pengembangan aplikasi e-commerce (KBLI 62191), "
    "'IT consulting/konsultan IT/software consultant' = aktivitas konsultasi manajemen dan bisnis (KBLI 70209), "
    "'online retail/e-commerce/toko online/online shop' = KBLI 47901 if the client OPERATES a marketplace platform, "
    "otherwise the code of the PRODUCT CATEGORY sold online (there is no single 'e-commerce' code in KBLI 2025), "
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
    "'bar/wine bar/cocktail bar/beach club' = aktivitas bar (KBLI 56301 — alcohol service still requires SKPL/PB-UMKU and local licensing), "
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

FOREIGN_INVESTMENT_QUERY_MARKERS: tuple[str, ...] = (
    "pma",
    "foreign",
    "foreigner",
    "foreign-owned",
    "foreign owned",
    "foreign investment",
    "asing",
    "investor",
    "100%",
)

PMA_SCALE_CONTEXT_BY_CODE: dict[str, str] = {
    "56101": (
        "The user is asking about a PT PMA or foreign-owned restaurant, so evaluate "
        "licensing as skala usaha Besar. Canonical KBLI 2025 data for 56101 shows "
        "Besar risk: Menengah Tinggi; licensing: NIB dan Sertifikat Standar; PB-UMKU "
        "can include SLHS, SKPL A/B/C when alcohol is sold, and NKV. Do not describe "
        "a PT PMA restaurant as Menengah Rendah."
    ),
}


def _is_foreign_investment_query(query: str) -> bool:
    normalized = query.lower()
    return any(marker in normalized for marker in FOREIGN_INVESTMENT_QUERY_MARKERS)


def _requires_structured_pma_gate(query: str) -> bool:
    """Return whether a multi-domain answer could make an ownership claim.

    The KG orchestrator owns its own retrieval path, so this router cannot prove
    that every PMA sentence in its free-form answer passed the five-field
    evidence gate. Foreign-investment and immigration-shaped questions stay on
    the KBLI router's fail-closed path until the orchestrator exposes equivalent
    structured provenance.
    """
    normalized = query.lower()
    ownership_terms = bool(
        re.search(r"\b(?:own|owner|ownership|kepemilikan|dimiliki)\b", normalized)
    )
    immigration_terms = any(
        marker in normalized
        for marker in (
            "kitas",
            "kitap",
            "visa",
            "work permit",
            "izin kerja",
            "izin tinggal",
            "imigrasi",
            "immigration",
        )
    )
    return _is_foreign_investment_query(query) or ownership_terms or immigration_terms


def _scale_specific_pma_context_note(code: str, query: str) -> str:
    if not _is_foreign_investment_query(query):
        return ""
    return PMA_SCALE_CONTEXT_BY_CODE.get(code, "")


async def _fill_bali_verdicts(results: list["KBLISearchResult"]) -> None:
    """Backfill the Bali verdict on any result that was not built from a Qdrant payload.

    THIS IS THE CLASS FIX, and it is here rather than at the constructors on
    purpose. Seven call sites in this module build a `KBLISearchResult`: two from
    a Qdrant payload, the other five from `kbli_documents`, `kg_nodes` or a
    hardcoded fallback — none of which carry the Bali layer (measured: 0 of 1,563
    `kbli_documents` rows hold an `l4_bali` key). Curing only the constructors I
    happened to look at would not reduce the risk, it would only move WHICH query
    shape gets the wrong answer — a code typed directly still resolves through
    the Postgres path.

    So the fill happens once, at the choke point every answer passes through, and
    every future constructor inherits it without knowing this exists.

    Failure is SILENCE, never a guess: if Qdrant is unreachable or the point has
    no verdict, `bali_blocked` stays None and the note helper says nothing. A
    degraded answer that omits the Bali warning is bad; one that invents "open"
    is the defect this whole lane exists to remove.
    """
    for result in results:
        needs_bali_verdict = result.bali_blocked is None
        if not needs_bali_verdict and result.pma_verdict_verified:
            continue
        try:
            payload = await _get_kbli_payload_from_qdrant(result.code)
        except Exception as exc:  # broad on purpose: degrade to silence, never to a claim
            logger.warning("Bali verdict lookup failed for %s: %s", result.code, exc)
            continue
        if not payload:
            continue
        # Apply the full national evidence tuple atomically. Constructing a
        # temporary response model runs the same fail-closed validator used by
        # the HTTP API, so a raw cap can never be backfilled without its locator
        # and vintage (Pydantic assignment itself is not validated here).
        disclosed = KBLISearchResult(
            **{
                **result.model_dump(),
                **_pma_disclosure_fields(payload),
            }
        )
        result.pma_status = disclosed.pma_status
        result.pma_max_asing = disclosed.pma_max_asing
        result.pma_verification_status = disclosed.pma_verification_status
        result.pma_official_basis = disclosed.pma_official_basis
        result.pma_source_vintage = disclosed.pma_source_vintage
        # These two fields share the PMA gate.  Copy them back as part of the
        # same atomic disclosure decision so a later payload that downgrades a
        # result to ``declared_gap`` cannot leave previously attached prose on
        # the mutable response object.
        result.expert_legal = disclosed.expert_legal
        result.bali_reason = disclosed.bali_reason
        # A result already carrying the Bali verdict came from the same point as
        # the search hit.  The extra read above may be needed only to complete
        # its PMA evidence tuple; never let that later read replace the verdict
        # the search actually returned.
        if not needs_bali_verdict:
            continue

        blocked = _payload_value(payload, "bali_blocked")
        if blocked is None:
            continue
        result.bali_blocked = bool(blocked)
        result.bali_status = _payload_value(payload, "bali_status")
        result.bali_reason = (
            _payload_value(payload, "bali_reason", default="") or ""
            if result.pma_verdict_verified
            else ""
        )
        logger.info(
            "🌴 Backfilled Bali verdict for %s: %s (blocked=%s)",
            result.code,
            result.bali_status,
            result.bali_blocked,
        )


# --------------------------------------------------------------- national scope
#
# WHY THIS EXISTS. The note below used to open EVERY block with "This is a
# PROVINCIAL restriction ... an activity can be 100% open nationally and still be
# unregistrable in Bali." That is true of the Bali moratorium and false of the
# rest: measured 2026-08-05 on `data/source_documents/KBLI_2025_FINAL_CLEAN.json`,
# 518 codes carry `l4_bali.blocked` and **77** of them are closed to a PT PMA
# everywhere in Indonesia. Asked about 64110 in production, the bot was right on
# the substance and then framed a Bank Indonesia State monopoly as a provincial
# rule — an answer whose natural next step for the reader is "then I will
# register it in Jakarta".
#
# THE RULE IS DELIBERATELY THE PAGE'S RULE, code for code and status for status
# (`apps/mouth/src/lib/kbli-bali-block.ts::isNationalClosure`). Two surfaces
# answering the same question from the same record must not each grow their own
# list — that is how `/kbli/69104` came to say one thing while WhatsApp said
# another. They cannot share a module across Python and TypeScript, so the
# identity is pinned by a test that reads the TypeScript file instead.
#
# The third input, the national ceiling, is the page's `nationallyClosed`
# derivation: `pma_status == TERTUTUP` or a ceiling of 0%. It carries 63 of the
# 77 on its own; the status set and the code list exist for the 14 where
# `pma_status` says TERBUKA/100 while the activity is reserved by name.
_NATIONAL_CLOSURE_STATUSES: dict[str, str] = {
    "CHIUSO_REGOLATORE_SETTORIALE": "a sectoral regulator reserves the activity nationwide",
    "CHIUSO_PMA_NO_BESAR": (
        "the activity is allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II, "
        "a bidang usaha a PT PMA cannot take"
    ),
}

_NATIONAL_CLOSURE_CODES: dict[str, str] = {
    "01287": "narcotics/medicinal-plant cultivation, TERTUTUP nationally",
    "47111": "minimarket/supermarket retail, reserved to Indonesian citizens (WNI)",
    "47112": "minimarket/supermarket retail, reserved to Indonesian citizens (WNI)",
    "59131": "film/video distribution, TERTUTUP nationally",
    "69102": "legal consultancy, reserved to Indonesian-licensed advocates (UU 18/2003)",
    "69104": "notary/PPAT, a personal State office open to WNI only (UU 30/2004 as am. UU 2/2014)",
    "86201": "a solo doctor's practice, closed to foreign nationals under Kemenkes health law",
    "86202": "a solo specialist practice, closed to foreign nationals under Kemenkes health law",
}


# The pipeline's own vocabulary, rendered in words — a SECOND route into the
# same leak, and the measurement is stated exactly because it is not the route
# that was bleeding.
#
# The live leak was the note's own `Verdict code: {bali_status}` suffix: 450 of
# the 518 blocked codes handed the model a symbol, and production repeated
# `CHIUSO_REGOLATORE_SETTORIALE` to a client. Deleting that suffix is the cure.
#
# This helper covers the other way in: `bali_reason` is quoted to the model
# verbatim, so a symbol written INSIDE a reason sentence would leak just the
# same. Measured 2026-08-05 on the canonical: 9 reasons quote a symbol
# (`OK_or_HIGHER_RISK` x6, `CHIUSO_MORATORIA_BALI` x2, `pma_cap_verified` x1)
# and **none of the 9 is on a blocked code**, so today this guards a population
# of ZERO — said plainly rather than counted as nine fixes. It is here because
# the reason text is rewritten by cure lanes most weeks and a blocked code's
# reason is one edit away from carrying one; its own mutation test proves it
# bites, so it is defence-in-depth, not decoration.
#
# The sentence is still passed through; only the tokens are spoken. The fallback
# — underscores to spaces — is what makes it fail-CLOSED: a symbol nobody has
# mapped yet degrades to readable words instead of reaching a client.
_INTERNAL_SYMBOL_RE = re.compile(r"\b[A-Za-z]+(?:_[A-Za-z]+)+\b")

_SYMBOL_PLAIN_TEXT: dict[str, str] = {
    "OK_or_HIGHER_RISK": "not reached by the moratorium",
    "APERTO_BALI_RISCHIO_ALTO": "open in Bali at a higher risk tier",
    "BLOCCATO_CLASSE_RISCHIO": "blocked by its risk class",
    "BLOCCATO_DIPENDE_SCOPE": "blocked depending on the declared scope",
    "CHIUSO_BALI": "closed in Bali",
    "CHIUSO_BALI_PROPOSTO": "proposed for closure in Bali",
    "CHIUSO_MORATORIA_BALI": "closed by the Bali moratorium",
    "CHIUSO_PMA_NO_BESAR": "allocated to Koperasi/UMKM, not open to a PT PMA",
    "CHIUSO_REGOLATORE_SETTORIALE": "closed by the sectoral regulator",
    "NON_CLASSIFICABILE": "not classifiable from the data we hold",
    "pma_cap_verified": "foreign-ownership cap verified",
}


def _speak_internal_symbols(text: object) -> str:
    """Render pipeline enum tokens as words, leaving the sentence otherwise intact.

    Takes `object`, not `str`, deliberately. This runs on EVERY answer, and the
    reason is ASSIGNED onto the model from a Qdrant payload — Pydantic does not
    validate on assignment, so a point storing a number there would hand `re.sub`
    a non-string and 500 the answer. The first draft did exactly that and took 8
    sibling tests down with it; a cosmetic step must never be able to kill the
    answer it decorates.
    """
    if not isinstance(text, str):
        text = str(text)
    return _INTERNAL_SYMBOL_RE.sub(
        lambda m: _SYMBOL_PLAIN_TEXT.get(m.group(0), m.group(0).replace("_", " ")),
        text,
    )


def _is_zero_ceiling(value: object) -> bool:
    """True only for a REAL 0% cap — absence must never read as a closure.

    The indexer writes an absent cap as `""` and `_payload_value` maps `""`/None
    to the default, so absence arrives as `None`. Comparing either to 0 is
    already False in Python; this helper exists so that a later "tidy-up" to
    `int(value or 0)` — which would turn every point without the field into a
    national closure — has to argue with a named function and its test.

    A digit STRING counts. The canonical stores integers and a string should not
    occur, but if one ever does, the failure has to land on the safe side: `"0"`
    read as "no ceiling recorded" is the reading that tells a client an activity
    closed to foreign capital is open.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == 0
    if isinstance(value, str):
        text = value.strip()
        return text.isdigit() and int(text) == 0  # "" is not a digit string
    return False


def _national_closure_basis(result: "KBLISearchResult") -> str | None:
    """Why this activity is closed to a PT PMA nationwide, or None if it is not.

    Returns a PHRASE, not a boolean, because the note has to tell the reader what
    closed it: "closed nationally" with no basis is the kind of assertion this
    lane keeps having to withdraw.
    """
    if not result.pma_verdict_verified:
        return None

    by_code = _NATIONAL_CLOSURE_CODES.get(result.code)
    if by_code:
        return by_code
    by_status = _NATIONAL_CLOSURE_STATUSES.get(result.bali_status or "")
    if by_status:
        return by_status
    if (result.pma_status or "").strip().upper() == "TERTUTUP":
        return "the national PMA list closes the activity (TERTUTUP)"
    if _is_zero_ceiling(result.pma_max_asing):
        return "the national foreign-ownership ceiling is 0%"
    return None


def _bali_verdict_context_note(result: "KBLISearchResult") -> str:
    """The Bali provincial verdict, as a line the model cannot miss.

    DERIVED from the payload, never a hand-maintained table: the sibling note
    above reads `PMA_SCALE_CONTEXT_BY_CODE`, which is fine for a handful of
    special cases and hopeless for the 518 codes this covers.

    Three deliberate choices, each one a way this could go wrong:

    * **Silence when the payload says nothing.** `bali_blocked is None` means the
      point predates the Bali layer, not that the activity is open. Inventing
      "open" from an absent field is the exact inference this lane spent a week
      withdrawing.
    * **Not gated on the query.** `_scale_specific_pma_context_note` only fires
      when the question mentions foreign investment; a Bali block is material
      even when it does not ("how do I open a massage parlour in Bali?"), and
      staying silent there is what produced the wrong answer.
    * **The reason is passed through only with a verified PMA tuple.** The Bali
      verdict is an independent structured signal and still blocks unsafe
      advice when national PMA provenance is absent.  Its free-form reason,
      however, can also contain national ownership conclusions.  Publishing
      that prose for a `declared_gap` row would bypass the exact provenance gate.

    Two more, added 2026-08-05 (see `_national_closure_basis` above):

    * **Scope before wording.** A block is described as provincial only when it
      IS provincial. 77 of the 518 are national, and calling those "a Bali
      restriction" hands the reader the wrong next step.
    * **No internal symbol reaches the model.** The note used to end with
      `Verdict code: CHIUSO_REGOLATORE_SETTORIALE`, and production repeated that
      token to a client. The vocabulary of the pipeline is not the vocabulary of
      an answer — the page has held that line since 2026-07-25
      (`kbli-status-labels.ts::INTERNAL_ENUM_LABELS`); this was the surface that
      had not. The symbol still goes to the log, where it belongs.

    NOT handled here, and measured rather than assumed: an activity that is
    nationally closed and carries NO Bali verdict at all. Today that set is
    empty (0 of 1,559), and widening the silence-on-absence contract to cover a
    population of zero would trade a proven innocence property for nothing.
    """
    if result.bali_blocked is None:
        return ""

    pma_verified = result.pma_verdict_verified
    national = _national_closure_basis(result)
    # Coerce BEFORE `.strip()`, not after: `(42 or "").strip()` raises, and that
    # ordering bug predates this change — it has been one malformed payload away
    # from a 500 since the field was added.
    reason = _speak_internal_symbols(result.bali_reason or "").strip() if pma_verified else ""

    if not result.bali_blocked:
        if national:
            # 79122 today, and the shape is what matters: the moratorium does not
            # reach it, so the old text said "NOT blocked" and stopped — a
            # sentence whose only reading is "go ahead" on an activity closed to
            # foreign capital outright. "Not blocked in Bali" is not permission.
            return (
                "NOT blocked by the Bali provincial moratorium — but this activity is "
                "closed to a foreign-owned company (PT PMA) at the NATIONAL level "
                f"({national}), so the absence of a Bali block is NOT permission. You "
                "MUST NOT present it as registrable by a PT PMA."
            )
        if pma_verified:
            return (
                "BALI: this activity is NOT blocked for a PT PMA by the Bali provincial "
                "moratorium. National ownership rules still apply separately."
            )
        return (
            "BALI: this activity is NOT blocked in the Bali-side record by the "
            "provincial moratorium. The national PMA status and ownership ceiling are "
            "NOT_VERIFIED; do not infer national permission from the Bali result."
        )

    if national:
        note = (
            "CLOSED TO A FOREIGN-OWNED COMPANY (PT PMA) — NATIONALLY, not only in Bali. "
            f"The closure is {national}, so it applies everywhere in Indonesia: "
            "registering the activity in another province does NOT change the answer, "
            "and there is no Jakarta route around it."
        )
        if reason:
            note = f"{note} Stated cause: {reason}"
        return (
            f"{note} You MUST say a PT PMA cannot register this activity anywhere in "
            "Indonesia and give this cause. Do NOT describe it as a Bali-only "
            "restriction and do NOT offer another province as an alternative."
        )

    if pma_verified:
        note = (
            "BALI — BLOCKED FOR A FOREIGN-OWNED COMPANY (PT PMA). This is a PROVINCIAL "
            "restriction and it is independent of the national PMA status above: an "
            "activity can be 100% open nationally and still be unregistrable in Bali."
        )
    else:
        note = (
            "BALI — BLOCKED FOR A FOREIGN-OWNED COMPANY (PT PMA). This Bali-side "
            "verdict does not verify the national PMA status or ownership ceiling; "
            "both remain NOT_VERIFIED."
        )
    if reason:
        note = f"{note} Stated cause: {reason}"
    note = (
        f"{note} You MUST say the activity is blocked in Bali and give this cause. "
        "Do not answer that it can be registered in Bali."
    )
    return note


_TRANSLATE_SYSTEM = (
    "You are an expert in KBLI (Klasifikasi Baku Lapangan Usaha Indonesia), the Indonesian Business Classification System.\n"
    "Your task: translate any business activity query (in any language) into the most accurate Indonesian KBLI search phrase.\n\n"
    "Rules:\n"
    "1. Output ONLY the Indonesian search phrase. No explanation, no quotes, no punctuation.\n"
    "2. Use terminology from official KBLI 2025 titles (BPS Regulation No. 7/2025).\n"
    "3. For sector/category questions (e.g. 'construction sector', 'tourism sector'), use the Indonesian sector name.\n"
    "4. For comparison questions (e.g. 'difference between X and Y'), output both Indonesian terms separated by a space.\n"
    "5. For KBLI code numbers (e.g. 'KBLI 56101'), pass them through unchanged.\n"
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
    ttl=604800,
    prefix="kbli_translate_v14",
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
            logger.warning("⚠️ Translation returned empty from %s, using original", model_used)
            return query

        translated = translated.strip().strip('"').strip("'")
        logger.info("🌐 Query translation: '%s' → '%s' (model: %s)", query, translated, model_used)
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
    query: str,
    results: list[KBLISearchResult],
    parent_docs: dict[str, _VerifiedParentDocument] | None = None,
) -> str:
    """Generate KBLI explanation using Gemini Flash - Fast, Cost-Effective.

    Uses Google Gemini 2.0 Flash with a simplified prompt focused on
    clarity and accuracy.
    """
    logger.info("🤖 Using Gemini Flash for KBLI explanation")
    return await _generate_kbli_explanation(query, results, parent_docs)


@cached(
    ttl=43200,
    prefix="kbli_explain_v32",
)  # Cache explanations for 12 hours.
# v28 (2026-08-03): the Bali provincial verdict now reaches the model. The bump is
# NOT cosmetic — this cache is 12h deep and keyed on the prefix, so every answer
# already stored under v27 was generated blind to the Bali block and would keep
# being served for half a day after the deploy. A cure the cache hides is not live.
# v29 (2026-08-05): 77 national closures are no longer framed as Bali-provincial,
# and no internal verdict symbol reaches the model. Same reason for the bump, and
# it bites harder here: an answer cached under v28 is one that told a client to
# try another province, and it would keep saying so for 12 hours after deploy.
# v30 (2026-08-15): raw whole-code PMA prose is withheld unless the result
# carries located + official basis + source vintage. Old answers may contain the
# now-withheld claim, so the prefix is part of the disclosure boundary.
# v31 (2026-08-15): declared-gap rows keep the structured Bali warning but no
# longer pass through a mixed free-form reason that can contain national PMA
# claims. Cached v30 answers may already quote that prose.
# v32 (2026-08-15): generated kbli_documents prose is admitted only when that
# row's own PMA tuple matches the verified search result. Cached v31 answers may
# already contain unbound or divergent parent-document ownership claims.
async def _generate_kbli_explanation(
    query: str,
    results: list[KBLISearchResult],
    parent_docs: dict[str, _VerifiedParentDocument] | None = None,
) -> str:
    """Generate a grounded explanation of KBLI search results using LLM.

    Args:
        query: User query
        results: Search results with codes and metadata
        parent_docs: Provenance-bound parent documents from kbli_documents.
    """
    if not results:
        return "No matching KBLI codes found for your search. Try different keywords or describe your business activity in more detail."

    lang = _detect_language(query)
    logger.info(f"🌐 Detected language: {lang} for query: '{query[:40]}'")

    # Every answer passes here, whatever built its results — see _fill_bali_verdicts.
    await _fill_bali_verdicts(results)

    context_parts = []
    for r in results:
        pma_verified = r.pma_verdict_verified
        # Check if we have deep metadata from Postgres/Expert injection
        expert_info = ""
        if pma_verified and hasattr(r, "expert_legal") and r.expert_legal:
            ex = r.expert_legal
            expert_info = f"\n  Expert Data (PP 28/2025): Bab {ex.get('bab')}, Pasal {ex.get('pasal')}. PB-UMKU: {', '.join(ex.get('pb_umku', []))}. Note: {ex.get('pma_implications')}"

        scale_note = _scale_specific_pma_context_note(r.code, query) if pma_verified else ""
        if scale_note:
            expert_info = f"{expert_info}\n  PMA/foreign-owned scale note: {scale_note}"

        bali_note = _bali_verdict_context_note(r)
        if bali_note:
            expert_info = f"{expert_info}\n  {bali_note}"

        # Parent documents and expert blobs contain generated ownership prose.
        # They are eligible only after the structured PMA evidence gate.  For a
        # gap, give the model the safe classification scope plus an explicit
        # abstention instruction; never ask it to sanitize prose heuristically.
        parent_doc = parent_docs.get(r.code) if parent_docs else None
        if pma_verified and _parent_document_matches_result(parent_doc, r):
            full_content = parent_doc.content
            logger.debug(f"  Using full parent doc for {r.code}: {len(full_content)} chars")
            context_parts.append(
                f"- KBLI {r.code}: {r.title}\n  Full details:\n{full_content}{expert_info}",
            )
        else:
            logger.debug(f"  Using truncated description for {r.code}")
            pma_line = (
                f"PMA: {r.pma_status}; maximum foreign ownership: {r.pma_max_asing}; "
                f"official basis: {r.pma_official_basis}; source vintage: {r.pma_source_vintage}"
                if pma_verified
                else (
                    "PMA: NOT_VERIFIED. Do not state or infer an ownership status or "
                    "percentage for this code; explain the evidence gap and recommend "
                    "official OSS/BKPM verification."
                )
            )
            context_parts.append(
                f"- KBLI {r.code}: {r.title}\n  Scope: {r.description}\n  {pma_line}\n  Risk: {r.risk_category}{expert_info}",
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
        f"2. PMA STATUS: State a code-specific verdict/cap only when its context includes a located official basis and source vintage. For NOT_VERIFIED, state the evidence gap and do not infer a verdict.\n"
        f"3. CAPITAL REQUIREMENTS: If PMA relevant, state BOTH thresholds correctly — modal disetor "
        f"(paid-up capital) minimum Rp 2.5 Billion per BKPM 5/2025 (effective 2025-10-02), and minimum "
        f"investment value per KBLI per location of more than Rp 10 Billion (excluding land/buildings). "
        f"Never call Rp 10 Billion the paid-up capital minimum\n"
        f"4. LICENSING & RISK: Explain how requirements vary by business scale (Mikro/Kecil/Menengah/Besar)\n"
        f"5. PRACTICAL GUIDANCE: Include next steps, where to register (OSS), or any Bali-specific considerations\n\n"
        f"Be thorough and use only the eligible detailed information provided in the context data above. "
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

        response_text, model_used, _resp_obj, usage = await gateway.send_message(
            chat=chat,
            message=message,
            system_prompt=lang_system,
            tier=TIER_FLASH,
            enable_function_calling=False,
            conversation_messages=[{"role": "user", "content": message}],
        )

        # CRITICAL: Validate response is not empty
        if not response_text or not response_text.strip():
            logger.error("❌ LLM returned empty response. Model: %s, Usage: %s", model_used, usage)
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


# Minimum score threshold for ABSTAIN logic.
# Calibrated 2026-07-08 against the LIVE prod score distribution (query embedder
# text-embedding-3-small vs the enriched ~6k-char kbli_2025_final docs): legit
# natural-language questions score 0.28-0.52, legit single keywords 0.18-0.32,
# off-domain noise 0.11-0.16. The previous 0.40 (tuned on the older, shorter
# pre-enrichment collection) sat ABOVE the entire legit band and abstained on
# every natural question in prod — including the site's own suggested examples.
# Tripwire test: TestChatAbstainThreshold (test_kbli_notebook.py).
MIN_RELEVANCE_SCORE = 0.18

# Hardcoded known KBLI codes not present in Qdrant collection
# Used as synthetic fallback when code lookup fails via both PostgreSQL and Qdrant
# NOTE: 56101 and 56210 removed — now present in Qdrant with correct BPS data (TERBUKA)
KNOWN_KBLI_CODES: dict[str, dict] = {
    # Was "47911" with pma_status TERBATAS — a KBLI **2020** code, retired in
    # 2025 and absent from the catalogue, so both PostgreSQL and Qdrant miss it
    # by construction and this dict was its ONLY possible answer. It is reached
    # by the e-commerce keyword row below ("online shop", "toko online",
    # "jual online", ...), i.e. one of the most common questions there is — and
    # "TERBATAS" was invented: the 2025 activity is OPEN. Repointed to the real
    # successor, whose values come from the catalogue, not from this file.
    "47901": {
        "title": "PLATFORM DIGITAL INTERMEDIASI PERDAGANGAN ECERAN",
        "description": (
            "Digital intermediation platform for retail trade: online marketplaces "
            "that intermediate OTHER sellers' transactions. KBLI 2025 split the 2020 "
            "code 47911 (PERDAGANGAN ECERAN MELALUI MEDIA UNTUK BERBAGAI MACAM "
            "BARANG), which no longer exists, into two different things, and which "
            "one applies depends on the business: (a) you OPERATE the marketplace "
            "and intermediate other sellers -> 47901, TERBUKA, 100% foreign "
            "ownership; (b) you SELL YOUR OWN goods online -> the code is the "
            "PRODUCT CATEGORY you sell, not the online channel, and it carries that "
            "category's own restrictions — e.g. alcoholic beverages 47221 is "
            "TERBATAS and 47222 is TERTUTUP, while most categories are TERBUKA. Ask "
            "which of the two the client is doing before naming a single code."
        ),
        "pma_status": "TERBUKA",
        "risk_category": "Verify at OSS",
    },
    "56290": {
        "title": "AKTIVITAS PENYEDIAAN JASA BOGA LAINNYA",
        # Was "TERBATAS" — the catalogue says TERBUKA, max foreign 100%. A
        # restriction asserted where none exists refuses a lawful investment,
        # which is the costlier direction to be wrong in.
        "description": "Other food service and catering activities not elsewhere classified. Includes canteen management, institutional catering, and similar food services.",
        "pma_status": "TERBUKA",
        "risk_category": "Verify at OSS",
    },
    "56301": {
        "title": "AKTIVITAS BAR",
        "description": "Bar activities serving alcoholic and non-alcoholic beverages for on-premises consumption. Includes cocktail bars, wine bars, and other licensed drinking establishments.",
        "pma_status": "TERBUKA",
        "risk_category": "Menengah Tinggi",
    },
    "47690": {
        "title": "PERDAGANGAN ECERAN KHUSUS BARANG KESENIAN DAN REKREASI YTDL",
        "description": "Retail trade of art, recreation and collectibles, including: recorded media, musical instruments and accessories, philately/numismatics/collectibles, commercial art gallery activities (selling paintings/sculptures). Also includes art supplies (beads, clay, canvas, oils, watercolors).",
        "pma_status": "TERBUKA",
        "risk_category": "Rendah",
    },
    "96210": {
        "title": "AKTIVITAS PENATAAN DAN PANGKAS RAMBUT",
        "description": "Hair salon and barbershop activities: hair washing, cutting, styling, coloring, perming, straightening; shaving and grooming beards/mustaches. PMA: reserved for Koperasi and UMKM (Perpres 49/2021 Lampiran II, p.16, row 'Pangkas rambut/ barber shop' — dialokasikan) — maximum foreign ownership 0%, a PT PMA cannot take this bidang usaha.",
        "pma_status": "TERBATAS",
        "risk_category": "Rendah",
    },
    "96220": {
        "title": "AKTIVITAS PERAWATAN KECANTIKAN DAN PERAWATAN KECANTIKAN LAINNYA",
        "description": "Beauty care activities not performed by doctors: nail studio (nail art, manicure/pedicure), eyelash studio (eyelash extension, lash lift), brow studio (sulam alis, brow lamination), wax studio, make-up artist (MUA), facial massage, skin tanning. PMA: reserved for Koperasi and UMKM (Perpres 49/2021 Lampiran II, p.16, row 'Salon kecantikan' — dialokasikan) — maximum foreign ownership 0%, a PT PMA cannot take this bidang usaha.",
        "pma_status": "TERBATAS",
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
        "description": "Laundry and dry cleaning services: washing, ironing, dry cleaning of clothing and textiles including fur; pick-up and delivery; carpet and curtain cleaning; coin-operated laundromat; reusable diaper service. PMA: reserved for Koperasi and UMKM (Perpres 49/2021 Lampiran II, p.16, row 'Penatu' — dialokasikan) — maximum foreign ownership 0%, a PT PMA cannot take this bidang usaha. Risk level is SCALE-DEPENDENT: Mikro/Kecil/Menengah = Rendah (NIB only); Besar = Tinggi (NIB + Izin required).",
        "pma_status": "TERBATAS",
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
            "🌐 Multi-domain query detected: business=%s, visa=%s, legal=%s",
            has_business,
            has_visa,
            has_legal,
        )

    return is_multi_domain


async def _fetch_parent_documents_from_kbli_table(
    codes: list[str],
    pool,
    expected_pma: dict[str, dict[str, Any]],
) -> dict[str, _VerifiedParentDocument]:
    """Fetch only parent documents carrying the expected PMA evidence tuple.

    ``kbli_documents.content`` contains generated ownership prose.  It is not
    eligible merely because a separate Qdrant result is verified: the row's
    own metadata must carry a complete tuple and match that result exactly.
    """
    if not codes or not pool or not expected_pma:
        return {}

    parent_docs: dict[str, _VerifiedParentDocument] = {}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT kode_kbli, content, metadata FROM kbli_documents WHERE kode_kbli = ANY($1)",
                codes,
            )
            for row in rows:
                code = row["kode_kbli"]
                raw_metadata = row["metadata"]
                try:
                    metadata = (
                        raw_metadata if isinstance(raw_metadata, dict) else json.loads(raw_metadata)
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    logger.warning("Withholding parent document %s: invalid metadata", code)
                    continue

                document_evidence = _publishable_pma_evidence(metadata)
                expected_evidence = _publishable_pma_evidence(expected_pma.get(code, {}))
                content = row["content"]
                if (
                    document_evidence is None
                    or expected_evidence is None
                    or document_evidence != expected_evidence
                    or not isinstance(content, str)
                    or not content.strip()
                ):
                    logger.warning(
                        "Withholding parent document %s: PMA provenance is absent or divergent",
                        code,
                    )
                    continue
                parent_docs[code] = _VerifiedParentDocument(content, document_evidence)

            if rows:
                logger.info(
                    "✅ Admitted %s/%s parent documents from kbli_documents",
                    len(parent_docs),
                    len(rows),
                )
            else:
                logger.warning("⚠️ No parent documents found in kbli_documents for codes: %s", codes)
    except Exception as e:
        logger.error("❌ Failed to fetch parent documents: %s", e)

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
                            direct_kbli_match = KBLISearchResult(
                                code=code,
                                title=row["judul"],
                                description=_official_scope(metadata, code),
                                score=1.0,
                                pma_status=metadata.get("pma_status", "Verify at OSS"),
                                pma_max_asing=metadata.get("pma_max_asing"),
                                pma_verification_status=metadata.get(
                                    "pma_verification_status", "declared_gap"
                                ),
                                pma_official_basis=metadata.get("pma_official_basis"),
                                pma_source_vintage=metadata.get("pma_source_vintage"),
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
                                pma_max_asing=props.get("pma_max_asing"),
                                pma_verification_status=props.get(
                                    "pma_verification_status", "declared_gap"
                                ),
                                pma_official_basis=props.get("pma_official_basis"),
                                pma_source_vintage=props.get("pma_source_vintage"),
                                risk_category=props.get("kategori_risiko", "Verify at OSS"),
                            )
                            logger.info("⚠️ Direct lookup fallback to kg_nodes: %s", code)
                            break
                except Exception as lookup_err:
                    logger.warning("Direct lookup failed for %s: %s", code, lookup_err)

        # P0 FIX: If KBLI code in query but not found in PostgreSQL, try Qdrant payload filter
        if codes_from_query and not direct_kbli_match:
            code = codes_from_query[0]
            logger.info("🔢 Code %s not in kg_nodes, trying Qdrant payload filter lookup", code)
            qdrant_payload = await _get_kbli_payload_from_qdrant(code)
            if qdrant_payload:
                direct_kbli_match = _result_from_payload(qdrant_payload, score=1.0)
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
                    description=f"KBLI classification: {known['title']}.",
                    score=1.0,
                    pma_status=known["pma_status"],
                    risk_category=known["risk_category"],
                )
                logger.info(
                    f"📖 Found KBLI {code} via hardcoded KNOWN_KBLI_CODES: {known['title']}",
                )

        # P2 FIX: Keyword-to-code injection for activities not in Qdrant
        # Detects activity keywords in query and injects a direct match BEFORE semantic search
        # CORRECTED 2026-07-27: this comment used to read "prevents wrong codes
        # (e.g. 47901 for online retail instead of 47911)" — exactly backwards, and
        # that belief is what put a retired 2020 code on the channel. 47911 does not
        # exist in the KBLI 2025 catalogue; 47901 does, and it is the code that cites
        # 47911 in its pp28_sources. Verify a target against the catalogue before
        # adding a row here: a code this map names but the stores do not have will be
        # answered by the hardcoded dict alone, with no retrieval to correct it.
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
                "47901",
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
                        description=f"KBLI classification: {known['title']}.",
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
                results.append(_result_from_payload(p, score=r.get("score", 0.0)))
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
                                if r.pma_verdict_verified and "expert_legal" in props:
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
            logger.warning("⚠️ Qdrant search failed, falling back to PostgreSQL: %s", q_err)
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
                                    pma_max_asing=props.get("pma_max_asing"),
                                    pma_verification_status=props.get(
                                        "pma_verification_status", "declared_gap"
                                    ),
                                    pma_official_basis=props.get("pma_official_basis"),
                                    pma_source_vintage=props.get("pma_source_vintage"),
                                    risk_category=props.get("kategori_risiko", "Unknown"),
                                ),
                            )
                        logger.info(
                            f"✅ Found {len(results)} KBLI results from PostgreSQL fallback",
                        )
            except Exception as db_err:
                logger.error("❌ PostgreSQL fallback failed: %s", db_err)

        # Detect KBLI codes from results
        codes_from_results = [r.code for r in results if r.code != "N/A"]
        detected_kbli = list(dict.fromkeys(codes_from_query + codes_from_results))

        # MULTI-DOMAIN ROUTING: If query spans KBLI + visa/legal, use KG Orchestrator
        if _is_multi_domain_query(kbli_request.query) and not _requires_structured_pma_gate(
            kbli_request.query
        ):
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
                logger.error("❌ KG Orchestrator failed, falling back to KBLI-only: %s", kg_err)
                # Fall through to standard KBLI processing
        elif _is_multi_domain_query(kbli_request.query):
            logger.info(
                "🛡️ Multi-domain query kept on structured KBLI path because it may require a PMA verdict"
            )

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
                "- Modal disetor (paid-up capital) minimum for PMA: Rp 2.5 Billion (Permen BKPM 5/2025, "
                "effective 2025-10-02) — separate from the minimum investment value per KBLI per location "
                "(more than Rp 10 Billion, excluding land/buildings)\n"
                "- Verify the exact cap for your specific KBLI code at: oss.go.id/perizinan\n\n"
                "Compare with: TERBUKA (100% foreign ownership allowed) | TERTUTUP (foreigners cannot invest)"
            ),
            "terbuka": (
                "**TERBUKA** means the business activity is *fully open to foreign investment*. "
                "Foreign investors (PMA) can own up to 100% of the business.\n\n"
                "**Key facts:**\n"
                "- No ownership cap for foreigners\n"
                "- Modal disetor (paid-up capital) minimum for PMA: Rp 2.5 Billion (Permen BKPM 5/2025, "
                "effective 2025-10-02) — separate from the minimum investment value per KBLI per location "
                "(more than Rp 10 Billion, excluding land/buildings)\n"
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
                logger.info("📚 Glossary shortcut triggered for term: %s", term)
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
                "⚠️ All results below threshold %s. Triggering ABSTAIN.",
                MIN_RELEVANCE_SCORE,
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
            # Keyword-injected match (no code in query): use ONLY the direct match,
            # so a lower-ranked Qdrant hit cannot displace the code the keyword map
            # deliberately chose. (The original comment here named 47901 as the
            # "wrong" result to suppress in favour of 47911 — backwards: 47911 is a
            # retired 2020 code absent from KBLI 2025, 47901 is the live successor.)
            results = [direct_kbli_match]
            logger.info(
                f"🎯 Keyword injection: restricting results to direct match only ({direct_kbli_match.code})",
            )
        elif not has_direct_match:
            results = filtered_results if filtered_results else results

        # Resolve the authoritative Qdrant tuple before considering generated
        # Postgres prose. The parent reader then requires its own tuple to match.
        await _fill_bali_verdicts(results)

        # Fetch full parent documents from kbli_documents table for complete context
        codes_to_fetch = [r.code for r in results if r.code != "N/A"]
        expected_pma = {r.code: r.model_dump() for r in results if r.code != "N/A"}
        parent_docs = await _fetch_parent_documents_from_kbli_table(
            codes_to_fetch,
            pool,
            expected_pma,
        )

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
        logger.error(f"❌ KBLI Chat Error: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI Engine error: {e!s}") from e
