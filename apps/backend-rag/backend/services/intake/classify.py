"""Document-intake OCR + classification stage (FASE 3a).

Two responsibilities, local by default (Symbiosis Law 2 / UU-PDP):

  1. ``ocr_pages``        -- run a vision model over preprocessed pages,
                            returning per-page transcribed text + confidence.
  2. ``classify_document`` -- decide the document TYPE from the OCR text, with a
                            hard anti-hallucination floor: undeterminable ->
                            {"type": "unknown", "confidence": 0.0}, never a guess.
                            A gated local text-LLM fallback may classify OCR text
                            that keyword rules cannot, still review-band only.

OCR provider contract
---------------------
Default runtime is strict local: ``INTAKE_OCR_PROVIDER`` unset -> Ollama
``qwen2.5vl:7b`` on localhost. Gemini OCR is opt-in only:
``INTAKE_OCR_PROVIDER=gemini`` AND ``OCR_ALLOW_CLOUD_VISION=true``. If either
condition is absent, the document image is not sent to cloud OCR. If Gemini is
enabled but returns no usable text or errors, the path falls back to the local
Ollama cascade below.

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
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import httpx

from backend.llm.config import ModelName
from backend.services.intake.inference_runtime import (
    ollama_inference_slot,
    ollama_keep_alive,
)
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
_GEMINI_OCR_MODEL = os.getenv("INTAKE_GEMINI_OCR_MODEL", ModelName.FALLBACK)
_GEMINI_OCR_AUTH_FAILED = False
_GEMINI_OCR_AUTH_ERROR_MARKERS = (
    "401",
    "403",
    "api key",
    "api_key",
    "forbidden",
    "permission_denied",
    "reported as leaked",
    "unauthorized",
)

# Per-page hard cap. CLAUDE.md OCR rule: 120s for >3 pages -- but we OCR one page
# per request, so this is the single-page ceiling (reasoning VLM is slow).
OCR_PAGE_TIMEOUT_SECONDS = 120.0

# Token budget for transcription. Generous because qwen3-vl spends most of it on
# (discarded) thinking before -- sometimes -- emitting text.
OCR_NUM_PREDICT = 2048
OCR_MAX_IMAGE_DIM = 0  # disabled by default; set INTAKE_OCR_MAX_IMAGE_DIM to bound latency

_OCR_PROMPT = (
    "Transcribe ALL legible text from this document image verbatim. "
    "Preserve numbers, dates, names exactly as printed. "
    "Output the transcription only -- no commentary, no labels. "
    "If a region is unreadable, write [unreadable]."
)


def _resolve_ocr_model() -> str:
    """Prefer the FASE-0 registry ``ocr_vision`` role; else the hardcoded default."""
    return resolve_model_role("ocr_vision", _OCR_PRIMARY_DEFAULT)


def _positive_env_int(name: str, default: int) -> int:
    """Read a positive integer env override; return default on unset/invalid."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("invalid %s=%r; using %d", name, raw, default)
        return default
    if value <= 0:
        logger.warning("invalid %s=%r; using %d", name, raw, default)
        return default
    return value


def _ocr_num_predict() -> int:
    """Runtime OCR token budget, configurable for benchmark/worker tuning."""
    return _positive_env_int("INTAKE_OCR_NUM_PREDICT", OCR_NUM_PREDICT)


def _ocr_max_image_dim() -> int:
    """Runtime max page dimension; 0 means no downscale."""
    return _positive_env_int("INTAKE_OCR_MAX_IMAGE_DIM", OCR_MAX_IMAGE_DIM)


def _ocr_provider() -> str:
    """Return the configured OCR primary provider; fail closed to local Ollama."""
    provider = os.getenv("INTAKE_OCR_PROVIDER", "ollama").strip().lower()
    return "gemini" if provider in {"gemini", "gemini_first", "gemini-first"} else "ollama"


def _is_gemini_auth_error(exc: Exception) -> bool:
    """Return True for Gemini failures that should stop repeat cloud attempts."""
    text = f"{type(exc).__name__}: {exc!r}".casefold()
    return any(marker in text for marker in _GEMINI_OCR_AUTH_ERROR_MARKERS)


def _cloud_vision_allowed() -> bool:
    """Lazy wrapper for tests and fail-closed cloud OCR gating."""
    from backend.services.multimodal.cloud_vision_gate import cloud_vision_allowed

    return cloud_vision_allowed()


