"""
PDF Vision Service
Analisi multimodale di PDF — OCR, tabelle, passaporti, documenti CRM.
Integrato con Google Drive per scaricare i file on-demand.

Primary: Local Ollama qwen2.5vl:7b (free, ~30s per page, confirmed working)
Fallback: Google Gemini 2.0 Flash Vision (API)

NOTE: qwen3.5:27b/9b Q4_K_M quantization does NOT work for vision despite
      reporting "vision" capability. Use qwen2.5vl:7b instead.
UPDATED 2026-03-09:
- Switched from qwen3.5:27b to qwen2.5vl:7b (confirmed passport OCR working)
"""

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


class PDFVisionService:
    """
    Servizio per analisi multimodale di PDF.
    Ollama-first (qwen3.5:27b vision) con Gemini Flash fallback.
    Supporta download da Google Drive.
    """

    def __init__(self, api_key: str = None, ai_client=None):
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
                logger.warning(f"Failed to initialize PDFVisionService GenAI client: {e}")
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
                    f"👁️ Vision analysis complete via Ollama for {local_path} p.{page_number}"
                )
                if is_drive_file and os.path.exists(local_path):
                    os.remove(local_path)
                return result

            # 5. Fallback to Gemini Vision
            result = await self._analyze_via_gemini(prompt, image_base64)
            if result:
                logger.info(
                    f"👁️ Vision analysis complete via Gemini for {local_path} p.{page_number}"
                )
                if is_drive_file and os.path.exists(local_path):
                    os.remove(local_path)
                return result

            return "Vision service not available (both Ollama and Gemini failed)."

        except Exception as e:
            logger.error(f"❌ Vision analysis failed: {e}")
            return f"Error analyzing page: {str(e)}"

    async def _analyze_via_ollama(self, prompt: str, image_base64: str) -> str | None:
        """Analyze image using local Ollama qwen3.5:27b vision."""
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
                    }
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
            logger.warning(f"Ollama vision error: {e}")
            return None

    async def _analyze_via_gemini(self, prompt: str, image_base64: str) -> str | None:
        """Fallback: Analyze image using Gemini Vision API."""
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
            logger.warning(f"Gemini vision error: {e}")
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
        self, pdf_identifier: str, page_range: tuple[int, int], is_drive_file: bool = True
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
            logger.error(f"PDF extraction failed: {e}")
            return f"Error extracting PDF: {str(e)}"

    async def analyze_vision(self, pdf_data: bytes) -> dict[str, Any]:
        """Analyze PDF using vision model (for test compatibility)."""
        if self.ai_client and hasattr(self.ai_client, "analyze_pdf_vision"):
            return await self.ai_client.analyze_pdf_vision(pdf_data)

        text = await self.extract_text(pdf_data)
        return {
            "text": text,
            "structure": {"pages": 1, "sections": 0},
        }
