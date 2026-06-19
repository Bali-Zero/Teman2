"""Document-intake preprocessing (FASE 3a).

Turns a blob (PDF / image) on local disk into a list of OCR-ready PNG pages
plus metadata, so the downstream classify/OCR stage (``classify.py``) can feed
clean images to the local vision model.

PII / Symbiosis Law 2: this module touches raw document bytes (passports, akta,
KTP). It reads ONLY from local disk, writes NOTHING to disk, and makes ZERO
network calls. No cloud, no external LLM, no external API. Bytes stay in-process
on the Pro.

Reuse-first lineage:
  * Multi-page PDF rasterization forked from
    ``backend.services.crm_guardian.ocr._rasterize_pdf_pages`` (pypdfium2 path,
    same DPI sweet spot). CLAUDE.md OCR rule: ALWAYS render every page -- akta
    directors live on page 2-3 -- so we lift the per-page cap well above the
    crm_guardian 8-page budget (intake must be exhaustive, not cost-bounded).
  * Image enhancement uses opencv (``opencv-python-headless`` already in the
    venv) -- deskew + grayscale + adaptive-threshold + denoise -- applied only
    when it demonstrably helps a low-contrast scan. If enhancement raises, we
    fall back to the raw page (graceful degradation, never block OCR).

Output contract (consumed by classify.ocr_pages):

    PreprocessResult(
        pages: list[PageImage]   # 1+ PNG-encoded, OCR-ready pages, in order
        n_pages: int
        mime: str                # detected/declared mime of the source blob
        notes: str | None        # e.g. "enhanced", "raw_fallback", "rasterize_failed"
    )

Graceful contract: if preprocessing fails entirely (corrupt PDF, unknown
format), we return a single-page result wrapping the RAW blob bytes so the OCR
stage can still try the vision model directly. We never raise to the caller for
a recoverable input problem -- only programmer errors propagate.
"""

from __future__ import annotations

import asyncio
import io
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("zantara.intake.preprocess")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Page rasterization DPI. 200 is crm_guardian's printed-PDF sweet spot; intake
# scans (phone photos of passports) tolerate the same.
PAGE_RENDER_DPI = 200

# Hard cap on pages we rasterize. Intake must read EVERY page (akta directors on
# page 2-3, multi-page contracts), so the cap is generous -- only there to stop a
# pathological 500-page PDF from exhausting memory. crm_guardian caps at 8 for
# cost; intake is correctness-first, so 30.
MAX_PAGES = 30

# Below this mean pixel std-dev a page is "low contrast" and benefits from the
# opencv enhancement pass. Above it the raw render is already crisp; enhancement
# would only add artifacts, so we skip it.
LOW_CONTRAST_STD_THRESHOLD = 55.0

# qwen2.5vl's ImageProcessor.SmartResize panics (kills the whole Ollama vision
# runner, taking down every queued OCR request — TAC 2026-06-19, finding #16)
# when an image side is smaller than its resize factor of 28px. Any image with
# a side below this is upscaled before it ever reaches the model. Upscale, not
# drop: a tiny thumbnail still gets a chance at OCR instead of silently 0-char.
MIN_OCR_DIMENSION = 28

# Text-layer fast-path. Born-digital PDFs (NIB/OSS/NPWP printouts, e-akta, bank
# letters) carry a selectable text layer -- extracting it is ~instant and
# lossless, vs ~120s/page on the local vision model rasterizing an image of the
# same text. When a page's embedded text clears TEXTLAYER_MIN_CHARS of
# non-whitespace we attach it to the PageImage; the OCR stage then uses it
# verbatim and skips the vision call for that page. Scanned/photographed pages
# (no text layer) fall through to vision unchanged. Toggle off via
# INTAKE_TEXTLAYER_FASTPATH=false. Still 100% local (pypdfium2 in-process) --
# Symbiosis Law 2 preserved (0 bytes to cloud).
TEXTLAYER_FASTPATH = os.getenv(
    "INTAKE_TEXTLAYER_FASTPATH", "true"
).strip().lower() not in ("0", "false", "no", "off")
TEXTLAYER_MIN_CHARS = int(os.getenv("INTAKE_TEXTLAYER_MIN_CHARS", "100"))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageImage:
    """A single OCR-ready page."""

    index: int  # 0-based page number within the source document
    png_bytes: bytes  # PNG-encoded image bytes
    enhanced: bool  # True if opencv enhancement was applied
    # Born-digital text layer extracted from the source PDF page when present
    # and above TEXTLAYER_MIN_CHARS. When set, the OCR stage uses this verbatim
    # and skips the vision model (fast-path); None => OCR via vision as usual.
    # Optional with a default so existing call-sites (and tests) that build a
    # PageImage with three positional args keep working unchanged.
    text: str | None = None


@dataclass
class PreprocessResult:
    """Outcome of preprocessing one blob."""

    pages: list[PageImage] = field(default_factory=list)
    n_pages: int = 0
    mime: str = "application/octet-stream"
    notes: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.pages)


# ---------------------------------------------------------------------------
# MIME detection
# ---------------------------------------------------------------------------


