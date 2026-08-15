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
from collections.abc import Iterable
from inspect import isawaitable
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from backend.app.core.config import settings
from backend.app.dependencies import (
    get_optional_database_pool,
    get_search_service,
)
from backend.core.collection_registry import resolve_collection_name
from backend.services.kbli_pma_disclosure import (
    disclose_bali,
    disclose_pma,
    pma_claims_verified,
)
from backend.services.kbli_pp28_provenance import licensing_disclosure
from backend.services.kbli_requires_kind import (
    classify_requires_target,
    permit_name_verdict,
)

logger = logging.getLogger(__name__)

KBLI_QUERY_MAX_LENGTH = 1024
KBLI_SESSION_ID_MAX_LENGTH = 128
KBLI_PUBLIC_LIMIT_MAX = 25
KBLISearchQuery = Annotated[str, Query(min_length=1, max_length=KBLI_QUERY_MAX_LENGTH)]
KBLIPublicLimit = Annotated[int, Query(ge=1, le=KBLI_PUBLIC_LIMIT_MAX)]

# Persistent KBLI HTTP client (Golden Rule 10: never create AsyncClient per-request)
_kbli_http_client: httpx.AsyncClient | None = None


def _get_kbli_client() -> httpx.AsyncClient:
    """Get or create persistent HTTP client for KBLI Qdrant queries."""
    global _kbli_http_client
    if _kbli_http_client is None or _kbli_http_client.is_closed:
        _kbli_http_client = httpx.AsyncClient(
            timeout=15.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _kbli_http_client


async def close_kbli_http_client() -> None:
    """Close persistent KBLI Qdrant HTTP client during app shutdown."""
    global _kbli_http_client
    if _kbli_http_client is None:
        return
    await _kbli_http_client.aclose()
    _kbli_http_client = None


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


class _PMADisclosure(BaseModel):
    """Fail-closed public contract for whole-code foreign-ownership claims.

    A raw status/cap is not publishable evidence.  It is disclosed only when
    the same record carries the canonical verification state, an official
    locator, and the source vintage.  Keeping this invariant on the response
    model protects every constructor (including old cache entries and future
    fallback paths), rather than relying on each caller to remember the gate.
    """

    pma_status: str = "NOT_VERIFIED"
    pma_max_asing: int | float | str | None = None
    pma_verification_status: str = "declared_gap"
    pma_official_basis: str | None = None
    pma_source_vintage: str | None = None
    pma_cap_special: bool = False
    pma_cap_verified: bool = False

    @model_validator(mode="before")
    @classmethod
    def _withhold_unverified_pma(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        disclosed = dict(value)
        public = disclose_pma(disclosed)
        disclosed.update(
            {
                key: public[key]
                for key in (
                    "pma_status",
                    "pma_max_asing",
                    "pma_verification_status",
                    "pma_official_basis",
                    "pma_source_vintage",
                    "pma_cap_special",
                    "pma_cap_verified",
                )
            }
        )
        return disclosed

    @property
    def pma_verdict_verified(self) -> bool:
        # Re-check the full tuple instead of trusting the marker alone.  Models
        # are mutable in this router, so a later assignment must not turn a
        # partial tuple into a publishable verdict merely by leaving ``located``
        # behind.
        return pma_claims_verified(self.model_dump())


class KBLIDetail(_PMADisclosure):
    code: str
    title: str
    description: str
    licensing_status: str
    sector: str
    risk_profile: str
    licenses: list[KBLILicense]
    # REQUIRES-edge targets that are NOT permits, bucketed by what they are
    # (costs / durations / obligations / regulations / documents / entity_forms
    # / immigration / systems / other). Additive and defaulted, so a cached
    # payload written before this field existed still validates on read.
    related_requirements: dict[str, list[str]] = {}
    related_codes: list[str] = []
    expert_legal: dict | None = None
    # WHOSE licences these are. A KBLI-2025 code that is new in the 2025
    # numbering has no PP 28/2025 row of its own; the canonical fills it from
    # the KBLI-2020 ancestors and records them here. 390 of 1,559 codes serve
    # carried content, and 217 inherit a `pb_umku` permit that way — `62110`
    # (video games) shows three defence-industry permits belonging to the five
    # 62xxx programming codes it was sourced from.
    #
    # Both fields are additive and defaulted, so a payload cached before they
    # existed still validates on read. The note is BUILT FROM the list, so the
    # sentence and the codes cannot drift apart.
    licensing_content_inherited_from: list[str] | None = None
    licensing_note: str | None = None

    @model_validator(mode="after")
    def _withhold_unverified_editorial(self) -> "KBLIDetail":
        """Do not let cached or future detail constructors bypass the PMA gate."""
        if not self.pma_verdict_verified:
            self.expert_legal = None
        return self


class KBLISearchResult(_PMADisclosure):
    code: str
    title: str
    description: str
    score: float
    risk_category: str = "Unknown"
    expert_legal: dict | None = None
    # The Bali provincial verdict, carried on the same flat Qdrant payload as
    # `pma_status` and — until 2026-08-03 — read by nothing. `pma_status` answers
    # "may a foreigner own this activity in Indonesia"; these answer "may a PT PMA
    # register it in Bali", and the two disagree on 518 codes. Measured on the
    # live collection that day: point `86995` carried `bali_blocked: true` while
    # `chat_kbli` told a client "yes, you absolutely can" open one in Bali. The
    # store knew; the model never saw it.
    #
    # `None` means the payload carried no verdict, and is NOT "open" — a point
    # written before the Bali layer existed must produce silence, never a claim.
    bali_status: str | None = None
    bali_blocked: bool | None = None
    bali_reason: str = ""
    # The national foreign-ownership CEILING, carried on the same flat payload.
    # `pma_status` is a word ("TERBUKA"/"TERBATAS"/"TERTUTUP") and it is the only
    # ownership fact the context line prints; the ceiling is the number, and the
    # two can disagree in the direction that matters. Measured 2026-08-05 on the
    # canonical: `79122` (Umrah/Hajj travel) reads `TERBATAS` with a ceiling of
    # **0** — closed to foreign capital outright — while its Bali verdict is "not
    # blocked". A reader shown only the word hears "restricted, so find a local
    # partner"; the number says there is nothing to partner into.
    #
    # `None` means the payload carried no ceiling. It is NOT zero: an absent cap
    # is stored as `""` by the indexer, and reading absence as 0% would invent a
    # closure on every point written before the field existed.

    @model_validator(mode="before")
    @classmethod
    def _withhold_malformed_bali(cls, value: Any) -> Any:
        """Apply the Bali tuple gate before Pydantic can coerce source values."""
        if not isinstance(value, dict):
            return value
        disclosed = dict(value)
        bali = disclose_bali(disclosed)
        disclosed.update(
            {
                "bali_status": bali["bali_status"],
                "bali_blocked": bali["bali_blocked"],
                "bali_reason": bali["bali_reason"],
            }
        )
        return disclosed

    @model_validator(mode="after")
    def _withhold_unverified_editorial(self) -> "KBLISearchResult":
        """Withhold PMA-dependent Bali and editorial claims as one atom."""
        if not self.pma_verdict_verified:
            self.bali_status = None
            self.bali_blocked = None
            self.bali_reason = ""
            self.expert_legal = None
        return self


class KBLINotebookChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=KBLI_QUERY_MAX_LENGTH)
    session_id: str | None = Field(default=None, max_length=KBLI_SESSION_ID_MAX_LENGTH)


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


# The ingestion script (reindex_kbli_2025_final.py) stores the embedding text —
# which opens with an internal "[CONTEXT: ...]" grounding header — as the payload
# `content` field. That header exists for the embedding model, not for humans:
# strip it before content is used as a user-facing snippet.
_CONTEXT_HEADER_RE = re.compile(r"^\s*\[CONTEXT:[^\]]*\]\s*")

_KBLI_CODE_RE = re.compile(r"^\d{4,5}$")


def _clean_snippet(text: str | None) -> str:
    """Strip the internal [CONTEXT: ...] embedding header from payload content."""
    return _CONTEXT_HEADER_RE.sub("", text or "").lstrip()


def _pma_disclosure_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the complete PMA evidence tuple from one authoritative record."""
    return {
        "pma_status": _payload_value(payload, "pma_status", default="NOT_VERIFIED"),
        "pma_max_asing": _payload_value(payload, "pma_max_asing"),
        "pma_verification_status": _payload_value(
            payload,
            "pma_verification_status",
            default="declared_gap",
        ),
        "pma_official_basis": _payload_value(payload, "pma_official_basis"),
        "pma_source_vintage": _payload_value(payload, "pma_source_vintage"),
        "pma_cap_special": _payload_value(payload, "pma_cap_special", default=False),
        "pma_cap_verified": _payload_value(payload, "pma_cap_verified", default=False),
    }


def _official_scope(payload: dict[str, Any], code: str) -> str:
    """Return only an explicitly labelled official KBLI description.

    Legacy gold Qdrant points used ``description`` for generated editorial, so
    that ambiguous key is not an eligible fallback on a public/search surface.
    """
    description = _payload_value(payload, "official_description", "uraian", default="")
    if description:
        return _clean_snippet(str(description))[:200] + "..."
    return f"Official BPS description unavailable for KBLI {code}."


def _result_from_payload(payload: dict[str, Any], score: float) -> "KBLISearchResult":
    """Build a KBLISearchResult from a flat/legacy Qdrant KBLI payload."""
    code = _payload_value(payload, "kode_kbli", "kode", "kode_kbli_2025", default="N/A")
    return KBLISearchResult(
        code=code,
        title=_payload_value(payload, "judul", "title_id", default="N/A"),
        # `content`/`text` contains generated licensing and PMA prose.  Search
        # snippets are public output, so only explicitly labelled BPS scope is
        # eligible; legacy ``description`` can be gold editorial.
        description=_official_scope(payload, code),
        score=round(score, 4),
        risk_category=_payload_value(payload, "kategori_risiko", default="Unknown"),
        bali_status=_payload_value(payload, "bali_status"),
        bali_blocked=_payload_value(payload, "bali_blocked"),
        bali_reason=_payload_value(payload, "bali_reason", default="") or "",
        **_pma_disclosure_fields(payload),
    )


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
        health_status["error"] = f"Health check failed: {e!s}"
        logger.error("❌ LLM health check error: %s", e, exc_info=True)

    return health_status


async def _get_kbli_payload_from_qdrant(code: str) -> dict | None:
    """Fetch Qdrant payload for a specific KBLI code (by exact match on kode_kbli).

    Selects the canonical BPS record POSITIVELY (doc_type == kbli_bps) rather than
    excluding kbli_gold. Since 2026-08-09 a code can carry a second Qdrant point
    (doc_type=kbli_gold, same kode_kbli — index_kbli_gold_content.py::build_payload
    writes the identical field this filter matches on) sharing this exact query.
    With `limit: 1` below and no `order_by`, Qdrant used to return whichever of the
    two points has the smaller internal point ID — and the BPS/gold point IDs are
    md5-hash UUIDs of two UNRELATED strings ("kbli_2025_bps::<code>" in
    reindex_kbli_2025_final.py::deterministic_uuid() vs "kbli_gold_editorial::<code>"
    in index_kbli_gold_content.py::deterministic_uuid()), so which one sorted first
    was a per-code coin-flip with zero relation to score, recency, or doc_type —
    measured empirically at 10/10 correlation between "smaller UUID" and the
    observed winner on a 10-code sample during the 2026-08-09 gold-314 apply, 3 of
    which flipped to gold-first with the twin BPS record vanishing entirely from
    `/search` results (not merely demoted: the semantic-search branch below
    separately drops any hit sharing this code once `exact_result` is chosen, so
    the losing twin was excluded twice over).
    A NEGATIVE filter (exclude kbli_gold) would have fixed today's known culprit
    but left the same coin-flip primed for the next new doc_type this collection
    grows; a POSITIVE selection of the entity this endpoint's contract actually
    promises -- "the canonical BPS record for this code" -- stays correct by
    construction regardless of what else gets indexed later. Honest edge: a code
    with no BPS point (e.g. a gold-only orphan) now correctly falls through to
    not-found instead of serving gold content as if it were canonical.
    """
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    url = f"{settings.qdrant_url}/collections/{KBLI_COLLECTION}/points/scroll"
    try:
        client = _get_kbli_client()
        for filter_key in (
            "kode_kbli",
            "kode",
            "metadata.kode",
            "metadata.kode_kbli",
            "metadata.kode_kbli_2025",
        ):
            payload = {
                "filter": {
                    "must": [
                        {"key": filter_key, "match": {"value": code}},
                        # Flat vs legacy-nested doc_type, same dual-key idiom used
                        # by reindex_kbli_2025_final.py's own delete/count filters
                        # and by this router's _payload_value() reader.
                        {
                            "should": [
                                {"key": "doc_type", "match": {"value": "kbli_bps"}},
                                {
                                    "key": "metadata.doc_type",
                                    "match": {"value": "kbli_bps"},
                                },
                            ],
                        },
                    ],
                },
                "limit": 1,
                "with_payload": True,
            }
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            points = resp.json().get("result", {}).get("points", [])
            if points:
                return points[0].get("payload", {})
    except Exception as e:
        logger.warning("Qdrant lookup for KBLI %s failed (non-critical): %s", code, e)
    return None


async def _search_kbli_qdrant(query_embedding: list[float], limit: int) -> list[dict]:
    """Direct Qdrant search for KBLI collection (flat payload structure)."""
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    url = f"{settings.qdrant_url}/collections/{KBLI_COLLECTION}/points/query"
    payload = {"query": query_embedding, "using": "dense", "limit": limit, "with_payload": True}
    client = _get_kbli_client()
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {}).get("points", data.get("result", []))


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


def related_codes_from_rows(rows: Iterable[str], code: str) -> list[str]:
    """Map `kbli:<code>` entity ids to bare codes, deduped, self excluded.

    The SQL already does both (see the caller), so this is a second, independent
    line rather than the only one: the graph holds 1,341 duplicated BELONGS_TO
    rows, and a future edit to that query — or a caller that forgets `DISTINCT` —
    would put the duplicates straight back in front of a client. Order is the
    caller's (the query is `ORDER BY source_entity_id`), preserved here.
    """
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        bare = row.replace("kbli:", "", 1).strip()
        if not bare or bare == code or bare in seen:
            continue
        seen.add(bare)
        out.append(bare)
    return out


def _resolve_risk_profile(qdrant_risk: str | None, licenses: list["KBLILicense"]) -> str:
    """Risk label surfaced to the client for a KBLI code.

    Honest gap over false reassurance (Zero decision 2026-07-17): when no risk is
    defined anywhere — no Qdrant ``kategori_risiko`` and no license risk row — return
    ``"Not classified"`` instead of a made-up ``"Low"``. A cured false-friend code
    (``per_skala`` detached from a cross-vintage collision) has NO risk basis, and
    ``"Low"`` would be a false-reassuring assertion. The mouth explorer's
    ``getRiskLevel``/``getRiskBadge`` + ``RiskGauge`` render this as a neutral,
    needle-less state; WA/webchat pass the string verbatim to the LLM.
    """
    return qdrant_risk or (licenses[0].risk_level if licenses else None) or "Not classified"


@router.get("/search", response_model=list[KBLISearchResult])
async def search_kbli(
    query: KBLISearchQuery,
    limit: KBLIPublicLimit = 10,
    search_service=Depends(get_search_service),
) -> Any:
    """Search for KBLI codes using semantic search (Qdrant)."""
    start_time = time.time()
    logger.info("🔍 KBLI Search Request: '%s' (limit: %s)", query, limit)

    try:
        # Exact-code fast-path: a bare 4/5-digit query is a code lookup, not a
        # semantic search — embedding a bare number ranks by noise (observed live
        # 2026-07-08: "68111" did not surface 68111 in the top 5). Unknown codes
        # fall through to semantic search so non-canonical forms (e.g. 68100)
        # still get neighborly suggestions.
        exact_result: KBLISearchResult | None = None
        code_query = query.strip()
        if _KBLI_CODE_RE.fullmatch(code_query):
            exact_payload = await _get_kbli_payload_from_qdrant(code_query)
            if exact_payload:
                exact_result = _result_from_payload(exact_payload, score=1.0)

        embedding = await _resolve_embedding(search_service, query)
        results = await _search_kbli_qdrant(embedding, limit)

        search_results: list[KBLISearchResult] = [exact_result] if exact_result else []
        for r in results:
            if len(search_results) >= limit:
                break
            candidate = _result_from_payload(r.get("payload", {}), score=r.get("score", 0.0))
            if exact_result and candidate.code == exact_result.code:
                continue
            search_results.append(candidate)

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"✅ KBLI Search Completed: found {len(search_results)} results in {duration:.2f}ms",
        )
        return search_results
    except httpx.HTTPStatusError as e:
        logger.warning("⚠️ KBLI Search Qdrant error: %s", e)
        raise HTTPException(status_code=503, detail="Search engine temporarily unavailable") from e
    except httpx.TimeoutException as e:
        logger.warning("⚠️ KBLI Search timeout: %s", e)
        raise HTTPException(status_code=503, detail="Search engine temporarily unavailable") from e
    except Exception as e:
        logger.error(f"❌ KBLI Search Failed: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search engine unavailable") from e


@router.get("/inspect/{code}", response_model=KBLIDetail)
async def inspect_kbli(code: str, pool=Depends(get_optional_database_pool)) -> Any:
    """Retrieve deep KG metadata with dynamic TTL based on sector volatility."""
    from backend.core.cache import get_cache_service

    # v2 → v3 (2026-08-06): the payload gained the inherited-licensing
    # disclosure. A cached v2 entry validates on read — the new fields simply
    # default to None — so a carried code would keep answering WITHOUT the note
    # for up to the 30-day TTL, and a shipped cure invisible for a month is
    # indistinguishable from one that never shipped. Bumping the version evicts
    # atomically at deploy instead of depending on someone remembering to run
    # the per-code cache-bust for the right 390 codes.
    #
    # v3 → v4 (2026-08-06): this one is WORSE than a missing field and needs the
    # bump for a different reason. `permit_name_verdict` changes the CONTENT of
    # `licenses[]` — entries that were served as permits move to `obligations`
    # and `unspecified_permits`. A cached v3 entry is fully valid on read and
    # would keep serving `izin_usaha_tidak_diketahui` as a permit named "Izin
    # Usaha" on the 186 codes that carry it. The stale payload is not
    # incomplete, it is WRONG, and nothing in the response would betray it.
    # Rule of thumb for the next reader: bump whenever the meaning of an
    # existing field changes, not only when a field is added.
    # v4 -> v5: PMA values are now an evidence tuple.  Old cache entries carry
    # raw status/cap without the required locator and vintage, so they must be
    # re-read through the fail-closed response contract immediately.
    cache_key = f"kbli_inspect_v5_{code}"
    ttl = get_kbli_ttl(code)

    # Try manual cache check
    cache_manager = get_cache_service()
    if cache_manager:
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            return KBLIDetail(**cached_data)

    logger.info("🧐 KBLI Inspection (Dynamic TTL %ss): %s", ttl, code)
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
                "SELECT * FROM kg_nodes WHERE entity_id = $1",
                f"kbli:{code}",
            )

            if not node:
                logger.warning("⚠️ KBLI %s not found in Knowledge Graph", code)
                raise HTTPException(status_code=404, detail=f"KBLI code {code} not found")

            # 2. Extract Properties
            props = (
                json.loads(node["properties"])
                if isinstance(node["properties"], str)
                else node["properties"]
            )

            # 3. Fetch REQUIRES-edge targets.
            #
            # These are NOT all licences. The graph hangs costs, durations,
            # obligations, regulations, company forms and the OSS system itself
            # off the same relationship — 35 distinct target entity types were
            # measured on prod. Rendering every one of them as a licence told a
            # restaurant client that "10 Billion IDR" and "PT PMA" were permits
            # to obtain. `entity_type` is now selected and classified; see
            # `backend/services/kbli_requires_kind.py` for the reasoning.
            license_query = """
                SELECT n.*, n.entity_type AS target_entity_type, e.properties as edge_props
                FROM kg_nodes n
                JOIN kg_edges e ON n.entity_id = e.target_entity_id
                WHERE e.source_entity_id = $1 AND e.relationship_type = 'REQUIRES'
            """
            licenses_raw = await conn.fetch(license_query, f"kbli:{code}")

            licenses = []
            related_requirements: dict[str, list[str]] = {}
            for lic in licenses_raw:
                lic_props = (
                    json.loads(lic["properties"])
                    if isinstance(lic["properties"], str)
                    else lic["properties"]
                )
                # A node whose `properties` is a scalar (67 such rows exist for
                # entity_type='kbli' alone) must not crash the lookup.
                if not isinstance(lic_props, dict):
                    lic_props = {}

                kind = classify_requires_target(lic["target_entity_type"])
                if kind == "license":
                    # The TYPE says permit; the NAME can still say otherwise.
                    # `izin_usaha_tidak_diketahui` — the graph admitting it does
                    # not know which permit — reached 186 codes as a permit
                    # called "Izin Usaha"; 71 whole obligation sentences reached
                    # 39 more. Same treatment as any non-permit: bucketed, never
                    # dropped. See kbli_requires_kind.permit_name_verdict.
                    kind = permit_name_verdict(lic["entity_id"], lic["name"])
                    if kind == "permit":
                        kind = "license"
                if kind != "license":
                    # Kept, never silently dropped — bucketed so a reader can
                    # still see what the graph attached to this code.
                    related_requirements.setdefault(kind, []).append(lic["name"])
                    continue

                licenses.append(
                    KBLILicense(
                        type=lic["name"],
                        scale=lic_props.get("skala_usaha", ["All"]),
                        risk_level=lic_props.get("kategori_risiko", "Unknown"),
                        sla=lic_props.get("jangka_waktu", "N/A"),
                        requirements=lic_props.get("kewajiban", []),
                    ),
                )

            # Stable order per bucket: the endpoint is cached, and a set-like
            # jitter between calls would look like data churn to a consumer.
            related_requirements = {
                bucket: sorted(set(names)) for bucket, names in sorted(related_requirements.items())
            }

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
                #
                # DISTINCT and the self-exclusion both belong in SQL, not after the
                # fetch: `LIMIT 6` is applied by Postgres, so anything filtered out
                # afterwards silently COSTS A SLOT instead of being replaced. The
                # graph carries 1,341 duplicated (source, sector) BELONGS_TO rows —
                # every duplicated pair appears exactly twice — so the old query
                # spent its six rows on three codes and then showed each twice.
                # Measured on prod: 79122 returned ['79110','79110','79121','79121']
                # and now returns six distinct siblings; 56101 likewise.
                sector_prefix = code[:2]
                others = await conn.fetch(
                    "SELECT DISTINCT source_entity_id FROM kg_edges "
                    "WHERE target_entity_id = $1 AND relationship_type = 'BELONGS_TO' "
                    "AND source_entity_id LIKE $2 "
                    "AND source_entity_id <> $3 "
                    "ORDER BY source_entity_id LIMIT 6",
                    sector_id,
                    f"kbli:{sector_prefix}%",
                    f"kbli:{code}",
                )
                related_codes = related_codes_from_rows(
                    (r["source_entity_id"] for r in others), code
                )

            # 5. Enrich with Qdrant payload (pma_status, risk category)
            qdrant_payload = await _get_kbli_payload_from_qdrant(code)
            qdrant_risk = (
                _payload_value(qdrant_payload, "kategori_risiko") if qdrant_payload else None
            )

            # Never splice a status from one store to provenance from another.
            # A Qdrant point is one atomic evidence record; only when no point
            # exists do we use the KG node as the complete fallback record.
            pma_source = qdrant_payload if qdrant_payload else props
            pma_disclosure = _pma_disclosure_fields(pma_source)

            risk_profile = _resolve_risk_profile(qdrant_risk, licenses)

            # Patch licenses with "Unknown" risk using Qdrant value
            if qdrant_risk:
                for lic in licenses:
                    if lic.risk_level == "Unknown":
                        lic.risk_level = qdrant_risk

            # Disclose carried licensing content. Requires
            # `properties.pp28_sources` on the node, which
            # `backend/scripts/kg_kbli_resync.py` syncs from the canonical; an
            # unsynced node yields None here — today's silence, never a
            # fabricated provenance.
            inherited_from, licensing_note = licensing_disclosure(
                props.get("pp28_sources"), code, bool(licenses)
            )

            logger.info(
                "✅ KBLI %s details retrieved (pma=%s, risk=%s, inherited_licensing=%s)",
                code,
                pma_disclosure["pma_status"],
                risk_profile,
                bool(inherited_from),
            )

            result = KBLIDetail(
                code=code,
                title=node["name"],
                description=props.get("uraian", node["description"]),
                licensing_status=props.get("licensing_status", "REGULATED"),
                sector=sector_id.replace("sektor:", "") if sector_id else "N/A",
                risk_profile=risk_profile,
                licenses=licenses,
                related_requirements=related_requirements,
                related_codes=related_codes,
                # The legacy blob contains unstructured PMA implications.  It
                # is publishable only under the same verified tuple; otherwise
                # omit it wholesale instead of attempting prose heuristics.
                expert_legal=(
                    props.get("expert_legal")
                    if pma_disclosure.get("pma_verification_status") == "located"
                    and pma_disclosure.get("pma_official_basis")
                    and pma_disclosure.get("pma_source_vintage")
                    else None
                ),
                licensing_content_inherited_from=inherited_from,
                licensing_note=licensing_note,
                **pma_disclosure,
            )

            # Save to cache with dynamic TTL
            if cache_manager:
                await cache_manager.set(cache_key, result.model_dump(), ttl=ttl)

            return result
    except HTTPException:
        raise
    except (ConnectionResetError, OSError) as e:
        # Stale connection from Fly.io cold start — expire and signal retry
        logger.warning("⚠️ KBLI Inspection stale connection for %s: %s", code, e)
        try:
            await pool.expire_connections()
        except Exception as pool_err:
            logger.debug("Pool expire skipped: %s", pool_err)
        raise HTTPException(
            status_code=503,
            detail="Database connection reset — please retry",
            headers={"Retry-After": "5"},
        ) from e
    except Exception as e:
        err_msg = str(e)
        if "connection was closed" in err_msg or "connection is closed" in err_msg:
            logger.warning("⚠️ KBLI Inspection closed connection for %s: %s", code, e)
            try:
                await pool.expire_connections()
            except Exception as pool_err:
                logger.debug("Pool expire skipped: %s", pool_err)
            raise HTTPException(
                status_code=503,
                detail="Database connection reset — please retry",
                headers={"Retry-After": "5"},
            ) from e
        logger.error("❌ KBLI Inspection Error for %s: %s", code, err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal processing error: {err_msg}") from e


# CHAT ENDPOINT & LLM HELPERS → kbli_notebook_chat.py
