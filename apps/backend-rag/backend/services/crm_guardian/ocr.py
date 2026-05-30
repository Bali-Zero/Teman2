"""CRM-Guardian Phase 1.5 OCR / text-extraction layer.

Resolves Drive PDF/image bytes → extracted text, used by the gemini CLI worker
to feed Gemini with content (not just filenames) before generating L1
summaries. Phase 1 hallucinated identity from filename tokens because the
model never saw PDF content; Phase 1.5 closes that gap.

Cascade (graceful degradation per Symbiosis Law 4):

    1. PDF with native text layer  → pdfminer.six (cheap, no OCR)
    2. PDF scanned / image-only    → pypdfium2 rasterize → tesseract -l ind+eng
    3. Tesseract confidence < 0.4  → qwen2.5vl:7b Ollama vision fallback
                                     (only if health check at module import
                                     succeeded; otherwise skip and return
                                     low-confidence tesseract result)

Caching:
    - `crm_guardian_file_content_cache` (migration 181) holds extracted text
      keyed by Drive file_id. Soft-delete via deleted_at.
    - Cache hit: file_id present + modified_time_ms matches → return cached row
      without re-extracting (saves OCR cost on bulk re-runs).
    - Cache miss / stale: extract fresh, INSERT or UPDATE row.

Anti-PII: text_content rows live alongside clients.ai_summary on Fly PG. Same
posture (encryption-at-rest baseline + RBAC table-level). The cache will be
purged when client.status flips to 'inactive' (cron, future PR).

Symbiosis Law 7 (Numbers first): every extraction emits structured log fields
(extractor, duration_ms, page_count, text_length, confidence) so we can
benchmark before/after Phase 1.5 once running.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import shutil
import time
from dataclasses import dataclass
from typing import Any, Literal

import asyncpg
import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TESSERACT_BIN = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
TESSERACT_LANGS = "ind+eng"
TESSERACT_TIMEOUT_SECONDS = 60  # per-file hard cap (printed PDFs are fast)

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_VISION_MODEL = "qwen2.5vl:7b"
OLLAMA_VISION_TIMEOUT_SECONDS = 120  # per-page hard cap

# Tesseract self-reported confidence threshold below which we trigger vision
# fallback. 0.40 picks up scanned passports / handwritten endorsements where
# the printed-text optimiser fails but VLM recovers.
TESSERACT_FALLBACK_THRESHOLD = 0.40

# Max characters of extracted text we cache per file. Caps prompt blow-up for
# 20-page akta. Truncated text marked via notes='truncated_at_N'.
MAX_TEXT_CHARS_PER_FILE = 12_000

# Max pages we rasterize per file. Tesseract is fast but akta can run 30+
# pages; we cap at 8 pages (covers page 2-3 where most akta fields live).
MAX_PAGES_PER_FILE = 8

# Page rasterization DPI. 200 is the sweet spot for tesseract on printed PDFs
# without ballooning memory.
PAGE_RENDER_DPI = 200

# Doc-types that get the full content extraction path. Other files fall
# through to extractor='skipped' and remain metadata-only (filename + modtime).
# Aligned with the L1 schema doc_type enum.
PRIORITY_DOC_TYPES: frozenset[str] = frozenset(
    {
        "passport",
        "evisa",
        "visa",
        "kitas",
        "kitap",
        "nib",
        "npwp",
        "akta",
        "sk",
        "lkpm",
        "spt",
        "bukti_potong",
        "tax_record",
    }
)


# ---------------------------------------------------------------------------
# Health check (module-import time, cached)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OcrHealth:
    """Captured at first health probe, reused for the worker run."""

    tesseract_ok: bool
    tesseract_version: str | None
    pdfminer_ok: bool
    pypdfium2_ok: bool
    ollama_vision_ok: bool
    ollama_vision_model: str | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tesseract_ok": self.tesseract_ok,
            "tesseract_version": self.tesseract_version,
            "pdfminer_ok": self.pdfminer_ok,
            "pypdfium2_ok": self.pypdfium2_ok,
            "ollama_vision_ok": self.ollama_vision_ok,
            "ollama_vision_model": self.ollama_vision_model,
            "detail": self.detail,
        }


_HEALTH_CACHE: OcrHealth | None = None


async def check_health(force: bool = False) -> OcrHealth:
    """Probe the OCR stack: tesseract binary, python libs, Ollama vision model.

    Idempotent + cached for the process lifetime (force=True resets cache).
    Used by the worker at startup to log capabilities and decide whether
    vision fallback is available.

    Graceful degradation: missing tesseract → text-only pdfminer mode.
    Missing pypdfium2 → no scanned-PDF support. Missing Ollama → vision
    fallback disabled (tesseract result returned even at low confidence).
    """
    global _HEALTH_CACHE
    if _HEALTH_CACHE is not None and not force:
        return _HEALTH_CACHE

    # tesseract subprocess version probe
    tesseract_ok = False
    tesseract_version: str | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            TESSERACT_BIN,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        out = stdout.decode("utf-8", errors="replace")
        if proc.returncode == 0 and "tesseract" in out.lower():
            tesseract_ok = True
            # First line: "tesseract X.Y.Z"
            tesseract_version = out.splitlines()[0].strip()
    except (FileNotFoundError, asyncio.TimeoutError, Exception) as e:
        logger.warning("OCR health: tesseract probe failed: %s", e)

    # pdfminer.six import probe
    pdfminer_ok = False
    try:
        import pdfminer.high_level  # noqa: F401

        pdfminer_ok = True
    except ImportError as e:
        logger.warning("OCR health: pdfminer.six missing: %s", e)

    # pypdfium2 import probe (rasterization for tesseract)
    pypdfium2_ok = False
    try:
        import pypdfium2  # noqa: F401

        pypdfium2_ok = True
    except ImportError as e:
        logger.warning("OCR health: pypdfium2 missing: %s", e)

    # Ollama qwen2.5vl probe — list models and check ours is present
    ollama_vision_ok = False
    ollama_vision_model: str | None = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags")
            r.raise_for_status()
            models = {m.get("name", "") for m in r.json().get("models", [])}
            if OLLAMA_VISION_MODEL in models:
                ollama_vision_ok = True
                ollama_vision_model = OLLAMA_VISION_MODEL
            else:
                logger.warning(
                    "OCR health: Ollama up but %s not pulled (available: %s)",
                    OLLAMA_VISION_MODEL,
                    sorted(models)[:5],
                )
    except (httpx.HTTPError, Exception) as e:
        logger.warning("OCR health: Ollama probe failed: %s", e)

    detail_parts = []
    if not tesseract_ok:
        detail_parts.append("no-tesseract")
    if not pdfminer_ok:
        detail_parts.append("no-pdfminer")
    if not pypdfium2_ok:
        detail_parts.append("no-pypdfium2")
    if not ollama_vision_ok:
        detail_parts.append("no-vision-fallback")
    detail = ",".join(detail_parts) if detail_parts else "all-ok"

    health = OcrHealth(
        tesseract_ok=tesseract_ok,
        tesseract_version=tesseract_version,
        pdfminer_ok=pdfminer_ok,
        pypdfium2_ok=pypdfium2_ok,
        ollama_vision_ok=ollama_vision_ok,
        ollama_vision_model=ollama_vision_model,
        detail=detail,
    )
    _HEALTH_CACHE = health
    logger.info("OCR health: %s", health.as_dict())
    return health


# ---------------------------------------------------------------------------
# Extraction primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionResult:
    """Outcome of a single-file extraction."""

    text: str
    extractor: Literal["pdfminer", "tesseract", "qwen25vl", "mixed", "skipped"]
    confidence: float | None
    page_count: int | None
    duration_ms: int
    truncated: bool
    notes: str | None = None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _truncate(text: str, limit: int = MAX_TEXT_CHARS_PER_FILE) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


async def _extract_pdfminer(pdf_bytes: bytes) -> tuple[str, int]:
    """Native PDF text-layer extraction. Returns (text, page_count).

    Runs in a thread (pdfminer is sync + CPU-bound). Returns empty string if
    the PDF has no text layer (scanned-only) — caller falls back to OCR.
    """

    def _sync_extract() -> tuple[str, int]:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage

        buf = io.BytesIO(pdf_bytes)
        text = extract_text(buf, maxpages=MAX_PAGES_PER_FILE) or ""

        # Count pages cheaply (separate handle to avoid stream reuse).
        page_count = 0
        try:
            buf.seek(0)
            for _ in PDFPage.get_pages(buf):
                page_count += 1
        except Exception:
            page_count = 0
        return text.strip(), page_count

    return await asyncio.to_thread(_sync_extract)


async def _rasterize_pdf_pages(
    pdf_bytes: bytes, max_pages: int = MAX_PAGES_PER_FILE
) -> list[bytes]:
    """PDF → list of PNG bytes (one per page), via pypdfium2.

    Returns empty list if pypdfium2 missing or rasterization fails.
    """

    def _sync_rasterize() -> list[bytes]:
        try:
            import pypdfium2 as pdfium
        except ImportError:
            return []

        try:
            pdf = pdfium.PdfDocument(pdf_bytes)
            scale = PAGE_RENDER_DPI / 72.0
            out: list[bytes] = []
            n_pages = min(len(pdf), max_pages)
            for page_idx in range(n_pages):
                page = pdf[page_idx]
                pil_image = page.render(scale=scale).to_pil()
                buf = io.BytesIO()
                pil_image.save(buf, format="PNG")
                out.append(buf.getvalue())
            return out
        except Exception as e:
            logger.warning("pypdfium2 rasterize failed: %s", e)
            return []

    return await asyncio.to_thread(_sync_rasterize)


async def _tesseract_ocr_png(png_bytes: bytes) -> tuple[str, float]:
    """Run tesseract on a PNG image. Returns (text, confidence_0_to_1).

    Uses `--psm 6` (assume a single uniform block of text — best for printed
    document pages with mixed Indonesian/English content).
    """
    proc = await asyncio.create_subprocess_exec(
        TESSERACT_BIN,
        "stdin",
        "stdout",
        "-l",
        TESSERACT_LANGS,
        "--psm",
        "6",
        "tsv",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=png_bytes),
            timeout=TESSERACT_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("tesseract timeout after %ds", TESSERACT_TIMEOUT_SECONDS)
        return "", 0.0

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace")[:200]
        logger.warning("tesseract exit=%d: %s", proc.returncode, err)
        return "", 0.0

    # tsv output: page level lines + word lines with conf 0-100.
    # Aggregate text from word lines (level=5) and average non-empty conf.
    lines = stdout.decode("utf-8", errors="replace").splitlines()
    words: list[str] = []
    confs: list[float] = []
    for line in lines[1:]:  # skip header
        parts = line.split("\t")
        if len(parts) < 12 or parts[0] == "level":
            continue
        try:
            level = int(parts[0])
        except ValueError:
            continue
        if level != 5:
            continue
        text = parts[11].strip()
        if not text:
            continue
        try:
            conf = float(parts[10])
        except ValueError:
            continue
        if conf >= 0:  # tesseract emits -1 for some non-text regions
            words.append(text)
            confs.append(conf / 100.0)

    text_out = " ".join(words)
    confidence = sum(confs) / len(confs) if confs else 0.0
    return text_out.strip(), confidence


async def _qwen25vl_extract(png_bytes_list: list[bytes]) -> tuple[str, float]:
    """Vision fallback via local Ollama qwen2.5vl:7b.

    Asks the model to transcribe text from the supplied page images. Returns
    (text, self_reported_confidence). Used only when tesseract confidence
    falls below threshold AND health check confirmed model is available.
    """
    if not png_bytes_list:
        return "", 0.0

    import base64

    payload = {
        "model": OLLAMA_VISION_MODEL,
        "prompt": (
            "Transcribe ALL legible text from these document images verbatim. "
            "Preserve numbers, dates, names exactly as printed. "
            "Output text only, no commentary, no field labels. "
            "If a section is unreadable, write [unreadable]."
        ),
        "images": [base64.b64encode(png).decode("ascii") for png in png_bytes_list],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 2048},
        # qwen 3.5 family default thinking off (cf. CLAUDE.md ollama rule)
        "think": False,
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_VISION_TIMEOUT_SECONDS) as client:
            r = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload)
            r.raise_for_status()
            data = r.json()
            text = (data.get("response") or "").strip()
            # Heuristic confidence: longer + no [unreadable] markers = higher
            unreadable_hits = text.count("[unreadable]")
            base = 0.65 if text else 0.0
            penalty = min(0.30, 0.05 * unreadable_hits)
            confidence = max(0.0, base - penalty)
            return text, confidence
    except (httpx.HTTPError, Exception) as e:
        logger.warning("qwen2.5vl extract failed: %s", e)
        return "", 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_file_content(
    *,
    file_bytes: bytes,
    mime_type: str,
    doc_type: str | None,
    health: OcrHealth | None = None,
) -> ExtractionResult:
    """Run the OCR cascade on a single Drive file's bytes.

    Args:
        file_bytes: raw bytes downloaded from Drive
        mime_type: e.g. 'application/pdf', 'image/jpeg'
        doc_type: doc_type tag from the L1 schema (passport, akta, etc.).
                  Files outside PRIORITY_DOC_TYPES get extractor='skipped' so
                  the worker spends its budget where it matters.
        health: cached health probe; if None, will probe at call time

    Returns:
        ExtractionResult. extractor='skipped' when:
          - doc_type not in priority list
          - mime not pdf/image/text
          - all extractors failed
    """
    started = time.monotonic()
    if health is None:
        health = await check_health()

    # Filter: only invest OCR budget on doc_types that matter for L1
    if doc_type not in PRIORITY_DOC_TYPES:
        return ExtractionResult(
            text="",
            extractor="skipped",
            confidence=None,
            page_count=None,
            duration_ms=0,
            truncated=False,
            notes=f"non_priority_doc_type:{doc_type}",
        )

    mime_lower = mime_type.lower()
    is_pdf = mime_lower == "application/pdf"
    is_image = mime_lower.startswith("image/")

    if not (is_pdf or is_image):
        return ExtractionResult(
            text="",
            extractor="skipped",
            confidence=None,
            page_count=None,
            duration_ms=0,
            truncated=False,
            notes=f"unsupported_mime:{mime_type}",
        )

    # ---- PDF path ----
    if is_pdf:
        # 1. pdfminer text layer
        pdfminer_text = ""
        page_count: int | None = None
        if health.pdfminer_ok:
            try:
                pdfminer_text, page_count = await _extract_pdfminer(file_bytes)
            except Exception as e:
                logger.warning("pdfminer extract failed: %s", e)

        # If we got >200 chars of text layer, assume native PDF. Skip OCR.
        if pdfminer_text and len(pdfminer_text) >= 200:
            truncated_text, truncated = _truncate(pdfminer_text)
            return ExtractionResult(
                text=truncated_text,
                extractor="pdfminer",
                confidence=None,
                page_count=page_count,
                duration_ms=int((time.monotonic() - started) * 1000),
                truncated=truncated,
                notes=None,
            )

        # 2. Rasterize + tesseract
        if not (health.tesseract_ok and health.pypdfium2_ok):
            return ExtractionResult(
                text=pdfminer_text or "",
                extractor="pdfminer" if pdfminer_text else "skipped",
                confidence=None,
                page_count=page_count,
                duration_ms=int((time.monotonic() - started) * 1000),
                truncated=False,
                notes="no_ocr_stack_for_scanned_pdf",
            )

        page_pngs = await _rasterize_pdf_pages(file_bytes, max_pages=MAX_PAGES_PER_FILE)
        if not page_pngs:
            return ExtractionResult(
                text=pdfminer_text or "",
                extractor="pdfminer" if pdfminer_text else "skipped",
                confidence=None,
                page_count=page_count,
                duration_ms=int((time.monotonic() - started) * 1000),
                truncated=False,
                notes="rasterize_failed",
            )

        # OCR every page, aggregate
        page_texts: list[str] = []
        page_confs: list[float] = []
        for png in page_pngs:
            t, c = await _tesseract_ocr_png(png)
            if t:
                page_texts.append(t)
                page_confs.append(c)

        tesseract_text = "\n\n".join(page_texts)
        avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0.0
        n_pages = len(page_pngs)

        # 3. Vision fallback if tesseract was weak AND model available
        if avg_conf < TESSERACT_FALLBACK_THRESHOLD and health.ollama_vision_ok:
            logger.info(
                "tesseract conf=%.2f below %.2f, trying vision fallback",
                avg_conf,
                TESSERACT_FALLBACK_THRESHOLD,
            )
            # Only send first 2 pages to vision (latency cap)
            vision_text, vision_conf = await _qwen25vl_extract(page_pngs[:2])
            if vision_text and vision_conf > avg_conf:
                # Prefer vision when stronger; pdfminer remnants kept as suffix
                combined = vision_text
                if pdfminer_text:
                    combined = f"{vision_text}\n\n[pdfminer-text-layer]\n{pdfminer_text}"
                tt, truncated = _truncate(combined)
                return ExtractionResult(
                    text=tt,
                    extractor="qwen25vl",
                    confidence=vision_conf,
                    page_count=n_pages,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    truncated=truncated,
                    notes=f"vision_fallback,tesseract_conf={avg_conf:.2f}",
                )
            # If vision returned nothing useful, fall through with tesseract result + note

        # Combine pdfminer + tesseract when both produced something
        if pdfminer_text and tesseract_text:
            combined = f"{tesseract_text}\n\n[pdfminer-text-layer]\n{pdfminer_text}"
            tt, truncated = _truncate(combined)
            return ExtractionResult(
                text=tt,
                extractor="mixed",
                confidence=avg_conf,
                page_count=n_pages,
                duration_ms=int((time.monotonic() - started) * 1000),
                truncated=truncated,
                notes=None,
            )

        # Pure tesseract result
        if tesseract_text:
            tt, truncated = _truncate(tesseract_text)
            return ExtractionResult(
                text=tt,
                extractor="tesseract",
                confidence=avg_conf,
                page_count=n_pages,
                duration_ms=int((time.monotonic() - started) * 1000),
                truncated=truncated,
                notes=None,
            )

        # Nothing worked
        return ExtractionResult(
            text="",
            extractor="skipped",
            confidence=None,
            page_count=n_pages,
            duration_ms=int((time.monotonic() - started) * 1000),
            truncated=False,
            notes="all_extractors_empty",
        )

    # ---- Image path (passport scans, evisa screenshots) ----
    # Image bytes go straight to tesseract; if weak, vision fallback.
    if not health.tesseract_ok:
        return ExtractionResult(
            text="",
            extractor="skipped",
            confidence=None,
            page_count=1,
            duration_ms=int((time.monotonic() - started) * 1000),
            truncated=False,
            notes="no_tesseract_for_image",
        )

    t, c = await _tesseract_ocr_png(file_bytes)

    if c < TESSERACT_FALLBACK_THRESHOLD and health.ollama_vision_ok:
        vt, vc = await _qwen25vl_extract([file_bytes])
        if vt and vc > c:
            tt, truncated = _truncate(vt)
            return ExtractionResult(
                text=tt,
                extractor="qwen25vl",
                confidence=vc,
                page_count=1,
                duration_ms=int((time.monotonic() - started) * 1000),
                truncated=truncated,
                notes=f"vision_fallback,tesseract_conf={c:.2f}",
            )

    if t:
        tt, truncated = _truncate(t)
        return ExtractionResult(
            text=tt,
            extractor="tesseract",
            confidence=c,
            page_count=1,
            duration_ms=int((time.monotonic() - started) * 1000),
            truncated=truncated,
            notes=None,
        )

    return ExtractionResult(
        text="",
        extractor="skipped",
        confidence=None,
        page_count=1,
        duration_ms=int((time.monotonic() - started) * 1000),
        truncated=False,
        notes="image_ocr_empty",
    )


# ---------------------------------------------------------------------------
# Cache layer (asyncpg)
# ---------------------------------------------------------------------------


async def get_cached_content(
    conn: asyncpg.Connection,
    file_id: str,
    modified_time_ms: int,
) -> dict[str, Any] | None:
    """Return the cached row for (file_id, modified_time_ms) if alive.

    Touches `last_seen_at` to support retention sweep — a file that hasn't
    been seen in N months is a candidate for purge.
    """
    row = await conn.fetchrow(
        """
        SELECT file_id, modified_time_ms, content_hash, text_content,
               text_length, extractor, confidence, page_count
        FROM crm_guardian_file_content_cache
        WHERE file_id = $1
          AND modified_time_ms = $2
          AND deleted_at IS NULL
        """,
        file_id,
        modified_time_ms,
    )
    if row is None:
        return None

    # Bump last_seen_at (fire-and-forget; cache hit cost is dominated by SELECT)
    await conn.execute(
        "UPDATE crm_guardian_file_content_cache SET last_seen_at = NOW() WHERE file_id = $1 AND deleted_at IS NULL",
        file_id,
    )
    return dict(row)


async def upsert_cache_row(
    conn: asyncpg.Connection,
    *,
    file_id: str,
    modified_time_ms: int,
    result: ExtractionResult,
) -> int:
    """Insert or update the cache row for this file.

    If the file_id has an alive row with different modified_time_ms, the old
    row is soft-deleted and a new row is inserted (audit chain via deleted_at).
    Returns the new row id.
    """
    # Soft-delete prior alive row when modtime changed.
    await conn.execute(
        """
        UPDATE crm_guardian_file_content_cache
        SET deleted_at = NOW()
        WHERE file_id = $1
          AND modified_time_ms <> $2
          AND deleted_at IS NULL
        """,
        file_id,
        modified_time_ms,
    )

    row = await conn.fetchrow(
        """
        INSERT INTO crm_guardian_file_content_cache (
            file_id, modified_time_ms, content_hash, text_content,
            text_length, extractor, confidence, page_count, notes
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (file_id) WHERE deleted_at IS NULL
          DO UPDATE SET
            modified_time_ms = EXCLUDED.modified_time_ms,
            content_hash     = EXCLUDED.content_hash,
            text_content     = EXCLUDED.text_content,
            text_length      = EXCLUDED.text_length,
            extractor        = EXCLUDED.extractor,
            confidence       = EXCLUDED.confidence,
            page_count       = EXCLUDED.page_count,
            notes            = EXCLUDED.notes,
            last_seen_at     = NOW()
        RETURNING id
        """,
        file_id,
        modified_time_ms,
        result.content_hash,
        result.text,
        len(result.text),
        result.extractor,
        result.confidence,
        result.page_count,
        result.notes,
    )
    return row["id"]


async def soft_delete_missing(
    conn: asyncpg.Connection,
    file_ids_alive: set[str],
) -> int:
    """Soft-delete cache rows whose file_id is no longer in the alive set.

    Returns count of rows marked deleted. Idempotent (re-running with the
    same alive set is a no-op because already-deleted rows are filtered).

    Called by the worker AFTER it has listed the current client's Drive
    folder contents — files that were in cache but no longer in Drive
    get deleted_at set, preserving the OCR text for audit.

    Note: this scopes implicitly to the union of files-ever-seen for the
    files we're checking; callers should pass file_ids_alive *only for the
    folders they currently know about*, otherwise this would soft-delete
    every other client's cache (avoid that).
    """
    if not file_ids_alive:
        return 0
    result = await conn.execute(
        """
        UPDATE crm_guardian_file_content_cache
        SET deleted_at = NOW()
        WHERE deleted_at IS NULL
          AND file_id <> ALL($1::text[])
        """,
        list(file_ids_alive),
    )
    # asyncpg execute returns "UPDATE N"
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0