def _detect_mime(blob_path: str, declared_mime: str | None) -> str:
    """Resolve a mime type: declared wins, else sniff magic bytes, else guess."""
    if declared_mime:
        return declared_mime.lower()

    # Magic-byte sniff (cheap, local, no python-magic dependency).
    try:
        with open(blob_path, "rb") as fh:
            head = fh.read(16)
        if head.startswith(b"%PDF-"):
            return "application/pdf"
        if head.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return "image/webp"
        if head[:2] in (b"II", b"MM"):
            return "image/tiff"
    except OSError as exc:
        logger.warning("mime sniff failed for %s: %s", blob_path, exc)

    guessed, _ = mimetypes.guess_type(blob_path)
    return (guessed or "application/octet-stream").lower()


# ---------------------------------------------------------------------------
# opencv enhancement (sync, CPU-bound -- run in a thread)
# ---------------------------------------------------------------------------


def _enhance_png_sync(png_bytes: bytes) -> tuple[bytes, bool]:
    """Deskew + grayscale + adaptive threshold + denoise a page, if it helps.

    Returns (png_bytes, enhanced_flag). On any failure returns the input
    unchanged with enhanced=False (never raises). Only applies the pass when the
    page is low-contrast; crisp pages are returned untouched.
    """
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return png_bytes, False

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Decide if enhancement is worth it: low std-dev == washed-out / low
        # contrast scan. Crisp text pages have high std-dev -- leave them alone.
        if float(gray.std()) >= LOW_CONTRAST_STD_THRESHOLD:
            return png_bytes, False

        # Deskew: estimate dominant text angle from foreground pixels.
        deskewed = _deskew(gray, cv2)

        # Denoise (non-local means) then adaptive threshold to a clean B/W image
        # that vision OCR reads more reliably on low-contrast input.
        denoised = cv2.fastNlMeansDenoising(
            deskewed, None, h=10, templateWindowSize=7, searchWindowSize=21
        )
        binarized = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        )

        ok, buf = cv2.imencode(".png", binarized)
        if not ok:
            return png_bytes, False
        return buf.tobytes(), True
    except Exception as exc:  # broad except: enhancement is best-effort.
        logger.warning("opencv enhancement failed, using raw page: %s", exc)
        return png_bytes, False