def _note_cloud_ocr_blocked(context: str) -> None:
    """Lazy wrapper so intake uses the shared cloud OCR audit signal."""
    from backend.services.multimodal.cloud_vision_gate import note_cloud_ocr_blocked

    note_cloud_ocr_blocked(context)


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
_FENCED_BLOCK = re.compile(r"^```(?:[a-zA-Z0-9_-]+)?\s*\n(?P<body>.*?)\n?```$", re.DOTALL)


def _ocr_line_from_item(item: Any) -> str:
    """Extract visible OCR text from a JSON list item."""
    if isinstance(item, dict):
        for key in ("text", "line", "value"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    return str(item).strip()


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


def _clean_ocr_response(text: str) -> str:
    """Normalize common VLM wrapper formats while preserving visible text."""
    raw = text.strip()
    if not raw:
        return ""
    fenced = _FENCED_BLOCK.fullmatch(raw)
    if fenced:
        raw = fenced.group("body").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if isinstance(parsed, list):
        lines = [line for item in parsed if (line := _ocr_line_from_item(item))]
        return "\n".join(lines) if lines else raw

    if isinstance(parsed, dict):
        for key in ("text", "transcription", "ocr_text"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("lines", "ocr_lines", "pages"):
            value = parsed.get(key)
            if isinstance(value, list):
                lines = [line for item in value if (line := _ocr_line_from_item(item))]
                return "\n".join(lines) if lines else raw

    return raw


async def _ollama_vision(
    model: str,
    png_b64: str,
    prompt: str = _OCR_PROMPT,
    num_predict: int | None = None,
) -> tuple[str, str | None]:
    """Single /api/generate vision call. Returns (response_text, thinking_text)."""
    resolved_num_predict = num_predict if num_predict is not None else _ocr_num_predict()
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "images": [png_b64],
        "stream": False,
        "keep_alive": ollama_keep_alive(),
        "options": {"temperature": 0.0, "num_predict": resolved_num_predict},
        # CLAUDE.md S9: qwen 3.x family needs think:false. qwen3-vl ignores it
        # for vision (empirically still reasons) but qwen2.5vl honours it.
        "think": False,
    }
    client = _get_client()
    async with ollama_inference_slot(operation="ocr_vision", model=model):
        # Admission wait is intentionally outside the request timeout.  A busy
        # local GPU should queue work, not make a request expire before it has
        # started running.
        r = await asyncio.wait_for(
            client.post(f"{OLLAMA_URL}/api/generate", json=payload),
            timeout=OCR_PAGE_TIMEOUT_SECONDS,
        )
    r.raise_for_status()
    data = r.json()
    return (
        _clean_ocr_response(data.get("response") or ""),
        _clean_ocr_response(data.get("thinking") or ""),
    )


async def _gemini_vision(
    png_b64: str,
    prompt: str = _OCR_PROMPT,
    num_predict: int | None = None,
) -> str:
    """Single gated Gemini Vision OCR call through the shared GenAI client."""
    from backend.llm.genai_client import get_genai_client

    client = get_genai_client()
    if not getattr(client, "is_available", False):
        return ""

    result = await client.generate_content(
        contents=[
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": png_b64}},
        ],
        model=_GEMINI_OCR_MODEL,
        max_output_tokens=num_predict if num_predict is not None else _ocr_num_predict(),
        temperature=0.0,
        timeout_ms=int(OCR_PAGE_TIMEOUT_SECONDS * 1000),
        endpoint="intake_ocr",
    )
    return _clean_ocr_response((result or {}).get("text") or "")


def _heuristic_confidence(text: str) -> float:
    """Confidence for OCR text: length + low [unreadable] density. 0.0 if empty."""
    if not text:
        return 0.0
    unreadable = text.count("[unreadable]")
    base = 0.70 if len(text) >= 40 else 0.45
    penalty = min(0.40, 0.06 * unreadable)
    return round(max(0.0, base - penalty), 3)


# qwen2.5vl in Ollama (>=0.20.x) crashes its runner on two classes of input,
# both surfacing as HTTP 500 -> page chars=0 -> job stalls at ocr_done forever
# (SCAR 2026-06-20: this silently froze the intake tail for 33h):
#   1. "height:N or width:N must be larger than factor:28" — SmartResize panic
#      on any dimension below the 28px patch factor.
#   2. "image: unknown format" — non-PNG/odd-encoded bytes (HEIC/WebP/TIFF or a
#      mis-rendered page) Ollama's Go image decoder cannot parse.
# Fix: re-encode EVERY page through PIL to a canonical RGB PNG and pad it up to
# MIN_OCR_DIM. This normalizes format AND size in one pass. PIL handles far more
# formats than Ollama's decoder, so "unknown format" pages become valid PNGs.
MIN_OCR_DIM = 32  # one patch above the 28px factor, safe margin


def _ensure_min_size(png: bytes) -> bytes:
    """Re-encode any image to a canonical RGB PNG and pad to >= MIN_OCR_DIM.
    Normalizes both format ('unknown format') and size (SmartResize panic).
    Degrades to original bytes if PIL cannot parse it at all (never crash)."""
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(png)) as im:
            im = im.convert("RGB")
            w, h = im.size
            new_w, new_h = max(w, MIN_OCR_DIM), max(h, MIN_OCR_DIM)
            if (new_w, new_h) != (w, h):
                canvas = Image.new("RGB", (new_w, new_h), (255, 255, 255))
                canvas.paste(im, (0, 0))
                im = canvas
            max_image_dim = _ocr_max_image_dim()
            if max_image_dim >= MIN_OCR_DIM and max(new_w, new_h) > max_image_dim:
                scale = max_image_dim / max(new_w, new_h)
                target_w = max(MIN_OCR_DIM, round(new_w * scale))
                target_h = max(MIN_OCR_DIM, round(new_h * scale))
                im = im.resize((target_w, target_h), Image.LANCZOS)
                new_w, new_h = target_w, target_h
            out = io.BytesIO()
            im.save(out, format="PNG")
            data = out.getvalue()
            if (new_w, new_h) != (w, h) or len(data) != len(png):
                logger.info(
                    "intake OCR normalized page %dx%d -> %dx%d PNG (size/format safe for qwen25vl)",
                    w,
                    h,
                    new_w,
                    new_h,
                )
            return data
    except Exception as exc:  # never let normalization break OCR
        logger.warning("intake OCR _ensure_min_size skipped (unparseable): %s", exc)
        return png


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
    global _GEMINI_OCR_AUTH_FAILED

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

        b64 = base64.b64encode(_ensure_min_size(png)).decode("ascii")

        text = ""
        via = "empty"
        model_used = primary

        # Optional cloud OCR primary. This is disabled by default and requires
        # both INTAKE_OCR_PROVIDER=gemini and the shared cloud vision gate.
        if _ocr_provider() == "gemini" and not _GEMINI_OCR_AUTH_FAILED:
            if _cloud_vision_allowed():
                try:
                    resp = await asyncio.wait_for(
                        _gemini_vision(b64),
                        timeout=OCR_PAGE_TIMEOUT_SECONDS,
                    )
                    resp = _clean_ocr_response(resp)
                    if resp:
                        text, via, model_used = resp, "gemini", _GEMINI_OCR_MODEL
                except Exception as exc:
                    logger.warning("OCR Gemini primary failed on page %d: %r", idx, exc)
                    if _is_gemini_auth_error(exc):
                        _GEMINI_OCR_AUTH_FAILED = True
                        logger.error(
                            "OCR Gemini primary disabled for this worker after auth failure"
                        )
            else:
                _note_cloud_ocr_blocked("intake.classify.ocr_pages")

        # (a) resolved primary: prefer response, salvage thinking (no-op for
        # non-reasoning VLMs like qwen2.5vl).
        if not text:
            try:
                resp, thinking = await _ollama_vision(primary, b64)
                resp = _clean_ocr_response(resp)
                thinking = _clean_ocr_response(thinking or "")
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
                resp, _ = await _ollama_vision(_OCR_FALLBACK, b64)
                resp = _clean_ocr_response(resp)
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
        logger.info("intake OCR page=%d via=%s model=%s chars=%d", idx, via, model_used, len(text))

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
    "itas",
    "itap",
    "itk",
    "sk_kemenkumham",
    "oss",
    "visa",
    "skt",
    "ktp",
    "family_card",
    "birth_certificate",
    "marriage_certificate",
    "payment_receipt",
    "travel_ticket",
    "bank_statement",
    "medical_insurance",
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
    "family_card": [
        ("kartu keluarga", 0.6),
        ("family card", 0.6),
        ("nomor kartu keluarga", 0.55),
        ("no. kk", 0.45),
        ("no kk", 0.45),
        ("kepala keluarga", 0.35),
        ("daftar anggota keluarga", 0.35),
        ("susunan keluarga", 0.3),
    ],
    "birth_certificate": [
        ("kutipan akta kelahiran", 0.7),
        ("akta kelahiran", 0.6),
        ("birth certificate", 0.6),
        ("certificate of birth", 0.6),
        ("dinas kependudukan dan pencatatan sipil", 0.25),
        ("kelahiran", 0.25),
        ("anak ke", 0.25),
    ],
    "marriage_certificate": [
        ("kutipan akta perkawinan", 0.7),
        ("akta perkawinan", 0.6),
        ("akta nikah", 0.6),
        ("buku nikah", 0.55),
        ("marriage certificate", 0.6),
        ("certificate of marriage", 0.6),
        ("kantor urusan agama", 0.35),
        ("pernikahan", 0.35),
        ("perkawinan", 0.35),
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
    "visa": [
        ("e-visa", 0.6),
        ("evisa", 0.6),
        ("electronic visa", 0.6),
        ("visa on arrival", 0.5),
        ("voa", 0.4),
        ("visa kunjungan", 0.45),
        ("visit visa", 0.45),
        ("visa tinggal", 0.45),
        ("limited stay visa", 0.45),
        ("visa index", 0.45),
        ("index visa", 0.45),
        ("b211", 0.4),
        ("b-211", 0.4),
        ("visa", 0.2),
    ],
    "payment_receipt": [
        ("bukti pembayaran", 0.6),
        ("payment receipt", 0.6),
        ("bukti transfer", 0.55),
        ("bukti transaksi", 0.55),
        ("transfer berhasil", 0.5),
        ("kwitansi", 0.5),
        ("tanda terima", 0.5),
        ("nomor referensi", 0.35),
        ("transaction id", 0.35),
        ("transaction date", 0.3),
        ("jumlah pembayaran", 0.35),
        ("total bayar", 0.35),
        ("invoice", 0.3),
        ("receipt", 0.3),
        ("pembayaran", 0.25),
    ],
    "travel_ticket": [
        ("boarding pass", 0.6),
        ("flight itinerary", 0.55),
        ("e-ticket", 0.55),
        ("tiket elektronik", 0.55),
        ("eticket", 0.5),
        ("ticket number", 0.45),
        ("booking reference", 0.4),
        ("booking code", 0.35),
        ("kode booking", 0.35),
        ("nomor penerbangan", 0.25),
        ("passenger", 0.25),
        ("departure", 0.2),
        ("arrival", 0.2),
        ("gate", 0.15),
        ("seat", 0.15),
    ],
    "bank_statement": [
        ("bank statement", 0.6),
        ("rekening koran", 0.6),
        ("statement of account", 0.6),
        ("account statement", 0.5),
        ("mutasi rekening", 0.45),
        ("saldo awal", 0.25),
        ("saldo akhir", 0.25),
        ("debit", 0.15),
        ("credit", 0.15),
    ],
    "medical_insurance": [
        ("travel insurance", 0.6),
        ("medical insurance", 0.6),
        ("health insurance", 0.5),
        ("insurance policy", 0.5),
        ("polis asuransi", 0.55),
        ("asuransi kesehatan", 0.5),
        ("policy number", 0.35),
        ("nomor polis", 0.35),
        ("insured person", 0.3),
        ("sum insured", 0.3),
        ("asuransi", 0.25),
        ("insurance", 0.25),
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


def _evidence_phrase_matches(text: str, phrase: str) -> bool:
    """Return true when an evidence phrase is present in normalized OCR text."""
    if phrase == "nik":
        return re.search(r"(?<![a-z0-9])nik(?![a-z0-9])", text) is not None
    return phrase in text


def _score_types(text: str) -> dict[str, float]:
    """Sum keyword-evidence weights per type over the OCR text (lowercased)."""
    low = text.lower()
    scores: dict[str, float] = {}
    for dtype, evidence in _TYPE_EVIDENCE.items():
        s = 0.0
        for phrase, weight in evidence:
            if _evidence_phrase_matches(low, phrase):
                s += weight
        if s > 0:
            scores[dtype] = round(min(s, 1.0), 3)
    return scores


# ---------------------------------------------------------------------------
# Stay-permit disambiguation (ITK / ITAS / ITAP) -- deterministic OVERRIDE
# ---------------------------------------------------------------------------
#
# WHY (live defect, proposals 12937 / 15368 / 12694, 2026-06-17): an Indonesian
# electronic stay-permit card (izin tinggal) prints a "Passport Number" field on
# its face. The keyword scorer therefore credits ``passport`` ("passport" 0.5 +
# "republik indonesia" 0.2 = 0.7-0.8) ABOVE ``kitas`` (0.75) and ``max(scores)``
# files the stay permit under the passport category -- a real misfile.
#
# A genuine passport NEVER carries an "izin tinggal" / "stay permit" title, so
# gating the override on those markers is innocent toward real passports (see
# the innocence test in test_intake_classify.py). When a marker is present the
# document IS a stay permit; we then pick the SPECIFIC subtype and emit
# itk/itas/itap -- never passport.

# Presence markers: ANY of these in the OCR text means "this is a stay permit".
# Lower-cased substring match (the scorer convention). Kept broad on purpose --
# a real passport lacks every one of them, so breadth costs no false-positive.
_STAY_PERMIT_MARKERS: tuple[str, ...] = (
    "izin tinggal",
    "stay permit",
    "stay/multiple entries permit",
    "stay permit index",
    "permit number",
    "electronic limited stay",
    "izin tinggal terbatas",
    "izin tinggal tetap",
    "izin tinggal kunjungan",
)

# Subtype markers, most-specific first. The first family whose ANY marker is
# present wins. itk = visit, itas = limited, itap = permanent.
_STAY_PERMIT_SUBTYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("itap", ("izin tinggal tetap", "permanent stay", "itap", "kitap")),
    ("itk", ("izin tinggal kunjungan", "visit stay", "itk")),
    (
        "itas",
        (
            "izin tinggal terbatas",
            "limited stay",
            "electronic limited stay",
            "itas",
            "kitas",
        ),
    ),
)


def _stay_permit_subtype(text: str) -> str | None:
    """Return itk/itas/itap if OCR text is an izin-tinggal card, else None.

    Deterministic, text-only, no model. A document is a stay permit iff it
    carries ANY :data:`_STAY_PERMIT_MARKERS` token. The subtype is then chosen
    by :data:`_STAY_PERMIT_SUBTYPES` (most-specific family first); if a permit
    is detected but no subtype family matches, we default to ``itas`` (the most
    common card) -- but we NEVER fall back to passport.
    """
    low = text.lower()
    if not any(m in low for m in _STAY_PERMIT_MARKERS):
        return None
    for subtype, markers in _STAY_PERMIT_SUBTYPES:
        if any(m in low for m in markers):
            return subtype
    return "itas"


# ---------------------------------------------------------------------------
# Vision classification fallback (keyword score below the unknown floor)
# ---------------------------------------------------------------------------

# Confidence CAP for a vision-only classification: always in the review band,
# NEVER enough to auto-commit (the gate needs >= human review on vision alone).
VISION_CLASSIFY_CONF = 0.55
VISION_CLASSIFY_MAX_PAGES = 3

# Confidence CAP for local text-LLM classification. This is deliberately below
# HIGH_CONFIDENCE_THRESHOLD (0.70 in the audit/dashboard) so LLM-only cataloging
# creates/reprocesses review proposals, never silent attachment.
TEXT_LLM_CLASSIFY_CONF = 0.60
TEXT_LLM_CLASSIFY_MIN_CHARS = int(os.getenv("INTAKE_TEXT_LLM_MIN_CHARS", "100"))
TEXT_LLM_CLASSIFY_TIMEOUT_SECONDS = float(os.getenv("INTAKE_TEXT_LLM_TIMEOUT_SECONDS", "45"))
_TEXT_LLM_CLASSIFY_MODEL_DEFAULT = "qwen3.5:9b"

# One constrained call. qwen2.5vl:7b is used directly (NOT the qwen3-vl
# primary): the 2026-06-04 empirical finding above shows qwen3-vl buries its
# answer in `thinking` and returns `response` empty — useless for a
# single-token contract. qwen2.5vl honours think:false and answers cleanly.
# Both are local Ollama — 0 bytes to cloud (Law 2).
_VISION_CLASSIFY_MODEL = _OCR_FALLBACK
_VISION_CLASSIFY_NUM_PREDICT = 16

_DOC_TYPE_ANSWER_RE = re.compile(r"[a-z_]+")


def _resolve_text_llm_model() -> str:
    """Resolve the local text classifier model. No cloud path."""
    return os.getenv("INTAKE_TEXT_LLM_MODEL", _TEXT_LLM_CLASSIFY_MODEL_DEFAULT)


def _text_llm_classify_enabled() -> bool:
    """Feature flag for OCR-text LLM fallback; disabled unless explicitly enabled."""
    return os.getenv("INTAKE_TEXT_LLM_CLASSIFY_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


_VISION_CLASSIFY_PROMPT = (
    "You are classifying an Indonesian administrative document image. "
    "Answer with EXACTLY ONE word from this list: "
    + ", ".join(DOC_TYPES)
    + ". If you are not sure, answer: unknown. "
    "One word only — no punctuation, no explanation."
)


def _parse_doc_type_answer(raw: str | None) -> str | None:
    """Accept ONLY an exact DOC_TYPES member (case-insensitive); else None.

    The contract is a single token; we tolerate surrounding whitespace or a
    trailing period, but a sentence ("this is a passport") is rejected — the
    whole cleaned answer must be exactly one type token.
    """
    if not raw:
        return None
    cleaned = raw.strip().strip(".,:;!\"'`").lower()
    if not _DOC_TYPE_ANSWER_RE.fullmatch(cleaned):
        return None
    return cleaned if cleaned in DOC_TYPES else None


def _parse_vision_answer(raw: str | None) -> str | None:
    """Backward-compatible wrapper for vision tests."""
    return _parse_doc_type_answer(raw)


def _text_llm_classify_prompt(ocr_text: str) -> str:
    """Build a constrained local-only prompt for OCR-text doc classification."""
    return (
        "Classify this Indonesian administrative document OCR text. "
        "Answer with EXACTLY ONE token from this list: "
        + ", ".join(DOC_TYPES)
        + ". If uncertain, noisy, or not an administrative document, answer unknown. "
        "Do not infer from names, phone numbers, or dates alone. "
        "One token only -- no punctuation, no explanation.\n\nOCR:\n" + ocr_text[:6000]
    )


async def _ollama_text_classify(model: str, prompt: str) -> tuple[str, str | None]:
    """Single local Ollama text classification call. Returns (response, thinking)."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "keep_alive": ollama_keep_alive(),
        "options": {"temperature": 0.0, "num_predict": 24},
    }
    client = _get_client()
    async with ollama_inference_slot(operation="text_classify", model=model):
        r = await asyncio.wait_for(
            client.post(f"{OLLAMA_URL}/api/generate", json=payload),
            timeout=TEXT_LLM_CLASSIFY_TIMEOUT_SECONDS,
        )
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip(), (data.get("thinking") or "").strip()


async def _text_llm_classify(ocr_text: str | None) -> str | None:
    """Local text-LLM doc-type fallback for OCR-ready unknowns.

    It is opt-in, exact-token only, and never raises. Raw OCR text is only sent to
    local Ollama; logs carry model/type/status counts, not document content.
    """
    if not _text_llm_classify_enabled():
        return None
    text = (ocr_text or "").strip()
    if len(text) < TEXT_LLM_CLASSIFY_MIN_CHARS:
        return None
    model = _resolve_text_llm_model()
    try:
        response, thinking = await _ollama_text_classify(
            model,
            _text_llm_classify_prompt(text),
        )
    except Exception as exc:
        logger.warning("text LLM classify fallback failed model=%s error=%r", model, exc)
        return None
    answer = _parse_doc_type_answer(response) or _parse_doc_type_answer(thinking)
    if answer and answer != "unknown":
        logger.info("text LLM classify fallback answered type=%s model=%s", answer, model)
        return answer
    return None


async def _vision_classify_page(png_bytes: bytes) -> str | None:
    """ONE local vision call to type a document page the keywords could not.

    Returns a DOC_TYPES member or None. NEVER raises: any error/timeout/
    non-conforming answer degrades to None (caller keeps "unknown").
    """
    try:
        b64 = base64.b64encode(_ensure_min_size(png_bytes)).decode("ascii")
        resp, thinking = await _ollama_vision(
            _VISION_CLASSIFY_MODEL,
            b64,
            prompt=_VISION_CLASSIFY_PROMPT,
            num_predict=_VISION_CLASSIFY_NUM_PREDICT,
        )
    except Exception as exc:
        logger.warning("vision classify fallback failed: %s", exc)
        return None
    # Prefer the clean response; tolerate a thinking-only model defensively.
    answer = _parse_vision_answer(resp) or _parse_vision_answer(thinking)
    if answer:
        logger.info("vision classify fallback answered type=%s", answer)
    return answer


async def _vision_classify_pages(pages: list[bytes]) -> tuple[str | None, int | None]:
    """Try up to VISION_CLASSIFY_MAX_PAGES pages, returning (type, page_offset).

    The fallback is intentionally sequential and capped: it runs only after the
    keyword floor fails, and every vision-only type remains review-band. Page 1
    is often a cover/blank scan in WhatsApp uploads; letting page 2/3 answer
    rescues those without guessing from text.
    """
    for offset, png in enumerate(pages[:VISION_CLASSIFY_MAX_PAGES]):
        if not png:
            continue
        answer = await _vision_classify_page(png)
        if answer and answer != "unknown":
            return answer, offset
    return None, None


async def classify_document(
    ocr_text: str | None,
    pages: list[dict[str, Any]] | None = None,
    *,
    first_page_png: bytes | None = None,
    vision_page_pngs: list[bytes] | None = None,
) -> dict[str, Any]:
    """Classify a document from OCR text. Local-only, anti-hallucination.

    Args:
        ocr_text: concatenated OCR text (all pages). If None, derived from pages.
        pages: per-page OCR dicts from ``ocr_pages`` (used to attribute the
               winning evidence to a specific source page).
        first_page_png: backward-compatible shortcut for a single first-page
               fallback image.
        vision_page_pngs: optional raw PNG bytes for the first candidate pages.
               When the keyword score lands below the unknown floor, capped
               local vision calls (:func:`_vision_classify_pages`) get a
               chance to type the document -- confidence capped at
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

    # Stay-permit OVERRIDE (deterministic, runs BEFORE the score winner is
    # honoured). An izin-tinggal card prints a "Passport Number" field, so the
    # scorer wrongly ranks passport (0.8) above kitas (0.75). If the OCR carries
    # a stay-permit marker the document is NOT a passport -- emit the specific
    # itk/itas/itap subtype. Real passports lack these markers (innocence test).
    if ocr_text and ocr_text.strip():
        stay_subtype = _stay_permit_subtype(ocr_text)
        if stay_subtype is not None:
            return {
                # Confidence: keyword score for kitas if present, else the
                # marker-detection floor (still review-band, > unknown floor).
                "type": stay_subtype,
                "confidence": max(scores.get("kitas", 0.0), 0.55),
                "source_page": _attribute_source_page("kitas", pages),
                "scores": scores,
                "via": "stay_permit_override",
            }

    # Anti-hallucination floor: weak keyword evidence -> NOT a guess. One local
    # text LLM pass and then one local vision pass may still type it -- both capped
    # in the review band.
    if best_type is None or best_score < 0.30:
        text_llm_type = await _text_llm_classify(ocr_text)
        if text_llm_type:
            return {
                "type": text_llm_type,
                "confidence": TEXT_LLM_CLASSIFY_CONF,
                "source_page": _attribute_source_page(text_llm_type, pages),
                "scores": scores,
                "via": "local_text_llm_fallback",
                "llm_model": _resolve_text_llm_model(),
            }

        candidate_pngs = vision_page_pngs or (
            [first_page_png] if first_page_png is not None else []
        )
        if candidate_pngs:
            vtype, page_offset = await _vision_classify_pages(candidate_pngs)
            if vtype and vtype != "unknown":
                source_page = None
                if page_offset is not None:
                    source_page = (
                        pages[page_offset].get("page") if page_offset < len(pages) else page_offset
                    )
                return {
                    "type": vtype,
                    "confidence": VISION_CLASSIFY_CONF,
                    "source_page": source_page,
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


def _attribute_source_page(dtype: str, pages: list[dict[str, Any]]) -> int | None:
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


async def _fetch_blob_meta(pool: asyncpg.Pool, queue_id: int) -> tuple[str | None, str | None]:
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
    vision_pngs = [
        getattr(page, "png_bytes", b"")
        for page in pre.pages[:VISION_CLASSIFY_MAX_PAGES]
        if getattr(page, "png_bytes", b"")
    ]
    cls = await classify_document(
        full_text,
        ocr,
        first_page_png=first_png,
        vision_page_pngs=vision_pngs,
    )

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
        "classify_llm_model": cls.get("llm_model"),
    }
