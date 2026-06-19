"""Document-intake OCR + classification stage (FASE 3a).

Two responsibilities, both 100% local (Symbiosis Law 2 / UU-PDP):

  1. ``ocr_pages``        -- run a LOCAL vision model over preprocessed pages,
                            returning per-page transcribed text + confidence.
  2. ``classify_document`` -- decide the document TYPE from the OCR text, with a
                            hard anti-hallucination floor: undeterminable ->
                            {"type": "unknown", "confidence": 0.0}, never a guess.

STRICT-LOCAL / 0-byte-to-cloud
------------------------------
Forked from ``backend.app.routers.crm_enhanced`` Attempt-1 (Ollama vision) but
the cloud-LLM fallback (Attempt-2) is DROPPED entirely. There is no cloud path,
no external-CLI subprocess, no external API. The intake spec verifies the
absence of any cloud token over this file. PII (passport, KTP, akta) is read
from local images and sent ONLY to localhost:11434 (Ollama on the Pro).

Model choice (FASE 0 registry role ``ocr_vision``)
--------------------------------------------------
Registry role ``ocr_vision`` -> ``qwen2.5vl:7b`` is the PRIMARY OCR model
(MODEL_TOPOLOGY.json, flipped by PR #1359 on 2026-06-12; hardcoded default
aligned by the Antibody Debt #10 fix on 2026-06-13 so a missing/unreadable
topology can no longer silently resurrect the broken primary).

HISTORY — why qwen3-vl:8b is NOT the primary anymore. EMPIRICAL FINDING
(2026-06-04, verified on this Pro against a real Indonesian LHKPN document,
/api/generate + /api/chat, num_predict up to 4096): ``qwen3-vl:8b`` is a
*reasoning* VLM -- it emits its transcription into the ``thinking`` field and
returns ``response`` EMPTY (done_reason="length"), burning the whole token
budget on chain-of-thought without finalizing. Raw probe: response=0 chars,
thinking=9353 chars ("Got it, let's transcribe..."). ``qwen2.5vl:7b``
transcribed the SAME page cleanly (1148 verbatim chars). Under batch load the
dual model-swap thrash (qwen3-vl <-> qwen2.5vl) drove Ollama into 500s and the
2026-06-12 backlog run poisoned 782/812 review_pending proposals with empty
OCR (PR #1359 commit message). This matches the standing CLAUDE.md S9
invariant: vision = qwen2.5vl:7b ONLY.

The OCR path stays defensive:
  (a) call the resolved primary; if ``response`` has text, use it;
  (b) else salvage the ``thinking`` field (no-op for non-reasoning VLMs,
      kept for any future reasoning-VLM experiment via the topology role);
  (c) if still empty, CASCADE to ``_OCR_FALLBACK``. With today's topology
      primary == fallback, so step (c) is a same-model RETRY — kept on
      purpose: live logs show it rescues pages that returned empty once.
All calls are local Ollama -- the cascade never leaves the Pro.

Golden Rule #10: persistent httpx client (``_get_client``), never
``AsyncClient()`` per call. crm_enhanced violates this with ``async with`` in a
function -- we deliberately do NOT copy that.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import httpx

from backend.services.intake.model_roles import resolve_model_role

logger = logging.getLogger("zantara.intake.classify")

# ---------------------------------------------------------------------------
# Models / endpoint
# ---------------------------------------------------------------------------

# ocr_vision role (FASE 0 registry). Hardcoded default used when the topology
# file is unavailable in an isolated worker/test environment. MUST stay aligned
# with the CLAUDE.md S9 vision invariant (qwen2.5vl:7b ONLY): until 2026-06-13
# this defaulted to qwen3-vl:8b, so a missing topology silently resurrected the
# documented-broken primary (empty response, Ollama 500 thrash — see HISTORY in
# the module docstring). Guarded by test_ocr_primary_default_invariant.
_OCR_PRIMARY_DEFAULT = "qwen2.5vl:7b"  # ocr_vision role

# Local-only fallback (CLAUDE.md S9 default vision model). Used when the primary
# reasoning VLM returns no usable transcription. Both are Ollama -> 0 cloud.
_OCR_FALLBACK = "qwen2.5vl:7b"

OLLAMA_URL = os.getenv("INTAKE_OLLAMA_URL", os.getenv("OLLAMA_URL", "http://localhost:11434"))

# Per-page hard cap. CLAUDE.md OCR rule: 120s for >3 pages -- but we OCR one page
# per request, so this is the single-page ceiling (reasoning VLM is slow).
OCR_PAGE_TIMEOUT_SECONDS = 120.0

# Token budget for transcription. Generous because qwen3-vl spends most of it on
# (discarded) thinking before -- sometimes -- emitting text.
OCR_NUM_PREDICT = 2048

_OCR_PROMPT = (
    "Transcribe ALL legible text from this document image verbatim. "
    "Preserve numbers, dates, names exactly as printed. "
    "Output the transcription only -- no commentary, no labels. "
    "If a region is unreadable, write [unreadable]."
)


def _resolve_ocr_model() -> str:
    """Prefer the FASE-0 registry ``ocr_vision`` role; else the hardcoded default."""
    return resolve_model_role("ocr_vision", _OCR_PRIMARY_DEFAULT)


# ---------------------------------------------------------------------------
# Persistent HTTP client (Golden Rule #10)
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Get/create the persistent Ollama client. Localhost -> short connect TO."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(OCR_PAGE_TIMEOUT_SECONDS, connect=5.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )
    return _client


async def close_client() -> None:
    """Close the persistent client. Call from the worker/app lifespan teardown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
    logger.info("intake classify HTTP client closed")


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

