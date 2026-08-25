"""
PDF Vision Service
Analisi multimodale di PDF — OCR, tabelle, passaporti, documenti CRM.
Integrato con Google Drive per scaricare i file on-demand.

Primary: Local Ollama qwen2.5vl:7b (free, ~30s per page, confirmed working)
Fallback: Google Gemini 2.0 Flash Vision (API)

NOTE: qwen3.5 Q4_K_M quantization does NOT work for vision despite
      reporting "vision" capability. Use qwen2.5vl:7b instead.
UPDATED 2026-03-09: Switched to qwen2.5vl:7b (confirmed passport OCR working)
UPDATED 2026-04-06: Local fleet now gemma4:26b + qwen3.5:9b + deepseek-r1:32b + qwen2.5vl:7b
"""

import asyncio
import base64
import io
import logging
import os
from typing import Any

import fitz  # PyMuPDF
import httpx
from PIL import Image

from backend.app.core.config import settings
from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient
from backend.llm.ollama_client import is_ollama_available
from backend.services.oracle.smart_oracle import download_pdf_from_drive

logger = logging.getLogger(__name__)

# Gemini free tier allows 15 requests/minute. This paces the CLOUD path only:
# the local Ollama path has no such limit and sleeping on it turned a 100-page
# scan into 400 seconds of doing nothing.
GEMINI_VISION_PAGE_DELAY_SECONDS = 4.0

# A page whose rendered image carries essentially no ink is legitimately blank
# -- the empty verso of a two-sided scan -- and its silence is not a failure to
# transcribe. Anything above this ratio that came back empty IS a failure.
#
# The threshold is measured, not guessed (2026-08-25, this renderer at 2x zoom,
# luminance < 200 counted as ink):
#
#   real scanned decree pages ....... 4.7% - 8.4%
#   ONE short line on A4 ............ 0.049%   <- must NOT be called blank
#   a page bearing only its number .. 0.003%
#   a truly empty page .............. 0.000%
#
# 0.01% sits ~5x below the shortest line that carries law and ~3x above a bare
# page number. The bias is deliberate: misjudging a written page as blank hides
# a hole in a law, while misjudging a blank page as missing merely refuses the
# document out loud, which is recoverable.
BLANK_PAGE_INK_RATIO = 0.0001
BLANK_PAGE_LUMINANCE_THRESHOLD = 200


class IncompleteTranscriptionError(Exception):
    """Raised when only SOME pages of a scanned PDF could be transcribed.

    Deliberately NOT a ``RuntimeError``: `backend.core.parsers` uses
    ``except RuntimeError`` to mean "there is no running event loop", and a
    partially transcribed decree caught by that handler would be silently
    mistaken for an asyncio condition.

    Measured 2026-08-25: a three-page ministerial decree returned 1,204 of its
    6,109 characters because pages 2 and 3 timed out against a cold vision
    model, and the only trace was a warning in a log nobody reads. The document
    was stored looking whole. For a legal corpus that is the worst of the three
    outcomes -- worse than an error, and worse than nothing -- because every
    downstream reader, human or machine, treats an amputated decree as the
    decree. A partial transcription must therefore be a refusal, not a value.
    """

    def __init__(
        self,
        pdf_path: str,
        missing_pages: list[int],
        page_count: int,
        transcribed_chars: int,
    ) -> None:
        self.pdf_path = pdf_path
        self.missing_pages = list(missing_pages)
        self.page_count = page_count
        self.transcribed_chars = transcribed_chars
        super().__init__(
            f"Incomplete vision transcription of {pdf_path}: "
            f"{len(self.missing_pages)} of {page_count} pages produced no text "
            f"(pages {self.missing_pages}). "
            f"{transcribed_chars} characters were discarded rather than stored "
            "as if they were the whole document.",
        )