def _deskew(gray, cv2):
    """Rotate a grayscale image so its dominant text baseline is horizontal."""
    try:
        inverted = cv2.bitwise_not(gray)
        _, thresh = cv2.threshold(
            inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        # minAreaRect angle is in [-90, 0); normalize to a small correction.
        if angle < -45:
            angle = 90 + angle
        if abs(angle) < 0.5:  # already straight enough -- skip rotation cost
            return gray
        (h, w) = gray.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(
            gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
    except Exception:
        return gray


# ---------------------------------------------------------------------------
# Rasterization (sync helpers run via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _rasterize_pdf_sync(pdf_bytes: bytes, max_pages: int) -> list[bytes]:
    """PDF bytes -> list of per-page PNG bytes via pypdfium2. [] on failure.

    Forked from crm_guardian.ocr._rasterize_pdf_pages but exhaustive (every
    page up to max_pages) per the intake CLAUDE.md OCR rule.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        logger.warning("pypdfium2 missing, cannot rasterize PDF: %s", exc)
        return []
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        scale = PAGE_RENDER_DPI / 72.0
        out: list[bytes] = []
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_image = pdf[i].render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            out.append(buf.getvalue())
        return out
    except Exception as exc:
        logger.warning("pypdfium2 rasterize failed: %s", exc)
        return []


def _extract_pdf_textlayer_sync(pdf_bytes: bytes, max_pages: int) -> list[str | None]:
    """Per-page embedded text layer from a PDF via pypdfium2. [] on failure.

    Returns a list aligned to the rasterized pages: each entry is the page's
    selectable text when it clears ``TEXTLAYER_MIN_CHARS`` of non-whitespace
    (born-digital page), else ``None`` (scan/photo -> needs vision OCR). On any
    error returns ``[]`` so the caller degrades to full vision rasterization
    (never raises, never blocks OCR).
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        logger.warning("pypdfium2 missing, cannot extract text layer: %s", exc)
        return []
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        out: list[str | None] = []
        n = min(len(pdf), max_pages)
        for i in range(n):
            try:
                textpage = pdf[i].get_textpage()
                txt = textpage.get_text_range() or ""
            except Exception as exc:
                logger.debug("text-layer extract failed on page %d: %r", i, exc)
                txt = ""
            dense = len("".join(txt.split()))
            out.append(txt if dense >= TEXTLAYER_MIN_CHARS else None)
        return out
    except Exception as exc:
        logger.warning("pypdfium2 text-layer extract failed: %s", exc)
        return []


def _upscale_if_below_min(im: object, Image: object) -> object:
    """Upscale an image so its smallest side is >= MIN_OCR_DIMENSION.

    Guards qwen2.5vl's SmartResize panic on sub-28px images (kills the Ollama
    vision runner). Preserves aspect ratio; no-op when already large enough.
    """
    w, h = im.size
    smallest = min(w, h)
    if smallest >= MIN_OCR_DIMENSION:
        return im
    if smallest <= 0:
        return im  # degenerate; let the caller's try/except handle it
    scale = MIN_OCR_DIMENSION / smallest
    new_size = (max(MIN_OCR_DIMENSION, round(w * scale)),
                max(MIN_OCR_DIMENSION, round(h * scale)))
    logger.warning(
        "OCR image %dx%d below %dpx floor — upscaling to %dx%d (qwen2.5vl SmartResize guard)",
        w, h, MIN_OCR_DIMENSION, new_size[0], new_size[1],
    )
    return im.resize(new_size, Image.LANCZOS)


def _normalize_image_sync(image_bytes: bytes) -> bytes | None:
    """Re-encode an arbitrary image (jpeg/webp/tiff) to PNG. None on failure."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as im:
            im = im.convert("RGB")
            im = _upscale_if_below_min(im, Image)
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            return buf.getvalue()
    except Exception as exc:
        logger.warning("image normalize failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def preprocess_blob(
    blob_path: str,
    *,
    declared_mime: str | None = None,
    enhance: bool = True,
    max_pages: int = MAX_PAGES,
) -> PreprocessResult:
    """Prepare a local blob for OCR: rasterize all pages + optional enhancement.

    Args:
        blob_path: absolute path to the blob on local disk (PII stays local).
        declared_mime: mime from the intake row if known; else sniffed.
        enhance: run the opencv low-contrast enhancement pass (best-effort).
        max_pages: hard cap on pages rendered (memory guard).

    Returns:
        PreprocessResult with one PageImage per source page. On unrecoverable
        input we still return a single raw page so the OCR stage can try the
        vision model directly (graceful, never raises for bad input).
    """
    path = Path(blob_path)
    mime = _detect_mime(blob_path, declared_mime)

    try:
        raw = await asyncio.to_thread(path.read_bytes)
    except OSError as exc:
        logger.error("preprocess: cannot read blob %s: %s", blob_path, exc)
        return PreprocessResult(
            pages=[], n_pages=0, mime=mime, notes=f"read_failed:{exc}"
        )

    # --- Build the list of raw PNG pages ---
    page_pngs: list[bytes]
    notes_parts: list[str] = []
    # Per-page born-digital text layer (PDF only); aligned to page_pngs, may be
    # empty/shorter -- the enhancement loop guards the index. A None entry means
    # that page has no usable text layer and must go through vision OCR.
    page_texts: list[str | None] = []

    if mime == "application/pdf":
        page_pngs = await asyncio.to_thread(_rasterize_pdf_sync, raw, max_pages)
        if not page_pngs:
            # Rasterization failed -- hand the raw PDF bytes to OCR as a last
            # resort (some vision endpoints accept PDF directly).
            notes_parts.append("rasterize_failed")
            return PreprocessResult(
                pages=[PageImage(index=0, png_bytes=raw, enhanced=False)],
                n_pages=1,
                mime=mime,
                notes=",".join(notes_parts) + ",raw_pdf_fallback",
            )
        if TEXTLAYER_FASTPATH:
            page_texts = await asyncio.to_thread(
                _extract_pdf_textlayer_sync, raw, max_pages
            )
    elif mime.startswith("image/"):
        normalized = await asyncio.to_thread(_normalize_image_sync, raw)
        if normalized is None:
            notes_parts.append("normalize_failed")
            page_pngs = [raw]  # let OCR try the raw bytes
        else:
            page_pngs = [normalized]
    else:
        # Unknown/unsupported format -- pass raw bytes through; OCR may cope.
        logger.warning("preprocess: unsupported mime %s for %s", mime, blob_path)
        return PreprocessResult(
            pages=[PageImage(index=0, png_bytes=raw, enhanced=False)],
            n_pages=1,
            mime=mime,
            notes=f"unsupported_mime:{mime}",
        )

    # --- Optional enhancement pass (per page, in threads) ---
    pages: list[PageImage] = []
    enhanced_any = False
    textlayer_pages = 0
    for i, png in enumerate(page_pngs):
        page_text = page_texts[i] if i < len(page_texts) else None
        if page_text is not None:
            # Born-digital page: text layer already extracted. Skip the opencv
            # enhancement AND (downstream) the vision OCR. We keep the rendered
            # png for provenance and for the classify vision-fallback path.
            textlayer_pages += 1
            pages.append(
                PageImage(index=i, png_bytes=png, enhanced=False, text=page_text)
            )
            continue
        if enhance:
            out_png, was_enhanced = await asyncio.to_thread(_enhance_png_sync, png)
        else:
            out_png, was_enhanced = png, False
        enhanced_any = enhanced_any or was_enhanced
        pages.append(PageImage(index=i, png_bytes=out_png, enhanced=was_enhanced))

    if enhanced_any:
        notes_parts.append("enhanced")
    if textlayer_pages:
        notes_parts.append(f"textlayer:{textlayer_pages}/{len(page_pngs)}")

    return PreprocessResult(
        pages=pages,
        n_pages=len(pages),
        mime=mime,
        notes=",".join(notes_parts) if notes_parts else None,
    )