# Meta-preamble qwen3-vl emits before (sometimes) transcribing. We salvage the
# thinking field but drop this lead-in so it does not pollute the OCR text.
_THINK_PREAMBLE = re.compile(
    r"^(got it[,.]?|okay[,.]?|let'?s|first[,.]?|i need to|i'?ll|sure[,.]?).*?"
    r"(transcrib\w+|read|look at).*?[:.]\s*",
    re.IGNORECASE | re.DOTALL,
)


def _salvage_thinking(thinking: str) -> str:
    """Best-effort extraction of transcription text from a reasoning preamble.

    qwen3-vl puts the answer in ``thinking``. The text is the chain-of-thought
    so it is noisier than a clean ``response``, but for a page that the fallback
    can also read this is only a tie-breaker. We strip the obvious meta lead-in;
    if nothing survives, return "" so the cascade triggers.
    """
    if not thinking:
        return ""
    stripped = _THINK_PREAMBLE.sub("", thinking.strip(), count=1).strip()
    # If the model never got past meta-reasoning (no quoted content), bail.
    return stripped if len(stripped) >= 20 else ""


async def _ollama_vision(
    model: str,
    png_b64: str,
    prompt: str = _OCR_PROMPT,
    num_predict: int = OCR_NUM_PREDICT,
) -> tuple[str, str | None]:
    """Single /api/generate vision call. Returns (response_text, thinking_text)."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "images": [png_b64],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": num_predict},
        # CLAUDE.md S9: qwen 3.x family needs think:false. qwen3-vl ignores it
        # for vision (empirically still reasons) but qwen2.5vl honours it.
        "think": False,
    }
    client = _get_client()
    r = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip(), (data.get("thinking") or "").strip()


def _heuristic_confidence(text: str) -> float:
    """Confidence for OCR text: length + low [unreadable] density. 0.0 if empty."""
    if not text:
        return 0.0
    unreadable = text.count("[unreadable]")
    base = 0.70 if len(text) >= 40 else 0.45
    penalty = min(0.40, 0.06 * unreadable)
    return round(max(0.0, base - penalty), 3)


async def ocr_pages(pages: list[Any]) -> list[dict[str, Any]]:
    """OCR each preprocessed page LOCALLY. Returns one dict per page.

    Args:
        pages: list of objects exposing ``.png_bytes`` and ``.index`` (the
               ``PageImage`` from preprocess.py) OR raw ``bytes``.

    Returns (per page):
        {"page": int, "text": str, "confidence": float, "model": str,
         "via": "textlayer"|"response"|"thinking"|"fallback"|"empty"}

    Anti-hallucination: a page the model cannot read yields text="" and
    confidence 0.0 -- never invented content. The persistent client is reused
    across pages (Golden Rule #10).
    """
    primary = _resolve_ocr_model()
    results: list[dict[str, Any]] = []

    for i, page in enumerate(pages):
        png = getattr(page, "png_bytes", page)
        idx = getattr(page, "index", i)

        # Text-layer fast-path (preprocess INTAKE_TEXTLAYER_FASTPATH): a
        # born-digital PDF page already carries its extracted text layer. Use it
        # verbatim and SKIP the vision model entirely -- that call is the
        # dominant cost (~120s/page on the local VLM). Vision runs ONLY on pages
        # with no usable text layer (scans/photos). 100% local either way.
        pre_text = getattr(page, "text", None)
        if pre_text and pre_text.strip():
            results.append(
                {
                    "page": idx,
                    "text": pre_text,
                    "confidence": _heuristic_confidence(pre_text),
                    "model": "textlayer",
                    "via": "textlayer",
                }
            )
            logger.info(
                "intake OCR page=%d via=textlayer chars=%d (vision skipped)",
                idx,
                len(pre_text),
            )
            continue

        b64 = base64.b64encode(png).decode("ascii")

        text = ""
        via = "empty"
        model_used = primary

        # (a) resolved primary: prefer response, salvage thinking (no-op for
        # non-reasoning VLMs like qwen2.5vl).
        try:
            resp, thinking = await asyncio.wait_for(
                _ollama_vision(primary, b64), timeout=OCR_PAGE_TIMEOUT_SECONDS
            )
            if resp:
                text, via = resp, "response"
            else:
                salvaged = _salvage_thinking(thinking or "")
                if salvaged:
                    text, via = salvaged, "thinking"
        except (httpx.HTTPError, asyncio.TimeoutError, Exception) as exc:
            # %r, not %s: a bare ReadTimeout/HTTPError can str() to "" and the
            # log line carried zero diagnostic signal (W70 blind-log class).
            logger.warning("OCR primary %s failed on page %d: %r", primary, idx, exc)

        # (b) cascade to _OCR_FALLBACK when primary yielded nothing usable.
        # With today's topology primary == fallback, so this is a same-model
        # retry — kept deliberately (live logs show a second attempt rescues
        # pages that returned empty once). ``via`` stays "fallback" for
        # downstream compatibility.
        if not text:
            if _OCR_FALLBACK == primary:
                logger.info("OCR same-model retry (%s) on page %d", _OCR_FALLBACK, idx)
            try:
                resp, _ = await asyncio.wait_for(
                    _ollama_vision(_OCR_FALLBACK, b64),
                    timeout=OCR_PAGE_TIMEOUT_SECONDS,
                )
                if resp:
                    text, via, model_used = resp, "fallback", _OCR_FALLBACK
            except (httpx.HTTPError, asyncio.TimeoutError, Exception) as exc:
                logger.warning("OCR fallback failed on page %d: %r", idx, exc)

        results.append(
            {
                "page": idx,
                "text": text,
                "confidence": _heuristic_confidence(text),
                "model": model_used,
                "via": via,
            }
        )
        logger.info(
            "intake OCR page=%d via=%s model=%s chars=%d", idx, via, model_used, len(text)
        )

    return results


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

# Doc types intake recognizes. "unknown" is the anti-hallucination floor.
DOC_TYPES: tuple[str, ...] = (
    "passport",
    "akta_pendirian",
    "profil_perseroan",
    "nib",
    "npwp",
    "kitas",
    "sk_kemenkumham",
    "oss",
    "skt",
    "ktp",
    "unknown",
)

# Keyword evidence per type. Matching is case-insensitive substring on OCR text.
# These are document-title / boilerplate phrases that appear on the genuine
# Indonesian forms, chosen to be specific (low false-positive). Weight reflects
# how diagnostic the phrase is.
_TYPE_EVIDENCE: dict[str, list[tuple[str, float]]] = {
    "passport": [
        ("passport", 0.5),
        ("paspor", 0.5),
        ("republic of indonesia", 0.3),
        ("republik indonesia", 0.2),
        ("p<idn", 0.6),  # MRZ line for Indonesian passport
        ("p<", 0.35),  # generic MRZ TD3 lead-in (any nationality's passport)
        ("date of expiry", 0.2),
        ("nomor paspor", 0.5),
    ],
    "ktp": [
        ("nomor induk kependudukan", 0.6),
        ("kartu tanda penduduk", 0.6),
        ("nik", 0.2),
        ("provinsi", 0.15),
        ("golongan darah", 0.2),
        ("kewarganegaraan", 0.15),
        ("tempat/tgl lahir", 0.3),  # KTP-specific field label
    ],
    "npwp": [
        ("nomor pokok wajib pajak", 0.6),
        ("npwp", 0.5),
        ("direktorat jenderal pajak", 0.4),
        ("kementerian keuangan", 0.2),
    ],
    "nib": [
        ("nomor induk berusaha", 0.6),
        ("nib", 0.35),
        ("lembaga oss", 0.4),
        ("perizinan berusaha", 0.3),
    ],
    "oss": [
        ("online single submission", 0.6),
        ("lembaga pengelola", 0.2),
        ("perizinan berusaha berbasis risiko", 0.4),
    ],
    "akta_pendirian": [
        ("akta pendirian", 0.6),
        ("notaris", 0.35),
        ("perseroan terbatas", 0.3),
        ("anggaran dasar", 0.4),
        ("akta nomor", 0.3),
    ],
    "profil_perseroan": [
        ("profil perseroan", 0.6),
        ("company profile", 0.45),
        ("profil pt", 0.5),
        ("profile perseroan", 0.5),
        ("bidang usaha", 0.2),
        ("struktur permodalan", 0.3),
        ("susunan pengurus", 0.25),
    ],
    "sk_kemenkumham": [
        ("kementerian hukum dan hak asasi manusia", 0.5),
        ("keputusan menteri", 0.4),
        ("pengesahan badan hukum", 0.55),
        ("sk pengesahan", 0.5),
        ("ahu-", 0.4),  # AHU reference number prefix
    ],
    "kitas": [
        ("kitas", 0.55),
        ("izin tinggal terbatas", 0.6),
        ("kartu izin tinggal", 0.5),
        ("limited stay permit", 0.55),  # English title printed on the card
        ("itas", 0.2),
        ("imigrasi", 0.2),
    ],
    "skt": [
        ("surat keterangan terdaftar", 0.6),
        ("skt", 0.25),
    ],
}


def _score_types(text: str) -> dict[str, float]:
    """Sum keyword-evidence weights per type over the OCR text (lowercased)."""
    low = text.lower()
    scores: dict[str, float] = {}
    for dtype, evidence in _TYPE_EVIDENCE.items():
        s = 0.0
        for phrase, weight in evidence:
            if phrase in low:
                s += weight
        if s > 0:
            scores[dtype] = round(min(s, 1.0), 3)
    return scores


# ---------------------------------------------------------------------------
# Vision classification fallback (keyword score below the unknown floor)
# ---------------------------------------------------------------------------

# Confidence CAP for a vision-only classification: always in the review band,
# NEVER enough to auto-commit (the gate needs >= human review on vision alone).
VISION_CLASSIFY_CONF = 0.55

# One constrained call. qwen2.5vl:7b is used directly (NOT the qwen3-vl
# primary): the 2026-06-04 empirical finding above shows qwen3-vl buries its
# answer in `thinking` and returns `response` empty — useless for a
# single-token contract. qwen2.5vl honours think:false and answers cleanly.
# Both are local Ollama — 0 bytes to cloud (Law 2).
_VISION_CLASSIFY_MODEL = _OCR_FALLBACK
_VISION_CLASSIFY_NUM_PREDICT = 16

_VISION_CLASSIFY_PROMPT = (
    "You are classifying an Indonesian administrative document image. "
    "Answer with EXACTLY ONE word from this list: "
    + ", ".join(DOC_TYPES)
    + ". If you are not sure, answer: unknown. "
    "One word only — no punctuation, no explanation."
)

# Exact-member acceptance: strip surrounding punctuation/whitespace, lowercase.
_VISION_ANSWER_RE = re.compile(r"[a-z_]+")


def _parse_vision_answer(raw: str | None) -> str | None:
    """Accept ONLY an exact DOC_TYPES member (case-insensitive); else None.

    The contract is a single token; we tolerate surrounding whitespace or a
    trailing period, but a sentence ("this is a passport") is rejected — the
    whole cleaned answer must be exactly one type token.
    """
    if not raw:
        return None
    cleaned = raw.strip().strip(".,:;!\"'`").lower()
    if not _VISION_ANSWER_RE.fullmatch(cleaned):
        return None
    return cleaned if cleaned in DOC_TYPES else None


async def _vision_classify_first_page(png_bytes: bytes) -> str | None:
    """ONE local vision call to type a document the keywords could not.

    Returns a DOC_TYPES member or None. NEVER raises: any error/timeout/
    non-conforming answer degrades to None (caller keeps "unknown").
    """
    try:
        b64 = base64.b64encode(png_bytes).decode("ascii")
        resp, thinking = await asyncio.wait_for(
            _ollama_vision(
                _VISION_CLASSIFY_MODEL,
                b64,
                prompt=_VISION_CLASSIFY_PROMPT,
                num_predict=_VISION_CLASSIFY_NUM_PREDICT,
            ),
            timeout=OCR_PAGE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("vision classify fallback failed: %s", exc)
        return None
    # Prefer the clean response; tolerate a thinking-only model defensively.
    answer = _parse_vision_answer(resp) or _parse_vision_answer(thinking)
    if answer:
        logger.info("vision classify fallback answered type=%s", answer)
    return answer


async def classify_document(
    ocr_text: str | None,
    pages: list[dict[str, Any]] | None = None,
    *,
    first_page_png: bytes | None = None,
) -> dict[str, Any]:
    """Classify a document from OCR text. Local-only, anti-hallucination.

    Args:
        ocr_text: concatenated OCR text (all pages). If None, derived from pages.
        pages: per-page OCR dicts from ``ocr_pages`` (used to attribute the
               winning evidence to a specific source page).
        first_page_png: optional raw PNG bytes of the FIRST page. When the
               keyword score lands below the unknown floor, ONE constrained
               local vision call (:func:`_vision_classify_first_page`) gets a
               chance to type the document — confidence capped at
               ``VISION_CLASSIFY_CONF`` (review band, never auto-commit).

    Returns:
        {"type": str, "confidence": float, "source_page": int|None,
         "scores": dict}  -- type is "unknown" with confidence 0.0 when no
        evidence clears the floor. A vision-typed result additionally carries
        {"via": "vision_fallback"}. Never fabricates a type.
    """
    pages = pages or []
    if ocr_text is None:
        ocr_text = "\n".join(p.get("text", "") for p in pages)

    scores = _score_types(ocr_text) if ocr_text and ocr_text.strip() else {}
    best_type = max(scores, key=scores.get) if scores else None
    best_score = scores[best_type] if best_type is not None else 0.0

    # Anti-hallucination floor: weak keyword evidence -> NOT a guess. One local
    # vision attempt (catalog v2) may still type it — capped in the review band.
    if best_type is None or best_score < 0.30:
        if first_page_png is not None:
            vtype = await _vision_classify_first_page(first_page_png)
            if vtype and vtype != "unknown":
                return {
                    "type": vtype,
                    "confidence": VISION_CLASSIFY_CONF,
                    "source_page": pages[0].get("page") if pages else None,
                    "scores": scores,
                    "via": "vision_fallback",
                }
        return {"type": "unknown", "confidence": 0.0, "source_page": None, "scores": scores}

    # Attribute evidence to the page that contains the strongest phrase for the
    # winning type (where the type signal physically appears).
    source_page = _attribute_source_page(best_type, pages)

    return {
        "type": best_type,
        "confidence": best_score,
        "source_page": source_page,
        "scores": scores,
    }


def _attribute_source_page(
    dtype: str, pages: list[dict[str, Any]]
) -> int | None:
    """Return the page index whose text best matches the winning type's evidence."""
    evidence = _TYPE_EVIDENCE.get(dtype, [])
    best_page: int | None = None
    best_hit = 0.0
    for p in pages:
        low = (p.get("text") or "").lower()
        hit = sum(w for phrase, w in evidence if phrase in low)
        if hit > best_hit:
            best_hit = hit
            best_page = p.get("page")
    return best_page


# ---------------------------------------------------------------------------
# Worker stage handlers (FASE 2 contract)
# ---------------------------------------------------------------------------
#
# The FASE-2 worker (services/intake/worker.py) drives a stage machine:
#   pending --classify--> processing --ocr--> ocr --extract--> ...
# It injects a ``stage_handler: async def(job: dict, stage: str) -> dict`` whose
# return dict is merged into ``stage_output[stage]``. The claimed ``job`` dict
# carries: id, attempts, max_attempts, source, source_ref, _inbound_status --
# but NOT blob_path (the worker's RETURNING omits it). So our handler is built by
# a factory that fetches blob_path/mime from intake_queue by job id, using the
# worker's persistent pool. We do NOT modify worker.py; the integrator wires this
# factory as the worker's stage_handler.
#
# Stage semantics here (FASE 3a owns 'classify' + 'ocr'):
#   - stage 'classify' (inbound pending): preprocess + OCR + classify in one
#     pass, persisting OCR text + doc_type into stage_output. (Doing OCR here
#     too is intentional: classification needs the text, and re-OCR at the 'ocr'
#     stage would double the cost. The 'ocr' stage handler is therefore a cheap
#     passthrough that surfaces the already-computed OCR payload.)
#   - stage 'ocr' (inbound processing): returns the OCR summary already in
#     stage_output['classify'] (idempotent, no model call).

StageHandler = Callable[[dict, str], Awaitable[dict]]


async def _fetch_blob_meta(
    pool: asyncpg.Pool, queue_id: int
) -> tuple[str | None, str | None]:
    """Look up (blob_path, mime_type) for an intake_queue row.

    mime_type lives on document_instances (joined via instance_id), not on
    intake_queue, so we LEFT JOIN it.
    """
    row = await pool.fetchrow(
        """
        SELECT q.blob_path, di.mime_type
        FROM intake_queue q
        LEFT JOIN document_instances di ON di.id = q.instance_id
        WHERE q.id = $1
        """,
        queue_id,
    )
    if row is None:
        return None, None
    return row["blob_path"], row["mime_type"]


def build_stage_handler(pool: asyncpg.Pool) -> StageHandler:
    """Factory: return a stage_handler bound to the worker's asyncpg pool.

    Wire it into IntakeWorker(stage_handler=build_stage_handler(pool)). It
    handles the 'classify' and 'ocr' stages; any other stage name is returned to
    the worker as a no-op marker so the stage machine can advance (extract /
    validate / route are owned by agent-beta and the integrator).
    """

    async def handler(job: dict, stage: str) -> dict:
        if stage == "classify":
            return await _run_classify_stage(pool, job)
        if stage == "ocr":
            # OCR already done in 'classify'; surface a stable marker. If the
            # classify payload is somehow absent (out-of-order), recompute.
            return {"deferred_to": "classify"}
        # Not our stage -- let the worker advance (beta/integrator owns it).
        return {"handled_by": "fase3a", "noop_stage": stage}

    return handler


async def _run_classify_stage(pool: asyncpg.Pool, job: dict) -> dict:
    """preprocess -> OCR (all pages, local) -> classify. Returns stage payload."""
    from backend.services.intake import preprocess as _pre

    queue_id = job["id"]
    blob_path, declared_mime = await _fetch_blob_meta(pool, queue_id)
    if not blob_path:
        # No blob to read -> cannot classify. Surface unknown (not a raise: the
        # worker would otherwise retry a permanently-missing blob 5x to DLQ).
        return {
            "doc_type": "unknown",
            "type_confidence": 0.0,
            "ocr_text_per_page": [],
            "n_pages": 0,
            "source_page": None,
            "model": _resolve_ocr_model(),
            "error": "blob_path_missing",
        }

    pre = await _pre.preprocess_blob(blob_path, declared_mime=declared_mime)
    ocr = await ocr_pages(pre.pages)
    full_text = "\n".join(p["text"] for p in ocr)
    first_png = getattr(pre.pages[0], "png_bytes", None) if pre.pages else None
    cls = await classify_document(full_text, ocr, first_page_png=first_png)

    return {
        "doc_type": cls["type"],
        "type_confidence": cls["confidence"],
        "ocr_text_per_page": ocr,
        "n_pages": pre.n_pages,
        "source_page": cls["source_page"],
        "model": _resolve_ocr_model(),
        "mime": pre.mime,
        "preprocess_notes": pre.notes,
        "type_scores": cls["scores"],
        "classified_via": cls.get("via", "keywords"),
    }