class PDFVisionService:
    """
    Servizio per analisi multimodale di PDF.
    Ollama-first (qwen2.5vl:7b vision) con Gemini Flash fallback.
    Supporta download da Google Drive.
    """

    def __init__(self, api_key: str = None, ai_client=None) -> None:
        self.ai_client = ai_client
        self.api_key = api_key or settings.google_api_key
        self._genai_client: GenAIClient | None = None
        self.model_name = "gemini-2.0-flash-lite"
        self.ollama_model = "qwen2.5vl:7b"  # confirmed working for vision OCR
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client for Ollama."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("PDFVisionService HTTP client closed.")

    def _get_genai_client(self) -> GenAIClient | None:
        """Lazy load GenAI client."""
        if self._genai_client is None and self.api_key and GENAI_AVAILABLE:
            try:
                self._genai_client = GenAIClient(api_key=self.api_key)
                if self._genai_client.is_available:
                    logger.debug("✅ PDFVisionService GenAI client loaded")
            except Exception as e:
                logger.warning("Failed to initialize PDFVisionService GenAI client: %s", e)
        return self._genai_client

    @property
    def _available(self) -> bool:
        """Check availability dynamically."""
        client = self._get_genai_client()
        return client.is_available if client else False

    async def analyze_page(
        self,
        pdf_path: str,
        page_number: int,
        prompt: str = "Extract the table data from this page.",
        is_drive_file: bool = False,
    ) -> str:
        """
        Analizza una specifica pagina PDF con vision.
        Tries Ollama first (local, free), falls back to Gemini Vision.
        """
        local_path = pdf_path

        try:
            # 1. Download da Drive se necessario
            if is_drive_file:
                downloaded_path = download_pdf_from_drive(pdf_path)
                if not downloaded_path:
                    return f"Error: Could not download file '{pdf_path}' from Drive."
                local_path = downloaded_path

            # 2. Renderizza pagina PDF come immagine
            image = self._render_page_to_image(local_path, page_number)

            # 3. Convert image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode()

            # 4. Try Ollama first (local, free)
            result = await self._analyze_via_ollama(prompt, image_base64)
            if result:
                logger.info(
                    "👁️ Vision analysis complete via Ollama for %s p.%s",
                    local_path,
                    page_number,
                )
                if is_drive_file and os.path.exists(local_path):
                    os.remove(local_path)
                return result

            # 5. Fallback to Gemini Vision
            # ⚠️ UU PDP COMPLIANCE: This sends document images to Google servers (cross-border transfer)
            # Art. 56 requires safeguards for cross-border data transfer
            logger.warning(
                "⚠️ [CROSS-BORDER] Ollama local OCR failed, falling back to Gemini API for %s p.%s. Document image will be sent to Google servers.",
                local_path,
                page_number,
            )
            result = await self._analyze_via_gemini(prompt, image_base64)
            if result:
                logger.info(
                    "👁️ Vision analysis complete via Gemini (CROSS-BORDER) for %s p.%s",
                    local_path,
                    page_number,
                )
                if is_drive_file and os.path.exists(local_path):
                    os.remove(local_path)
                return result

            return "Vision service not available (both Ollama and Gemini failed)."

        except Exception as e:
            logger.error("❌ Vision analysis failed: %s", e)
            return f"Error analyzing page: {e!s}"

    # Deliberately literal. A vision model asked to "extract" or "describe" a
    # page will paraphrase it, and a paraphrase entering the corpus AS the
    # document's text is worse than no text: unattributable, and authoritative
    # in tone.
    TRANSCRIPTION_PROMPT = (
        "Transcribe ALL visible text from this scanned document page. "
        "Output the text verbatim, preserving line breaks, ordering and table "
        "structure. Do not summarise, translate, explain or add anything. "
        "If the page contains no text, output nothing."
    )

    async def transcribe_scanned_pdf(
        self,
        pdf_path: str,
        max_pages: int | None = None,
        *,
        page_attempts: int = 2,
        allow_partial: bool = False,
    ) -> str | None:
        """Transcribe a PDF that carries no text layer, page by page.

        This is the ONE implementation of scanned-PDF reading. Until 2026-08-25
        there were two callers in `backend.core.parsers` and NEITHER could ever
        succeed:

        * the synchronous last resort in ``extract_text_from_pdf`` called
          ``extract_text()`` -- a method whose own docstring reads "(for test
          compatibility)" and which, absent an AI client, re-reads the PDF with
          PyMuPDF: precisely the step that had just returned nothing. It never
          rendered a page and never reached a vision model, so it could only
          ever return "". The failure then surfaced as "No text extracted from
          PDF (even with OCR/Vision)", which reads as "everything was tried";
        * ``extract_text_from_pdf_ocr_async`` gated itself on ``_available``,
          which consults the GEMINI client ONLY. With cloud vision unconfigured
          -- the default, since cross-border vision is gated under UU PDP
          Art. 56 -- it returned "" without ever asking the local Ollama engine,
          which was armed and working the whole time.

        Measured 2026-08-25 on a 3-page scanned ministerial decree: the two
        callers yielded 0 characters; this path yields 6,109.

        The completeness contract, added the same day after this method's OWN
        first live run returned 1,204 of those 6,109 characters with nothing
        but a warning to say so:

        * every page gets ``page_attempts`` tries -- the first attempt against a
          cold vision model is the one that pays to load it, which is exactly
          how pages 2 and 3 were lost while page 1 warmed ``qwen2.5vl:7b`` up;
        * a page that stays silent is measured, not assumed: a page with no ink
          on it is legitimately blank, any other silent page is MISSING;
        * a document with missing pages RAISES ``IncompleteTranscriptionError``
          instead of returning what survived. Callers that genuinely want a
          best-effort excerpt must say so with ``allow_partial=True``, and then
          the partiality is theirs to carry.

        Returns None when NO page could be transcribed, so callers raise rather
        than store an empty document.
        """
        try:
            document = fitz.open(pdf_path)
            page_count = document.page_count
            document.close()
        except Exception as exc:
            logger.error("Could not open PDF for transcription: %s", exc)
            return None

        if max_pages is not None:
            page_count = min(page_count, max_pages)

        transcribed: list[str] = []
        missing: list[int] = []
        for page_number in range(1, page_count + 1):
            page_text = await self._transcribe_page(pdf_path, page_number, page_attempts)
            if page_text:
                transcribed.append(page_text)
            elif self._page_is_blank(pdf_path, page_number):
                logger.info(
                    "Page %s of %s carries no ink and is treated as blank",
                    page_number,
                    pdf_path,
                )
            else:
                missing.append(page_number)

        if not transcribed:
            logger.warning(
                "Vision transcription produced nothing for %s (%s pages attempted)",
                pdf_path,
                page_count,
            )
            return None

        text = "\n\n".join(transcribed)

        if missing:
            if not allow_partial:
                raise IncompleteTranscriptionError(
                    pdf_path,
                    missing,
                    page_count,
                    len(text),
                )
            logger.warning(
                "PARTIAL vision transcription of %s: pages %s are missing and the "
                "caller asked for best-effort; %s characters returned",
                pdf_path,
                missing,
                len(text),
            )

        logger.info(
            "Vision transcription: %s/%s pages from %s",
            len(transcribed),
            page_count,
            pdf_path,
        )
        return text

    async def _transcribe_page(
        self,
        pdf_path: str,
        page_number: int,
        attempts: int,
    ) -> str | None:
        """Transcribe ONE page, retrying an attempt that failed or said nothing.

        The retry is not defensive decoration: on 2026-08-25 pages 2 and 3 of a
        three-page decree both hit the 120s client timeout while page 1 was
        still loading ``qwen2.5vl:7b`` into memory, and re-running the very same
        call by hand -- against the now-warm model -- returned both pages in
        full. That manual gesture is what this loop performs.
        """
        for attempt in range(1, max(1, attempts) + 1):
            page_text: str | None = None
            try:
                image = self._render_page_to_image(pdf_path, page_number)
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                image_base64 = base64.b64encode(buffered.getvalue()).decode()

                page_text = await self._analyze_via_ollama(
                    self.TRANSCRIPTION_PROMPT,
                    image_base64,
                )
                if not page_text:
                    # Cross-border fallback. Returns None when the sovereignty
                    # gate is shut, which is a degradation to report, not an
                    # error to raise.
                    page_text = await self._analyze_via_gemini(
                        self.TRANSCRIPTION_PROMPT,
                        image_base64,
                    )
                    if page_text:
                        await asyncio.sleep(GEMINI_VISION_PAGE_DELAY_SECONDS)
            except Exception as exc:
                logger.warning(
                    "Page %s of %s could not be transcribed (attempt %s/%s): %s",
                    page_number,
                    pdf_path,
                    attempt,
                    attempts,
                    exc,
                )
                continue

            if page_text and page_text.strip():
                return page_text.strip()

            logger.warning(
                "Page %s of %s produced no text (attempt %s/%s)",
                page_number,
                pdf_path,
                attempt,
                attempts,
            )
        return None

    def _page_is_blank(self, pdf_path: str, page_number: int) -> bool:
        """Is this page silent because it is EMPTY, or because we failed it?

        A page we cannot even render is not declared blank: an unmeasurable
        page counts as missing, so the doubt costs a loud failure rather than a
        quiet hole in a law.
        """
        try:
            image = self._render_page_to_image(pdf_path, page_number)
        except Exception as exc:
            logger.warning(
                "Could not render page %s of %s to judge whether it is blank: %s",
                page_number,
                pdf_path,
                exc,
            )
            return False

        ink_ratio = self._page_ink_ratio(image)
        logger.debug(
            "Page %s of %s ink ratio %.5f",
            page_number,
            pdf_path,
            ink_ratio,
        )
        return ink_ratio < BLANK_PAGE_INK_RATIO

    @staticmethod
    def _page_ink_ratio(image: Image.Image) -> float:
        """Fraction of pixels dark enough to be ink rather than paper."""
        histogram = image.convert("L").histogram()
        total = sum(histogram)
        if not total:
            return 0.0
        dark = sum(histogram[:BLANK_PAGE_LUMINANCE_THRESHOLD])
        return dark / total

    async def _analyze_via_ollama(self, prompt: str, image_base64: str) -> str | None:
        """Analyze image using local Ollama qwen2.5vl:7b vision."""
        try:
            if not await is_ollama_available(self.ollama_model):
                return None

            payload = {
                "model": self.ollama_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_base64],
                    },
                ],
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 8192,
                },
            }

            client = self._get_client()
            response = await client.post(
                f"{settings.ollama_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "").strip()
            if content:
                logger.info(f"👁️ Ollama vision ({self.ollama_model}) responded")
                return content
            return None

        except httpx.ConnectError:
            logger.debug("Ollama not available for vision")
            return None
        except httpx.TimeoutException:
            logger.warning("Ollama vision timeout (120s)")
            return None
        except Exception as e:
            logger.warning("Ollama vision error: %s", e)
            return None

    async def _analyze_via_gemini(self, prompt: str, image_base64: str) -> str | None:
        """Fallback: Analyze image using Gemini Vision API.

        PII-sovereignty gated: this sends the document image to Google (cross-border,
        UU PDP Art. 56 / SYMBIOSIS Law 2). Blocked unless OCR_ALLOW_CLOUD_VISION=true
        (default false). When blocked, returns None so the caller degrades locally.
        """
        from backend.services.multimodal.cloud_vision_gate import (
            cloud_vision_allowed,
            note_cloud_ocr_blocked,
        )

        if not cloud_vision_allowed():
            note_cloud_ocr_blocked("pdf_vision_service._analyze_via_gemini")
            return None
        try:
            client = self._get_genai_client()
            if not client or not client.is_available:
                return None

            contents = [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_base64}},
            ]

            result = await client.generate_content(
                contents=contents,
                model=self.model_name,
                max_output_tokens=8192,
            )

            return result.get("text") if result else None

        except Exception as e:
            logger.warning("Gemini vision error: %s", e)
            return None

    def _render_page_to_image(self, pdf_path: str, page_number: int) -> Image.Image:
        """Converte pagina PDF in PIL Image"""
        doc = fitz.open(pdf_path)
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"Invalid page number {page_number}")

        page = doc.load_page(page_number - 1)  # 0-indexed
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for clarity

        img_data = pix.tobytes("png")
        return Image.open(io.BytesIO(img_data))

    async def extract_kbli_table(
        self,
        pdf_identifier: str,
        page_range: tuple[int, int],
        is_drive_file: bool = True,
    ) -> str:
        """
        Estrae dati KBLI da un range di pagine.
        Default is_drive_file=True perché le leggi sono su Drive.
        """
        full_extraction = []
        prompt = """
        Analyze this image of a KBLI table.
        Extract the KBLI Code (Kode), Title (Judul), and Description (Uraian).
        Format as JSON list: [{"code": "...", "title": "...", "description": "..."}]
        If no table is visible, return empty list [].
        """

        local_path = pdf_identifier
        if is_drive_file:
            local_path = download_pdf_from_drive(pdf_identifier)
            if not local_path:
                return "Error: Could not download KBLI file from Drive."

        try:
            for page_num in range(page_range[0], page_range[1] + 1):
                result = await self.analyze_page(local_path, page_num, prompt, is_drive_file=False)
                full_extraction.append(f"--- Page {page_num} ---\n{result}")
        finally:
            if is_drive_file and local_path and os.path.exists(local_path):
                os.remove(local_path)

        return "\n".join(full_extraction)

    async def extract_text(self, pdf_data: bytes) -> str:
        """Extract text from PDF data (for test compatibility)."""
        if self.ai_client and hasattr(self.ai_client, "extract_pdf_text"):
            return await self.ai_client.extract_pdf_text(pdf_data)

        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
            doc.close()
            return text
        except Exception as e:
            logger.error("PDF extraction failed: %s", e)
            return f"Error extracting PDF: {e!s}"

    async def analyze_vision(self, pdf_data: bytes) -> dict[str, Any]:
        """Analyze PDF using vision model (for test compatibility)."""
        if self.ai_client and hasattr(self.ai_client, "analyze_pdf_vision"):
            return await self.ai_client.analyze_pdf_vision(pdf_data)

        text = await self.extract_text(pdf_data)
        return {
            "text": text,
            "structure": {"pages": 1, "sections": 0},
        }
